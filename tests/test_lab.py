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

# --------------------------------------------------------------------------
print("\nTHE NEW BENCHES, AGAINST HAND-WORKED VALUES")
# Every expected number here was computed on paper first.
sp = L.spring(200, 0.5, 0.1)
check("F = kx", near(sp["force_n"], 20), str(sp["force_n"]))
check("E = half k x squared", near(sp["energy_j"], 1.0))
check("T = 2pi root(m/k) = 0.314 s", near(sp["period_s"], 0.31416),
      str(sp["period_s"]))
check("the period does not depend on the pull",
      L.spring(200, 0.5, 0.4)["period_s"] == sp["period_s"])
check("four times the mass doubles the period",
      near(L.spring(200, 2.0, 0.1)["period_s"], sp["period_s"] * 2))

c = L.collision(2, 3, 1, 0, True)
check("elastic: 2kg at 3 into 1kg gives 1 and 4",
      near(c["v1"], 1) and near(c["v2"], 4), f"{c['v1']}, {c['v2']}")
check("momentum is conserved", near(c["p_before"], c["p_after"]))
check("elastic keeps all the kinetic energy",
      near(c["ke_before"], c["ke_after"]) and near(c["ke_lost_j"], 0))
ci = L.collision(2, 3, 1, 0, False)
check("inelastic: they leave together at 2", near(ci["v1"], 2)
      and near(ci["v2"], 2))
check("and momentum still holds", near(ci["p_before"], ci["p_after"]))
check("but 3 J of kinetic energy is gone", near(ci["ke_lost_j"], 3),
      str(ci["ke_lost_j"]))
check("equal masses in an elastic head-on swap speeds",
      near(L.collision(1, 5, 1, 0, True)["v2"], 5))

g = L.gas(101.325, 22.414, 273.15)
check("a mole of gas at STP", near(g["moles"], 1.0, 0.005), str(g["moles"]))
g2 = L.gas(100, 1, 300, p2=200, t2=300)
check("Boyle: double the pressure, halve the volume",
      near(g2["v2_l"], 0.5), str(g2["v2_l"]))
g3 = L.gas(100, 1, 300, p2=100, t2=600)
check("Charles: double the temperature, double the volume",
      near(g3["v2_l"], 2.0), str(g3["v2_l"]))
check("it says which one it solved for", g3["solved"] == "volume")

cal = L.calorimetry(0.1, 80, 0.1, 20)
check("equal masses settle halfway", near(cal["final_c"], 50))
check("twice as much cold water pulls it lower",
      near(L.calorimetry(0.1, 80, 0.2, 20)["final_c"], 40),
      str(L.calorimetry(0.1, 80, 0.2, 20)["final_c"]))
check("the heat moved is m c dT", near(cal["heat_moved_j"], 0.1 * 4186 * 30),
      str(cal["heat_moved_j"]))

w = L.wave(170, speed=340)
check("v = f lambda", near(w["wavelength_m"], 2.0))
ws = L.wave(50, speed=100, length=1)
check("a 1 m string at 100 m/s has a 50 Hz fundamental",
      near(ws["fundamental_hz"], 50), str(ws["fundamental_hz"]))
check("harmonics are whole multiples",
      ws["harmonics_hz"][:3] == [50.0, 100.0, 150.0],
      str(ws["harmonics_hz"][:3]))

p = L.punnett("Aa", "Aa")
check("Aa x Aa is 1:2:1",
      p["genotypes"] == {"AA": 1, "Aa": 2, "aa": 1}, str(p["genotypes"]))
check("and 3:1 by phenotype",
      p["phenotype_ratio"] == "3 dominant : 1 recessive")
check("Aa x aa is 2:2",
      L.punnett("Aa", "aa")["phenotype_ratio"] == "2 dominant : 2 recessive")
check("AA x aa is all dominant",
      L.punnett("AA", "aa")["phenotype_ratio"] == "4 dominant : 0 recessive")
check("aa x aa is none",
      L.punnett("aa", "aa")["phenotype_ratio"] == "0 dominant : 4 recessive")
check("two different genes are refused", not L.punnett("Aa", "Bb")["ok"])
check("a malformed genotype is refused", not L.punnett("A", "aa")["ok"])

pop = L.population(100, 0.1, 3)
check("unchecked growth compounds",
      pop["exponential"] == [100.0, 110.0, 121.0, 133.1],
      str(pop["exponential"]))
check("the doubling time is right", near(pop["doubling_time"], 7.2725),
      str(pop["doubling_time"]))
cap = L.population(100, 0.5, 40, capacity=1000)
check("logistic growth stops at the ceiling",
      cap["logistic"][-1] <= cap["capacity"] + 1,
      f"{cap['logistic'][-1]} vs {cap['capacity']}")
check("and gets close to it", cap["logistic"][-1] > 900,
      str(cap["logistic"][-1]))
check("unchecked growth blows past it",
      cap["exponential"][-1] > cap["capacity"] * 100)

check("0.01 M strong acid is pH 2", near(L.ph(0.01)["ph"], 2))
check("0.01 M strong base is pH 12", near(L.ph(0.01, "base")["ph"], 12))
check("pH and pOH add to 14",
      near(L.ph(0.001)["ph"] + L.ph(0.001)["poh"], 14))
check("a tenfold dilution moves pH by one",
      near(L.ph(0.001)["ph"] - L.ph(0.01)["ph"], 1))
check("zero concentration is refused", not L.ph(0)["ok"])
check("the verdict matches the number",
      L.ph(0.1)["verdict"] == "strongly acidic"
      and L.ph(1e-7)["verdict"] == "about neutral",
      L.ph(1e-7)["verdict"])

print("\nEVERY BENCH IS REACHABLE")
ids = [e["id"] for e in L.EXPERIMENTS]
check("ids are unique", len(set(ids)) == len(ids))
check("there are more than five now", len(ids) >= 13, str(len(ids)))
check("each one says what it is for",
      all(e.get("ask") and e.get("name") and e.get("subject")
          for e in L.EXPERIMENTS))
check("the open bench is last",
      ids[-1] == "any", ids[-1])
check("more than one subject is covered",
      len({e["subject"] for e in L.EXPERIMENTS}) >= 4,
      str(sorted({e["subject"] for e in L.EXPERIMENTS})))

print(f"\nPASSED {ok}   FAILED {fail}")
sys.exit(1 if fail else 0)
