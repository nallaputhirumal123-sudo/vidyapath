"""Gate 1: everything about a lesson that a machine can check for itself.

A learning platform's only real failure mode is teaching something wrong,
confidently. A student who learns a wrong constant and writes it in an exam
has been actively harmed, and the cache makes it worse — one bad lesson is
served to everyone who asks that question afterwards.

So anything machine-checkable is checked here, before a lesson is stored.
This costs nothing: no model call, no network, no per-student expense. It runs
on every lesson and it never asks anybody's opinion — every finding below is
either arithmetic or a lookup against a fixed table.

Deliberately narrow. It only reports what it can prove, because a checker that
guesses trains people to ignore it. Anything requiring judgement belongs to a
later gate, and things this cannot see are not claimed to be verified.
"""
import math
import re

# --------------------------------------------------------------------------
# Physical constants, from CODATA. Never from a model's memory — that is the
# entire point of the table.
# --------------------------------------------------------------------------
CONSTANTS = {
    "g": (9.80665, "m/s^2", ("gravity", "acceleration due to gravity",
                             "gravitational acceleration")),
    "c": (2.99792458e8, "m/s", ("speed of light",)),
    "h": (6.62607015e-34, "J s", ("planck", "planck's constant")),
    "N_A": (6.02214076e23, "/mol", ("avogadro", "avogadro's number",
                                    "avogadro constant")),
    "R": (8.314462, "J/mol/K", ("gas constant", "universal gas constant",
                                "molar gas constant")),
    "e": (1.602176634e-19, "C", ("elementary charge", "charge on an electron",
                                 "electron charge")),
    "k_B": (1.380649e-23, "J/K", ("boltzmann", "boltzmann constant")),
    "m_e": (9.1093837e-31, "kg", ("electron mass", "mass of an electron")),
    "m_p": (1.67262192e-27, "kg", ("proton mass", "mass of a proton")),
    "G": (6.67430e-11, "N m^2/kg^2", ("gravitational constant",)),
    "F": (96485.33, "C/mol", ("faraday", "faraday constant")),
    "atm": (101325.0, "Pa", ("atmospheric pressure", "standard pressure",
                             "one atmosphere")),
    "Vm": (22.414, "L/mol", ("molar volume", "molar volume at stp")),
    "T0": (-273.15, "degC", ("absolute zero",)),
}

# Teaching approximations that are not errors. g = 10 is used deliberately in
# school mechanics and flagging it would make the checker noise.
ACCEPTED = {
    "g": (9.8, 9.81, 10.0),
    "c": (3.0e8,),
    "N_A": (6.02e23, 6.023e23),
    "R": (8.31, 8.314),
    "Vm": (22.4,),
}

TOLERANCE = 0.02          # 2% — tighter than this and rounding trips it


def _close(a, b, tol=TOLERANCE):
    if b == 0:
        return abs(a) < 1e-12
    return abs(a - b) / abs(b) <= tol


_NUM = r"[-+]?\d[\d,]*\.?\d*(?:\s*[x×*]\s*10\s*\^?\s*[-+]?\d+|[eE][-+]?\d+)?"


def _value(s):
    """Parse a number, including '3 x 10^8' and '6.022e23'."""
    s = s.strip().replace(",", "")
    m = re.match(r"^([-+]?\d*\.?\d+)\s*[x×*]\s*10\s*\^?\s*([-+]?\d+)$", s)
    if m:
        try:
            return float(m.group(1)) * (10 ** int(m.group(2)))
        except ValueError:
            return None
    try:
        return float(s)
    except ValueError:
        return None


def constants(text):
    """Stated values of named physical constants, checked against the table."""
    out = []
    low = (text or "").lower()
    for key, (true, unit, names) in CONSTANTS.items():
        for name in names:
            # "avogadro's number is 6.02 x 10^23", "g = 9.8"
            for m in re.finditer(
                    re.escape(name) + r"[^.\n]{0,40}?(?:is|=|of|about)\s*(" +
                    _NUM + r")", low):
                got = _value(m.group(1))
                if got is None:
                    continue
                if _close(got, true) or any(_close(got, a, 1e-9)
                                            for a in ACCEPTED.get(key, ())):
                    continue
                out.append({
                    "severity": "critical", "kind": "constant",
                    "problem": f"{name} is given as {m.group(1).strip()}",
                    "correction": f"{name} is {true:g} {unit}",
                })
    return out


def arithmetic(text):
    """Simple stated sums, checked. 'so 2 x 3 = 7' is catchable and worth it."""
    out = []
    pattern = (r"(" + _NUM + r")\s*([+\-x×*/])\s*(" + _NUM +
               r")\s*=\s*(" + _NUM + r")")
    for m in re.finditer(pattern, text or ""):
        a, op, b, c = (_value(m.group(1)), m.group(2),
                       _value(m.group(3)), _value(m.group(4)))
        if a is None or b is None or c is None:
            continue
        try:
            if op == "+":
                want = a + b
            elif op == "-":
                want = a - b
            elif op in "x×*":
                want = a * b
            else:
                if b == 0:
                    continue
                want = a / b
        except (ValueError, OverflowError, ZeroDivisionError):
            continue
        # Generous, because a lesson legitimately rounds its own working.
        if _close(c, want, 0.01):
            continue
        out.append({
            "severity": "critical", "kind": "arithmetic",
            "problem": f"it says {m.group(0).strip()}",
            "correction": f"{a:g} {op} {b:g} = {want:g}",
        })
    return out


# A quantity and the units it can be measured in. Only unambiguous pairs —
# "power" in watts, never "current" in amps-or-coulombs-depending.
UNITS = {
    "force": ({"n", "newton", "newtons", "kn"}, "newtons"),
    "energy": ({"j", "joule", "joules", "kj", "mj", "ev", "kwh", "cal",
                "kcal"}, "joules"),
    "work": ({"j", "joule", "joules", "kj", "mj"}, "joules"),
    "power": ({"w", "watt", "watts", "kw", "mw", "hp"}, "watts"),
    "pressure": ({"pa", "pascal", "pascals", "kpa", "mpa", "bar", "atm",
                  "psi", "mmhg", "torr"}, "pascals"),
    "frequency": ({"hz", "hertz", "khz", "mhz", "ghz"}, "hertz"),
    "charge": ({"c", "coulomb", "coulombs", "mc"}, "coulombs"),
    "resistance": ({"ohm", "ohms", "kohm", "mohm"}, "ohms"),
    "voltage": ({"v", "volt", "volts", "mv", "kv"}, "volts"),
    "current": ({"a", "amp", "amps", "ampere", "amperes", "ma"}, "amperes"),
    "wavelength": ({"m", "metre", "metres", "meter", "meters", "nm", "mm",
                    "cm", "km", "pm", "angstrom"}, "metres"),
}
_UNIT_WORD = re.compile(r"[a-zA-Zµ]+")


def units(text):
    """A quantity stated in a unit that cannot measure it."""
    out = []
    low = (text or "").lower()
    for quantity, (allowed, expect) in UNITS.items():
        for m in re.finditer(
                re.escape(quantity) + r"\s+(?:of|is|=|:)?\s*" + _NUM +
                r"\s*([a-zA-Zµ]+)", low):
            unit = m.group(1).strip(".,;:")
            if not unit or unit in allowed:
                continue
            # Only complain when the word is a unit belonging to something
            # else. An ordinary word after a number is prose, not a claim.
            elsewhere = any(unit in a for q, (a, _) in UNITS.items()
                            if q != quantity)
            if not elsewhere:
                continue
            out.append({
                "severity": "major", "kind": "units",
                "problem": f"{quantity} is given in {unit}",
                "correction": f"{quantity} is measured in {expect}",
            })
    return out


def schema(lesson):
    """Structural faults: things that point at nothing, or sit off the page."""
    out = []
    steps = lesson.get("steps") or []
    for i, st in enumerate(steps):
        d = st.get("draw")
        if not d:
            continue
        ids = set(d.get("ids") or [])
        for r in (st.get("reveal") or []):
            if r not in ids:
                out.append({
                    "severity": "major", "kind": "schema",
                    "problem": f"step {i + 1} reveals '{r}', which the drawing "
                               f"does not define",
                    "correction": "remove the reveal or add the element",
                })
        # Everything off-canvas is a drawing nobody can see.
        visible = 0
        for e in d.get("elements") or []:
            x = e.get("cx", e.get("x", e.get("x1", 500)))
            y = e.get("cy", e.get("y", e.get("y1", 300)))
            if -50 <= x <= 1050 and -50 <= y <= 650:
                visible += 1
        if d.get("elements") and visible == 0:
            out.append({
                "severity": "critical", "kind": "schema",
                "problem": f"step {i + 1}'s drawing is entirely off the canvas",
                "correction": "coordinates belong in 0-1000 by 0-600",
            })

        # A plot that marks a point should mark one its own curve passes
        # through, or the annotation contradicts the graph under it.
        sk = st.get("sketch")
        if sk and sk.get("kind") == "plot":
            for mk in sk.get("marks") or []:
                near = False
                for ser in sk.get("series") or []:
                    for px, py in ser.get("points") or []:
                        if (abs(px - mk["x"]) <= 0.06 * max(1, abs(px)) + 0.2
                                and abs(py - mk["y"]) <=
                                0.08 * max(1, abs(py)) + 0.5):
                            near = True
                            break
                    if near:
                        break
                if not near:
                    out.append({
                        "severity": "major", "kind": "schema",
                        "problem": f"the plot marks '{mk['label']}' at "
                                   f"({mk['x']:g}, {mk['y']:g}), which is not "
                                   f"on any curve it draws",
                        "correction": "move the mark onto the data",
                    })
    return out


def run(lesson):
    """Every check, over a whole lesson. Returns findings, worst first."""
    if not isinstance(lesson, dict):
        return []
    prose = []
    for st in (lesson.get("steps") or []):
        for k in ("t", "where", "code"):
            if st.get(k):
                prose.append(str(st[k]))
    for k in ("title", "takeaway"):
        if lesson.get(k):
            prose.append(str(lesson[k]))
    text = "\n".join(prose)

    found = constants(text) + arithmetic(text) + units(text) + schema(lesson)
    order = {"critical": 0, "major": 1, "minor": 2}
    found.sort(key=lambda f: order.get(f["severity"], 3))
    # The same wrong constant repeated in four steps is one problem.
    seen, unique = set(), []
    for f in found:
        key = (f["kind"], f["problem"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(f)
    return unique[:12]


def verdict(findings):
    """What to do with a lesson, given what was found.

    A critical finding means it must not be cached: caching is what turns one
    wrong answer into everyone's wrong answer. It can still be shown, marked
    down, because a lesson with one bad number is usually still worth reading
    and refusing outright teaches nobody anything.
    """
    if any(f["severity"] == "critical" for f in findings):
        return {"cache": False, "confidence": "low", "state": "flagged"}
    if findings:
        return {"cache": True, "confidence": "medium", "state": "checked"}
    return {"cache": True, "confidence": "high", "state": "checked"}
