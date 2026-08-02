"""The lab: the chemistry is right, and it refuses to guess.

Every expected value here was worked out by hand from the balanced equation
and the molar masses. If one of these fails, the arithmetic is wrong — not the
test.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lab as L                                                     # noqa: E402

ok = fail = 0


def check(n, c, d=""):
    global ok, fail
    if c:
        ok += 1
        print(f"  PASS  {n}" + (f"  ({d})" if d else ""))
    else:
        fail += 1
        print(f"  FAIL  {n}" + (f"  ({d})" if d else ""))


def near(a, b, tol=0.02):
    return a is not None and abs(a - b) <= tol * max(1.0, abs(b))


# --------------------------------------------------------------------------
print("IT REFUSES TO INVENT CHEMISTRY")
r = L.react("NaCl", "KI", 10, 10)
check("an unlisted pair is refused, not guessed",
      not r["ok"] and r.get("known") is False)
check("and it says so in words a person can act on",
      "will not guess" in r["error"], r["error"][:60])
check("an unknown reagent is refused",
      not L.react("Unobtainium", "HCl", 1, 1)["ok"])
check("the same thing twice is refused",
      not L.react("HCl", "HCl", 1, 1)["ok"])
check("nothing at all is refused", not L.react("HCl", "NaOH", 0, 0)["ok"])
check("negative amounts are treated as none",
      not L.react("HCl", "NaOH", -5, -5)["ok"])

# --------------------------------------------------------------------------
print("\nSTOICHIOMETRY IS EXACT")
# One mole of each, and the equation is one to one, so both vanish.
r = L.react("HCl", "NaOH", 36.46, 40.00)
check("a 1:1 reaction consumes both exactly",
      r["ok"] and r["left_over"]["HCl"] == 0.0
      and r["left_over"]["NaOH"] == 0.0)
check("and makes one mole of salt", near(r["products"]["NaCl"], 58.44),
      str(r["products"]["NaCl"]))
check("the water is accounted for too", near(r["products"]["H2O"], 18.02))

# 1 mol HCl against 1 mol Na2CO3, but the equation needs 2 HCl per carbonate,
# so the acid runs out at half a mole of reaction.
r = L.react("HCl", "Na2CO3", 36.46, 105.99)
check("the limiting reagent is found from the coefficients, not the mass",
      r["limiting"] == "HCl", str(r["limiting"]))
check("half a mole of reaction runs", near(r["runs_mol"], 0.5))
check("half a mole of CO2 is 12.2 litres", near(r["gas_ml"], 12225, 0.01),
      str(r["gas_ml"]))
check("the carbonate is left over", "Na2CO3" in r["excess"])
check("and the leftover mass is right", near(r["left_over"]["Na2CO3"], 52.995),
      str(r["left_over"]["Na2CO3"]))

# Mg + 2 HCl, given exactly one mole and two moles.
r = L.react("Mg", "HCl", 24.31, 72.92)
check("a 1:2 reaction with exact amounts leaves nothing",
      r["left_over"]["Mg"] == 0.0 and r["left_over"]["HCl"] == 0.0)
check("one mole of hydrogen is 24.45 litres", near(r["gas_ml"], 24450, 0.01))

check("a reaction that makes no gas reports none",
      L.react("AgNO3", "NaCl", 169.87, 58.44)["gas_ml"] == 0.0)
check("a precipitate is named as one",
      L.react("AgNO3", "NaCl", 169.87, 58.44)["kind"] == "precipitate")

print("\nTHE HEAT IS PLAUSIBLE, AND SAYS WHAT IT ASSUMED")
r = L.react("HCl", "NaOH", 36.46, 40.00)
# The number this has to match is the one a school actually measures: equal
# volumes of 1 M hydrochloric acid and 1 M sodium hydroxide rise by just under
# 7 degrees. 57.3 kJ into the two litres of solution being mixed gives 6.9.
check("1 M acid and alkali rise by the measured ~6.9 degrees",
      near(r["temp_rise_c"], 6.9, 0.03), str(r["temp_rise_c"]))
check("a solid brings no solvent with it, so metal in acid runs much hotter",
      L.react("Mg", "HCl", 24.31, 72.92)["temp_rise_c"] > 40)
check("nothing in this lab reports a boiling flask",
      all((L.react(*p, 40, 40).get("temp_rise_c") or 0) < 100
          for p in [sorted(x["pair"]) for x in L.REACTIONS]))
check("the assumption is stated", "1 molar" in r["temp_note"])
check("a reaction with no heat term says nothing about temperature",
      L.react("AgNO3", "NaCl", 10, 10)["temp_rise_c"] is None)

print("\nEVERY REACTION IN THE TABLE IS USABLE")
bad = []
for rx in L.REACTIONS:
    a, b = sorted(rx["pair"])
    out = L.react(a, b, 40, 40)
    if not out["ok"] or not out["products"] or not out["see"] or not out["why"]:
        bad.append(a + "+" + b)
check("all of them run and explain themselves", not bad, str(bad))
check("every symbol used has a molar mass",
      not [s for rx in L.REACTIONS
           for s in list(rx["reactants"]) + list(rx["products"])
           if s not in L.MOLAR])
check("no pair is listed twice",
      len({frozenset(r["pair"]) for r in L.REACTIONS}) == len(L.REACTIONS))
check("the dangerous ones carry a hazard note",
      all(rx["hazard"] for rx in L.REACTIONS
          if rx["kind"] in ("gas",) or "Pb" in str(rx["pair"])
          or "Ag" in str(rx["pair"])),
      str([sorted(r["pair"]) for r in L.REACTIONS
           if not r["hazard"] and r["kind"] == "gas"]))

# --------------------------------------------------------------------------
print("\nTHE PHYSICS MATCHES THE TEXTBOOK")
p = L.projectile(20, 45)
check("range at 45 degrees is v squared over g", near(p["range_m"], 40.77),
      str(p["range_m"]))
check("peak height is right", near(p["peak_m"], 10.19), str(p["peak_m"]))
check("it lands at the speed it left", near(p["impact_ms"], 20.0),
      str(p["impact_ms"]))
check("the path starts and ends on the ground",
      p["path"][0][1] == 0 and abs(p["path"][-1][1]) < 0.05)
check("launching from a height goes further",
      L.projectile(20, 45, 10)["range_m"] > p["range_m"])
check("straight up goes nowhere sideways", near(L.projectile(20, 90)["range_m"], 0))

c = L.circuit([100, 100, 100], 12, True)
check("three 100 ohms in series is 300", near(c["total_r"], 300))
check("and draws 40 milliamps", near(c["current_a"], 0.04))
check("the voltages across them add to the supply",
      near(sum(x["v"] for x in c["per_resistor"]), 12))
c = L.circuit([100, 100, 100], 12, False)
check("three 100 ohms in parallel is 33.3", near(c["total_r"], 33.333))
check("and the currents add up",
      near(sum(x["i"] for x in c["per_resistor"]), c["current_a"]))
check("no resistors is refused", not L.circuit([], 12)["ok"])

pe = L.pendulum(1.0, 10)
check("a one metre pendulum swings in about 2 seconds",
      near(pe["period_small_s"], 2.006), str(pe["period_small_s"]))
check("at 10 degrees the small-angle error is under a percent",
      pe["error_pct"] < 1, str(pe["error_pct"]))
check("at 60 degrees it is around 7 percent",
      near(L.pendulum(1.0, 60)["error_pct"], 7.3, 0.1),
      str(L.pendulum(1.0, 60)["error_pct"]))

ln = L.lens(50, 75)
check("an object at 1.5f images at 3f", near(ln["image_mm"], 150))
check("and is magnified two times, inverted",
      near(ln["magnification"], -2.0) and ln["inverted"] and ln["real"])
ln = L.lens(50, 25)
check("inside the focal length the image is virtual and upright",
      not ln["real"] and not ln["inverted"], str(ln["magnification"]))
check("an object exactly at the focus forms no image",
      L.lens(50, 50)["at_focus"])
check("a zero focal length is refused", not L.lens(0, 100)["ok"])

print(f"\nPASSED {ok}   FAILED {fail}")
sys.exit(1 if fail else 0)
