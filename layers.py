"""Layer stacks at their real thicknesses.

The layers scene took a thickness per layer from the model, on an arbitrary
scale, so a gate oxide and a silicon wafer came out within a factor of two of
each other. They differ by a factor of about a quarter of a million: the oxide
is two nanometres and the wafer is half a millimetre, and that ratio is the
entire reason gate oxides are interesting. A stack drawn without it teaches
that a MOSFET is a sandwich of comparable slices, which is the opposite of
what makes one work.

So the stacks that get taught are held here with their real thicknesses, and
the drawing uses the logarithm of the thickness. That is stated, not hidden:
at true scale the oxide is invisible — one pixel in a stack the height of a
building — and at equal thickness the picture is a lie. A log scale keeps the
order and shows that the layers differ enormously, and the real figure is
printed on every layer.

Thicknesses are typical values for the node or device named, not a single
manufacturer's specification. A lesson that says "about two nanometres" is
right; one that says 1.8 is claiming a precision nobody has.
"""
import math

# Colours by material, so the same material reads the same across stacks.
_C = {
    "silicon": 0x6E7B8B, "oxide": 0x9AA7B0, "poly": 0xC9A227,
    "metal": 0xD8D8D8, "nitride": 0x8FA36E, "photoresist": 0xC46A8A,
    "glass": 0xA8C8D8, "n": 0x4A90D9, "p": 0xD9603B, "air": 0x223040,
}


def _layer(name, nm, material, note=""):
    return {"name": name, "nm": nm, "material": material,
            "color": _C.get(material, 0x7A8A99), "note": note}


# Each stack is listed bottom to top, the way it is grown.
STACKS = {
    "mosfet": [
        _layer("p-type silicon substrate", 500_000, "silicon", "the wafer"),
        _layer("gate oxide (SiO₂)", 2, "oxide", "1-3 nm at 90 nm node"),
        _layer("polysilicon gate", 150, "poly"),
        _layer("silicide contact", 30, "metal"),
        _layer("aluminium interconnect", 500, "metal"),
    ],
    "pn junction": [
        _layer("p-type silicon", 250_000, "p"),
        _layer("depletion region", 500, "air", "widens under reverse bias"),
        _layer("n-type silicon", 250_000, "n"),
    ],
    "solar cell": [
        _layer("aluminium back contact", 20_000, "metal"),
        _layer("p-type silicon base", 180_000, "p"),
        _layer("n-type emitter", 300, "n"),
        _layer("silicon nitride anti-reflection", 75, "nitride",
               "quarter-wave at 600 nm"),
        _layer("silver front grid", 15_000, "metal"),
    ],
    "led": [
        _layer("sapphire substrate", 400_000, "glass"),
        _layer("n-GaN", 4_000, "n"),
        _layer("InGaN quantum wells", 3, "nitride", "2-3 nm per well"),
        _layer("p-GaN", 200, "p"),
        _layer("ITO current spreader", 200, "metal"),
    ],
    "capacitor": [
        _layer("metal plate", 1_000, "metal"),
        _layer("dielectric", 100, "oxide"),
        _layer("metal plate", 1_000, "metal"),
    ],
    "pcb": [
        _layer("copper", 35_000, "metal", "1 oz copper"),
        _layer("FR-4 core", 1_600_000, "glass", "1.6 mm board"),
        _layer("copper", 35_000, "metal"),
        _layer("solder mask", 25_000, "photoresist"),
    ],
    "graphene": [
        _layer("SiO₂ on silicon", 300, "oxide",
               "300 nm makes graphene visible"),
        _layer("graphene", 0.335, "poly", "one atom thick"),
    ],
    "thin film": [
        _layer("glass substrate", 1_100_000, "glass"),
        _layer("transparent conductor", 200, "metal"),
        _layer("absorber", 2_000, "p"),
        _layer("buffer", 50, "n"),
    ],
}

_ALIASES = {
    "mosfet": "mosfet", "transistor": "mosfet", "gate stack": "mosfet",
    "field effect transistor": "mosfet", "cmos": "mosfet",
    "gate oxide": "mosfet",
    "pn junction": "pn junction", "p-n junction": "pn junction",
    "diode": "pn junction", "depletion region": "pn junction",
    "solar cell": "solar cell", "photovoltaic": "solar cell",
    "solar panel": "solar cell", "pv cell": "solar cell",
    "led": "led", "light emitting diode": "led", "quantum well": "led",
    "capacitor": "capacitor", "parallel plate capacitor": "capacitor",
    "pcb": "pcb", "printed circuit board": "pcb", "circuit board": "pcb",
    "graphene": "graphene",
    "thin film": "thin film", "thin film solar": "thin film",
}


def human(nm):
    """A thickness a person can read: nm, micrometres or millimetres."""
    if nm < 1:
        return f"{nm:g} nm"
    if nm < 1000:
        return f"{nm:g} nm"
    if nm < 1_000_000:
        return f"{nm / 1000:g} µm"
    return f"{nm / 1_000_000:g} mm"


def find(topic):
    """The measured stack for this topic, or nothing."""
    t = " ".join(str(topic or "").lower().split())
    if not t:
        return None
    hits = [k for k in _ALIASES if k in t]
    if not hits:
        return None
    return STACKS[_ALIASES[max(hits, key=len)]]


def clean(topic):
    """A layers scene with real thicknesses, or an empty dict.

    Drawn thickness is the logarithm of the real one. At true scale a two
    nanometre oxide on a half millimetre wafer is invisible; at equal
    thickness the picture says they are comparable, which is the one thing
    that is certainly false. The log keeps the order and shows the layers
    differ hugely, and every real figure is printed.
    """
    stack = find(topic)
    if not stack:
        return {}
    # Drawn thickness is the logarithm of the real one, normalised across
    # this stack into the range the scene schema accepts (it caps a layer at
    # 3.0, and raw logs run to 7.4 — every measured stack would have been
    # silently flattened to one height, the exact fault the log scale exists
    # to avoid). Normalising against the stack rather than an absolute scale
    # also means a stack of similar layers still spreads out to fill the
    # picture, and one spanning six orders of magnitude still fits inside it.
    logs = [math.log10(max(l['nm'], 0.1)) for l in stack]
    lo, hi = min(logs), max(logs)
    span = (hi - lo) or 1.0
    out = []
    for lay, lg in zip(stack, logs):
        t = 0.35 + (lg - lo) / span * 2.3      # 0.35..2.65, inside the cap
        out.append({"name": lay["name"], "t": round(t, 3),
                    "color": lay["color"],
                    "nm": lay["nm"], "real": human(lay["nm"]),
                    "note": lay["note"]})
    return {"layers": out, "measured": True,
            "scale_note": "thickness on a log scale; real values shown"}
