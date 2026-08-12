"""Is the equation the answer just wrote actually balanced?

maths.py substitutes a claimed root back into the equation the working
states, and catches a confident wrong number before a class copies it into
their books. This is the same idea for the other half of a science paper: a
chemical equation either balances or it does not, and counting atoms needs
no model, no key and no network.

It is worth counting because of where the marks are. "Write the balanced
equation for the reaction of zinc with dilute sulphuric acid" is a whole
question on a Class 10 paper, and an equation that is right in every respect
except the coefficients loses most of them. A model gets this wrong in a
particular, plausible way — the formulas are correct, the reaction is
correct, and one coefficient is missing — which is exactly the kind of error
a student reads straight past.

**It only ever complains.** Nothing here stamps an equation correct: a
balanced equation can still be the wrong reaction, and this knows nothing
about chemistry beyond how to count. It stays silent unless both sides parse
completely into real elements and the totals genuinely disagree.

Two things it deliberately declines to judge:

- **Ionic equations.** "Ag+ + Cl- -> AgCl" needs charge balanced as well as
  atoms, and the plus sign is doing two jobs in one line — a separator
  between terms and a charge on one of them. Rather than guess which, any
  equation carrying a charge is left alone.
- **A skeleton equation that the answer goes on to balance.** Writing the
  unbalanced equation first and then balancing it is how the working is
  supposed to read. So an unbalanced equation is only reported when no
  balanced equation over the same elements appears anywhere in the answer.
"""
import re

# Every element, because a paper can name any of them, and because the list
# is what keeps this from reading ordinary words as chemistry: a side that
# contains one token which is not an element is not an equation at all.
ELEMENTS = set(
    ("H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co "
     "Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb "
     "Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re "
     "Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es "
     "Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og").split())

# No word boundaries in this file. A \b has arrived here as a literal
# backspace enough times today that the rule is now: character classes only.
_ARROW = r"(?:-{1,3}>|=+>|<-+>|<=+>|→|⇌|⇄|←)"
# A term has no spaces in it, and terms are joined only by a plus. That is
# what stops a side from running off into the sentence around it: in "the
# skeleton H2 + O2 -> H2O balances as 2H2 + O2 -> 2H2O" a side that could
# swallow spaces read the right-hand side as "H2O balances as 2H2 + O2" and
# reported the sentence itself as an unbalanced equation.
_TERM = r"[0-9]{0,3}[A-Za-z(][0-9A-Za-z()·.]*"
_SIDE = _TERM + r"(?:\s*\+\s*" + _TERM + r")*"
_EQ = re.compile(r"(" + _SIDE + r")\s*" + _ARROW + r"\s*(" + _SIDE + r")")
# A state symbol is not part of the formula: CaCO3(s) is CaCO3.
_STATE = re.compile(r"\(\s*(?:s|l|g|aq)\s*\)", re.I)
# A charge, attached to its term and closing it off. Distinct from the plus
# that separates two terms, which has a space or a coefficient after it.
_CHARGE = re.compile(r"[A-Za-z0-9][0-9]?[+−-](?=\s|$|\+)")


def atoms(formula):
    """Atom counts for one formula, or None if it is not one.

    Brackets nest — Al2(SO4)3, Ca(OH)2 — and a hydrate's dot is handled by
    the caller, which splits on it first.
    """
    s = str(formula).strip()
    if not s:
        return None
    i, n, stack = 0, len(s), [{}]
    while i < n:
        c = s[i]
        if c == "(":
            stack.append({})
            i += 1
        elif c == ")":
            if len(stack) == 1:
                return None
            grp = stack.pop()
            i += 1
            j = i
            while j < n and s[j].isdigit():
                j += 1
            mult = int(s[i:j]) if j > i else 1
            i = j
            for k, v in grp.items():
                stack[-1][k] = stack[-1].get(k, 0) + v * mult
        elif c.isupper():
            j = i + 1
            if j < n and s[j].islower():
                j += 1
            sym = s[i:j]
            if sym not in ELEMENTS:
                return None
            i = j
            k = i
            while k < n and s[k].isdigit():
                k += 1
            cnt = int(s[i:k]) if k > i else 1
            i = k
            stack[-1][sym] = stack[-1].get(sym, 0) + cnt
        else:
            return None
    return stack[0] if len(stack) == 1 and stack[0] else None


def _term(text, mult=1):
    """One term — coefficient, formula, hydrate dot and all."""
    t = _STATE.sub("", str(text)).strip().strip(".,;:")
    if not t:
        return None
    m = re.match(r"^([0-9]{1,3})\s*(.+)$", t)
    if m:
        mult *= int(m.group(1))
        t = m.group(2).strip()
    out = {}
    # CuSO4.5H2O is copper sulphate and five waters, counted as both.
    for part in re.split(r"[.·]", t):
        part = part.strip()
        if not part:
            continue
        sub = _term(part, 1) if re.match(r"^[0-9]", part) else atoms(part)
        if sub is None:
            return None
        for k, v in sub.items():
            out[k] = out.get(k, 0) + v * mult
    return out or None


def side(text):
    """Atom totals for one side of an equation, or None if it is not one."""
    t = str(text)
    if _CHARGE.search(t):
        return None                      # an ionic equation; not judged here
    parts = re.split(r"\s*\+\s*", t.strip())
    total = {}
    for idx, p in enumerate(parts):
        p = p.strip()
        if not p:
            return None
        # Prose runs into the equation from the outside — "so the equation is
        # 2H2 + O2" on the left, "2H2O and it is balanced" on the right — so
        # the outermost term is trimmed to the word nearest the arrow.
        words = p.split()
        if len(words) > 1:
            p = words[-1] if idx == 0 else words[0]
            if idx not in (0, len(parts) - 1):
                return None
        got = _term(p)
        if got is None:
            return None
        for k, v in got.items():
            total[k] = total.get(k, 0) + v
    return total or None


def equations(text):
    """Every chemical equation in the text, as (source, left, right)."""
    out = []
    for line in str(text or "").splitlines():
        for m in _EQ.finditer(line):
            lhs, rhs = side(m.group(1)), side(m.group(2))
            if lhs and rhs:
                out.append((m.group(0).strip(), lhs, rhs))
    return out


def unbalanced(text):
    """Equations whose two sides do not have the same atoms, said plainly."""
    found = equations(text)
    if not found:
        return []
    # An equation the answer later balances is the working doing its job.
    settled = {frozenset(list(l) + list(r)) for src, l, r in found if l == r}
    out = []
    for src, lhs, rhs in found:
        if lhs == rhs or frozenset(list(lhs) + list(rhs)) in settled:
            continue
        off = []
        for el in sorted(set(list(lhs) + list(rhs))):
            a, b = lhs.get(el, 0), rhs.get(el, 0)
            if a != b:
                off.append(f"{a} {el} on the left and {b} on the right")
        out.append(f"{src} is not balanced — " + ", ".join(off[:3]))
    return out
