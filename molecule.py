"""Real molecules in 3D, from their measured coordinates.

The board has eight procedural 3D scenes — a cell, a leaf, a heart and so on —
each one built by hand from ellipsoids and tubes. They are honest about being
diagrams, but there are only eight of them, and a lesson on caffeine or
sulfuric acid gets nothing.

PubChem has three-dimensional coordinates for something over a hundred million
compounds. They are computed conformers, not artist's impressions: every atom
is where the chemistry puts it, and the bonds are the real bonds. So a
molecule is not drawn here at all — it is fetched and plotted.

That distinction is the whole reason this is allowed to exist. Everything
visual in this product is either derived from the lesson's own numbers or
refused, because a picture a student cannot check is worse than no picture. A
downloaded conformer satisfies that: the geometry comes from a chemical
database and nothing in this file invents a position.

The format is MDL SDF, which is fixed-width text: a counts line, then one line
per atom giving x, y, z and an element symbol, then one line per bond giving
two atom numbers and an order. Parsing it is arithmetic, and everything that
does not parse is dropped rather than guessed at.
"""
import re

PUBCHEM_3D = ("https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
              "{}/SDF?record_type=3d")

UA = "Craxle/1.0 (https://craxle.com; learning platform) python-httpx"
TIMEOUT = 8.0

# A molecule big enough to be worth turning is still small enough to send.
# Past this it is a protein, which needs a different renderer and a different
# lesson; hydrogens alone can double the count, so the cap is generous.
MAX_ATOMS = 300
MAX_BONDS = 400

# Elements this can colour and size. Anything outside it still renders, in
# grey, at a default radius — an unknown element is not a reason to refuse a
# molecule, only a reason not to pretend to know its colour.
#
# Colours follow the CPK convention every chemistry textbook uses, so a
# student sees the same oxygen-red and nitrogen-blue they have seen before.
# Radii are covalent radii in ångström, which is what sets the visual scale.
ELEMENTS = {
    "H": (0.31, 0xFFFFFF), "C": (0.76, 0x303030), "N": (0.71, 0x3050F8),
    "O": (0.66, 0xFF0D0D), "F": (0.57, 0x90E050), "P": (1.07, 0xFF8000),
    "S": (1.05, 0xFFFF30), "Cl": (1.02, 0x1FF01F), "Br": (1.20, 0xA62929),
    "I": (1.39, 0x940094), "Na": (1.66, 0xAB5CF2), "K": (2.03, 0x8F40D4),
    "Mg": (1.41, 0x8AFF00), "Ca": (1.76, 0x3DFF00), "Fe": (1.32, 0xE06633),
    "Zn": (1.22, 0x7D80B0), "Cu": (1.32, 0xC88033), "Mn": (1.61, 0x9C7AC7),
    "B": (0.84, 0xFFB5B5), "Si": (1.11, 0xF0C8A0), "Se": (1.20, 0xFFA100),
    "Li": (1.28, 0xCC80FF), "Al": (1.21, 0xBFA6A6), "Ni": (1.24, 0x50D050),
}
DEFAULT = (0.95, 0x909090)

# A compound name PubChem might resolve. Not a formula and not a sentence.
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ,'()\-\[\]]{0,60}$")


def wanted(name: str) -> bool:
    """Is this worth asking PubChem about?"""
    n = " ".join(str(name or "").split())
    return bool(n) and bool(_NAME.match(n)) and len(n.split()) <= 4


def parse_sdf(text: str) -> dict:
    """Atoms and bonds from an MDL SDF record, or an empty dict.

    Fixed-width by specification, but real files vary in their spacing, so
    the atom line is read by splitting on whitespace: the first three fields
    are the coordinates and the fourth is the element. The counts line is
    trusted only as far as it agrees with the number of lines actually
    present — a truncated download must produce nothing, not a molecule with
    invented atoms.
    """
    lines = str(text or "").splitlines()
    if len(lines) < 5:
        return {}
    counts = lines[3]
    try:
        n_atoms = int(counts[0:3])
        n_bonds = int(counts[3:6])
    except (ValueError, IndexError):
        return {}
    if not (0 < n_atoms <= MAX_ATOMS) or not (0 <= n_bonds <= MAX_BONDS):
        return {}
    if len(lines) < 4 + n_atoms + n_bonds:
        return {}

    atoms = []
    for row in lines[4:4 + n_atoms]:
        parts = row.split()
        if len(parts) < 4:
            return {}
        try:
            x, y, z = float(parts[0]), float(parts[1]), float(parts[2])
        except ValueError:
            return {}
        el = parts[3][:2].strip()
        if not el.isalpha():
            return {}
        el = el[0].upper() + el[1:].lower()
        radius, colour = ELEMENTS.get(el, DEFAULT)
        atoms.append({"el": el, "x": round(x, 3), "y": round(y, 3),
                      "z": round(z, 3), "r": radius, "c": colour})

    bonds = []
    for row in lines[4 + n_atoms:4 + n_atoms + n_bonds]:
        # Bond lines are fixed-width three-character fields, and split() is
        # wrong here: two-digit atom numbers run together as "1011".
        try:
            a = int(row[0:3]) - 1
            b = int(row[3:6]) - 1
            order = int(row[6:9]) if row[6:9].strip() else 1
        except (ValueError, IndexError):
            continue
        if not (0 <= a < len(atoms)) or not (0 <= b < len(atoms)) or a == b:
            continue
        bonds.append([a, b, order if order in (1, 2, 3) else 1])

    if not atoms:
        return {}

    # Centre on the molecule's middle so it turns about itself rather than
    # swinging around a corner, and report its size so the camera can frame
    # it without the renderer having to guess.
    cx = sum(a["x"] for a in atoms) / len(atoms)
    cy = sum(a["y"] for a in atoms) / len(atoms)
    cz = sum(a["z"] for a in atoms) / len(atoms)
    span = 0.0
    for a in atoms:
        a["x"] = round(a["x"] - cx, 3)
        a["y"] = round(a["y"] - cy, 3)
        a["z"] = round(a["z"] - cz, 3)
        span = max(span, abs(a["x"]), abs(a["y"]), abs(a["z"]))

    return {"atoms": atoms, "bonds": bonds, "span": round(span or 1.0, 3),
            "formula": formula(atoms)}


def formula(atoms) -> str:
    """The molecular formula, in Hill order: carbon, hydrogen, then the rest
    alphabetically. That is the order every chemistry text prints."""
    counts = {}
    for a in atoms:
        counts[a["el"]] = counts.get(a["el"], 0) + 1
    order = ([e for e in ("C", "H") if e in counts]
             + sorted(e for e in counts if e not in ("C", "H")))
    out = []
    for el in order:
        n = counts[el]
        out.append(el + (str(n) if n > 1 else ""))
    return "".join(out)


async def find(client, name: str) -> dict:
    """A named compound in three dimensions, or nothing.

    Never raises. A missing molecule is a lesson without a molecule, which is
    the lesson it would have been anyway.
    """
    if not wanted(name):
        return {}
    n = " ".join(str(name).split())
    from urllib.parse import quote
    try:
        r = await client.get(PUBCHEM_3D.format(quote(n, safe="")),
                             timeout=TIMEOUT, headers={"User-Agent": UA})
        # PubChem answers 404 for anything it cannot resolve as a compound,
        # which is the filter wanted: no match, no molecule.
        if r.status_code != 200:
            return {}
        # Some compounds have no computed 3D conformer at all. That is a
        # normal answer, not a failure.
        if len(r.text) < 60:
            return {}
    except Exception as e:
        print(f"3D molecule lookup failed for {n!r}: {type(e).__name__}: {e}")
        return {}

    mol = parse_sdf(r.text)
    if mol:
        mol["name"] = n[:60]
    return mol


def clean(raw) -> dict:
    """Rebuild a molecule from an untrusted dict, field by field.

    Cached lessons are re-read from the database and a model could, in
    principle, be persuaded to emit something shaped like this. Coordinates
    are numbers and are treated as numbers; nothing here is passed through.
    """
    if not isinstance(raw, dict):
        return {}
    atoms = []
    for a in (raw.get("atoms") or [])[:MAX_ATOMS]:
        if not isinstance(a, dict):
            continue
        try:
            x, y, z = float(a.get("x")), float(a.get("y")), float(a.get("z"))
        except (TypeError, ValueError):
            continue
        if not all(abs(v) < 1e4 and v == v for v in (x, y, z)):
            continue
        el = str(a.get("el") or "")[:2]
        radius, colour = ELEMENTS.get(el, DEFAULT)
        atoms.append({"el": el, "x": round(x, 3), "y": round(y, 3),
                      "z": round(z, 3), "r": radius, "c": colour})
    if not atoms:
        return {}
    bonds = []
    for b in (raw.get("bonds") or [])[:MAX_BONDS]:
        try:
            i, j, o = int(b[0]), int(b[1]), int(b[2])
        except (TypeError, ValueError, IndexError):
            continue
        if 0 <= i < len(atoms) and 0 <= j < len(atoms) and i != j:
            bonds.append([i, j, o if o in (1, 2, 3) else 1])
    try:
        span = float(raw.get("span") or 1.0)
    except (TypeError, ValueError):
        span = 1.0
    return {"atoms": atoms, "bonds": bonds,
            "span": round(max(0.5, min(span, 1e3)), 3),
            "formula": str(raw.get("formula") or "")[:60],
            "name": str(raw.get("name") or "")[:60]}
