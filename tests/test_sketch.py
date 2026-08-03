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
# Three, not eight. Only the kinds with conventions worth encoding stay here:
# an axis, a bar and a dated line are better purpose-built than composed from
# primitives every time. Everything else is drawn, not named.
check("only the kinds with real conventions remain",
      set(K.KINDS) == {"plot", "bar", "timeline"}, str(K.KINDS))

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

print("\nTHE PROMPT MATCHES THE VALIDATOR")
for k in K.KINDS:
    check(f"{k} is offered to the model", f'"{k}"' in K.PROMPT)
check("it says to send points, not a formula", "Never send a formula" in K.PROMPT)
check("it says a sketch and a scene are alternatives",
      "alternatives, not a pair" in K.PROMPT)

print(f"\nPASSED {ok}   FAILED {fail}")
sys.exit(1 if fail else 0)
