"""Flat drawings, for the things a camera is the wrong tool for.

The 3D scenes handle anything with structure you would want to turn around: a
molecule, a layer stack, a leaf. They are the wrong answer for a graph. A
curve seen in perspective is a curve you cannot read values off, a timeline
with a vanishing point is worse than a line, and nobody has ever understood a
free-body diagram better for being able to orbit it.

So this is the other half: the drawings that live on a plane. Same discipline
as everywhere else — the model sends numbers and short labels, this rebuilds
them field by field, and the renderer draws. There is no field here that can
carry markup or code, so there is nothing to sanitise, only a shape to
enforce.

The same discipline is why the table and the pie live here rather than being
composed from `draw`. A pie built out of arc paths asks a model for angles,
and a model that gets one wrong draws a confidently wrong pie; a table built
out of rectangles asks it for column positions, and gets them wrong on the
first long cell. Both are DATA — names and values — and the geometry is
arithmetic that belongs on this side of the wire.

Points are sent as data, not as formulas. A model that could send "the
function to plot" would be sending something to evaluate in a browser, and a
nicer curve is not worth that.
"""

# Only the three with conventions worth encoding. tree, forces, circuit, venn
# and ray were named diagram types — the exact thing that made most questions
# get no picture at all, because a question that is none of them got nothing.
# They are all reachable from the drawing primitives now. The renderers stay
# in draw.js's sibling for anything already cached, but nothing offers them.
KINDS = ("plot", "bar", "timeline", "table", "pie")

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
# A table is the thing a board could not do at all, and it is what half of
# teaching wants: active against passive, the alkali metals down a column,
# reactants against products, a comparison of three methods. There was no way
# to put one on the board, so those lessons arrived as prose describing a
# table, which is the hardest form to read and the easiest to write.
#
# Six columns and ten rows. Past that it is a spreadsheet, not a blackboard,
# and it stops being readable from the back of a classroom — which is the only
# measure that matters for this screen.
MAX_COLS = 6
MAX_ROWS = 10
# Eight slices. A pie with more is a pie nobody can read; the ninth thing is
# "other", and saying so is better than drawing a sliver.
MAX_SLICES = 8
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

    if kind == "table":
        heads = [_label(h, 26) for h in (d.get("columns") or [])[:MAX_COLS]]
        # Empty headings are kept IN PLACE, not filtered out. The first
        # column usually carries the thing being compared and its heading is
        # blank — dropping it shifted every column one to the left, so the
        # table still drew, still looked like a table, and had every value
        # under the wrong heading. Trailing blanks go, since those are a
        # column nobody filled in.
        while heads and not heads[-1]:
            heads.pop()
        if len(heads) < 2 or not any(heads):
            return None
        rows = []
        for r in (d.get("rows") or [])[:MAX_ROWS]:
            if not isinstance(r, (list, tuple)):
                continue
            # Padded and trimmed to the header, rather than dropped. A row
            # with a cell missing is the common case — a comparison where one
            # side has no equivalent — and it should draw as an empty cell,
            # which is itself the answer, not vanish.
            cells = [_label(c, 42) for c in list(r)[:len(heads)]]
            cells += [""] * (len(heads) - len(cells))
            if any(cells):
                rows.append(cells)
        if not rows:
            return None
        # A table asks for its own height. Everything else here is drawn into
        # a fixed 300 and looks right; ten rows in 300 are 20 pixels each,
        # which is a spreadsheet printed small rather than something readable
        # from the back of a room.
        out.update(columns=heads, rows=rows,
                   height=min(380, 46 + 30 * len(rows)))
        return out

    if kind == "pie":
        slices = []
        for s in (d.get("slices") or [])[:MAX_SLICES]:
            if not isinstance(s, dict):
                continue
            nm = _label(s.get("name"), 24)
            # Negative and zero shares are not small slices, they are a
            # drawing that cannot be made. A pie is a whole divided up.
            val = _n(s.get("value"), 0, 1e9)
            if not nm or val <= 0:
                continue
            item = {"name": nm, "value": val}
            c = _colour(s.get("color"))
            if c is not None:
                item["color"] = c
            slices.append(item)
        if len(slices) < 2:
            return None
        out.update(slices=slices, unit=_label(d.get("unit"), 16))
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


PROMPT = """CHARTS AND TABLES, as `sketch`. Five kinds, for the five things that have
conventions worth keeping: an axis, a bar, a dated line, a grid and a share of
a whole. Anything else you want to draw, compose with `draw` instead.

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

"table"     {"kind":"table","columns":["","Active","Passive"],
             "rows":[["Subject","does the action","receives it"],
                     ["Example","The board deleted the logs",
                      "The logs were deleted"],
                     ["Actor","named","can be hidden"]]}
            USE THIS OFTEN. It is the shape of half of teaching and the board
            could not draw one until now, so lessons whose real form is a
            table were arriving as prose describing a table — the hardest
            form to read. Anything compared across cases belongs here:
            active against passive, two methods, the halogens down a group,
            reactants and products, before and after, advantages and costs,
            a declension, the parts of a system and what each does.
            Two to six columns, up to ten rows. Keep cells short — a few
            words, not sentences; long cells are clipped. The first column
            carries the thing being compared and its heading may be empty.

"pie"       {"kind":"pie","unit":"dry air",
             "slices":[{"name":"Nitrogen","value":78},
                       {"name":"Oxygen","value":21},
                       {"name":"Argon","value":0.9},
                       {"name":"Other","value":0.1}]}
            A share of ONE whole, which is the thing a bar chart does not
            say: the composition of air or of the atmosphere, where a rupee
            of tax goes, a population split, a budget. Send the values; the
            percentages are worked out from them and drawn for you, so never
            send both. Two to eight slices, and if there are more, sum the
            tail into "Other" rather than drawing slivers.
            Not for comparing separate quantities — that is "bar". If the
            parts do not add up to one whole, it is the wrong chart.

Rules:
- A sketch and a 3D scene are alternatives, not a pair. Pick whichever
  actually shows the idea, and give a step at most one of them. The sketch is
  the usual answer; the 3D scene is for when the arrangement in space is
  itself the thing being taught.
- `caption` says what to look at, in under twelve words.
- Real values. A plot with invented numbers is worse than no plot, because it
  will be read as data.
- THE SKETCH IS OF THIS STEP, not of the subject. Its numbers are the numbers
  this step works with, its axis labels are the quantities and units this step
  names, and its series names are the cases this step compares. A generic
  rising curve labelled "time" and "value" on a step about terminal velocity
  is not wrong and is not about that step either, and a reader can tell.
- Then refer to it: name the mark, the crossing point or the taller bar in the
  step's own sentences, so the reader knows which part to look at while
  reading which line. If the step's content has no quantities in it, leave the
  sketch out rather than attaching a decorative one."""
