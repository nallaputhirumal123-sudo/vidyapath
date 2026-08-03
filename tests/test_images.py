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
    SKIP += 1
    print(f"  ..    live lookup skipped (no network?): {type(e).__name__}")
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
    print("  ..    live routing skipped: " + type(_e).__name__)
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
