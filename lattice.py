"""Crystal structures with their real lattice parameters.

The lattice scene took its basis and its lattice constant from the model. Ask
for rock salt and you get a plausible arrangement of spheres with a plausible
spacing, and a student cannot check either — the same fault the molecule scene
had before its coordinates came from PubChem.

Crystallography is not a matter of opinion. Rock salt is face-centred cubic
with a = 5.640 Å and each ion six-coordinate; caesium chloride is simple cubic
with a = 4.123 Å and each ion eight-coordinate, and the difference between
those two is most of what an introductory lesson on ionic solids is about. So
the structures are held here, measured, with their coordination numbers and
their lattice constants.

Not a database. This is the set that gets taught: the ones in every
introductory solid-state chapter, plus the semiconductors and the common
metals. A structure not on the list gets whatever the model described, marked
as schematic like every other drawn scene — which is honest, and better than
refusing to show anything.

Positions are fractional coordinates of the conventional unit cell, which is
how every reference prints them.
"""

# Face-centred cubic: corner plus three face centres.
_FCC = [(0.0, 0.0, 0.0), (0.5, 0.5, 0.0), (0.5, 0.0, 0.5), (0.0, 0.5, 0.5)]
# Body-centred cubic: corner plus the middle.
_BCC = [(0.0, 0.0, 0.0), (0.5, 0.5, 0.5)]
# The four extra sites that make diamond out of FCC.
_DIA = [(0.25, 0.25, 0.25), (0.75, 0.75, 0.25),
        (0.75, 0.25, 0.75), (0.25, 0.75, 0.75)]


def _sites(positions, element):
    return [{"el": element, "x": p[0], "y": p[1], "z": p[2]}
            for p in positions]


def _rocksalt(a_el, b_el):
    """Two interpenetrating FCC lattices, offset by half a cell edge."""
    return (_sites(_FCC, a_el)
            + _sites([(x + 0.5, y, z) for x, y, z in _FCC], b_el))


def _zincblende(a_el, b_el):
    return _sites(_FCC, a_el) + _sites(_DIA, b_el)


# name -> (lattice constant in angstrom, basis, structure type, coordination)
STRUCTURES = {
    "sodium chloride": (5.640, _rocksalt("Na", "Cl"), "rock salt (FCC)", 6),
    "rock salt": (5.640, _rocksalt("Na", "Cl"), "rock salt (FCC)", 6),
    "nacl": (5.640, _rocksalt("Na", "Cl"), "rock salt (FCC)", 6),
    "table salt": (5.640, _rocksalt("Na", "Cl"), "rock salt (FCC)", 6),
    "halite": (5.640, _rocksalt("Na", "Cl"), "rock salt (FCC)", 6),

    "caesium chloride": (4.123, _sites([(0, 0, 0)], "Cs")
                         + _sites([(0.5, 0.5, 0.5)], "Cl"),
                         "caesium chloride (simple cubic)", 8),
    "cesium chloride": (4.123, _sites([(0, 0, 0)], "Cs")
                        + _sites([(0.5, 0.5, 0.5)], "Cl"),
                        "caesium chloride (simple cubic)", 8),
    "cscl": (4.123, _sites([(0, 0, 0)], "Cs")
             + _sites([(0.5, 0.5, 0.5)], "Cl"),
             "caesium chloride (simple cubic)", 8),

    "diamond": (3.567, _sites(_FCC, "C") + _sites(_DIA, "C"), "diamond", 4),
    "silicon": (5.431, _sites(_FCC, "Si") + _sites(_DIA, "Si"), "diamond", 4),
    "germanium": (5.658, _sites(_FCC, "Ge") + _sites(_DIA, "Ge"),
                  "diamond", 4),

    "zinc blende": (5.406, _zincblende("Zn", "S"), "zinc blende", 4),
    "sphalerite": (5.406, _zincblende("Zn", "S"), "zinc blende", 4),
    "zinc sulfide": (5.406, _zincblende("Zn", "S"), "zinc blende", 4),
    "gallium arsenide": (5.653, _zincblende("Ga", "As"), "zinc blende", 4),
    "gaas": (5.653, _zincblende("Ga", "As"), "zinc blende", 4),

    "fluorite": (5.463, _sites(_FCC, "Ca") + _sites(
        _DIA + [(0.25, 0.25, 0.75), (0.75, 0.75, 0.75),
                (0.75, 0.25, 0.25), (0.25, 0.75, 0.25)], "F"),
        "fluorite", 8),
    "calcium fluoride": (5.463, _sites(_FCC, "Ca") + _sites(
        _DIA + [(0.25, 0.25, 0.75), (0.75, 0.75, 0.75),
                (0.75, 0.25, 0.25), (0.25, 0.75, 0.25)], "F"),
        "fluorite", 8),

    "copper": (3.615, _sites(_FCC, "Cu"), "face-centred cubic", 12),
    "aluminium": (4.050, _sites(_FCC, "Al"), "face-centred cubic", 12),
    "aluminum": (4.050, _sites(_FCC, "Al"), "face-centred cubic", 12),
    "gold": (4.078, _sites(_FCC, "Au"), "face-centred cubic", 12),
    "silver": (4.086, _sites(_FCC, "Ag"), "face-centred cubic", 12),
    "nickel": (3.524, _sites(_FCC, "Ni"), "face-centred cubic", 12),
    "lead": (4.950, _sites(_FCC, "Pb"), "face-centred cubic", 12),

    "iron": (2.866, _sites(_BCC, "Fe"), "body-centred cubic", 8),
    "tungsten": (3.165, _sites(_BCC, "W"), "body-centred cubic", 8),
    "chromium": (2.880, _sites(_BCC, "Cr"), "body-centred cubic", 8),
    "sodium": (4.291, _sites(_BCC, "Na"), "body-centred cubic", 8),
    "potassium": (5.328, _sites(_BCC, "K"), "body-centred cubic", 8),

    "polonium": (3.359, _sites([(0, 0, 0)], "Po"), "simple cubic", 6),

    # Graphite, which a chemistry class asks for more often than any of the
    # metals above and which returned nothing at all. Diamond was here and
    # graphene was in layers.py as a wafer stack, so the one structure the
    # syllabus actually pairs with diamond — same element, different
    # arrangement, which is the whole point of the lesson — was the one
    # missing.
    #
    # ABAB stacking, in the hexagonal cell: a = 2.464 Å, c = 6.711 Å, so
    # c/a = 2.724. The sites are given in fractional coordinates of that
    # cell, and the interlayer gap that makes graphite soft and a conductor
    # along the sheets is the real 3.355 Å.
    "graphite": (2.464, [
        {"el": "C", "x": 0.0, "y": 0.0, "z": 0.0},
        {"el": "C", "x": 1 / 3, "y": 2 / 3, "z": 0.0},
        {"el": "C", "x": 0.0, "y": 0.0, "z": 0.5},
        {"el": "C", "x": 2 / 3, "y": 1 / 3, "z": 0.5},
    ], "graphite (ABAB layers)", 3),
}

# Everyday names for things the table lists formally.
#
# A class says "salt", not "sodium chloride"; "rust", not "iron(III) oxide".
# The table is keyed the formal way, so the word a child actually types
# missed — and the board answered as though nothing were known about salt.
_COMMON = {
    "salt": "sodium chloride",
    "table salt": "sodium chloride",
    "rock salt": "sodium chloride",
    "common salt": "sodium chloride",
    "pencil lead": "graphite",
    "black lead": "graphite",
}

# Words a caption wraps a structure in.
_NOISE = ("crystal", "structure", "lattice", "unit", "cell", "the", "a", "an",
          "of", "in", "solid", "3d", "model", "arrangement", "packing",
          "conventional", "diagram", "showing", "shown")


def find(topic):
    """The measured structure for this topic, or nothing.

    Returns (lattice constant, basis, type, coordination). Never raises: a
    structure that is not on the list is not an error, it is a lesson that
    gets the schematic it described.
    """
    t = " ".join(str(topic or "").lower().split())
    if not t:
        return None
    # The word a class uses, before the word a chemist uses.
    t = _COMMON.get(t, t)
    if t in STRUCTURES:
        return STRUCTURES[t]
    words = [w for w in t.replace(",", " ").split() if w not in _NOISE]
    stripped = " ".join(words)
    stripped = _COMMON.get(stripped, stripped)
    if stripped in STRUCTURES:
        return STRUCTURES[stripped]
    # And inside a longer phrase: "the structure of table salt".
    for common, formal in _COMMON.items():
        if common in t:
            return STRUCTURES[formal]
    # "the crystal structure of sodium chloride" -> the longest name it
    # contains, so "sodium chloride" wins over "sodium".
    hits = [k for k in STRUCTURES if k in t]
    if hits:
        return STRUCTURES[max(hits, key=len)]
    return None


def clean(topic):
    """A lattice scene's measured fields, or an empty dict."""
    got = find(topic)
    if not got:
        return {}
    a, basis, kind, coord = got
    return {
        "a": a,
        "basis": [dict(b) for b in basis],
        "structure": kind,
        "coordination": coord,
        "measured": True,
    }
