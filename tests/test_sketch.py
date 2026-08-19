"""The flat drawings: rebuilt from the model's reply, never trusted.

Same rule as the 3D scenes. Every field here is a number or a short label, so
there is nothing to escape — but there is plenty to enforce, and a renderer
that receives a shape it did not expect draws nothing at all.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sketch as K                                                  # noqa: E402

ok = fail = 0


def check(n, c, d=""):
    global ok, fail
    if c:
        ok += 1
        print(f"  PASS  {n}" + (f"  ({d})" if d else ""))
    else:
        fail += 1
        print(f"  FAIL  {n}" + (f"  ({d})" if d else ""))


# --------------------------------------------------------------------------
print("NOTHING UNRECOGNISED SURVIVES")
check("a made-up kind is dropped", K.clean({"kind": "mandala"}) is None)
check("junk instead of an object is dropped", K.clean("nope") is None)
check("no kind at all is dropped", K.clean({}) is None)
# Five, not eight, and not three. Only the kinds with conventions worth
# encoding stay here: an axis, a bar, a dated line, a grid and a share of a
# whole are better purpose-built than composed from primitives every time.
# Everything else is drawn, not named.
#
# The table and the pie joined late because they were missing entirely — a
# lesson whose real shape was a table arrived as prose describing one, which
# is the hardest form to read. They belong on this side rather than in `draw`
# for the same reason the others do: they are DATA, and the geometry is
# arithmetic. A pie composed from arc paths asks a model for angles, and a
# model that gets one wrong draws a confidently wrong pie.
check("only the kinds with real conventions remain",
      set(K.KINDS) == {"plot", "bar", "timeline", "table", "pie"},
      str(K.KINDS))

print("\nPLOTS CARRY DATA, NOT FORMULAS")
p = K.clean({"kind": "plot", "x": "t", "y": "v",
             "series": [{"name": "fall", "points": [[0, 0], [1, 9.8], [2, 19.6]]}],
             "marks": [{"x": 2, "y": 19.6, "label": "after 2 s"}]})
check("a good plot survives", p and len(p["series"][0]["points"]) == 3)
check("marks survive", p["marks"][0]["label"] == "after 2 s")
check("a single point is not a line",
      K.clean({"kind": "plot", "series": [{"points": [[0, 0]]}]}) is None)
check("a plot with no series at all is dropped",
      K.clean({"kind": "plot", "series": []}) is None)
# There is no field that could carry an expression, which is the point.
check("no formula field exists", "fn" not in (p or {}) and "expr" not in (p or {}))
check("NaN coordinates become zero rather than breaking the axes",
      K.clean({"kind": "plot", "series": [{"points": [[float("nan"), 1],
                                                      [1, 2]]}]}
              )["series"][0]["points"][0][0] == 0.0)
check("infinities too",
      K.clean({"kind": "plot", "series": [{"points": [[float("inf"), 1],
                                                      [1, 2]]}]}
              )["series"][0]["points"][0][0] == 0.0)
check("points are capped",
      len(K.clean({"kind": "plot",
                   "series": [{"points": [[i, i] for i in range(500)]}]}
                  )["series"][0]["points"]) == K.MAX_POINTS)
check("series are capped",
      len(K.clean({"kind": "plot",
                   "series": [{"points": [[0, 0], [1, 1]]}] * 9}
                  )["series"]) == K.MAX_SERIES)

print("\nTHE REST OF THE KINDS")
check("a bar chart needs at least two bars",
      K.clean({"kind": "bar", "bars": [{"name": "a", "value": 1}]}) is None)
check("a bar chart with two survives",
      len(K.clean({"kind": "bar", "bars": [{"name": "a", "value": 1},
                                           {"name": "b", "value": 2}]}
                  )["bars"]) == 2)
check("a timeline needs at least two events",
      K.clean({"kind": "timeline", "events": [{"name": "one"}]}) is None)
check("an event with no name is dropped",
      len(K.clean({"kind": "timeline",
                   "events": [{"name": "a"}, {"at": "1900"}, {"name": "b"}]}
                  )["events"]) == 2)

# The five named diagram types are gone. They answered five questions and
# left every other question with no picture at all, which is the whole reason
# most answers arrived as text. Each of them composes from the drawing
# primitives now — a Venn is two ellipses, a free-body diagram is arrows, a
# circuit is symbols on a path — so the validator refuses them here and the
# model is pointed at `draw` instead. Covered in test_draw.py.
for retired in ("tree", "forces", "circuit", "venn", "ray"):
    check(f"{retired} is refused now", K.clean({"kind": retired}) is None)
check("a retired kind cannot sneak through with a full payload",
      K.clean({"kind": "venn", "a": "Mitosis", "b": "Meiosis"}) is None)

print("\nLABELS ARE TEXT AND NOTHING ELSE")
long_name = "x" * 400
check("labels are truncated",
      len(K.clean({"kind": "bar",
                   "bars": [{"name": long_name, "value": 1},
                            {"name": "b", "value": 2}]}
                  )["bars"][0]["name"]) <= 20)
check("control characters are stripped",
      "\x07" not in K.clean({"kind": "bar",
                             "bars": [{"name": "a\x07b", "value": 1},
                                      {"name": "c", "value": 2}]}
                            )["bars"][0]["name"])
check("a hex colour is parsed",
      K.clean({"kind": "bar", "bars": [{"name": "a", "value": 1,
                                        "color": "#ff8800"},
                                       {"name": "b", "value": 2}]}
              )["bars"][0]["color"] == 0xff8800)
check("a nonsense colour is simply absent",
      "color" not in K.clean({"kind": "bar",
                              "bars": [{"name": "a", "value": 1,
                                        "color": "puce"},
                                       {"name": "b", "value": 2}]})["bars"][0])

print("\nA TABLE, WHICH THE BOARD COULD NOT DRAW AT ALL")
# The shape of half of teaching: active against passive, two methods, the
# halogens down a group, reactants and products. There was no way to put one
# on this board, so those lessons arrived as prose describing a table — the
# hardest form to read and the easiest to write.
T = K.clean({"kind": "table", "columns": ["", "Active", "Passive"],
             "rows": [["Subject", "does the action", "receives it"],
                      ["Actor", "named", "can be hidden"]]})
check("a table survives", T is not None)
check("an empty first heading is KEPT, in place",
      T["columns"] == ["", "Active", "Passive"],
      "dropped, every column shifts one left and every value sits under the "
      "wrong heading — and it still looks like a perfectly good table")
check("the rows line up with it", T["rows"][0][0] == "Subject")
check("a short row is padded rather than dropped",
      K.clean({"kind": "table", "columns": ["A", "B", "C"],
               "rows": [["one"]]})["rows"] == [["one", "", ""]],
      "a comparison where one side has no equivalent is the common case, "
      "and the empty cell is itself the answer")
check("a long row is trimmed to the headings",
      len(K.clean({"kind": "table", "columns": ["A", "B"],
                   "rows": [["1", "2", "3", "4"]]})["rows"][0]) == 2)
check("a trailing blank heading goes",
      K.clean({"kind": "table", "columns": ["A", "B", ""],
               "rows": [["1", "2", "3"]]})["columns"] == ["A", "B"])
check("one column is not a table", K.clean(
    {"kind": "table", "columns": ["A"], "rows": [["1"]]}) is None)
check("nor is a table with no headings at all", K.clean(
    {"kind": "table", "columns": ["", ""], "rows": [["1", "2"]]}) is None)
check("nor one with no rows", K.clean(
    {"kind": "table", "columns": ["A", "B"], "rows": []}) is None)
check("columns are capped", len(K.clean(
    {"kind": "table", "columns": [f"c{i}" for i in range(20)],
     "rows": [["x"] * 20]})["columns"]) == K.MAX_COLS)
check("rows are capped", len(K.clean(
    {"kind": "table", "columns": ["A", "B"],
     "rows": [["x", "y"]] * 40})["rows"]) == K.MAX_ROWS)
# Everything else here draws into a fixed 300. Ten rows in 300 is 20 pixels
# each: a spreadsheet printed small, not something readable from the back of
# a classroom.
check("a table asks for a height that fits its rows",
      K.clean({"kind": "table", "columns": ["A", "B"],
               "rows": [["x", "y"]] * 10})["height"] == 346)
check("and it is bounded",
      K.clean({"kind": "table", "columns": ["A", "B"],
               "rows": [["x", "y"]] * 10})["height"] <= 380)

print("\nA PIE, FOR THE ONE THING A BAR CHART DOES NOT SAY")
P = K.clean({"kind": "pie", "unit": "dry air",
             "slices": [{"name": "Nitrogen", "value": 78.09},
                        {"name": "Oxygen", "value": 20.95},
                        {"name": "Argon", "value": 0.93}]})
check("a pie survives", P is not None)
check("it keeps the values, not percentages", P["slices"][0]["value"] == 78.09,
      "asked for both, a model will send values that disagree with its own "
      "percentages, and then the drawing argues with the label on it")
check("the whole it is of is kept", P["unit"] == "dry air")
check("a zero share is refused, not drawn as a hairline",
      len(K.clean({"kind": "pie",
                   "slices": [{"name": "a", "value": 1},
                              {"name": "b", "value": 2},
                              {"name": "c", "value": 0}]})["slices"]) == 2)
check("a negative share is refused",
      len(K.clean({"kind": "pie",
                   "slices": [{"name": "a", "value": 1},
                              {"name": "b", "value": 2},
                              {"name": "c", "value": -5}]})["slices"]) == 2)
check("one slice is not a pie", K.clean(
    {"kind": "pie", "slices": [{"name": "all", "value": 1}]}) is None)
check("an unnamed slice goes", len(K.clean(
    {"kind": "pie", "slices": [{"name": "a", "value": 1},
                               {"name": "b", "value": 1},
                               {"name": "", "value": 1}]})["slices"]) == 2)
check("slices are capped", len(K.clean(
    {"kind": "pie", "slices": [{"name": f"s{i}", "value": 1}
                               for i in range(20)]})["slices"]) == K.MAX_SLICES)

print("\nTHE RENDERER HAS ONE FOR EVERY KIND THE VALIDATOR PASSES")
_JS = open(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "sketch.js"), encoding="utf-8").read()
for k in K.KINDS:
    check(f"sketch.js draws {k}", f"DRAW.{k} = function" in _JS,
          "a kind the server passes and the renderer has never heard of "
          "draws nothing, silently")
check("a share under one per cent says so rather than rounding to 0%",
      'return "<1%"' in _JS,
      "carbon dioxide in a pie of dry air is 0.04 per cent, and it is the "
      "single most interesting number on that chart")
check("a cell too wide for its column is clipped, not wrapped",
      "function clipTo(" in _JS,
      "a wrapped cell changes its row's height, and rows of different "
      "heights are harder to read across than a truncated cell")

print("\nTHE PROMPT MATCHES THE VALIDATOR")
for k in K.KINDS:
    check(f"{k} is offered to the model", f'"{k}"' in K.PROMPT)
check("the table is pushed, since it was missing entirely",
      "USE THIS OFTEN" in K.PROMPT)
check("and the pie says what it is not for",
      "that is \"bar\"" in K.PROMPT,
      "a pie of unrelated quantities is the commonest chart mistake there is")
check("it says to send points, not a formula", "Never send a formula" in K.PROMPT)
check("it says a sketch and a scene are alternatives",
      "alternatives, not a pair" in K.PROMPT)

print(f"\nPASSED {ok}   FAILED {fail}")
sys.exit(1 if fail else 0)
