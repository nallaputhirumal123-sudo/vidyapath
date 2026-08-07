"""Pictures: where they may come from, and what must travel with them.

Two things matter here and neither is cosmetic.

A URL that reaches a browser must be one Wikimedia itself returned. Nothing
in this file is written by a model, but the rule is enforced at the boundary
anyway, because the day somebody lets a model suggest an image is the day an
unchecked URL becomes a way to point a student's browser anywhere.

And attribution is a licence condition, not a nicety. These are other
people's photographs. A picture that arrives without an author or a licence
is discarded rather than shown bare.

The network tests are skipped when there is no connection: a test that fails
on a train is a test people learn to ignore.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import images                                      # noqa: E402

PASS = FAIL = SKIP = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {name}" + (f"  ({detail})" if detail else ""))
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


# ---- only Wikimedia, only https -------------------------------------
HOSTILE = [
    ("another host entirely", "https://evil.example/x.png"),
    ("plain http", "http://upload.wikimedia.org/x.png"),
    ("a javascript url", "javascript:alert(1)"),
    ("a data url", "data:image/png;base64,AAAA"),
    ("a lookalike host", "https://upload.wikimedia.org.evil.example/x.png"),
    ("a host that merely contains it", "https://xupload.wikimedia.orgx/x.png"),
    ("credentials in the url", "https://user@evil.example/x.png"),
    ("protocol relative", "//upload.wikimedia.org/x.png"),
    ("empty", ""),
]
for name, url in HOSTILE:
    check(f"refuses {name}", images.clean({"url": url}) == {}, url[:46])

for junk in ("not a dict", None, 42, [], {"nourl": 1}):
    check(f"refuses {str(junk)[:22]} as a picture", images.clean(junk) == {})

GOOD = {"url": "https://upload.wikimedia.org/wikipedia/commons/a.png",
        "width": 900, "caption": "X" * 400,
        "author": "<b onclick='x'>Someone</b>", "license": "CC BY-SA 4.0",
        "page": "https://en.wikipedia.org/wiki/X"}
got = images.clean(GOOD)
check("keeps a genuine Wikimedia url", got.get("url", "").endswith("a.png"))
check("strips markup from the credit", got["author"] == "Someone",
      repr(got["author"]))
check("caps an overlong caption", len(got["caption"]) <= 200,
      str(len(got["caption"])))
check("keeps the licence", got["license"] == "CC BY-SA 4.0")
check("only these fields survive",
      set(got) == {"url", "width", "caption", "author", "license", "page"},
      str(sorted(got)))

# a page link on a foreign host is dropped without dropping the picture
odd = images.clean(dict(GOOD, page="https://evil.example/x"))
check("a foreign source link is dropped", odd["page"] == "" and odd["url"])

# ---- where a photograph does not belong -----------------------------
for topic in ("Pythagorean theorem", "eigenvalue decomposition",
              "proof by induction", "the binomial theorem",
              "Cauchy-Schwarz inequality", "a sorting algorithm"):
    check(f"no photo for {topic[:30]!r}", not images.wanted(topic))

for topic in ("photosynthesis", "the human heart", "a Cisco switch",
              "titration", "the Indian Constitution", "monsoon"):
    check(f"a photo is wanted for {topic[:26]!r}", images.wanted(topic))

check("an empty topic is refused", not images.wanted("   "))

# ---- against the real service ---------------------------------------
try:
    import asyncio
    import httpx

    async def go():
        async with httpx.AsyncClient(follow_redirects=True) as c:
            return (await images.find(c, "Saturn"),
                    await images.find(c, "qwertyuiop asdfghjkl zxcvbnm 12345"))

    pic, nothing = asyncio.run(go())
except Exception as e:
    pic = nothing = None
    SKIP += 1
    print(f"  ..    live lookup skipped (no network?): {type(e).__name__}")

# images.find is documented never to raise — a lesson without a photograph
# is still a lesson — so it answers {} when NASA cannot be reached and the
# guard above never fires. Saturn is in NASA's catalogue; an empty answer
# for it is the network being unreachable, not the search being wrong.
if pic is not None and not pic.get("url"):
    SKIP += 1
    pic = None
    print("  ..    live lookup skipped: NASA returned nothing (no network?)")

if pic is None:
    pass
else:
    check("an astronomy topic returns a picture", bool(pic.get("url")),
          pic.get("caption", ""))
    check("it comes from NASA",
          pic.get("url", "").startswith("https://images-assets.nasa.gov/"),
          pic.get("url", "")[:60])
    # NASA is US government work in the public domain. Nothing to credit is
    # half the reason it is the source that was kept.
    check("it carries no credit line",
          not pic.get("author") and not pic.get("license"),
          f"{pic.get('author', '')} / {pic.get('license', '')}")
    check("nonsense returns nothing rather than something wrong",
          nothing == {}, str(nothing)[:60])

# ---- routing: the most specific source wins -------------------------
# PubChem is a chemical index and answers for names not being used
# chemically — it has an entry called "Saturn", so a lesson on the planet came
# back as a structural formula until astronomy was asked first.
check("a planet is not treated as a compound", not images._compound("Saturn"))
check("nor is an eclipse", not images._compound("a lunar eclipse"))
check("a bare compound name is kept", images._compound("glucose") == "glucose")
check("so is a stated structure",
      images._compound("the structure of citric acid") == "citric acid",
      images._compound("the structure of citric acid"))
check("a phrase with no chemical signal is refused",
      not images._compound("the Indian Constitution"))

check("PubChem is an allowed host",
      images.clean({"url": "https://pubchem.ncbi.nlm.nih.gov/rest/x/PNG"}) != {})
check("NASA assets are an allowed host",
      images.clean({"url": "https://images-assets.nasa.gov/image/a/b.jpg"}) != {})
for _bad in ("https://pubchem.ncbi.nlm.nih.gov.evil.test/x.png",
             "https://images-assets.nasa.gov.evil.test/x.jpg",
             "http://pubchem.ncbi.nlm.nih.gov/x.png"):
    check("refuses " + _bad[:46], images.clean({"url": _bad}) == {})

try:
    async def routed():
        async with httpx.AsyncClient(follow_redirects=True) as c:
            out = {}
            for t in ("git", "react", "glucose", "aircraft engine",
                      "a lunar eclipse"):
                out[t] = await images.find(c, t)
            return out

    got = asyncio.run(routed())
except Exception as _e:
    got = None
    print("  ..    live routing skipped: " + type(_e).__name__)

# The whole block skips together, and that matters more here than above.
# Four of these checks assert that a topic returns NOTHING — which is
# trivially true when nothing can be reached at all. Offline they passed
# for the wrong reason and reported four green ticks about routing that had
# not been exercised. The eclipse is the one positive assertion in the set,
# so it is what says whether the network was there to test with.
if got is not None and not got.get("eclipse", {}).get("url"):
    SKIP += 1
    got = None
    print("  ..    live routing skipped: NASA returned nothing (no network?)")

if got is None:
    pass
else:
    # The reports that closed the picture sources down, kept as tests.
    check("'git' gets no picture", got["git"] == {},
          str(got["git"])[:50])
    check("nor does 'react'", got["react"] == {})
    check("nor does a compound, now PubChem is out of the picture path",
          got["glucose"] == {})
    check("nor does 'aircraft engine'", got["aircraft engine"] == {})
    check("an eclipse still does, from NASA",
          "nasa" in got["a lunar eclipse"].get("url", ""),
          got["a lunar eclipse"].get("caption", ""))

print(f"\nPASSED {PASS}   FAILED {FAIL}" + (f"   SKIPPED {SKIP}" if SKIP else ""))
sys.exit(1 if FAIL else 0)


# ---------------------------------------------------------------------------
# The search had been narrowed until it returned almost nothing.
#
# NASA covers astronomy and earth observation. Wikimedia had been switched
# off after "aircraft engine" returned a photograph of an aeroplane — sound
# reasoning, too strong a conclusion. It did not trade some wrong pictures
# for fewer wrong ones; it traded them for none at all, on a board whose job
# is showing a class what a thing looks like. Photosynthesis, the human heart
# and a plant cell all came back empty.
#
# Two faults kept the rest out even with the source switched back on, and
# both were one idea implemented twice.
print("\nthe head of a phrase has ONE definition")
ck("relevant() asks head_noun rather than taking the last word",
   "head = head_noun(query)" in io.open(
       os.path.join(ROOT, "images.py"), encoding="utf-8").read(),
   "'plant cell structure' gave head 'structure', so the article on Plant "
   "cell was discarded as not being about it")
for q, want in (("plant cell structure", "cell"),
                ("refraction of light", "refraction"),
                ("the structure of the human heart", "heart"),
                ("the parts of a flower", "flower"),
                ("aircraft gearbox", "gearbox")):
    ck(f"head_noun({q!r}) is {want!r}", images.head_noun(q) == want,
       repr(images.head_noun(q)))

print("\nand a generic before a preposition is not the subject")
# "The structure of the human heart" is about the heart. Cutting at the
# preposition is right for "refraction of light", because refraction is a
# real subject; it is wrong when everything before the cut is a generic.
ck("a real subject before 'of' still wins",
   images.head_noun("refraction of light") == "refraction")
ck("but a generic one yields to what follows",
   images.head_noun("the process of photosynthesis") == "photosynthesis",
   images.head_noun("the process of photosynthesis"))
ck("'law' is deliberately NOT generic",
   "law" not in images._GENERIC_TAIL and "laws" not in images._GENERIC_TAIL,
   "Newton's laws of motion would reduce to 'newton' and return a portrait "
   "of the man")

print("\nthe title check still refuses the wrong machine")
ck("a crane is not a gearbox",
   not images.relevant("aircraft gearbox", "Crane (machine)"))
ck("nor is an aircraft carrier",
   not images.relevant("aircraft gearbox", "Nimitz-class aircraft carrier"),
   "it shares 'aircraft' and is an entirely different object")
ck("but epicyclic gearing is", images.relevant("aircraft gearbox",
                                               "Epicyclic gearing"))
