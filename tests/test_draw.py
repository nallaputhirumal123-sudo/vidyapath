"""The drawing vocabulary: composed pictures, rebuilt from the model's reply.

This replaced eight named diagram types. The point of the change is reach — a
question that is not a plot, a tree or a Venn used to get no picture at all —
so these checks are as much about what it can express as about what it
refuses.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import draw as D                                                    # noqa: E402
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


def one(**kw):
    """A drawing with a single element, for testing that element."""
    return D.clean({"elements": [kw]})


# --------------------------------------------------------------------------
print("IT DRAWS WHAT IT SAYS IT DRAWS")
cell = D.clean({"caption": "An animal cell", "elements": [
    {"id": "membrane", "type": "ellipse", "cx": 500, "cy": 300,
     "rx": 400, "ry": 235, "stroke": "chalk"},
    {"id": "nucleus", "type": "circle", "cx": 420, "cy": 285, "r": 95,
     "stroke": "amber", "fill": "amber", "opacity": 0.2},
    {"id": "nlbl", "type": "label", "x": 420, "y": 290, "text": "Nucleus"},
    {"id": "er", "type": "path", "d": "M620 200 q45 28 0 56 q-45 28 0 56"},
    {"id": "ptr", "type": "arrow", "x1": 880, "y1": 150, "x2": 690, "y2": 205,
     "label": "Endoplasmic reticulum"}],
    "animations": [{"target": "er", "type": "draw", "duration": 1400}]})
check("a composed drawing survives whole", len(cell["elements"]) == 5)
check("its ids are collected for reveal checking",
      cell["ids"] == ["er", "membrane", "nlbl", "nucleus", "ptr"],
      str(cell["ids"]))
check("the animation is kept", len(cell["animations"]) == 1)
check("the caption comes through", cell["caption"] == "An animal cell")

for t, kw in (("circle", {"cx": 1, "cy": 2, "r": 3}),
              ("ellipse", {"cx": 1, "cy": 2, "rx": 3, "ry": 4}),
              ("rect", {"x": 1, "y": 2, "w": 3, "h": 4}),
              ("line", {"x1": 0, "y1": 0, "x2": 9, "y2": 9}),
              ("arrow", {"x1": 0, "y1": 0, "x2": 9, "y2": 9}),
              ("path", {"d": "M0 0 L10 10"}),
              ("polygon", {"points": [[0, 0], [5, 0], [5, 5]]}),
              ("label", {"x": 1, "y": 2, "text": "hi"}),
              ("symbol", {"name": "resistor", "x": 1, "y": 2})):
    got = one(id="e1", type=t, **kw)
    check(f"{t} is drawable", got is not None and got["elements"][0]["type"] == t)

check("every advertised type is implemented",
      set(D.TYPES) == {"circle", "ellipse", "rect", "line", "path", "polygon",
                       "arrow", "label", "symbol"})
check("there are enough symbols to be useful", len(D.SYMBOLS) >= 30,
      str(len(D.SYMBOLS)))
check("the symbol groups people actually need are present",
      all(x in D.SYMBOLS for x in ("resistor", "and_gate", "spring", "beaker",
                                   "condenser", "transistor", "pulley")))

# --------------------------------------------------------------------------
print("\nNOTHING UNRECOGNISED SURVIVES")
check("an invented element type is dropped",
      one(id="a", type="hologram") is None)
check("an invented symbol is dropped",
      one(id="a", type="symbol", name="flux_capacitor", x=1, y=1) is None)
check("an element with no id is dropped", one(type="circle", r=5) is None)
check("a drawing with nothing usable is None",
      D.clean({"elements": [{"type": "nope"}]}) is None)
check("junk instead of an object is None", D.clean("nope") is None)

# The path is the one field that carries a string of syntax, so it gets the
# strictest treatment: rejected outright rather than stripped, because a path
# with characters removed is a different shape drawn confidently.
for bad in ("M0 0 L10 10; alert(1)", "javascript:alert(1)",
            "M0 0 <script>", "M0 0 L10 10 /*x*/"):
    check(f"path rejected: {bad[:26]}",
          one(id="p", type="path", d=bad) is None)
check("a real path is accepted",
      one(id="p", type="path", d="M10 10 C 20 20, 40 20, 50 10 Z") is not None)

check("a duplicate id is dropped, not overwritten",
      len(D.clean({"elements": [
          {"id": "a", "type": "circle", "cx": 1, "cy": 1, "r": 1},
          {"id": "a", "type": "circle", "cx": 9, "cy": 9, "r": 9}]}
      )["elements"]) == 1)
check("an id is stripped to safe characters",
      one(id="a b<script>", type="circle", cx=1, cy=1, r=1
          )["elements"][0]["id"] == "abscript")
check("a colour outside the palette falls back",
      one(id="a", type="circle", cx=1, cy=1, r=1, stroke="#deadbeef"
          )["elements"][0]["stroke"] == D.INK["chalk"])
check("fill may be none", one(id="a", type="circle", cx=1, cy=1, r=1,
                              fill="none")["elements"][0]["fill"] == "none")
check("a polygon needs three points",
      one(id="a", type="polygon", points=[[0, 0], [1, 1]]) is None)
check("a label with no text is dropped",
      one(id="a", type="label", x=1, y=1, text="") is None)
check("elements are capped",
      len(D.clean({"elements": [
          {"id": f"e{i}", "type": "circle", "cx": 1, "cy": 1, "r": 1}
          for i in range(200)]})["elements"]) == D.MAX_ELEMENTS)
check("NaN coordinates become a default, not a crash",
      one(id="a", type="circle", cx=float("nan"), cy=1, r=1
          )["elements"][0]["cx"] == 500)

print("\nANIMATIONS POINT AT SOMETHING REAL")
d = D.clean({"elements": [{"id": "a", "type": "circle", "cx": 1, "cy": 1,
                           "r": 1}],
             "animations": [{"target": "a", "type": "draw"},
                            {"target": "ghost", "type": "draw"},
                            {"target": "a", "type": "explode"}]})
check("an animation on a missing element is dropped",
      len(d["animations"]) == 1 and d["animations"][0]["target"] == "a",
      str(d["animations"]))
check("an invented animation type is dropped",
      all(a["type"] in D.ANIMS for a in d["animations"]))
check("durations are clamped",
      D.clean({"elements": [{"id": "a", "type": "circle", "cx": 1, "cy": 1,
                             "r": 1}],
               "animations": [{"target": "a", "type": "fade",
                               "duration": 999999}]}
              )["animations"][0]["duration"] == 6000)

print("\nNARRATION CANNOT REVEAL WHAT IS NOT THERE")
check("a missing reveal id is reported",
      D.check_reveals(cell, [{"reveal": ["nucleus", "ghost"]}]) == ["ghost"])
check("ids that exist are not reported",
      D.check_reveals(cell, [{"reveal": ["nucleus", "er"]}]) == [])
check("no drawing means nothing to report",
      D.check_reveals(None, [{"reveal": ["anything"]}]) == [])

print("\nTHE NAMED DIAGRAM TYPES ARE GONE")
# This is the change itself: five named types that only answered five
# questions, replaced by a vocabulary that composes any of them.
check("only the three chart kinds remain",
      K.KINDS == ("plot", "bar", "timeline"), str(K.KINDS))
for gone in ("tree", "forces", "circuit", "venn", "ray"):
    check(f"{gone} is no longer a named kind", gone not in K.KINDS)
    check(f"and is not offered in the prompt", f'"{gone}"' not in K.PROMPT)
check("the chart prompt points elsewhere for everything else",
      "compose with `draw`" in K.PROMPT)
check("the drawing prompt offers the symbol library",
      "and_gate" in D.PROMPT and "condenser" in D.PROMPT)
check("and names the coordinate space",
      "1000 wide by 600 tall" in D.PROMPT)
check("and warns against wrong labels",
      "destroys trust" in D.PROMPT)

print(f"\nPASSED {ok}   FAILED {fail}")
sys.exit(1 if fail else 0)
