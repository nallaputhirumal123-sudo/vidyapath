"""A drawing vocabulary, instead of a list of diagram types.

The eight fixed kinds in sketch.py answer eight questions well and everything
else not at all. Somebody asks how a gearbox shifts, or what a nephron does,
or how a syllogism is structured, and none of "plot, bar, timeline, tree,
forces, circuit, venn, ray" fits — so the lesson arrives with no picture, and
"only some questions get a sketch" is the direct consequence of naming the
pictures in advance.

So this names shapes rather than diagrams. Circles, rectangles, paths, arrows,
labels and a library of symbols, in a fixed 1000x600 space. A cell, a
gearbox, a food web, a sentence tree and a distillation rig are all the same
handful of primitives arranged differently, which is why a vocabulary reaches
every subject and a list of diagram types never can.

Three things are kept from the old approach because they earn it: a plot, a
bar chart and a timeline have conventions worth encoding, and drawing them
out of primitives every time would produce a worse axis than a purpose-built
one. Everything else is composed.

The security position is unchanged and is the reason this is safe to accept
from a model: every field below is a number, a name from a fixed list, or a
short label. Nothing here is executed. Path data is validated to a strict
character set — it goes to Path2D, which parses geometry, not code.
"""
import re

# Fixed drawing space. Everything arrives in these coordinates and the
# renderer scales; a model that has one canvas size to think about places
# things far more consistently than one that has to ask how wide it is.
W, H = 1000.0, 600.0

TYPES = ("circle", "ellipse", "rect", "line", "path", "polygon", "arrow",
         "label", "symbol")

ANIMS = ("draw", "move", "rotate", "scale", "fade", "pulse")

# The named parts. A resistor drawn from primitives comes out looking
# hand-made; drawn from the library it looks like a schematic, which is the
# difference between a diagram a student trusts and one they do not.
SYMBOLS = (
    # circuits
    "resistor", "capacitor", "battery", "cell", "lamp", "switch", "diode",
    "led", "transistor", "ammeter", "voltmeter", "motor", "ground",
    "inductor", "fuse", "speaker",
    # logic
    "and_gate", "or_gate", "not_gate", "nand_gate", "nor_gate", "xor_gate",
    # mechanics
    "spring", "pulley", "mass", "pivot", "damper", "wheel",
    # lab
    "beaker", "flask", "test_tube", "burette", "funnel", "bunsen",
    "condenser", "thermometer", "balance",
)

MAX_ELEMENTS = 60
MAX_ANIMS = 24
MAX_POINTS = 40

# Path data only. Commands, numbers, separators — nothing that could be read
# as anything but geometry.
_PATH_OK = re.compile(r"^[MmLlHhVvCcSsQqTtAaZz0-9eE ,.\-+]*$")

# A short palette rather than free colour. Chalk on a dark board reads well;
# a model choosing its own hex values produces lessons that fight the page.
INK = {
    "chalk": "#eafff2", "amber": "#ffb020", "blue": "#7fb8ff",
    "green": "#8fe3b0", "rose": "#d98fb0", "violet": "#c9a0ff",
    "grey": "#8fa3b0", "dim": "#5c6b7a", "red": "#e0714a",
}
FILLS = dict(INK)
FILLS["none"] = "none"


def _n(v, lo, hi, default=0.0):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if f != f or f in (float("inf"), float("-inf")):
        return default
    return max(lo, min(hi, f))


def _label(v, n=42):
    s = "".join(c for c in str(v or "") if ord(c) >= 32)
    return s.strip()[:n]


def _ident(v):
    """An element id, safe to use as a dictionary key and a reveal target."""
    s = re.sub(r"[^a-zA-Z0-9_]", "", str(v or ""))[:40]
    return s or ""


def _ink(v, table=INK, default="chalk"):
    k = str(v or "").strip().lower()
    return table.get(k, table[default])


def _element(e, seen):
    if not isinstance(e, dict):
        return None
    t = str(e.get("type") or "").strip().lower()
    if t not in TYPES:
        return None
    eid = _ident(e.get("id"))
    if not eid or eid in seen:
        return None

    out = {"id": eid, "type": t,
           "stroke": _ink(e.get("stroke")),
           "fill": _ink(e.get("fill"), FILLS, "none"),
           "w": _n(e.get("strokeWidth"), 0.5, 10, 2),
           "opacity": _n(e.get("opacity"), 0.05, 1, 1),
           "dash": bool(e.get("dash"))}
    rot = e.get("rotate")
    if rot is not None:
        out["rotate"] = _n(rot, -360, 360, 0)

    if t in ("circle", "ellipse"):
        out["cx"] = _n(e.get("cx"), -W, W * 2, W / 2)
        out["cy"] = _n(e.get("cy"), -H, H * 2, H / 2)
        if t == "circle":
            out["r"] = _n(e.get("r"), 1, W, 40)
        else:
            out["rx"] = _n(e.get("rx"), 1, W, 60)
            out["ry"] = _n(e.get("ry"), 1, H, 40)
    elif t == "rect":
        out["x"] = _n(e.get("x"), -W, W * 2, 0)
        out["y"] = _n(e.get("y"), -H, H * 2, 0)
        out["rw"] = _n(e.get("w"), 1, W * 2, 100)
        out["rh"] = _n(e.get("h"), 1, H * 2, 60)
        out["radius"] = _n(e.get("radius"), 0, 60, 0)
    elif t in ("line", "arrow"):
        out["x1"] = _n(e.get("x1"), -W, W * 2, 0)
        out["y1"] = _n(e.get("y1"), -H, H * 2, 0)
        out["x2"] = _n(e.get("x2"), -W, W * 2, 100)
        out["y2"] = _n(e.get("y2"), -H, H * 2, 0)
        if t == "arrow":
            out["double"] = bool(e.get("double"))
        lb = _label(e.get("label"))
        if lb:
            out["label"] = lb
    elif t == "path":
        d = str(e.get("d") or "").strip()[:1200]
        # Rejected rather than stripped: a path with characters removed is a
        # different shape, and a wrong shape drawn confidently is the thing
        # this whole file exists to avoid.
        if not d or not _PATH_OK.match(d):
            return None
        out["d"] = d
    elif t == "polygon":
        pts = []
        for p in (e.get("points") or [])[:MAX_POINTS]:
            try:
                pts.append([_n(p[0], -W, W * 2), _n(p[1], -H, H * 2)])
            except (TypeError, IndexError):
                continue
        if len(pts) < 3:
            return None
        out["points"] = pts
        out["closed"] = e.get("closed") is not False
    elif t == "label":
        txt = _label(e.get("text"), 90)
        if not txt:
            return None
        out["x"] = _n(e.get("x"), -W, W * 2, W / 2)
        out["y"] = _n(e.get("y"), -H, H * 2, H / 2)
        out["text"] = txt
        out["size"] = _n(e.get("size"), 9, 40, 16)
        a = str(e.get("anchor") or "middle").lower()
        out["anchor"] = a if a in ("start", "middle", "end") else "middle"
        out["plate"] = e.get("plate") is not False
    elif t == "symbol":
        nm = str(e.get("name") or "").strip().lower()
        if nm not in SYMBOLS:
            return None
        out["name"] = nm
        out["x"] = _n(e.get("x"), -W, W * 2, W / 2)
        out["y"] = _n(e.get("y"), -H, H * 2, H / 2)
        out["scale"] = _n(e.get("scale"), 0.3, 4, 1)
        lb = _label(e.get("label"), 24)
        if lb:
            out["label"] = lb

    seen.add(eid)
    return out


def clean(d):
    """Validate a composed drawing, or None if there is not a usable one."""
    if not isinstance(d, dict):
        return None
    els, seen = [], set()
    for e in (d.get("elements") or [])[:MAX_ELEMENTS]:
        got = _element(e, seen)
        if got:
            els.append(got)
    if not els:
        return None

    anims = []
    for a in (d.get("animations") or [])[:MAX_ANIMS]:
        if not isinstance(a, dict):
            continue
        kind = str(a.get("type") or "").strip().lower()
        target = _ident(a.get("target"))
        # An animation pointed at nothing is a silent no-op that makes a
        # lesson look broken for no visible reason.
        if kind not in ANIMS or target not in seen:
            continue
        item = {"type": kind, "target": target,
                "duration": int(_n(a.get("duration"), 120, 6000, 900)),
                "delay": int(_n(a.get("delay"), 0, 10000, 0)),
                "loop": bool(a.get("loop"))}
        to = a.get("to")
        if kind == "move" and isinstance(to, dict):
            item["to"] = {"x": _n(to.get("x"), -W, W * 2, 0),
                          "y": _n(to.get("y"), -H, H * 2, 0)}
        elif kind in ("rotate", "scale"):
            item["to"] = _n(to, -360 if kind == "rotate" else 0.1,
                            360 if kind == "rotate" else 4,
                            180 if kind == "rotate" else 1.4)
        anims.append(item)

    return {"kind": "draw", "caption": _label(d.get("caption"), 110),
            "elements": els, "animations": anims,
            "ids": sorted(seen)}


def check_reveals(drawing, narration):
    """Every id a step reveals must exist. Returns the ids that do not.

    The spec's rule, and worth enforcing rather than trusting: a step that
    reveals an element the drawing never defined leaves the narration talking
    about something the student cannot see, which is worse than no narration.
    """
    if not drawing:
        return []
    have = set(drawing.get("ids") or [])
    missing = []
    for step in (narration or []):
        for r in (step.get("reveal") or []):
            rid = _ident(r)
            if rid and rid not in have:
                missing.append(rid)
    return sorted(set(missing))


PROMPT = """DRAWING. Instead of choosing from a list of diagram types, compose
the picture from shapes. That is why this reaches every subject: a cell, a
gearbox, a food web, a sentence tree and a distillation rig are the same
handful of primitives arranged differently.

Send it as `draw`. The space is 1000 wide by 600 tall — all coordinates in
that space, origin top-left.

{"draw": {"caption": "what to look at, under twelve words",
  "elements": [
    {"id":"membrane","type":"ellipse","cx":500,"cy":300,"rx":380,"ry":230,
     "stroke":"chalk","fill":"none","strokeWidth":3},
    {"id":"nucleus","type":"circle","cx":430,"cy":290,"r":85,
     "stroke":"amber","fill":"amber","opacity":0.18},
    {"id":"nucleus_lbl","type":"label","x":430,"y":290,"text":"Nucleus"},
    {"id":"er","type":"path","d":"M600 200 q40 30 0 60 q-40 30 0 60",
     "stroke":"blue","strokeWidth":2},
    {"id":"er_ptr","type":"arrow","x1":810,"y1":170,"x2":650,"y2":215,
     "label":"Endoplasmic reticulum"}],
  "animations":[{"target":"er","type":"draw","duration":1200},
                {"target":"nucleus","type":"pulse","duration":900,"loop":true}]}}

TYPES: circle (cx,cy,r) · ellipse (cx,cy,rx,ry) · rect (x,y,w,h,radius) ·
line and arrow (x1,y1,x2,y2, arrow takes label and double) · path (d, SVG path
syntax) · polygon (points [[x,y],...]) · label (x,y,text,size,anchor) ·
symbol (name,x,y,scale,label).

SYMBOLS, drawn properly so a schematic looks like a schematic:
  circuits  resistor capacitor battery cell lamp switch diode led transistor
            ammeter voltmeter motor ground inductor fuse speaker
  logic     and_gate or_gate not_gate nand_gate nor_gate xor_gate
  mechanics spring pulley mass pivot damper wheel
  lab       beaker flask test_tube burette funnel bunsen condenser
            thermometer balance

COLOURS, by name only: chalk amber blue green rose violet grey dim red, and
fill also takes none. Not hex — the palette is chosen to read on this board.

ANIMATIONS: draw (traces a stroke on) · move (to {x,y}) · rotate (to degrees) ·
scale (to factor) · fade · pulse. Each takes duration, delay, loop.

RULES
- Every element needs a unique id, lowercase letters, digits and underscores.
- Label what you are sure of. An unlabelled part is fine; a wrongly labelled
  one destroys trust in everything else on the board.
- Use the symbol library for any circuit, logic or lab apparatus. Drawing a
  resistor out of rectangles produces something a student will not recognise.
- Draw the thing at a readable size. Fill the space rather than putting a
  small diagram in the middle of an empty board.
- Animate only where the motion carries meaning — a stroke drawing itself in
  the order the process happens, a part that rotates. Decoration that moves
  is worse than a still picture.
- A plot, a bar chart or a timeline should still use `sketch`, which has the
  axes and conventions those need. Everything else composes here."""
