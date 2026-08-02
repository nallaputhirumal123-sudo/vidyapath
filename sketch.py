"""Flat drawings, for the things a camera is the wrong tool for.

The 3D scenes handle anything with structure you would want to turn around: a
molecule, a layer stack, a leaf. They are the wrong answer for a graph. A
curve seen in perspective is a curve you cannot read values off, a timeline
with a vanishing point is worse than a line, and nobody has ever understood a
free-body diagram better for being able to orbit it.

So this is the other half: eight kinds of drawing that live on a plane. Same
discipline as everywhere else — the model sends numbers and short labels, this
rebuilds them field by field, and the renderer draws. There is no field here
that can carry markup or code, so there is nothing to sanitise, only a shape
to enforce.

Points are sent as data, not as formulas. A model that could send "the
function to plot" would be sending something to evaluate in a browser, and a
nicer curve is not worth that.
"""

KINDS = ("plot", "bar", "timeline", "tree", "forces", "circuit", "venn",
         "ray")

# Free-body arrows point in eight directions and no others. A free angle
# invites 37.4 degrees, which is a worse drawing than the nearest eighth.
DIRS = ("up", "down", "left", "right", "ne", "nw", "se", "sw")

PARTS = ("battery", "resistor", "lamp", "switch", "capacitor", "ammeter",
         "voltmeter", "motor", "diode")

BODIES = ("block", "ball", "car", "crate", "person", "plane")

MAX_SERIES = 4
MAX_POINTS = 80
MAX_BARS = 10
MAX_EVENTS = 8
MAX_PARTS = 6
MAX_ARROWS = 6
MAX_NODES = 24


def _n(v, lo, hi, default=0.0):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if f != f or f in (float("inf"), float("-inf")):
        return default
    return max(lo, min(hi, f))


def _label(v, n=28):
    s = "".join(c for c in str(v or "") if ord(c) >= 32)
    return s.strip()[:n]


def _colour(v):
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, str):
        try:
            v = int(v.strip().lstrip("#"), 16)
        except ValueError:
            return None
    try:
        i = int(v)
    except (TypeError, ValueError):
        return None
    return i if 0 <= i <= 0xFFFFFF else None


def clean(d):
    """Validate one sketch, or None if there is not a usable one."""
    if not isinstance(d, dict):
        return None
    kind = str(d.get("kind") or "").strip().lower()
    if kind not in KINDS:
        return None
    out = {"kind": kind, "caption": _label(d.get("caption"), 110)}

    if kind == "plot":
        series = []
        for s in (d.get("series") or [])[:MAX_SERIES]:
            if not isinstance(s, dict):
                continue
            pts = []
            for p in (s.get("points") or [])[:MAX_POINTS]:
                try:
                    pts.append([_n(p[0], -1e6, 1e6), _n(p[1], -1e6, 1e6)])
                except (TypeError, IndexError):
                    continue
            if len(pts) < 2:
                continue
            item = {"name": _label(s.get("name"), 24), "points": pts,
                    "dashed": bool(s.get("dashed"))}
            c = _colour(s.get("color"))
            if c is not None:
                item["color"] = c
            series.append(item)
        if not series:
            return None
        marks = []
        for m in (d.get("marks") or [])[:6]:
            if not isinstance(m, dict):
                continue
            lb = _label(m.get("label"), 24)
            if not lb:
                continue
            marks.append({"x": _n(m.get("x"), -1e6, 1e6),
                          "y": _n(m.get("y"), -1e6, 1e6), "label": lb})
        out.update(series=series, marks=marks,
                   x=_label(d.get("x"), 30), y=_label(d.get("y"), 30))
        return out

    if kind == "bar":
        bars = []
        for b in (d.get("bars") or [])[:MAX_BARS]:
            if not isinstance(b, dict):
                continue
            nm = _label(b.get("name"), 20)
            if not nm:
                continue
            item = {"name": nm, "value": _n(b.get("value"), -1e6, 1e6)}
            c = _colour(b.get("color"))
            if c is not None:
                item["color"] = c
            bars.append(item)
        if len(bars) < 2:
            return None
        out.update(bars=bars, y=_label(d.get("y"), 30))
        return out

    if kind == "timeline":
        evs = []
        for e in (d.get("events") or [])[:MAX_EVENTS]:
            if not isinstance(e, dict):
                continue
            nm = _label(e.get("name"), 30)
            if not nm:
                continue
            evs.append({"at": _label(e.get("at"), 14), "name": nm,
                        "note": _label(e.get("note"), 46)})
        if len(evs) < 2:
            return None
        out["events"] = evs
        return out

    if kind == "tree":
        # Flattened here rather than in the renderer, and hard-capped: a
        # deeply nested reply could otherwise recurse as far as it liked.
        nodes, edges = [], []

        def walk(n, parent, depth):
            if not isinstance(n, dict) or depth > 4 or len(nodes) >= MAX_NODES:
                return
            nm = _label(n.get("name"), 22)
            if not nm:
                return
            idx = len(nodes)
            nodes.append({"name": nm, "depth": depth})
            if parent is not None:
                edges.append([parent, idx, _label(n.get("edge"), 16)])
            for c in (n.get("children") or [])[:5]:
                walk(c, idx, depth + 1)

        walk(d.get("root"), None, 0)
        if len(nodes) < 2:
            return None
        out.update(nodes=nodes, edges=edges)
        return out

    if kind == "forces":
        arrows = []
        for a in (d.get("arrows") or [])[:MAX_ARROWS]:
            if not isinstance(a, dict):
                continue
            dr = str(a.get("dir") or "").strip().lower()
            lb = _label(a.get("label"), 22)
            if dr not in DIRS or not lb:
                continue
            arrows.append({"dir": dr, "label": lb,
                           "size": _n(a.get("size"), 0.3, 1.0, 0.8)})
        if not arrows:
            return None
        body = str(d.get("body") or "").strip().lower()
        out.update(arrows=arrows, body=body if body in BODIES else "block",
                   surface=_label(d.get("surface"), 24))
        return out

    if kind == "circuit":
        parts = []
        for p in (d.get("parts") or [])[:MAX_PARTS]:
            if not isinstance(p, dict):
                continue
            t = str(p.get("type") or "").strip().lower()
            if t not in PARTS:
                continue
            parts.append({"type": t, "label": _label(p.get("label"), 18)})
        if not parts:
            return None
        lay = str(d.get("layout") or "").strip().lower()
        out.update(parts=parts,
                   layout=lay if lay in ("series", "parallel") else "series")
        return out

    if kind == "venn":
        a, b = _label(d.get("a"), 22), _label(d.get("b"), 22)
        if not a or not b:
            return None
        out.update(a=a, b=b,
                   only_a=_label(d.get("only_a"), 26),
                   only_b=_label(d.get("only_b"), 26),
                   both=_label(d.get("both"), 26))
        return out

    if kind == "ray":
        lens = str(d.get("lens") or "").strip().lower()
        out.update(lens=lens if lens in ("converging", "diverging") else
                   "converging",
                   f=_n(d.get("f"), 0.5, 6, 2),
                   u=_n(d.get("u"), 0.5, 12, 4),
                   height=_n(d.get("height"), 0.3, 3, 1))
        return out

    return None


PROMPT = """You may add a flat drawing to a step, as `sketch`. Use it for the
things a 3D scene cannot show properly — anything you would read values off,
or follow along a line. It is drawn from numbers, so only these eight exist.

"plot"      {"kind":"plot","x":"time (s)","y":"velocity (m/s)",
             "series":[{"name":"with drag","points":[[0,0],[1,8],[2,13]]}],
             "marks":[{"x":2,"y":13,"label":"terminal velocity"}]}
            Any relationship between two quantities: kinematics, demand and
            supply, titration curves, decay, growth, distributions. Send the
            POINTS, computed yourself — twenty or thirty is plenty for a
            smooth curve. Never send a formula.

"bar"       {"kind":"bar","y":"kJ/mol",
             "bars":[{"name":"C-H","value":413},{"name":"C-C","value":347}]}
            Comparing quantities across categories.

"timeline"  {"kind":"timeline","events":[{"at":"1789","name":"Estates-General",
             "note":"called for the first time since 1614"}]}
            History, a legal sequence, a geological period, project phases.

"tree"      {"kind":"tree","root":{"name":"Chordata","children":[
             {"name":"Mammalia","edge":"has hair"}]}}
            Taxonomy, a decision tree, an org chart, a syntax tree, a
            derivation that branches. Four levels deep at most.

"forces"    {"kind":"forces","body":"block","surface":"rough slope",
             "arrows":[{"dir":"down","label":"W = 49 N"},
                       {"dir":"ne","label":"N = 42 N"},
                       {"dir":"nw","label":"friction = 12 N"}]}
            A free-body diagram. Directions are one of up, down, left, right,
            ne, nw, se, sw.

"circuit"   {"kind":"circuit","layout":"series",
             "parts":[{"type":"battery","label":"12 V"},
                      {"type":"resistor","label":"100 ohm"}]}
            Electronics. Types: battery, resistor, lamp, switch, capacitor,
            ammeter, voltmeter, motor, diode.

"venn"      {"kind":"venn","a":"Mitosis","b":"Meiosis",
             "only_a":"one division","both":"DNA replicates first",
             "only_b":"crossing over"}
            Comparing two things that genuinely share properties.

"ray"       {"kind":"ray","lens":"converging","f":2,"u":4,"height":1}
            Optics. Distances in arbitrary units; the drawing traces the rays
            and finds the image itself.

Rules:
- A sketch and a 3D scene are alternatives, not a pair. Pick whichever
  actually shows the idea, and give a step at most one of them.
- `caption` says what to look at, in under twelve words.
- Real values. A plot with invented numbers is worse than no plot, because it
  will be read as data."""
