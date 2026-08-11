"""Orbits at their measured distances and periods.

The orbit scene spaced its bodies by index — the first at 2, the next at 3.3,
the next at 4.6 — so every system came out evenly spread. The solar system is
the opposite of evenly spread: the four inner planets fit inside 1.6 AU and
Neptune is at 30, and that emptiness is the single most surprising true thing
about it. A diagram that hides it has taught the wrong shape.

So the distances and periods are the measured ones, and the drawing uses the
square root of the distance for its radius. That is a choice worth stating: at
true scale Mercury and Venus overlap the Sun's disc on any screen, and at even
spacing the system is a lie. The square root keeps the order and the growing
gaps while fitting on a board, and the real number is printed beside each body
so nothing is hidden by the compression.

Kepler's third law is checked against the table rather than asserted: a cubed
over T squared is one for every planet, which is both a test of these numbers
and the thing a lesson on orbits is usually about.
"""
import math
import re

# name -> (semi-major axis in AU, orbital period in years, equatorial radius
#          in km, colour)
#
# IAU and NASA fact sheet values. Pluto is here because lessons still ask
# about it, labelled for what it is.
PLANETS = {
    "mercury": (0.3871, 0.2408, 2440, 0xB0A9A0),
    "venus": (0.7233, 0.6152, 6052, 0xE8CDA0),
    "earth": (1.0000, 1.0000, 6371, 0x4A90D9),
    "mars": (1.5237, 1.8808, 3390, 0xD9603B),
    "jupiter": (5.2029, 11.862, 69911, 0xD9A066),
    "saturn": (9.5367, 29.457, 58232, 0xE3C88F),
    "uranus": (19.189, 84.011, 25362, 0x8FD9D9),
    "neptune": (30.070, 164.79, 24622, 0x4666C4),
    "pluto": (39.482, 247.94, 1188, 0xC4B5A0),
}

SUN = {"name": "Sun", "radius_km": 696000, "colour": 0xFFCC55}

# Everything a lesson might call the whole system.
_WHOLE = ("solar system", "the planets", "planets", "planetary system",
          "inner planets", "outer planets", "orbits of the planets")


def kepler_error(name):
    """How far this planet departs from a cubed = T squared, as a fraction.

    Zero would be exact. Every value here should come out under a percent,
    which is a check on the table and the reason the table is worth having:
    a lesson that states Kepler's third law beside invented distances is
    stating something the picture contradicts.
    """
    a, t = PLANETS[name][0], PLANETS[name][1]
    return abs(a ** 3 - t ** 2) / (t ** 2)


def _body(name):
    a, period, radius_km, colour = PLANETS[name]
    return {
        "name": name.title(),
        "au": a,
        "years": period,
        "radius_km": radius_km,
        "color": colour,
        # Drawn on the square root of the true distance. At true scale the
        # inner planets sit inside the Sun's disc on any screen; evenly
        # spaced, the system is a lie. This keeps the order and the widening
        # gaps, and the real figure is printed beside each body.
        "r": round(2.0 + math.sqrt(a) * 2.6, 3),
        "size": round(0.16 + math.log10(radius_km) * 0.10, 3),
        "speed": round(0.55 / (period ** 0.5), 4),
    }


# Mercury is a planet and it is also a metal, and a chemistry class asks for
# it far more often than an astronomy one does. "mercury liquid" drew the
# Solar System, because the planet matched and the word that said which
# mercury was meant was thrown away.
#
# Earth is the same collision twice over — an earth wire, the earth's crust —
# and Saturn, Jupiter and Neptune turn up in mythology and in brand names.
# So a planet name arriving with a word that plainly belongs to another
# subject is not a request for an orbit, and this returns nothing rather
# than the wrong picture. Nothing is the honest answer: the caller then
# tries the molecule and lattice paths, which is where liquid mercury
# actually belongs.
_NOT_SKY = re.compile(
    r"\b(liquid|metal|metallic|element|elemental|atom|atomic|isotope|"
    r"thermometer|barometer|amalgam|poison\w*|toxic\w*|vapou?r|"
    r"boiling|melting|freezing|density|viscosity|conduct\w*|"
    r"symbol|periodic|valency|oxide|chloride|sulphide|sulfide|"
    r"compound|molecule|molecular|bond\w*|lattice|crystal|"
    r"wire|earthing|earthed|crust|mantle|soil|"
    r"god|goddess|myth\w*|roman|greek)\b", re.I)


def find(topic):
    """The measured bodies for this topic, or nothing."""
    t = " ".join(str(topic or "").lower().split())
    if not t:
        return None
    if _NOT_SKY.search(t):
        return None

    named = [p for p in PLANETS if p in t]
    if any(w in t for w in _WHOLE):
        if "inner" in t:
            names = ["mercury", "venus", "earth", "mars"]
        elif "outer" in t:
            names = ["jupiter", "saturn", "uranus", "neptune"]
        else:
            names = [p for p in PLANETS if p != "pluto"]
    elif named:
        names = named
    else:
        return None

    order = list(PLANETS)
    names.sort(key=order.index)
    return {
        "centre": SUN["name"],
        "centre_r": 0.9,
        "centre_color": SUN["colour"],
        "bodies": [_body(n) for n in names],
        "measured": True,
        "scale_note": "distances √-scaled to fit; real values shown",
    }


def clean(topic):
    """A measured orbit scene, or an empty dict."""
    got = find(topic)
    return got or {}
