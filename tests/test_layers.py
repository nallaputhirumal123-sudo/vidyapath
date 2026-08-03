"""Layer stacks, and the ratio that is the whole point of them.

The scene took a thickness per layer from the model on an arbitrary scale, so
a gate oxide and a silicon wafer came out within a factor of two of each
other. They differ by about a quarter of a million: two nanometres against
half a millimetre. That ratio is the entire reason gate oxides are
interesting, and a stack drawn without it teaches that a MOSFET is a sandwich
of comparable slices — the opposite of what makes one work.

The drawn heights are logarithmic and normalised into the range the scene
schema allows, which is worth testing on its own: the schema caps a layer at
3.0 and raw logarithms run to 7.4, so an unnormalised stack would have been
silently flattened to a single height — the exact fault the log scale exists
to prevent.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import layers                                      # noqa: E402
import scene                                       # noqa: E402

PASS = FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {name}" + (f"  ({detail})" if detail else ""))
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


# ---- the figures ------------------------------------------------------
mos = {L["name"]: L["nm"] for L in layers.clean("a MOSFET gate stack")["layers"]}
check("a gate oxide is about 2 nm",
      any("oxide" in k and v == 2 for k, v in mos.items()), str(mos))
check("a wafer is half a millimetre",
      any("substrate" in k and v == 500_000 for k, v in mos.items()))
check("the ratio between them is about 250,000",
      abs(max(mos.values()) / min(mos.values()) - 250_000) < 1,
      f"{max(mos.values()) / min(mos.values()):,.0f}x")

gr = {L["name"]: L["nm"] for L in layers.clean("graphene")["layers"]}
check("graphene is one atom thick", 0.33 < min(gr.values()) < 0.34,
      str(min(gr.values())))
check("on 300 nm of oxide, which is what makes it visible",
      max(gr.values()) == 300)

pcb = {L["name"]: L["nm"] for L in layers.clean("a PCB")["layers"]}
check("an FR-4 board is 1.6 mm", 1_600_000 in pcb.values())
check("and its copper is 35 µm", 35_000 in pcb.values())

# ---- the scaling ------------------------------------------------------
for topic in ("mosfet", "pn junction", "solar cell", "led", "capacitor",
              "pcb", "graphene", "thin film"):
    g = layers.clean(topic)
    ts = [L["t"] for L in g["layers"]]
    check(f"{topic}: drawn heights fit the schema",
          all(0.08 <= t <= 3.0 for t in ts), f"{min(ts):.2f}..{max(ts):.2f}")
    check(f"{topic}: thicker layers are drawn thicker",
          [t for _, t in sorted(zip([L["nm"] for L in g["layers"]], ts))]
          == sorted(ts))
    check(f"{topic}: every layer states its real thickness",
          all(L.get("real") for L in g["layers"]))

# The flattening this replaces: a 250,000x range must not become one height.
mts = [L["t"] for L in layers.clean("mosfet")["layers"]]
check("a huge real range still spreads on screen",
      max(mts) / min(mts) > 3, f"{max(mts) / min(mts):.1f}x drawn")

# ---- through the schema ----------------------------------------------
g = layers.clean("a MOSFET gate stack")
sc = scene.clean(dict({"kind": "layers", "caption": "MOSFET"}, **g))
check("the schema keeps the measured flag", sc.get("measured") is True)
check("and the scale note", bool(sc.get("scale_note")), sc.get("scale_note"))
check("and the real thickness on every layer",
      all(L.get("real") for L in sc["layers"]),
      str([L.get("real") for L in sc["layers"]]))
check("a stack the model wrote is not marked measured",
      scene.clean({"kind": "layers", "caption": "x",
                   "layers": [{"name": "a", "t": 1}, {"name": "b", "t": 1}]}
                  ).get("measured") is None)

# ---- naming -----------------------------------------------------------
for phrase, expect in (("a MOSFET gate stack", 5), ("the pn junction", 3),
                       ("a solar cell", 5), ("an LED", 5),
                       ("printed circuit board", 4), ("graphene", 2)):
    g = layers.clean(phrase)
    check(f"{phrase!r} finds its stack", g and len(g["layers"]) == expect,
          str(len(g["layers"]) if g else None))

for absent in ("photosynthesis", "the Krebs cycle", "", None, "   "):
    check(f"{str(absent)[:20]!r} is not a listed stack",
          layers.clean(absent) == {})

check("thicknesses are written the way people say them",
      (layers.human(2), layers.human(500), layers.human(35_000),
       layers.human(1_600_000)) == ("2 nm", "500 nm", "35 µm", "1.6 mm"),
      str((layers.human(2), layers.human(35_000), layers.human(1_600_000))))

print(f"\nPASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
