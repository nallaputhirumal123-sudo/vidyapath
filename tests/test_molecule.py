"""3D molecules: measured coordinates, not written ones.

The molecule scene took its atomic positions from the model. Every other
picture in this product is derived from real values or refused, on the grounds
that a student cannot check a picture — and this was the one place that rule
quietly did not apply. A model writing out the xyz of caffeine produces
plausible numbers, and plausible atomic geometry is wrong geometry.

PubChem's conformers are computed from the chemistry, so the geometry is now
fetched. The model still decides that a molecule belongs in the lesson and
what to say about it. It no longer decides where the atoms are.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import molecule                                    # noqa: E402

PASS = FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {name}" + (f"  ({detail})" if detail else ""))
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


# ---- a real record parses to real chemistry -------------------------
WATER = """water
  Marvin

  3  2  0  0  0  0            999 V2000
    0.0000    0.0000    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
    0.9572    0.0000    0.0000 H   0  0  0  0  0  0  0  0  0  0  0  0
   -0.2400    0.9270    0.0000 H   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0  0  0  0
  1  3  1  0  0  0  0
M  END
"""
w = molecule.parse_sdf(WATER)
check("water parses", bool(w), str(sorted(w))[:70])
check("it has three atoms", len(w.get("atoms", [])) == 3)
check("and two bonds", len(w.get("bonds", [])) == 2)
check("the formula is H2O", w.get("formula") == "H2O", w.get("formula"))
check("oxygen is CPK red",
      any(a["el"] == "O" and a["c"] == 0xFF0D0D for a in w["atoms"]))
check("it is centred on itself",
      abs(sum(a["x"] for a in w["atoms"])) < 1e-6)

# ---- Hill order, which every chemistry text prints ------------------
check("carbon first, then hydrogen",
      molecule.formula([{"el": "O"}, {"el": "H"}, {"el": "H"}, {"el": "C"}])
      == "CH2O",
      molecule.formula([{"el": "O"}, {"el": "H"}, {"el": "H"}, {"el": "C"}]))
check("without carbon it is alphabetical",
      molecule.formula([{"el": "S"}, {"el": "O"}, {"el": "H"}]) == "HOS")

# ---- a truncated download must produce nothing ----------------------
# Half a file is the dangerous case: the counts line promises atoms that are
# not there, and inventing them would put a molecule on the board that does
# not exist.
check("a truncated record is refused",
      molecule.parse_sdf("\n".join(WATER.splitlines()[:5])) == {})
for junk in ("", "not an sdf at all", "\n\n\n\n", None,
             "x\ny\nz\n  9  9  0\n"):
    check(f"refuses {str(junk)[:24]!r}", molecule.parse_sdf(junk) == {})

# a counts line claiming more atoms than any molecule has
check("an absurd atom count is refused",
      molecule.parse_sdf("a\nb\nc\n999999  1  0\n") == {})

# ---- nothing is trusted on the way back in --------------------------
# Lessons are cached and re-read, so the stored shape is rebuilt field by
# field like every other structure here.
dirty = {"atoms": [{"el": "C", "x": 0, "y": 0, "z": 0},
                   {"el": "<script>", "x": "1", "y": 0, "z": 0},
                   {"el": "O", "x": float("inf"), "y": 0, "z": 0},
                   {"el": "N", "x": "nope", "y": 0, "z": 0}],
         "bonds": [[0, 1, 1], [0, 99, 1], [5, 6, 2], [0, 0, 1],
                   ["a", "b", "c"]],
         "span": "huge", "formula": "x" * 300}
got = molecule.clean(dirty)
check("bad coordinates are dropped", len(got["atoms"]) == 2,
      str([a["el"] for a in got["atoms"]]))
check("a bond to nowhere is dropped", got["bonds"] == [[0, 1, 1]],
      str(got["bonds"]))
check("an unparseable span falls back", got["span"] == 1.0, str(got["span"]))
check("the formula is capped", len(got["formula"]) <= 60)
check("an unknown element still renders, in grey",
      got["atoms"][1]["c"] == molecule.DEFAULT[1])
for junk in (None, "text", 42, [], {"atoms": []}):
    check(f"clean refuses {str(junk)[:18]}", molecule.clean(junk) == {})

# ---- which names are worth asking about -----------------------------
for good in ("caffeine", "glucose", "sodium chloride", "citric acid"):
    check(f"{good!r} is worth a lookup", molecule.wanted(good))
for bad in ("", "   ", "a" * 80,
            "the mechanism by which the enzyme lowers activation energy"):
    check(f"{bad[:28]!r} is not", not molecule.wanted(bad))

# ---- against the real service ---------------------------------------
try:
    import asyncio
    import httpx

    async def go():
        async with httpx.AsyncClient(follow_redirects=True) as c:
            out = {}
            for n in ("caffeine", "glucose", "benzene",
                      "zzqqxx not a compound"):
                out[n] = await molecule.find(c, n)
            return out

    real = asyncio.run(go())
except Exception as e:
    real = None
    print(f"  ..    live lookup skipped: {type(e).__name__}")

# molecule.find is documented never to raise — it answers {} when PubChem
# cannot be reached. So the guard above never fires, and what actually
# happened offline was every check failing and then a KeyError on
# real["benzene"]["atoms"], which reads as a broken parser rather than a
# missing network. An empty answer for a compound PubChem certainly has is
# the network, not the code.
if real is not None and not real.get("caffeine"):
    print("  ..    live lookup skipped: PubChem returned nothing "
          "(no network?)")
    real = None

if real is None:
    pass
else:
    check("caffeine is C8H10N4O2",
          real["caffeine"].get("formula") == "C8H10N4O2",
          real["caffeine"].get("formula"))
    check("glucose is C6H12O6",
          real["glucose"].get("formula") == "C6H12O6",
          real["glucose"].get("formula"))
    check("benzene is C6H6", real["benzene"].get("formula") == "C6H6",
          real["benzene"].get("formula"))
    check("benzene is a flat ring",
          all(abs(a["z"]) < 0.3 for a in real["benzene"]["atoms"]
              if a["el"] == "C"),
          "carbons coplanar")
    check("nonsense returns nothing", real["zzqqxx not a compound"] == {})
    check("real coordinates are not all zero",
          any(a["x"] or a["y"] or a["z"]
              for a in real["caffeine"]["atoms"]))

print(f"\nPASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
