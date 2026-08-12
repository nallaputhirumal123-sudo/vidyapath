"""Chemistry on a solved paper: set as chemistry, and counted.

Two separate things, and both of them started as the same complaint about
a maths paper — "it says A2B5, the numbers are not shown like in a question".

**Setting it.** A chemistry answer is mostly formulas and equations, and
nobody writes those as LaTeX: they arrive as plain letters and digits
because that is how the paper prints them. Three different things in that
text are all digits — the 2 in H2O is an atom count and goes below the
line, the 2 in 2H2O is a coefficient and stays full size, the 2 in Ca2+ is
a charge and goes above it. The coefficient was the one that showed:
a leading digit stopped the match dead, so a balanced equation — most of
what a chemistry paper asks a student to write — rendered as flat text.

**Counting it.** An equation either balances or it does not, and finding out
needs no model, no key and no network. It is worth counting because of where
the marks are: "write the balanced equation" is a whole question, and the way
a model gets it wrong is the way a student reads straight past — right
reaction, right formulas, one coefficient missing.

It only ever complains. Nothing here says an equation is correct, because a
balanced equation can still be the wrong reaction. Two things it refuses to
judge at all: an ionic equation, where the plus sign is both a separator and
a charge and where the charges must balance too; and a skeleton equation
that the same answer goes on to balance, which is the working doing exactly
what it should.
"""
import io
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import chem                                          # noqa: E402
import solver                                        # noqa: E402

MATHJS = io.open(os.path.join(ROOT, "mathtext.js"), encoding="utf-8").read()
P, F = [], []


def ck(name, cond, why=""):
    print(("PASS " if cond else "FAIL ") + name + (" — " + why if why else ""),
          flush=True)
    (P if cond else F).append(name)


print("\nan equation that does not balance is said so")
for eq, atom in (("H2 + O2 -> H2O", "O"),
                 ("CH4 + O2 -> CO2 + H2O", "H"),
                 ("Fe2O3 + CO -> Fe + CO2", "Fe"),
                 ("Na + Cl2 -> NaCl", "Cl")):
    bad = chem.unbalanced(eq)
    ck("caught: " + eq, bool(bad) and atom in bad[0],
       bad[0] if bad else "went unreported")

print("\nand one that does balance is left alone")
for eq in ("2H2 + O2 -> 2H2O",
           "Zn + H2SO4 -> ZnSO4 + H2",
           "CaCO3 -> CaO + CO2",
           "Fe2O3 + 3CO -> 2Fe + 3CO2",
           "2KClO3 -> 2KCl + 3O2",
           "C6H12O6 + 6O2 -> 6CO2 + 6H2O",
           "N2 + 3H2 <-> 2NH3",
           "2Mg + O2 → 2MgO",
           "Mg + 2HCl -> MgCl2 + H2"):
    ck("quiet on: " + eq, not chem.unbalanced(eq))

print("\nbrackets, hydrates and state symbols are read properly")
ck("a bracketed group multiplies through",
   chem.atoms("Ca(OH)2") == {"Ca": 1, "O": 2, "H": 2})
ck("and nests", chem.atoms("Al2(SO4)3") == {"Al": 2, "S": 3, "O": 12})
ck("a hydrate counts its water",
   chem.unbalanced("CuSO4.5H2O -> CuSO4 + 5H2O") == [],
   "the dot in CuSO4.5H2O is five waters, not a full stop")
ck("state symbols are not atoms",
   chem.unbalanced("CaCO3(s) -> CaO(s) + CO2(g)") == [],
   "(s), (l), (g) and (aq) belong to the equation, not to the formula")
ck("a real balanced double displacement passes",
   chem.unbalanced("Al2(SO4)3 + 6NaOH -> 2Al(OH)3 + 3Na2SO4") == [])

print("\nand it stays quiet where it cannot be sure")
ck("an ionic equation is not judged",
   chem.unbalanced("Ag+ + Cl- -> AgCl") == [],
   "the plus is a separator and a charge in the same line, and the charges "
   "have to balance too — guessing which is worse than not answering")
ck("a skeleton the answer goes on to balance is the working, not a fault",
   chem.unbalanced("The skeleton is H2 + O2 -> H2O; balancing gives "
                   "2H2 + O2 -> 2H2O") == [],
   "writing the unbalanced equation first is how it is taught")
ck("an arrow in ordinary text is not an equation",
   chem.unbalanced("x -> y in the graph") == []
   and chem.unbalanced("input -> output") == [])
ck("a maths line is not an equation either",
   chem.unbalanced("Speed = distance -> time") == [])
ck("a sentence around an equation does not become part of it",
   chem.unbalanced("So the balanced equation is 2KClO3 -> 2KCl + 3O2.") == [],
   "a side that could swallow spaces read 'H2O balances as 2H2 + O2' as "
   "one side and reported the sentence itself as unbalanced")
ck("an invented element is not an element",
   chem.atoms("Xq2") is None)

print("\nthe solved paper carries the doubt")
_bad = solver.verify([{"n": "1", "answer": "CH4 + O2 -> CO2 + H2O",
                       "working": ["Methane burns in oxygen."]}])
ck("an unbalanced equation reaches the page as a doubt",
   "doubt" in _bad[0] and "not balanced" in _bad[0]["doubt"][0])
_ok = solver.verify([{"n": "2", "answer": "CH4 + 2O2 -> CO2 + 2H2O",
                      "working": ["Balanced."]}])
ck("and a balanced one is not marked at all", "doubt" not in _ok[0],
   "nothing here says an answer is right; a balanced equation can still be "
   "the wrong reaction")

print("\nthe solving prompt asks for chemistry to be written as chemistry")
_SOLVE1 = " ".join(solver.SOLVE.split())
ck("balancing is asked for by name",
   "write it balanced, and count the atoms on both sides" in _SOLVE1)
ck("state symbols are mentioned", "state symbols" in _SOLVE1)
ck("a structure that cannot be drawn is described instead",
   "describe the bonding in words" in _SOLVE1,
   "leaving it out loses the marks; saying it cannot be drawn does not")

print("\nformulas are set as formulas on the page")
JS = r"""
global.katex = undefined;
eval(require('fs').readFileSync(process.argv[1], 'utf8'));
const esc = s => String(s).replace(/[&<>"']/g, c => (
  {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const out = {};
for (const t of JSON.parse(process.argv[2])) out[t] = mathText(esc(t));
console.log(JSON.stringify(out));
"""
CASES = [
    # what a chemistry answer actually contains
    "H2O", "A2B5", "H2SO4", "CaCO3 -> CaO + CO2",
    "2H2 + O2 -> 2H2O", "2H2+O2->2H2O",
    "Fe2O3 + 3CO -> 2Fe + 3CO2", "N2 + 3H2 <-> 2NH3",
    "Ca2+", "Na+ + Cl- -> NaCl", "CuSO4.5H2O",
    # and what is not chemistry, whatever it looks like
    "Find T2 from the graph", "Q1. Solve for x", "Class 10 Chemistry",
    "x -> y", "5 > 3", "profit is $3",
]
try:
    got = json.loads(subprocess.run(
        ["node", "-e", JS, os.path.join(ROOT, "mathtext.js"),
         json.dumps(CASES)],
        capture_output=True, text=True, timeout=60,
        encoding="utf-8").stdout or "{}")
except Exception as e:                                # node is not required
    got = {}
    print("(node unavailable, skipping the rendering checks: %s)" % e)

if got:
    SUB = "₀₁₂₃₄₅₆₇₈₉"
    ck("a subscript is a subscript", got["H2O"] == "H₂O")
    ck("the formula from the paper that started this",
       got["A2B5"] == "A₂B₅",
       "A and B are not elements; two groups and a digit is a formula "
       "whatever the letters are")
    ck("a longer one", got["H2SO4"] == "H₂SO₄")
    ck("a coefficient stays full size",
       got["2H2 + O2 -> 2H2O"] == "2H₂ + O₂ → 2H₂O",
       "the leading digit stopped the match dead, so a balanced equation — "
       "most of what a chemistry paper asks for — rendered as flat text")
    ck("with or without the spaces around it",
       got["2H2+O2->2H2O"] == "2H₂+O₂→2H₂O")
    ck("a lone O2 on an equation's line is oxygen",
       got["Fe2O3 + 3CO -> 2Fe + 3CO2"] == "Fe₂O₃ + 3CO → 2Fe + 3CO₂")
    ck("an equilibrium arrow is its own sign",
       got["N2 + 3H2 <-> 2NH3"] == "N₂ + 3H₂ ⇌ 2NH₃")
    ck("a charge goes above the line, not below",
       got["Ca2+"] == "Ca²⁺",
       "Ca2+ is one calcium carrying two, not two calciums")
    ck("and so does a bare one", got["Na+ + Cl- -> NaCl"] == "Na⁺ + Cl⁻ → NaCl")
    ck("a hydrate keeps its dot", got["CuSO4.5H2O"] == "CuSO₄.5H₂O")

    ck("a variable is not a molecule",
       got["Find T2 from the graph"] == "Find T2 from the graph",
       "one group on its own is as likely to be a variable as a molecule, "
       "so it needs a coefficient, a charge, or an equation beside it")
    ck("a question number is left alone",
       got["Q1. Solve for x"] == "Q1. Solve for x")
    ck("and so is a class", got["Class 10 Chemistry"] == "Class 10 Chemistry")
    ck("an arrow in prose is not a reaction arrow", got["x -> y"] == "x -&gt; y")
    ck("a greater-than is not an arrow", got["5 &gt; 3"] == "5 &gt; 3"
       if "5 &gt; 3" in got else got["5 > 3"] == "5 &gt; 3")
    ck("money is still money", got["profit is $3"] == "profit is $3")

print("\n" + ("PASSED %d   FAILED %d" % (len(P), len(F))))
if F:
    for name in F:
        print("  FAILED: " + name)
    sys.exit(1)
