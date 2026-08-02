"""The practice lab: mix things, and find out what actually happens.

The tempting way to build this is to ask a model what happens when you mix
two reagents. That is the one thing that must not be done here. A language
model will produce a confident, fluent, wrong reaction — and a wrong reaction
is not a wrong answer like a wrong date is a wrong answer. Somebody reads
"mixing bleach and ammonia gives you a harmless salt" and goes and does it.

So the chemistry in this file is a table. Fourteen reactions, each with its
real balanced equation, real molar masses, real observations and its real
hazard. The stoichiometry is arithmetic on that table: which reagent runs out
first, how much product that leaves, what you would actually see. It is exact,
it is free, and it cannot invent a reaction that does not exist — if a pair is
not in the table, the honest answer is "this one is not simulated", not a
plausible sentence.

The physics is closed-form for the same reason. A projectile's range is not a
matter of opinion.

Everything here is deterministic: no model call, no token, no per-student cost,
and the same inputs give the same answer to everyone forever.
"""
import math

# --------------------------------------------------------------------------
# Chemistry
# --------------------------------------------------------------------------
# g/mol, to two decimals. Used for the limiting-reagent arithmetic, so these
# have to be right rather than approximately right.
MOLAR = {
    "HCl": 36.46, "NaOH": 40.00, "NaCl": 58.44, "H2O": 18.02,
    "Na2CO3": 105.99, "CO2": 44.01, "NaHCO3": 84.01,
    "AgNO3": 169.87, "AgCl": 143.32, "NaNO3": 84.99,
    "BaCl2": 208.23, "Na2SO4": 142.04, "BaSO4": 233.39,
    "Pb(NO3)2": 331.21, "KI": 166.00, "PbI2": 461.01, "KNO3": 101.10,
    "CuSO4": 159.61, "Cu(OH)2": 97.56, "Cu": 63.55,
    "Mg": 24.31, "MgCl2": 95.21, "H2": 2.02,
    "Zn": 65.38, "ZnSO4": 161.44,
    "Fe": 55.85, "FeSO4": 151.91,
    "H2SO4": 98.08, "CaCO3": 100.09, "CaCl2": 110.98,
    "KMnO4": 158.03, "MnSO4": 151.00, "K2SO4": 174.26, "O2": 32.00,
    "H2O2": 34.01,
}

REAGENTS = [
    ("HCl", "Hydrochloric acid", "acid"),
    ("H2SO4", "Sulfuric acid", "acid"),
    ("NaOH", "Sodium hydroxide", "base"),
    ("Na2CO3", "Sodium carbonate", "salt"),
    ("NaHCO3", "Sodium bicarbonate", "salt"),
    ("AgNO3", "Silver nitrate", "salt"),
    ("NaCl", "Sodium chloride", "salt"),
    ("BaCl2", "Barium chloride", "salt"),
    ("Na2SO4", "Sodium sulfate", "salt"),
    ("Pb(NO3)2", "Lead(II) nitrate", "salt"),
    ("KI", "Potassium iodide", "salt"),
    ("CuSO4", "Copper(II) sulfate", "salt"),
    ("CaCO3", "Calcium carbonate", "solid"),
    ("Mg", "Magnesium ribbon", "metal"),
    ("Zn", "Zinc", "metal"),
    ("Fe", "Iron filings", "metal"),
    ("H2O2", "Hydrogen peroxide", "other"),
]
REAGENT_NAME = {k: n for k, n, _ in REAGENTS}
# Solids and metals bring no solvent with them, which matters for the
# temperature arithmetic: a magnesium ribbon does not arrive dissolved in a
# litre of water the way the acid does.
SOLIDS = {k: (t in ("metal", "solid")) for k, _, t in REAGENTS}


def _r(a, b, eq, reactants, products, see, kind, heat=0.0, hazard="",
       why=""):
    return {"pair": frozenset((a, b)), "eq": eq, "reactants": reactants,
            "products": products, "see": see, "kind": kind, "heat": heat,
            "hazard": hazard, "why": why}


# heat is kJ per mole of reaction as written, negative meaning it warms up.
REACTIONS = [
    _r("HCl", "NaOH",
       "HCl + NaOH -> NaCl + H2O",
       {"HCl": 1, "NaOH": 1}, {"NaCl": 1, "H2O": 1},
       "Nothing to see — no colour, no gas, no solid. The flask gets warm.",
       "neutralisation", -57.3,
       "Both are corrosive. The mixture spits if the acid goes in fast.",
       "The H+ from the acid and the OH- from the base become water. That is "
       "all neutralisation ever is, and it releases the same 57 kJ per mole "
       "whichever strong acid and strong base you pick — which is itself the "
       "evidence that the spectator ions are doing nothing."),

    _r("H2SO4", "NaOH",
       "H2SO4 + 2 NaOH -> Na2SO4 + 2 H2O",
       {"H2SO4": 1, "NaOH": 2}, {"Na2SO4": 1, "H2O": 2},
       "Clear throughout, and noticeably hot.",
       "neutralisation", -114.6,
       "Sulfuric acid is severely corrosive. Always acid into water.",
       "Two OH- are needed per H2SO4 because it has two protons to give. Read "
       "the equation before you read the bottle: half as much acid "
       "neutralises the same amount of base."),

    _r("HCl", "Na2CO3",
       "2 HCl + Na2CO3 -> 2 NaCl + H2O + CO2",
       {"HCl": 2, "Na2CO3": 1}, {"NaCl": 2, "H2O": 1, "CO2": 1},
       "Vigorous fizzing. The gas puts out a lit splint and turns limewater "
       "milky.",
       "gas", -26.0,
       "CO2 displaces air in a closed space. Keep it open.",
       "Carbonate plus any acid gives carbon dioxide. This is the standard "
       "test for a carbonate, and it is why vinegar fizzes on limescale."),

    _r("HCl", "NaHCO3",
       "HCl + NaHCO3 -> NaCl + H2O + CO2",
       {"HCl": 1, "NaHCO3": 1}, {"NaCl": 1, "H2O": 1, "CO2": 1},
       "Brisk fizzing that dies away as the solid disappears.",
       "gas", -28.0,
       "Never in a stoppered container — the carbon dioxide has to go "
       "somewhere, and a sealed tube becomes a pressure vessel.",
       "One-to-one here, not two-to-one, because bicarbonate already carries "
       "one hydrogen. Same gas, half the acid."),

    _r("HCl", "CaCO3",
       "2 HCl + CaCO3 -> CaCl2 + H2O + CO2",
       {"HCl": 2, "CaCO3": 1}, {"CaCl2": 1, "H2O": 1, "CO2": 1},
       "The chip fizzes and slowly shrinks; the solution stays clear.",
       "gas", -15.0,
       "Open vessel only. Carbon dioxide builds pressure if it is stoppered, "
       "and it pools in the bottom of an unventilated space.",
       "This is limestone dissolving in acid rain, and it is why caves and "
       "sinkholes exist. The same reaction, over ten thousand years."),

    _r("AgNO3", "NaCl",
       "AgNO3 + NaCl -> AgCl + NaNO3",
       {"AgNO3": 1, "NaCl": 1}, {"AgCl": 1, "NaNO3": 1},
       "A dense white precipitate forms at once. It darkens in daylight.",
       "precipitate", 0.0,
       "Silver nitrate stains skin black. It takes days to wear off.",
       "Silver chloride is insoluble, so it drops out the moment the ions "
       "meet. This is the chloride test, and the darkening in light is the "
       "same silver chemistry that photographic film ran on."),

    _r("BaCl2", "Na2SO4",
       "BaCl2 + Na2SO4 -> BaSO4 + 2 NaCl",
       {"BaCl2": 1, "Na2SO4": 1}, {"BaSO4": 1, "NaCl": 2},
       "A fine white precipitate, so insoluble it will not redissolve in "
       "acid.",
       "precipitate", 0.0,
       "Soluble barium salts are toxic. Barium sulfate is not, which is the "
       "whole point below.",
       "The test for sulfate. Barium sulfate is so insoluble that patients "
       "drink it before an X-ray: the barium never dissolves, so it never "
       "reaches the blood."),

    _r("Pb(NO3)2", "KI",
       "Pb(NO3)2 + 2 KI -> PbI2 + 2 KNO3",
       "",
       {"PbI2": 1, "KNO3": 2},
       "A brilliant yellow precipitate — the 'golden rain' demonstration.",
       "precipitate", 0.0,
       "Lead compounds are cumulative poisons. Not for skin contact.",
       "Lead iodide is insoluble cold and soluble hot, so cooling it slowly "
       "grows visible gold plates. The colour is the reaction: nothing else "
       "in the flask is yellow."),

    _r("CuSO4", "NaOH",
       "CuSO4 + 2 NaOH -> Cu(OH)2 + Na2SO4",
       {"CuSO4": 1, "NaOH": 2}, {"Cu(OH)2": 1, "Na2SO4": 1},
       "The blue solution throws down a pale blue gelatinous solid.",
       "precipitate", 0.0, "",
       "Copper hydroxide is insoluble, so the blue leaves the solution and "
       "becomes a solid. Heat it and it turns black — that is copper oxide, "
       "and the water leaving."),

    _r("Mg", "HCl",
       "Mg + 2 HCl -> MgCl2 + H2",
       {"Mg": 1, "HCl": 2}, {"MgCl2": 1, "H2": 1},
       "Rapid fizzing, the ribbon disappears, and the tube gets hot. The gas "
       "pops with a lit splint.",
       "gas", -462.0,
       "Hydrogen is explosive in air. Small quantities only, no flames "
       "nearby.",
       "A metal above hydrogen in the reactivity series displaces it from "
       "acid. The squeaky pop is that hydrogen burning back to water."),

    _r("Zn", "HCl",
       "Zn + 2 HCl -> ZnCl2 + H2",
       {"Zn": 1, "HCl": 2}, {"H2": 1},
       "Steady fizzing, slower than magnesium.",
       "gas", -153.9, "Hydrogen is flammable.",
       "Slower than magnesium because zinc sits lower in the reactivity "
       "series. The order of that series is exactly the order of these "
       "fizzing rates, which is how it was worked out."),

    _r("Zn", "CuSO4",
       "Zn + CuSO4 -> ZnSO4 + Cu",
       {"Zn": 1, "CuSO4": 1}, {"ZnSO4": 1, "Cu": 1},
       "The blue fades to colourless and a red-brown coating of copper forms "
       "on the zinc. The tube warms up.",
       "displacement", -217.0, "",
       "Zinc is more reactive, so it takes the sulfate and pushes copper out "
       "as metal. Run this same reaction with the two metals separated by a "
       "wire and you have a battery — that is precisely what a cell is."),

    _r("Fe", "CuSO4",
       "Fe + CuSO4 -> FeSO4 + Cu",
       {"Fe": 1, "CuSO4": 1}, {"FeSO4": 1, "Cu": 1},
       "The nail goes copper-coloured and the blue slowly pales.",
       "displacement", -149.0, "",
       "Same displacement, less enthusiastically, because iron is only just "
       "above copper. This is why an iron pipe joined to a copper one "
       "corrodes at the joint."),

    _r("H2O2", "KI",
       "2 H2O2 -> 2 H2O + O2  (KI catalyses)",
       {"H2O2": 2}, {"H2O": 2, "O2": 1},
       "Immediate foaming as oxygen is released. The iodide is unchanged at "
       "the end.",
       "catalysis", -196.0,
       "Concentrated peroxide burns skin. The foam is hot.",
       "The iodide is a catalyst: it speeds the peroxide's decomposition and "
       "comes out untouched, which is why it does not appear in the "
       "equation. Put washing-up liquid in and you get elephant's toothpaste."),
]

# Pb(NO3)2 + KI needs its reactant coefficients like everything else; declared
# here rather than inline so the table above stays readable.
for _x in REACTIONS:
    if _x["reactants"] == "":
        _x["reactants"] = {"Pb(NO3)2": 1, "KI": 2}

BY_PAIR = {r["pair"]: r for r in REACTIONS}


def react(a, b, grams_a, grams_b):
    """Mix two reagents and work out exactly what comes back.

    Returns the limiting reagent, what is left over, how much of each product
    forms, and what you would see. All of it arithmetic on the balanced
    equation — no judgement, no estimate.
    """
    a, b = (a or "").strip(), (b or "").strip()
    if a not in MOLAR or b not in MOLAR:
        return {"ok": False, "error": "Pick two reagents from the shelf."}
    if a == b:
        return {"ok": False, "error": "That is the same thing twice."}
    rxn = BY_PAIR.get(frozenset((a, b)))
    if not rxn:
        # The honest answer. Inventing one here is the failure mode this whole
        # file exists to avoid.
        return {"ok": False, "known": False,
                "error": f"{REAGENT_NAME.get(a, a)} and "
                         f"{REAGENT_NAME.get(b, b)} are not a pair this lab "
                         f"simulates. That does not mean nothing happens — it "
                         f"means this lab will not guess. Ask the board about "
                         f"it instead."}

    amounts = {a: max(0.0, float(grams_a or 0)),
               b: max(0.0, float(grams_b or 0))}
    if sum(amounts.values()) <= 0:
        return {"ok": False, "error": "Add some of each first."}

    # Moles available, and how many times the equation as written can run.
    runs = None
    limiting = None
    for sym, coeff in rxn["reactants"].items():
        moles = amounts.get(sym, 0.0) / MOLAR[sym]
        possible = moles / coeff
        if runs is None or possible < runs:
            runs = possible
            limiting = sym
    runs = max(0.0, runs or 0.0)

    used = {s: runs * c * MOLAR[s] for s, c in rxn["reactants"].items()}
    left = {s: round(max(0.0, amounts.get(s, 0.0) - used[s]), 3)
            for s in rxn["reactants"]}
    made = {s: round(runs * c * MOLAR[s], 3)
            for s, c in rxn["products"].items()}

    # Gases are more useful as a volume you could see collected.
    gas_ml = 0.0
    for g in ("CO2", "H2", "O2"):
        if g in rxn["products"]:
            gas_ml = runs * rxn["products"][g] * 24450  # 24.45 L/mol at 25C

    warmed = None
    solvent_g = 0.0
    if rxn["heat"]:
        # Every dissolved reactant arrives as its own 1 molar solution, and
        # they get poured together — so the water is a litre per mole of each
        # aqueous reactant, and a solid brings none with it.
        #
        # Two earlier versions of this were wrong in the same direction. A
        # flat 100 g reported 137 degrees for one mole of neutralisation, and
        # scaling with the reaction count instead of the reagents reported
        # 110 for magnesium in acid. Both were arithmetically correct on their
        # own assumption and both described a flask boiling dry. Counting the
        # solutions actually being mixed gives 6.9 degrees for equal volumes
        # of 1 M acid and alkali, which is what the experiment measures.
        for sym, coeff in rxn["reactants"].items():
            if SOLIDS.get(sym):
                continue
            solvent_g += runs * coeff * 1000.0
        solvent_g = max(100.0, solvent_g)
        joules = -rxn["heat"] * 1000 * runs
        warmed = round(joules / (solvent_g * 4.18), 1)

    return {
        "ok": True, "known": True,
        "equation": rxn["eq"],
        "kind": rxn["kind"],
        "limiting": limiting,
        "limiting_name": REAGENT_NAME.get(limiting, limiting),
        "runs_mol": round(runs, 5),
        "used": {s: round(v, 3) for s, v in used.items()},
        "left_over": left,
        "products": made,
        "gas_ml": round(gas_ml, 1),
        "temp_rise_c": warmed,
        "temp_note": (f"assuming about {int(solvent_g)} g of water — roughly "
                      f"1 molar solution" if warmed else ""),
        "see": rxn["see"],
        "why": rxn["why"],
        "hazard": rxn["hazard"],
        "excess": [s for s, v in left.items() if v > 0.001],
    }


# --------------------------------------------------------------------------
# Physics
# --------------------------------------------------------------------------
G = 9.81


def projectile(speed, angle_deg, height=0.0):
    """Where it lands, how high it gets, how long it is in the air."""
    v = max(0.0, min(500.0, float(speed or 0)))
    th = math.radians(max(0.0, min(90.0, float(angle_deg or 0))))
    h = max(0.0, min(500.0, float(height or 0)))
    vx, vy = v * math.cos(th), v * math.sin(th)
    # Time to fall back to y = 0 from height h.
    t = (vy + math.sqrt(max(0.0, vy * vy + 2 * G * h))) / G if G else 0.0
    return {"ok": True,
            "range_m": round(vx * t, 2),
            "peak_m": round(h + (vy * vy) / (2 * G), 2),
            "flight_s": round(t, 2),
            # vy - G*t, not vy + G*t. Gravity is taking velocity away on the
            # way up and giving it back on the way down; adding it made a
            # projectile land at three times the speed it left, which the
            # symmetry of the path says plainly cannot be right.
            "impact_ms": round(math.hypot(vx, abs(vy - G * t)), 2),
            "path": [[round(vx * (t * i / 24), 2),
                      round(h + vy * (t * i / 24)
                            - 0.5 * G * (t * i / 24) ** 2, 2)]
                     for i in range(25)],
            "why": ("Range peaks at 45 degrees when you launch and land at "
                    "the same height, because range goes as sin(2θ) and that "
                    "is largest at 90 degrees. Launch from a height and the "
                    "best angle drops below 45 — the extra fall time rewards "
                    "a flatter, faster shot.")}


def circuit(resistances, volts, series=True):
    """Ohm's law across a series or parallel set."""
    rs = [max(0.01, min(1e6, float(r))) for r in (resistances or [])][:6]
    v = max(0.0, min(1000.0, float(volts or 0)))
    if not rs:
        return {"ok": False, "error": "Add at least one resistor."}
    if series:
        total = sum(rs)
    else:
        total = 1.0 / sum(1.0 / r for r in rs)
    i = v / total if total else 0.0
    per = [{"r": round(r, 2),
            "v": round(i * r if series else v, 3),
            "i": round(i if series else v / r, 4),
            "w": round((i * i * r) if series else (v * v / r), 3)}
           for r in rs]
    return {"ok": True, "total_r": round(total, 3), "current_a": round(i, 4),
            "power_w": round(v * i, 3), "per_resistor": per,
            "why": ("In series the current is the same everywhere and the "
                    "voltages add up. In parallel the voltage is the same "
                    "across each and the currents add up — which is why "
                    "adding a parallel resistor lowers the total resistance "
                    "and draws more current, and why overloading a ring "
                    "circuit trips the breaker.")}


def pendulum(length_m, angle_deg=10.0):
    """Period of a simple pendulum, and where the small-angle rule breaks."""
    L = max(0.01, min(100.0, float(length_m or 0)))
    a = max(0.1, min(90.0, float(angle_deg or 10)))
    t0 = 2 * math.pi * math.sqrt(L / G)
    th = math.radians(a)
    # First two terms of the exact series — enough to show the divergence.
    t = t0 * (1 + (th ** 2) / 16 + (11 * th ** 4) / 3072)
    return {"ok": True,
            "period_small_s": round(t0, 3),
            "period_real_s": round(t, 3),
            "error_pct": round((t - t0) / t0 * 100, 2),
            "why": ("The textbook formula assumes the swing is small. At 10 "
                    "degrees it is out by under a tenth of a percent, which "
                    "is why nobody mentions it; at 60 degrees it is out by "
                    "about 7 percent, which would ruin a clock. The mass does "
                    "not appear at all — a heavy bob and a light one keep the "
                    "same time.")}


def lens(focal_mm, object_mm):
    """Thin lens: where the image forms, how big, which way up."""
    f = float(focal_mm or 0)
    u = max(1.0, min(100000.0, float(object_mm or 0)))
    if f == 0:
        return {"ok": False, "error": "Focal length cannot be zero."}
    if abs(u - f) < 1e-9:
        return {"ok": True, "at_focus": True, "image_mm": None,
                "magnification": None,
                "why": "The object is exactly at the focal point, so the rays "
                       "leave parallel and no image forms at any finite "
                       "distance. This is how a collimator works."}
    v = 1.0 / (1.0 / f - 1.0 / u) if f else 0.0
    m = -v / u
    return {"ok": True, "at_focus": False,
            "image_mm": round(v, 2), "magnification": round(m, 3),
            "real": v > 0, "inverted": m < 0,
            "why": ("A real image is one the light actually reaches, so it "
                    "can be caught on a screen; a virtual image only appears "
                    "to be there. Inside the focal length a converging lens "
                    "gives an upright virtual image — that is a magnifying "
                    "glass. Outside it, the image flips, which is why the "
                    "picture on a camera sensor is upside down.")}


EXPERIMENTS = [
    {"id": "mix", "name": "Mix two reagents", "subject": "Chemistry",
     "ask": "Choose two things off the shelf and how much of each. You get "
            "the balanced equation, which one runs out first, what is left "
            "over and what you would actually see."},
    {"id": "projectile", "name": "Projectile motion", "subject": "Physics",
     "ask": "Set a speed, an angle and a launch height, and see the path, "
            "the range and the time in the air."},
    {"id": "circuit", "name": "Series and parallel", "subject": "Physics",
     "ask": "Wire up to six resistors and watch the current, the voltage "
            "across each and the power."},
    {"id": "pendulum", "name": "Pendulum", "subject": "Physics",
     "ask": "Change the length and the swing, and see where the small-angle "
            "formula stops being true."},
    {"id": "lens", "name": "Thin lens", "subject": "Physics",
     "ask": "Move an object towards a lens and watch the image flip, grow "
            "and become virtual."},
]
