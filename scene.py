"""Validating a 3D scene the model asked for.

The renderer builds geometry from parameters, so what arrives here is numbers
and short labels — never geometry, never a formula, never markup. That is the
whole security design: there is no field in this schema that can carry code,
so there is nothing to sanitise, only a shape to enforce.

Rebuilt rather than filtered, like every other model output on the site. A key
that is not named below does not survive, so a field nobody anticipated cannot
ride along with the rest and reach the renderer.

Sizes are clamped rather than rejected. A model that says a slab is nine
hundred units thick has made a scaling mistake, not an attack, and clamping
gives a slightly wrong picture where rejecting gives none at all — but a
thousand atoms is a hung tab on a phone, so counts are cut hard.
"""

KINDS = ("molecule", "layers", "lattice", "surface", "orbit", "solid")

SHAPES = ("cube", "sphere", "cylinder", "cone", "torus", "tetra", "octa",
          "icosa", "prism")

# Named surfaces only. Accepting a formula to evaluate would mean running
# generated text in somebody's browser, which is not a trade worth making for
# a nicer-looking hill.
FUNCS = ("saddle", "bowl", "dome", "ripple", "well", "plane")

MAX_ATOMS = 120
MAX_BONDS = 160
MAX_LAYERS = 14
MAX_BODIES = 10
MAX_BASIS = 8


def _n(v, lo, hi, default=0.0):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if f != f or f in (float("inf"), float("-inf")):   # NaN and infinities
        return default
    return max(lo, min(hi, f))


def _label(v, n=24):
    s = "".join(c for c in str(v or "") if ord(c) >= 32)
    return s.strip()[:n]


def _colour(v):
    """A colour as an integer, or None to let the renderer choose.

    Accepts 0xRRGGBB or "#rrggbb" because models produce both, and refusing
    one of them would silently drop half the colours a lesson asked for.
    """
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, str):
        s = v.strip().lstrip("#")
        try:
            v = int(s, 16)
        except ValueError:
            return None
    try:
        i = int(v)
    except (TypeError, ValueError):
        return None
    return i if 0 <= i <= 0xFFFFFF else None


def clean(d):
    """Validate one scene, or return None if there is not a usable one."""
    if not isinstance(d, dict):
        return None
    kind = str(d.get("kind") or "").strip().lower()
    if kind not in KINDS:
        return None

    out = {"kind": kind, "caption": _label(d.get("caption"), 120),
           "height": int(_n(d.get("height"), 200, 460, 300))}

    if kind == "molecule":
        atoms = []
        for a in (d.get("atoms") or [])[:MAX_ATOMS]:
            if not isinstance(a, dict):
                continue
            atoms.append({"el": _label(a.get("el"), 2) or "C",
                          "x": _n(a.get("x"), -40, 40),
                          "y": _n(a.get("y"), -40, 40),
                          "z": _n(a.get("z"), -40, 40)})
        if len(atoms) < 2:
            return None
        bonds = []
        for b in (d.get("bonds") or [])[:MAX_BONDS]:
            try:
                i, j = int(b[0]), int(b[1])
                order = int(b[2]) if len(b) > 2 else 1
            except (TypeError, ValueError, IndexError):
                continue
            # An index past the end of the atom list would draw a bond to
            # nowhere, which the renderer skips — but dropping it here keeps
            # the payload honest about what it contains.
            if 0 <= i < len(atoms) and 0 <= j < len(atoms) and i != j:
                bonds.append([i, j, max(1, min(3, order))])
        out["atoms"] = atoms
        out["bonds"] = bonds
        return out

    if kind == "layers":
        layers = []
        for L in (d.get("layers") or [])[:MAX_LAYERS]:
            if not isinstance(L, dict):
                continue
            item = {"name": _label(L.get("name"), 28),
                    "t": _n(L.get("t"), 0.08, 3.0, 0.5),
                    "clear": bool(L.get("clear"))}
            if L.get("w") is not None:
                item["w"] = _n(L.get("w"), 0.5, 6.0, 6.0)
            if L.get("x") is not None:
                item["x"] = _n(L.get("x"), -3.0, 3.0, 0.0)
            c = _colour(L.get("color"))
            if c is not None:
                item["color"] = c
            layers.append(item)
        if len(layers) < 2:
            return None
        out["layers"] = layers
        return out

    if kind == "lattice":
        basis = []
        for b in (d.get("basis") or [])[:MAX_BASIS]:
            if not isinstance(b, dict):
                continue
            basis.append({"el": _label(b.get("el"), 2) or "Si",
                          "x": _n(b.get("x"), 0, 1),
                          "y": _n(b.get("y"), 0, 1),
                          "z": _n(b.get("z"), 0, 1)})
        if not basis:
            return None
        out["basis"] = basis
        out["a"] = _n(d.get("a"), 0.6, 6.0, 2.0)
        # Cubed, so this is the difference between 8 spheres and 500.
        out["repeat"] = int(_n(d.get("repeat"), 1, 4, 2))
        return out

    if kind == "surface":
        fn = str(d.get("fn") or "").strip().lower()
        out["fn"] = fn if fn in FUNCS else "saddle"
        out["span"] = _n(d.get("span"), 2, 8, 4)
        return out

    if kind == "orbit":
        bodies = []
        for b in (d.get("bodies") or [])[:MAX_BODIES]:
            if not isinstance(b, dict):
                continue
            item = {"name": _label(b.get("name"), 24),
                    "r": _n(b.get("r"), 1.2, 22, 3),
                    "size": _n(b.get("size"), 0.1, 1.2, 0.3),
                    "speed": _n(b.get("speed"), 0.02, 2.0, 0.4)}
            c = _colour(b.get("color"))
            if c is not None:
                item["color"] = c
            bodies.append(item)
        if not bodies:
            return None
        out["bodies"] = bodies
        out["centre"] = _label(d.get("centre"), 24)
        out["centre_r"] = _n(d.get("centre_r"), 0.3, 2.5, 0.9)
        c = _colour(d.get("centre_color"))
        if c is not None:
            out["centre_color"] = c
        return out

    if kind == "solid":
        shape = str(d.get("shape") or "").strip().lower()
        out["shape"] = shape if shape in SHAPES else "cube"
        c = _colour(d.get("color"))
        if c is not None:
            out["color"] = c
        return out

    return None


# What the model is told it may ask for. Kept here beside the validator so the
# two cannot drift: a prompt that offers a field the validator drops produces
# lessons that quietly lose their pictures.
PROMPT = """You may add a 3D scene to a lesson, as `scene`. It is built from
numbers, not from a model file, so only these six kinds exist. Use one only
where rotating and zooming the real structure teaches something. Most lessons
should have no scene at all, and a scene that is decoration is worse than
none.

"molecule"  {"kind":"molecule","caption":"...",
             "atoms":[{"el":"O","x":0,"y":0,"z":0}, ...],
             "bonds":[[0,1,1],[0,2,2]]}       bond order 1, 2 or 3
            Chemistry, biochemistry, materials, drug structure.

"lattice"   {"kind":"lattice","caption":"...","a":2.0,"repeat":2,
             "basis":[{"el":"Si","x":0,"y":0,"z":0}, ...]}
            Crystal structure, semiconductors, metals, salts.

"layers"    {"kind":"layers","caption":"...",
             "layers":[{"name":"p substrate","t":1.0},
                       {"name":"n+ source","t":0.4,"w":1.5,"x":-2},
                       {"name":"oxide","t":0.2,"clear":true}, ...]}
            Bottom layer first. Semiconductor and MOSFET cross-sections,
            thin films, PCB stack-ups, geological strata, battery cells,
            skin and tissue layers, anything built up in labelled layers.

"surface"   {"kind":"surface","fn":"saddle|bowl|dome|ripple|well|plane",
             "span":4}
            Optimisation, potentials, wave shapes, stationary points.

"orbit"     {"kind":"orbit","centre":"Sun","bodies":[{"name":"Earth","r":4,
             "size":0.3}]}
            Astronomy, and shell diagrams where the orbit is a convention.

"solid"     {"kind":"solid","shape":"cube|sphere|cylinder|cone|torus|tetra|
             octa|icosa|prism"}
            Geometry, volumes, packing, crystal habit.

Rules:
- Real coordinates and real proportions. An invented geometry taught
  confidently is worse than no picture.
- `caption` says what to look at, in under twelve words.
- If the thing worth showing is an organic shape — an organ, a bone, a whole
  cell — none of these can draw it honestly. Leave `scene` out and describe it
  in words instead."""
