"""Orbits, checked against Kepler rather than asserted.

The orbit scene spaced its bodies by index — first at 2, next at 3.3, next at
4.6 — so every system came out evenly spread. The solar system is the opposite
of evenly spread: the four inner planets fit inside 1.6 AU and Neptune is at
30, and that emptiness is the most surprising true thing about it. A diagram
that hides it has taught the wrong shape.

The best test of the table is the law it should obey. Kepler's third says a
cubed equals T squared in these units, for every planet, and nothing in the
table was fitted to make that true — the distances and periods were taken
separately from published values, so agreement is evidence they are right.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import orbits                                      # noqa: E402

PASS = FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {name}" + (f"  ({detail})" if detail else ""))
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


# ---- the law the table must obey ------------------------------------
for planet in orbits.PLANETS:
    err = orbits.kepler_error(planet)
    check(f"{planet}: a cubed = T squared", err < 0.005,
          f"off by {err * 100:.2f}%")

# ---- against the published figures ----------------------------------
PUBLISHED = {
    "mercury": (0.3871, 0.2408), "venus": (0.7233, 0.6152),
    "earth": (1.0, 1.0), "mars": (1.5237, 1.8808),
    "jupiter": (5.2029, 11.862), "saturn": (9.5367, 29.457),
    "uranus": (19.189, 84.011), "neptune": (30.070, 164.79),
}
for planet, (au, yr) in PUBLISHED.items():
    a, t = orbits.PLANETS[planet][0], orbits.PLANETS[planet][1]
    check(f"{planet} is {au} AU", abs(a - au) < 1e-3, str(a))
    check(f"{planet} takes {yr} years", abs(t - yr) < 1e-2, str(t))

# ---- order and spacing ----------------------------------------------
sol = orbits.clean("the solar system")
names = [b["name"] for b in sol["bodies"]]
check("eight planets, Pluto not among them",
      names == ["Mercury", "Venus", "Earth", "Mars", "Jupiter", "Saturn",
                "Uranus", "Neptune"], str(names))
aus = [b["au"] for b in sol["bodies"]]
check("distances increase outward", aus == sorted(aus))
radii = [b["r"] for b in sol["bodies"]]
check("and so do the drawn radii", radii == sorted(radii))
check("the inner four are drawn closer together than the outer four",
      (radii[3] - radii[0]) < (radii[7] - radii[4]),
      f"{radii[3] - radii[0]:.2f} vs {radii[7] - radii[4]:.2f}")
check("the drawing is not evenly spaced",
      abs((radii[1] - radii[0]) - (radii[7] - radii[6])) > 0.15,
      "even spacing would teach the wrong shape")
check("the compression is declared", bool(sol.get("scale_note")),
      sol.get("scale_note", ""))
check("outer planets orbit more slowly",
      sol["bodies"][0]["speed"] > sol["bodies"][-1]["speed"])

# ---- naming ----------------------------------------------------------
check("inner planets", [b["name"] for b in orbits.clean(
    "the inner planets")["bodies"]]
    == ["Mercury", "Venus", "Earth", "Mars"])
check("outer planets", len(orbits.clean("the outer planets")["bodies"]) == 4)
check("one planet on its own",
      [b["name"] for b in orbits.clean("Jupiter")["bodies"]] == ["Jupiter"])
check("two named planets come back in order",
      [b["name"] for b in orbits.clean("Mars and Earth")["bodies"]]
      == ["Earth", "Mars"])
check("Pluto if asked for by name",
      [b["name"] for b in orbits.clean("Pluto")["bodies"]] == ["Pluto"])

for absent in ("photosynthesis", "aircraft gearbox", "", None, "   "):
    check(f"{str(absent)[:20]!r} is not an orbit topic",
          orbits.clean(absent) == {})

# --------------------------------------------------------------------------
print("\nMercury the metal is not Mercury the planet")
# Reported from a live classroom board: a teacher typed "mercury liquid"
# into 3D structures and was shown the Solar System. The planet matched, and
# the word saying WHICH mercury was meant was thrown away.
#
# A chemistry class asks for mercury far more often than an astronomy one
# does, and Earth collides twice over — an earth wire, the earth's crust. So
# a planet name arriving with a word that plainly belongs to another subject
# is not a request for an orbit. Nothing comes back rather than the wrong
# picture, and the caller goes on to the molecule and lattice paths, which
# is where liquid mercury belongs.
for topic in ("mercury liquid", "liquid mercury", "mercury metal",
              "mercury thermometer", "mercury poisoning", "mercury vapour",
              "the atomic structure of mercury", "earth wire", "earthing",
              "the earth's crust", "saturn the roman god"):
    check(f"{topic!r} is not an orbit topic", orbits.find(topic) is None)

# ...and the sky still works, which is the half a filter like this breaks.
for topic in ("mercury", "mercury orbit", "orbit of mercury around the sun",
              "earth", "the earth and the moon", "the solar system",
              "inner planets", "jupiter"):
    check(f"{topic!r} still is one", orbits.find(topic) is not None)
check("the whole system is still eight bodies",
      len(orbits.find("the solar system")["bodies"]) == 8)

print(f"\nPASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
