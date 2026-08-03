"""Substitute the answer back into the question.

The scanner was given

    x + y + z = xyz,  x^2 + y^2 + z^2 = 3

and confidently answered that (1, 1, 1) is a solution. Put it back into the
first equation: 1 + 1 + 1 is 3, and xyz is 1. It had checked the second
equation and not the first. Every other solution it offered fails the same
way, and a student would have copied all of them into an exam.

Checking a claimed solution needs no cleverness at all — it is substitution
and arithmetic, which is the definition of something a machine should do and a
model should not be trusted with. So any lesson that states an equation and
then states a solution gets the solution put back in.

Nothing here evaluates a string. Expressions are parsed to a syntax tree and
walked node by node against an allowlist, so an expression that arrived from
a model can contain only numbers, the declared variables, arithmetic and a
short list of maths functions. Anything else — an attribute, a call to
something unlisted, a comprehension — is refused before a value is produced.
"""
import ast
import math
import re

# What may appear in an expression. Everything absent from this is rejected,
# which is the right default when the input came from a language model.
FUNCS = {
    "sqrt": math.sqrt, "abs": abs, "exp": math.exp,
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
    "log": math.log, "ln": math.log, "log10": math.log10,
    "floor": math.floor, "ceil": math.ceil,
    "min": min, "max": max,
}
CONSTS = {"pi": math.pi, "e": math.e}

MAX_POW = 64          # 2**1e9 is not a maths error, it is a hung process
MAX_NODES = 400


class Unsafe(Exception):
    """The expression contained something not on the allowlist."""


def _walk(node, vars_, depth=0):
    if depth > 25:
        raise Unsafe("too deeply nested")
    if isinstance(node, ast.Expression):
        return _walk(node.body, vars_, depth + 1)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(
                node.value, (int, float)):
            raise Unsafe("only numbers")
        return float(node.value)
    if isinstance(node, ast.Name):
        k = node.id
        if k in vars_:
            return float(vars_[k])
        if k in CONSTS:
            return CONSTS[k]
        raise Unsafe(f"unknown name {k}")
    if isinstance(node, ast.UnaryOp):
        v = _walk(node.operand, vars_, depth + 1)
        if isinstance(node.op, ast.UAdd):
            return v
        if isinstance(node.op, ast.USub):
            return -v
        raise Unsafe("unary operator")
    if isinstance(node, ast.BinOp):
        a = _walk(node.left, vars_, depth + 1)
        b = _walk(node.right, vars_, depth + 1)
        op = node.op
        if isinstance(op, ast.Add):
            return a + b
        if isinstance(op, ast.Sub):
            return a - b
        if isinstance(op, ast.Mult):
            return a * b
        if isinstance(op, ast.Div):
            if abs(b) < 1e-15:
                raise Unsafe("division by zero")
            return a / b
        if isinstance(op, ast.Pow):
            if abs(b) > MAX_POW:
                raise Unsafe("exponent too large")
            return a ** b
        if isinstance(op, ast.Mod):
            if abs(b) < 1e-15:
                raise Unsafe("modulo by zero")
            return a % b
        raise Unsafe("operator")
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in FUNCS:
            raise Unsafe("function")
        if node.keywords:
            raise Unsafe("keyword argument")
        args = [_walk(a, vars_, depth + 1) for a in node.args]
        return float(FUNCS[node.func.id](*args))
    raise Unsafe(type(node).__name__)


def evaluate(expr, vars_):
    """Value of an expression given the variables, or None if it cannot be."""
    src = _normalise(expr)
    if not src or len(src) > 300:
        return None
    try:
        tree = ast.parse(src, mode="eval")
    except SyntaxError:
        return None
    if sum(1 for _ in ast.walk(tree)) > MAX_NODES:
        return None
    try:
        v = _walk(tree, vars_)
    except (Unsafe, ValueError, OverflowError, ZeroDivisionError, TypeError):
        return None
    if isinstance(v, complex) or v != v or v in (float("inf"), float("-inf")):
        return None
    return v


def _normalise(expr):
    """Written maths into something Python's parser accepts.

    Only shape, never meaning: a caret is a power, 2x is two times x, and a
    unicode minus is a minus. Nothing here changes what the expression says.
    """
    s = str(expr or "").strip()
    s = (s.replace("^", "**").replace("×", "*").replace("·", "*")
          .replace("÷", "/").replace("−", "-").replace("–", "-")
          .replace("√", "sqrt"))
    s = re.sub(r"\s+", " ", s)
    # 2x -> 2*x, 3(x+1) -> 3*(x+1), )( -> )*(, x( stays a call only if named.
    s = re.sub(r"(\d)\s*([A-Za-z(])", r"\1*\2", s)
    s = re.sub(r"\)\s*(\()", r")*\1", s)
    s = re.sub(r"\)\s*([A-Za-z])", r")*\1", s)
    # sqrt3 -> sqrt(3), which models write often
    s = re.sub(r"\bsqrt\s*\*?\s*(\d+(?:\.\d+)?)", r"sqrt(\1)", s)
    return s.strip()


# --------------------------------------------------------------------------
# Finding the equations and the answers in a lesson
# --------------------------------------------------------------------------
_VARS = re.compile(r"\b([a-z])\b")

# Where an equation stops being an equation and becomes prose again.
_SPLIT = re.compile(r"(?:[,;:.]|\band\b|\bso\b|\bwhich\b|\bwhere\b|"
                    r"\bthen\b|\bgives\b|\bbecomes\b|\byields\b|"
                    r"\bbut\b|\bif\b|\bfor\b|\bis a\b|\n)+",
                    re.I)
_MATHY = re.compile(r"^[0-9a-zA-Z_^*/+\-().\s\u221a\u00d7\u00b7\u00f7\u2212=]+$")


# Words that introduce an equation without being part of one. "The system is
# x + y + z = xyz" is an equation with a preamble, and dropping the preamble
# is the difference between checking it and ignoring it.
_PREAMBLE = {
    "the", "a", "an", "this", "that", "these", "those", "system", "equation",
    "equations", "formula", "is", "are", "was", "we", "have", "has", "get",
    "gets", "given", "know", "first", "second", "third", "next", "let", "put",
    "using", "use", "from", "since", "as", "here", "now", "also", "our",
    "means", "say", "says", "substituting", "substitute", "solving",
    "solve", "rearranging", "consider", "suppose", "assume", "both", "sides",
    "side", "of", "in", "into", "to", "it", "they", "you", "recall", "note",
}


def _trim_prose(piece):
    """Drop the words in front of an equation, keeping the equation."""
    words = piece.split()
    while words and words[0].strip(",.:;").lower() in _PREAMBLE:
        words.pop(0)
    return " ".join(words)


def equations(text):
    """Equations stated in the text, as (left, right, variables).

    Found by cutting the text at clause boundaries and keeping the pieces that
    are entirely mathematical and contain exactly one equals sign. A single
    regex with non-greedy sides matched as little as possible and returned the
    tail of "x = y = z = 1" as though it were an equation — this discards that
    whole phrase instead, which is what it is: an assignment chain, not a
    claim about the system.
    """
    out = []
    for piece in _SPLIT.split(text or ""):
        piece = _trim_prose(piece.strip())
        if not piece or len(piece) > 190 or piece.count("=") != 1:
            continue
        if not _MATHY.match(piece):
            continue
        left, right = piece.split("=")
        left, right = left.strip(), right.strip()
        if not left or not right:
            continue
        names = (set(_VARS.findall(left.lower()))
                 | set(_VARS.findall(right.lower())))
        names -= set(CONSTS)
        # An equation with no variable is arithmetic, checked elsewhere; one
        # with five is not something a claimed triple can be tested against.
        if not names or len(names) > 4:
            continue
        probe = {n: 1.7 for n in names}
        if evaluate(left, probe) is None or evaluate(right, probe) is None:
            continue
        if (left, right) not in [(a, b) for a, b, _ in out]:
            out.append((left, right, sorted(names)))
    return out


_TUPLE = re.compile(r"\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)"
                    r"(?:\s*,\s*(-?\d+(?:\.\d+)?))?\s*\)")


def claimed_solutions(text):
    """Ordered tuples the text puts forward as answers, like (1, 1, 1)."""
    out = []
    for m in _TUPLE.finditer(text or ""):
        vals = [float(g) for g in m.groups() if g is not None]
        if 2 <= len(vals) <= 3:
            out.append((m.group(0), vals))
    return out


def check_solutions(text, order=("x", "y", "z")):
    """Put every claimed solution back into every stated equation.

    Only reports a failure when the equation genuinely uses exactly the
    variables the tuple supplies, and only when the mismatch is far larger
    than rounding. A checker that cries wolf gets switched off.
    """
    eqs = equations(text)
    sols = claimed_solutions(text)
    if not eqs or not sols:
        return []

    findings = []
    for shown, vals in sols:
        names = list(order[:len(vals)])
        vars_ = dict(zip(names, vals))
        for left, right, used in eqs:
            if set(used) - set(names):
                continue                      # equation needs more variables
            if not set(used):
                continue
            lv = evaluate(left, vars_)
            rv = evaluate(right, vars_)
            if lv is None or rv is None:
                continue
            scale = max(1.0, abs(lv), abs(rv))
            if abs(lv - rv) <= 1e-6 * scale:
                continue
            findings.append({
                "severity": "critical", "kind": "solution",
                "problem": f"it offers {shown} as a solution, but "
                           f"{left} = {right} gives {lv:g} = {rv:g} there",
                "correction": f"{shown} does not satisfy {left} = {right}",
            })
            break                              # one failure per claim is enough
    return findings


# --------------------------------------------------------------------------
# Surfaces, computed rather than chosen
# --------------------------------------------------------------------------
# The 3D surface scene offered six canned shapes — saddle, bowl, dome, ripple,
# well, plane — so a lesson on any other function got the nearest one, which
# is a picture of a different function. For mathematics that is not a rough
# edge, it is the whole content being wrong.
#
# A surface is the one visual on this board that can be produced exactly,
# because the lesson states the function and evaluating it is arithmetic. So
# the model gives the expression and the grid is computed here, point by
# point, with the same allowlisted evaluator used everywhere else in this
# file. Nothing executable is sent to the browser and nothing is executed
# here: the page receives a plain list of numbers.
GRID = 40                 # 41 x 41 points — smooth enough, ~1700 numbers
MAX_Z = 1e6


def surface(expr, span=4.0, n=GRID):
    """Height values for z = f(x, y) over a square grid, or None.

    Returns rows of z values from y = -span to +span, each row running
    x = -span to +span, with None where the function has no real value —
    a hole in the domain is a fact about the function and is drawn as one
    rather than filled in with a guess.
    """
    try:
        span = float(span)
    except (TypeError, ValueError):
        return None
    if not (0.1 <= span <= 50) or not (8 <= int(n) <= 80):
        return None
    n = int(n)
    src = _normalise(expr)
    if not src or len(src) > 200:
        return None
    # Parse once, then walk the same tree for every point: 1,681 re-parses of
    # the same string is the difference between instant and noticeable.
    try:
        tree = ast.parse(src, mode="eval")
    except SyntaxError:
        return None
    if sum(1 for _ in ast.walk(tree)) > MAX_NODES:
        return None

    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    if names - {"x", "y"} - set(CONSTS) - set(FUNCS):
        return None                       # a third variable is not a surface

    rows, seen = [], 0
    step = (2.0 * span) / n
    for j in range(n + 1):
        yv = -span + j * step
        row = []
        for i in range(n + 1):
            xv = -span + i * step
            try:
                v = _walk(tree, {"x": xv, "y": yv})
            except (Unsafe, ValueError, OverflowError, ZeroDivisionError,
                    TypeError):
                row.append(None)
                continue
            if v != v or abs(v) > MAX_Z:      # NaN, or off to infinity
                row.append(None)
                continue
            row.append(round(float(v), 4))
            seen += 1
        rows.append(row)
    # A function that is undefined nearly everywhere on this window is not
    # being shown honestly; better no picture than a scattering of fragments.
    if seen < (n + 1) * (n + 1) * 0.35:
        return None
    return rows
