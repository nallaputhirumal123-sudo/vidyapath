"""Crystal structures, against the published values.

The lattice scene took its basis and its lattice constant from the model, so
rock salt arrived as a plausible arrangement at a plausible spacing and a
student could check neither. Crystallography is not a matter of opinion, and
the difference an introductory lesson turns on — rock salt six-coordinate at
5.640 angstrom against caesium chloride eight-coordinate at 4.123 — is
exactly the part a plausible guess gets wrong.

Every constant below is checked against its published value, because a table
of measured numbers is only worth having if the numbers are right.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lattice                                     # noqa: E402

PASS = FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {name}" + (f"  ({detail})" if detail else ""))
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


# name -> (lattice constant in angstrom, coordination number)
PUBLISHED = {
    "sodium chloride": (5.640, 6),
    "caesium chloride": (4.123, 8),
    "diamond": (3.567, 4),
    "silicon": (5.431, 4),
    "germanium": (5.658, 4),
    "gallium arsenide": (5.653, 4),
    "zinc blende": (5.406, 4),
    "fluorite": (5.463, 8),
    "copper": (3.615, 12),
    "aluminium": (4.050, 12),
    "gold": (4.078, 12),
    "silver": (4.086, 12),
    "iron": (2.866, 8),
    "tungsten": (3.165, 8),
    "sodium": (4.291, 8),
    "polonium": (3.359, 6),
}
for name, (a, cn) in PUBLISHED.items():
    got = lattice.clean(name)
    check(f"{name} a = {a} A", got and abs(got["a"] - a) < 5e-4,
          str(got.get("a") if got else None))
    check(f"{name} is {cn}-coordinate", got and got["coordination"] == cn,
          str(got.get("coordination") if got else None))

# ---- the structures, not just the numbers ---------------------------
nacl = lattice.clean("sodium chloride")
check("rock salt has eight sites in the cell", len(nacl["basis"]) == 8,
      str(len(nacl["basis"])))
check("and both ions", {b["el"] for b in nacl["basis"]} == {"Na", "Cl"},
      str(sorted({b["el"] for b in nacl["basis"]})))
cscl = lattice.clean("caesium chloride")
check("caesium chloride has two", len(cscl["basis"]) == 2)
check("one at the corner and one at the centre",
      any(b["x"] == 0 and b["y"] == 0 and b["z"] == 0 for b in cscl["basis"])
      and any(b["x"] == 0.5 and b["y"] == 0.5 and b["z"] == 0.5
              for b in cscl["basis"]))
fe = lattice.clean("iron")
check("iron is body-centred", len(fe["basis"]) == 2
      and any(b["x"] == 0.5 for b in fe["basis"]))
cu = lattice.clean("copper")
check("copper is face-centred", len(cu["basis"]) == 4)
si = lattice.clean("silicon")
check("silicon is diamond cubic with eight sites", len(si["basis"]) == 8)

# every fractional coordinate belongs inside the cell
for name in PUBLISHED:
    g = lattice.clean(name)
    inside = all(0 <= b[ax] <= 1 for b in g["basis"] for ax in "xyz")
    check(f"{name} sites lie in the cell", inside)

# ---- naming ----------------------------------------------------------
for phrase in ("NaCl", "table salt", "rock salt",
               "the crystal structure of sodium chloride",
               "Sodium Chloride unit cell", "halite"):
    g = lattice.clean(phrase)
    check(f"{phrase!r} finds rock salt", g and abs(g["a"] - 5.640) < 5e-4)

check("the longest name wins over a substring",
      abs(lattice.clean("sodium chloride")["a"] - 5.640) < 5e-4,
      "not sodium's 4.291")

for absent in ("photosynthesis", "aircraft gearbox", "", "   ", None,
               "unobtainium"):
    check(f"{str(absent)[:22]!r} is not a listed structure",
          lattice.clean(absent) == {})

print(f"\nPASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
