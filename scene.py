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

# The surface grid is computed with the same allowlisted evaluator that
# checks a lesson's arithmetic. Nothing here executes a string.
import maths as _maths
import protein as _protein

KINDS = ("molecule", "protein", "layers", "lattice", "surface", "orbit",
         "solid", "process", "flow", "helix", "cell", "field", "wave")

# The four that were added when it became clear the first nine were a
# chemistry set. Biology got a leaf with arrows around it and physics got
# planets, and the two pictures a physics class most needs — a field, which
# fills a volume, and a wave, which moves — could not be asked for at all.
HELIX_FORMS = ("dna", "a-dna", "z-dna", "rna", "alpha")
WAVE_MODES = ("travelling", "standing", "interference")
# Only what the renderer has a measured size for. An organelle nobody
# measured would be drawn at whatever size looked right, which is exactly
# what a scale drawing must not do.
ORGANELLES = ("nucleus", "nucleolus", "mitochondrion", "chloroplast",
              "vacuole", "ribosome", "lysosome", "golgi",
              "endoplasmic reticulum", "centriole", "chromosome")
MAX_PARTS = 10
MAX_SOURCES = 6

MAX_STAGES = 8
MAX_FLOWS = 4

# Shapes that can be built honestly from curves. A leaf can; a liver cannot,
# and offering "liver" would get one drawn as an ellipsoid, which teaches the
# wrong shape to somebody who will be examined on the right one.
BODIES = ("leaf", "cell", "root", "panel", "vessel", "box")

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


# The nine solids, and what "size" means for each: the defining length a
# school problem gives you.
SOLIDS = {
    "cube": "edge", "sphere": "radius", "cylinder": "radius",
    "cone": "radius", "torus": "outer radius", "tetra": "edge",
    "octa": "edge", "icosa": "edge", "prism": "edge",
}


def _solid_measures(shape, a):
    """Volume and surface area, exactly, from the defining length.

    Height is taken as twice the radius for the cylinder and the cone, which
    is what the renderer draws — a figure whose numbers describe a different
    solid from the one on screen is worse than no numbers.
    """
    import math as _m
    a = float(a)
    if shape == "cube":
        v, s_ = a ** 3, 6 * a * a
    elif shape == "sphere":
        v, s_ = 4 / 3 * _m.pi * a ** 3, 4 * _m.pi * a * a
    elif shape == "cylinder":
        h = 2 * a
        v, s_ = _m.pi * a * a * h, 2 * _m.pi * a * (a + h)
    elif shape == "cone":
        h = 2 * a
        slant = _m.hypot(a, h)
        v, s_ = _m.pi * a * a * h / 3, _m.pi * a * (a + slant)
        v, s_ = v, s_
    elif shape == "torus":
        r = a * 0.35
        v, s_ = 2 * _m.pi ** 2 * a * r * r, 4 * _m.pi ** 2 * a * r
    elif shape == "tetra":
        v, s_ = a ** 3 / (6 * _m.sqrt(2)), _m.sqrt(3) * a * a
    elif shape == "octa":
        v, s_ = _m.sqrt(2) / 3 * a ** 3, 2 * _m.sqrt(3) * a * a
    elif shape == "icosa":
        v = 5 * (3 + _m.sqrt(5)) / 12 * a ** 3
        s_ = 5 * _m.sqrt(3) * a * a
    else:                                   # triangular prism, height 2a
        v, s_ = (_m.sqrt(3) / 4 * a * a) * (2 * a), \
                (_m.sqrt(3) / 2 * a * a) + 3 * a * (2 * a)
    return {"of": SOLIDS.get(shape, "edge"),
            "volume": round(v, 4), "area": round(s_, 4)}


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
        # Filled in from the measured table when the stack is one that
        # gets taught. The drawn thickness is a logarithm of the real
        # one; the figure printed beside it is the fact.
        if d.get("measured"):
            out["measured"] = True
            out["scale_note"] = _label(d.get("scale_note"), 60)
            src = d.get("layers") or []
            for i, lay in enumerate(out["layers"]):
                s_i = src[i] if (i < len(src)
                                 and isinstance(src[i], dict)) else {}
                if s_i.get("real"):
                    lay["real"] = _label(s_i.get("real"), 16)
                    lay["note"] = _label(s_i.get("note"), 40)
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
        # Filled in from the measured table when the structure is one that
        # gets taught. The drawing size and the real cell edge are different
        # numbers: 5.64 angstrom is the fact, 2.0 is what fits on screen.
        if d.get("measured"):
            out["measured"] = True
            out["structure"] = _label(d.get("structure"), 40)
            out["a_angstrom"] = _n(d.get("a_angstrom"), 0.1, 100, 1.0)
            try:
                out["coordination"] = int(d.get("coordination") or 0)
            except (TypeError, ValueError):
                out["coordination"] = 0
        # Cubed, so this is the difference between 8 spheres and 500.
        out["repeat"] = int(_n(d.get("repeat"), 1, 4, 2))
        return out

    if kind == "protein":
        # Backbone traces, filled in from the Protein Data Bank rather than
        # from the model. Everything here is rebuilt by protein.clean, which
        # treats coordinates as numbers and drops anything that is not one.
        out.update(_protein.clean(d))
        return out if out.get("traces") else None

    if kind == "solid":
        # A solid is shown to teach the relationship between its dimensions
        # and its volume and surface area, so those are computed here from
        # the stated size — exactly, by the formula the lesson is teaching.
        # Asking a model to write them risks a number that disagrees with the
        # picture beside it, and nobody would see which was wrong.
        shape = str(d.get("shape") or "cube").strip().lower()
        if shape not in SOLIDS:
            shape = "cube"
        size = _n(d.get("size"), 0.1, 100, 1)
        out["shape"] = shape
        out["size"] = size
        out["unit"] = _label(d.get("unit"), 8) or "unit"
        out["measures"] = _solid_measures(shape, size)
        c = _colour(d.get("color"))
        if c is not None:
            out["color"] = c
        return out

    if kind == "surface":
        fn = str(d.get("fn") or "").strip().lower()
        out["fn"] = fn if fn in FUNCS else "saddle"
        out["span"] = _n(d.get("span"), 2, 8, 4)
        # The function itself, if the lesson stated one.
        #
        # Six canned shapes meant a lesson on any other function got the
        # nearest of them — a picture of a different function, which in
        # mathematics is not a rough edge but the content being wrong. When
        # an expression is given it is evaluated here, on a grid, by the same
        # allowlisted walker used for checking answers: nothing executable
        # reaches the browser, and nothing is executed here either. The page
        # receives a list of numbers.
        expr = str(d.get("expr") or "").strip()[:200]
        if expr:
            grid = _maths.surface(expr, out["span"])
            if grid:
                out["z"] = grid
                out["expr"] = expr
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
            # The measured figures, when the body is one we have. Distance
            # on screen and distance in space are different numbers, and
            # only the second is a fact — so it travels beside the first
            # rather than replacing it.
            if b.get("au"):
                item["au"] = _n(b.get("au"), 0.001, 1e5, 1)
                item["years"] = _n(b.get("years"), 0.0001, 1e6, 1)
            c = _colour(b.get("color"))
            if c is not None:
                item["color"] = c
            bodies.append(item)
        if not bodies:
            return None
        out["bodies"] = bodies
        out["centre"] = _label(d.get("centre"), 24)
        if d.get("measured"):
            out["measured"] = True
            out["scale_note"] = _label(d.get("scale_note"), 60)
        out["centre_r"] = _n(d.get("centre_r"), 0.3, 2.5, 0.9)
        c = _colour(d.get("centre_color"))
        if c is not None:
            out["centre_color"] = c
        return out

    if kind == "flow":
        def side(key):
            got = []
            for x in (d.get(key) or [])[:MAX_FLOWS]:
                if isinstance(x, str):
                    x = {"name": x}
                if not isinstance(x, dict):
                    continue
                nm = _label(x.get("name"), 22)
                if not nm:
                    continue
                item = {"name": nm}
                c = _colour(x.get("color"))
                if c is not None:
                    item["color"] = c
                got.append(item)
            return got

        ins, outs = side("in"), side("out")
        if not ins and not outs:
            return None
        body = str(d.get("body") or "").strip().lower()
        out["body"] = body if body in BODIES else "box"
        out["in"] = ins
        out["out"] = outs
        return out

    if kind == "process":
        stages = []
        for st in (d.get("stages") or [])[:MAX_STAGES]:
            if not isinstance(st, dict):
                continue
            name = _label(st.get("name"), 32)
            if not name:
                continue
            stages.append({"name": name,
                           "in": _label(st.get("in"), 28),
                           "out": _label(st.get("out"), 28)})
        if len(stages) < 2:
            return None
        layout = str(d.get("layout") or "").strip().lower()
        out["layout"] = layout if layout in ("cycle", "chain") else "chain"
        out["stages"] = stages
        return out

    if kind == "solid":
        shape = str(d.get("shape") or "").strip().lower()
        out["shape"] = shape if shape in SHAPES else "cube"
        c = _colour(d.get("color"))
        if c is not None:
            out["color"] = c
        return out

    # ---- biology --------------------------------------------------------
    # The measured numbers are not accepted from the model at all. A helix's
    # rise, its bases per turn and its handedness are crystallography, and a
    # model asked for them writes a plausible helix that is wrong in the one
    # respect a student is examined on — B-DNA turns right, Z-DNA turns left.
    # So the form is named here and the renderer supplies the geometry.
    if kind == "helix":
        form = str(d.get("form") or "").strip().lower().replace(" ", "-")
        out["form"] = form if form in HELIX_FORMS else "dna"
        out["turns"] = _n(d.get("turns"), 1, 6, 2.5)
        seq = "".join(c for c in str(d.get("sequence") or "").upper()
                      if c in "ACGTU")[:60]
        if seq:
            out["sequence"] = seq
        return out

    if kind == "cell":
        parts = []
        for p in (d.get("parts") or [])[:MAX_PARTS]:
            if isinstance(p, str):
                p = {"name": p}
            if not isinstance(p, dict):
                continue
            name = _label(p.get("name"), 28).lower()
            # Only what can be placed at a real size. An organelle nobody
            # measured would be drawn at whatever size looked right, which
            # is the whole thing this is trying not to do.
            if name not in ORGANELLES:
                continue
            parts.append({"name": name,
                          "n": int(_n(p.get("n"), 1, 12, 1))})
        if not parts:
            return None
        out["cell"] = ("plant" if str(d.get("cell") or "").strip().lower()
                       == "plant" else "animal")
        out["parts"] = parts
        return out

    # ---- physics --------------------------------------------------------
    if kind == "field":
        charges = []
        for c_ in (d.get("charges") or [])[:MAX_SOURCES]:
            if not isinstance(c_, dict):
                continue
            charges.append({"q": _n(c_.get("q"), -6, 6, 1) or 1,
                            "x": _n(c_.get("x"), -8, 8),
                            "y": _n(c_.get("y"), -8, 8),
                            "z": _n(c_.get("z"), -8, 8)})
        loops = []
        for L in (d.get("loops") or [])[:MAX_SOURCES]:
            if not isinstance(L, dict):
                continue
            loops.append({"r": _n(L.get("r"), 0.4, 6, 2),
                          "i": _n(L.get("i"), -4, 4, 1) or 1,
                          "x": _n(L.get("x"), -8, 8),
                          "y": _n(L.get("y"), -8, 8),
                          "z": _n(L.get("z"), -8, 8)})
        if not charges and not loops:
            return None
        # One or the other. Two fields in one picture would be summed by
        # eye, and they are not the same field or the same units.
        if charges:
            out["charges"] = charges
        else:
            out["loops"] = loops
        return out

    if kind == "wave":
        mode = str(d.get("mode") or "").strip().lower()
        out["mode"] = mode if mode in WAVE_MODES else "travelling"
        out["wavelength"] = _n(d.get("wavelength"), 0.4, 8, 2)
        out["amplitude"] = _n(d.get("amplitude"), 0.05, 2, 0.5)
        out["span"] = _n(d.get("span"), 4, 16, 9)
        out["speed"] = _n(d.get("speed"), 0, 3, 0.6)
        srcs = []
        for s in (d.get("sources") or [])[:4]:
            if not isinstance(s, dict):
                continue
            srcs.append({"x": _n(s.get("x"), -8, 8),
                         "z": _n(s.get("z"), -8, 8)})
        if srcs:
            out["sources"] = srcs
        unit = _label(d.get("unit"), 6)
        if unit:
            out["unit"] = unit
        return out

    return None


# What the model is told it may ask for. Kept here beside the validator so the
# two cannot drift: a prompt that offers a field the validator drops produces
# lessons that quietly lose their pictures.
PROMPT = """You may add a 3D scene to a lesson, as `scene`. It is built from
numbers, not from a model file, so only these kinds exist. Use one only
where rotating and zooming the real structure teaches something. Most lessons
should have no scene at all, and a scene that is decoration is worse than
none.

"molecule"  {"kind":"molecule","caption":"...",
             "atoms":[{"el":"O","x":0,"y":0,"z":0}, ...],
             "bonds":[[0,1,1],[0,2,2]]}       bond order 1, 2 or 3
            Chemistry, biochemistry, materials, drug structure.

"lattice"   {"kind":"lattice","caption":"...","a":2.0,"repeat":2,
             "basis":[{"el":"Si","x":0,"y":0,"z":0}, ...]}
            Crystal structure, semiconductors, metals, salts. Name the
            substance in the caption — "Rock salt unit cell", "Caesium
            chloride" — and the real lattice constant, structure type and
            coordination number are filled in and drawn from a table of
            measured values. Do not write those yourself. For anything not
            in the table your basis is used and the scene is marked
            schematic.

"layers"    {"kind":"layers","caption":"...",
             "layers":[{"name":"p substrate","t":1.0},
                       {"name":"n+ source","t":0.4,"w":1.5,"x":-2},
                       {"name":"oxide","t":0.2,"clear":true}, ...]}
            Bottom layer first. Semiconductor and MOSFET cross-sections,
            thin films, PCB stack-ups, geological strata, battery cells,
            skin and tissue layers, anything built up in labelled layers.
            Name the device in the caption — "MOSFET gate stack", "pn
            junction", "solar cell", "LED", "PCB", "graphene" — and the
            real thicknesses are filled in from a table and printed on each
            layer. Do not write thicknesses yourself for those.

"surface"   {"kind":"surface","expr":"x^2 - y^2","span":4}
            Give "expr", the actual function of x and y this lesson is
            about, and it is evaluated and plotted exactly — any function,
            not a shape from a list. Use x and y only, with + - * / ^ and
            sqrt, sin, cos, tan, exp, log, abs. "span" is how far out from
            the origin to plot.
            Fall back to {"fn":"saddle|bowl|dome|ripple|well|plane"} only
            when the lesson is about the SHAPE rather than a formula.
            Optimisation, potentials, wave shapes, stationary points.

"orbit"     {"kind":"orbit","centre":"Sun","bodies":[{"name":"Earth","r":4,
             "size":0.3}]}
            Astronomy, and shell diagrams where the orbit is a convention.
            Name the planets in the caption — "The solar system", "The inner
            planets", "Jupiter" — and their real distances in AU, their
            periods in years and their spacing are filled in from measured
            values and printed beside each body. Do not write those numbers
            yourself.

"solid"     {"kind":"solid","shape":"cube|sphere|cylinder|cone|torus|tetra|
             octa|icosa|prism","size":3,"unit":"cm"}
            Give "size" — the defining length the problem states: the edge
            of a cube or tetrahedron, the radius of a sphere, cylinder or
            cone. Volume and surface area are computed from it and drawn on
            the solid, so do not write them yourself; use the same number
            the lesson uses and the picture and the working will agree.
            Cylinders and cones are drawn with height twice the radius.
            Geometry, volumes, packing, crystal habit.

"process"   {"kind":"process","layout":"cycle"|"chain","caption":"...",
             "stages":[{"name":"Light absorbed","in":"photon",
                        "out":"excited electron"}, ...]}
            A sequence of stages with something flowing between them, shown
            as linked stations you can walk around. "cycle" when the last
            stage feeds the first — the Krebs cycle, the water cycle, the
            nitrogen cycle, the carbon cycle, a refrigeration loop. "chain"
            when it runs start to finish — photosynthesis, digestion,
            transcription and translation, a production line, a CPU pipeline,
            a request travelling through a system.

"flow"      {"kind":"flow","body":"leaf"|"cell"|"root"|"panel"|"vessel"|"box",
             "caption":"...",
             "in":[{"name":"CO2"},{"name":"water"},{"name":"sunlight"}],
             "out":[{"name":"oxygen"},{"name":"glucose"}]}
            The thing itself, with what goes into it and what comes out
            moving around it. This is the one to reach for when a learner
            needs to see the object: photosynthesis is a LEAF with sunlight
            on it and gases going in and out, not four labelled discs and not
            a ball-and-stick chlorophyll. Also respiration in a cell, uptake
            in a root, a solar panel, a reactor vessel, a heat exchanger.
            Say "sunlight" or "light" among the inputs and a sun with rays
            is drawn.

"helix"     {"kind":"helix","form":"dna"|"a-dna"|"z-dna"|"rna"|"alpha",
             "turns":2.5,"sequence":"ATGCATGC","caption":"..."}
            DNA, RNA and the protein alpha-helix. Name the form; the rise
            per base pair, the bases per turn, the diameter and the
            handedness are filled in from measured crystallography and
            written on the scene. Do not write those numbers yourself, and
            do not give the second strand — the pairing is computed, which
            is the point of showing it. A sequence is optional and colours
            the bases. This is the structure a biology class is examined on
            the shape of: the two grooves are different widths and the
            strands run opposite ways, and neither is visible until it turns.

"cell"      {"kind":"cell","cell":"animal"|"plant","caption":"...",
             "parts":[{"name":"nucleus"},{"name":"mitochondrion","n":6},
                      {"name":"chloroplast","n":4}]}
            A cell with its organelles at their real relative sizes — a
            mitochondrion really is a fifth of the nucleus here. Names
            allowed: nucleus, nucleolus, mitochondrion, chloroplast,
            vacuole, ribosome, lysosome, golgi, endoplasmic reticulum,
            centriole, chromosome. Anything else is dropped rather than
            drawn at an invented size. "n" is how many, and it is a fact
            about the cell worth giving.

"field"     {"kind":"field","caption":"...",
             "charges":[{"q":1,"x":-2},{"q":-1,"x":2}]}
             or {"kind":"field","loops":[{"r":2,"i":1}]}
            Field lines, walked step by step along the field summed from
            every source — so a dipole's lines close on the negative charge
            because the arithmetic takes them there. Give point charges for
            an electric field ("q" in whatever units, sign matters) or
            current loops for a magnetic one. Not both: they are not the
            same field. Electrostatics, dipoles, the field of a bar magnet
            or a solenoid — the pictures a flat diagram cannot give.

"wave"      {"kind":"wave","mode":"travelling"|"standing"|"interference",
             "wavelength":2,"amplitude":0.5,"span":9,"unit":"cm",
             "sources":[{"x":-2,"z":0},{"x":2,"z":0}]}
            A surface that actually moves, recomputed each frame from the
            superposition. "standing" for nodes and antinodes — drawn still
            it is a curve, and the nodes holding still while everything
            between them moves IS the lesson. "interference" for two
            sources: from above it is the double-slit figure, from the side
            it is water, which is the connection that figure is making.

PREFER "flow" OVER "process" WHEN THERE IS A REAL OBJECT. Discs and arrows
are for something with no physical thing at its centre — a cycle of
transformations, an accounting loop. The moment the answer has an object in
it, show the object.

A PROCESS IS NOT A MOLECULE. If someone asks how photosynthesis works, the
answer is the stages and what passes between them, not a ball-and-stick model
of chlorophyll: drawing the magnesium and nitrogen atoms of one pigment
molecule answers a question nobody asked. Ask yourself whether the thing being
taught is a SHAPE or a SEQUENCE, and pick on that. Only reach for "molecule"
when the arrangement of the atoms is itself the lesson.

Rules:
- Real coordinates and real proportions. An invented geometry taught
  confidently is worse than no picture.
- `caption` says what to look at, in under twelve words.
- If the thing worth showing is an organic shape — an organ, a bone, a face —
  none of these can draw it honestly. Leave `scene` out and describe it in
  words instead. A cell is the exception and has its own kind: a nucleus IS a
  sphere and a mitochondrion IS a capsule, whereas a liver drawn as an
  ellipsoid teaches a shape that will be marked wrong.
- Physics and biology have their own kinds now — "field", "wave", "helix",
  "cell". Reach for those before settling for "surface" or "flow": a lesson
  on the electric field of a dipole is a field, not a saddle, and a lesson on
  DNA is a helix, not a ball-and-stick model of one base."""
