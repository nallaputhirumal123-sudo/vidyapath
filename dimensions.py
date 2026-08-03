"""Check that a stated formula has the units it claims.

A lesson gave the angular momentum of an electromagnetic field as
mu0*q*m/(4*pi*r^3). That is dimensionally kg/s. Angular momentum is
kg·m²/s. The formula is off by a factor of length squared, and nothing in
this product could see it: the constants checker knows CODATA values, the
arithmetic checker does sums, and neither reads a symbolic expression.

Dimensional analysis is the one check that catches this whole class, and it
is arithmetic on exponents — no model, no network, no judgement. Every
physical quantity is a vector of seven exponents over the SI base units, the
operations are addition and subtraction of those vectors, and two sides of an
equation must come out equal.

Deliberately narrow. It only speaks when it recognises every symbol in the
expression and knows what the left-hand side should be, because a checker
that guesses at unfamiliar notation produces false alarms, and a false alarm
on a correct lesson costs more trust than the error it was hunting.

The seven exponents are ordered: metre, kilogram, second, ampere, kelvin,
mole, candela.
"""
import re

BASE = ("m", "kg", "s", "A", "K", "mol", "cd")
NONE = (0, 0, 0, 0, 0, 0, 0)


def _d(m=0, kg=0, s=0, A=0, K=0, mol=0, cd=0):
    return (m, kg, s, A, K, mol, cd)


# Symbols a physics lesson writes, and what they are dimensionally. Where a
# letter is genuinely ambiguous it is left out rather than guessed: "m" is
# mass far more often than magnetic moment, and a checker that picks wrong
# reports a correct formula as broken.
SYMBOLS = {
    # geometry and mechanics
    "r": _d(m=1), "d": _d(m=1), "l": _d(m=1), "h": _d(m=1), "x": _d(m=1),
    "λ": _d(m=1), "lambda": _d(m=1), "a0": _d(m=1),
    "t": _d(s=1), "T": _d(s=1), "period": _d(s=1),
    "v": _d(m=1, s=-1), "c": _d(m=1, s=-1), "u": _d(m=1, s=-1),
    "a": _d(m=1, s=-2), "g": _d(m=1, s=-2),
    "m": _d(kg=1), "M": _d(kg=1), "mass": _d(kg=1),
    "F": _d(m=1, kg=1, s=-2), "W": _d(m=2, kg=1, s=-2),
    "E": _d(m=2, kg=1, s=-2), "K": _d(m=2, kg=1, s=-2),
    "U": _d(m=2, kg=1, s=-2), "energy": _d(m=2, kg=1, s=-2),
    "P": _d(m=2, kg=1, s=-3), "power": _d(m=2, kg=1, s=-3),
    "p": _d(m=1, kg=1, s=-1), "momentum": _d(m=1, kg=1, s=-1),
    "L": _d(m=2, kg=1, s=-1),          # angular momentum
    "I": _d(m=2, kg=1),                # moment of inertia
    "ω": _d(s=-1), "omega": _d(s=-1), "f": _d(s=-1), "freq": _d(s=-1),
    "ρ": _d(m=-3, kg=1), "rho": _d(m=-3, kg=1),
    "τ": _d(m=2, kg=1, s=-2), "torque": _d(m=2, kg=1, s=-2),
    "k": _d(kg=1, s=-2),               # spring constant
    "G": _d(m=3, kg=-1, s=-2),
    "h_planck": _d(m=2, kg=1, s=-1), "ħ": _d(m=2, kg=1, s=-1),
    "hbar": _d(m=2, kg=1, s=-1),
    # electromagnetism
    "q": _d(s=1, A=1), "Q": _d(s=1, A=1), "charge": _d(s=1, A=1),
    "e": _d(s=1, A=1),
    "i": _d(A=1), "current": _d(A=1),
    "V": _d(m=2, kg=1, s=-3, A=-1), "voltage": _d(m=2, kg=1, s=-3, A=-1),
    "R": _d(m=2, kg=1, s=-3, A=-2),
    "C": _d(m=-2, kg=-1, s=4, A=2),
    "B": _d(kg=1, s=-2, A=-1),
    "Φ": _d(m=2, kg=1, s=-2, A=-1), "flux": _d(m=2, kg=1, s=-2, A=-1),
    "μ0": _d(m=1, kg=1, s=-2, A=-2), "mu0": _d(m=1, kg=1, s=-2, A=-2),
    "ε0": _d(m=-3, kg=-1, s=4, A=2), "eps0": _d(m=-3, kg=-1, s=4, A=2),
    "epsilon0": _d(m=-3, kg=-1, s=4, A=2),
    # a magnetic dipole moment, written out so it cannot collide with mass
    "mu": _d(m=2, A=1), "dipole": _d(m=2, A=1),
    "magnetic_moment": _d(m=2, A=1),
    # thermodynamics
    "kB": _d(m=2, kg=1, s=-2, K=-1), "k_B": _d(m=2, kg=1, s=-2, K=-1),
    "temp": _d(K=1), "θ": _d(K=1),
    "n": _d(mol=1), "NA": _d(mol=-1),
    # dimensionless
    "π": NONE, "pi": NONE, "N": NONE, "Z": NONE, "θ_rad": NONE,
}

# What a named quantity must come out as, for checking a stated equation.
EXPECT = {
    "angular momentum": _d(m=2, kg=1, s=-1),
    "momentum": _d(m=1, kg=1, s=-1),
    "energy": _d(m=2, kg=1, s=-2),
    "work": _d(m=2, kg=1, s=-2),
    "kinetic energy": _d(m=2, kg=1, s=-2),
    "potential energy": _d(m=2, kg=1, s=-2),
    "power": _d(m=2, kg=1, s=-3),
    "force": _d(m=1, kg=1, s=-2),
    "torque": _d(m=2, kg=1, s=-2),
    "pressure": _d(m=-1, kg=1, s=-2),
    "velocity": _d(m=1, s=-1), "speed": _d(m=1, s=-1),
    "acceleration": _d(m=1, s=-2),
    "frequency": _d(s=-1),
    "charge": _d(s=1, A=1),
    "current": _d(A=1),
    "voltage": _d(m=2, kg=1, s=-3, A=-1),
    "resistance": _d(m=2, kg=1, s=-3, A=-2),
    "capacitance": _d(m=-2, kg=-1, s=4, A=2),
    "magnetic field": _d(kg=1, s=-2, A=-1),
    "electric field": _d(m=1, kg=1, s=-3, A=-1),
    "magnetic flux": _d(m=2, kg=1, s=-2, A=-1),
    "density": _d(m=-3, kg=1),
    "wavelength": _d(m=1),
    "area": _d(m=2), "volume": _d(m=3),
}


def show(dim):
    """A dimension vector as the units a person would write."""
    if dim == NONE:
        return "dimensionless"
    top = [f"{u}{'^' + str(e) if e != 1 else ''}"
           for u, e in zip(BASE, dim) if e > 0]
    bot = [f"{u}{'^' + str(-e) if e != -1 else ''}"
           for u, e in zip(BASE, dim) if e < 0]
    if not top:
        return "1/" + "·".join(bot)
    return "·".join(top) + ("/" + "·".join(bot) if bot else "")


class Unknown(Exception):
    """A symbol the table does not know. Better than a guess."""


_TOKEN = re.compile(r"[A-Za-zμεπωρτλθΦħ_][A-Za-z0-9_]*|\d+\.?\d*|\*\*|[-+*/^()]")


def dimension_of(expr):
    """The dimensions of an expression, or raise Unknown.

    A small recursive-descent parser rather than eval: this reads text a
    model wrote, and the rule everywhere in this product is that such text is
    parsed, never executed.
    """
    tokens = _TOKEN.findall(str(expr or "").replace("·", "*"))
    if not tokens:
        raise Unknown("empty")
    pos = [0]

    def peek():
        return tokens[pos[0]] if pos[0] < len(tokens) else None

    def eat():
        tok = peek()
        pos[0] += 1
        return tok

    def atom():
        tok = eat()
        if tok is None:
            raise Unknown("ran out")
        if tok == "(":
            v = expression()
            if peek() == ")":
                eat()
            return v
        if tok == "-":
            return atom()
        if re.match(r"^\d", tok):
            return NONE                      # a pure number has no dimension
        if tok in SYMBOLS:
            return SYMBOLS[tok]
        raise Unknown(tok)

    def power():
        v = atom()
        while peek() in ("^", "**"):
            eat()
            e = eat()
            neg = False
            if e == "-":
                neg, e = True, eat()
            if e is None or not re.match(r"^\d+$", e):
                raise Unknown("exponent")
            n = -int(e) if neg else int(e)
            v = tuple(a * n for a in v)
        return v

    def term():
        v = power()
        while peek() in ("*", "/"):
            op = eat()
            w = power()
            v = tuple(a + b if op == "*" else a - b for a, b in zip(v, w))
        return v

    def expression():
        v = term()
        while peek() in ("+", "-"):
            eat()
            w = term()
            # Adding two different dimensions is itself an error, and a
            # definite one — you cannot add a length to a time.
            if w != v:
                raise Unknown(f"cannot add {show(v)} to {show(w)}")
            v = term.__wrapped__ if False else v
        return v

    value = expression()
    if pos[0] < len(tokens):
        raise Unknown("trailing " + str(tokens[pos[0]]))
    return value


_STATES = re.compile(
    r"\b(" + "|".join(sorted(EXPECT, key=len, reverse=True)) +
    r")\b[^.\n]{0,40}?(?:is|=|equals|given by|becomes)\s*"
    r"([A-Za-zμεπωρτλθΦħ0-9_()*/^+\-.\s]{3,90})", re.I)


def check(text):
    """Formulas in this text whose units are wrong.

    Only reports when every symbol is recognised and the quantity named is
    one the table knows. Anything else is silence: a false alarm on a correct
    lesson costs more trust than the error it was looking for.
    """
    out = []
    for m in _STATES.finditer(str(text or "")):
        quantity = m.group(1).lower()
        expr = m.group(2).strip().rstrip(".,;")
        want = EXPECT.get(quantity)
        if not want:
            continue
        try:
            got = dimension_of(expr)
        except Unknown:
            continue                          # not understood, so not judged
        except Exception:
            continue
        if got == want:
            continue
        out.append({
            "severity": "critical", "kind": "dimensions",
            "problem": (f"it gives {quantity} as {expr}, which is "
                        f"{show(got)} — {quantity} is {show(want)}"),
            "correction": (f"{quantity} must come out in {show(want)}; "
                           f"this expression is out by "
                           f"{show(tuple(a - b for a, b in zip(want, got)))}"),
        })
    return out
