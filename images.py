"""A real picture to go with the drawing, from whoever draws it best.

Every picture on this site so far has been drawn from numbers — canvas
sketches and procedural 3D. That was the right default and it stays: a
diagram built from the lesson's own values cannot show something the lesson
did not say. But a diagram of a mitochondrion is not a mitochondrion, and for
a great many topics the thing itself is what somebody needs to see.

Three sources, asked in order of how specific they are.

PubChem draws the actual structural formula for a named compound: ask for
glucose and you get glucose, because it is generated from the structure rather
than chosen by an editor. NASA covers astronomy, planetary science and earth
observation with its own photographs. Both are public domain, so a chemistry
or astronomy lesson carries no credit line at all. Wikimedia catches
everything else, and its files are credited because their licence says so.

A real picture was chosen over an image-generation model for three reasons, in
order of how much they matter here.

It costs nothing. Generating an image per lesson would be the single most
expensive thing in the product, on a site where the whole economics rests on
calling a model once per topic and caching the answer forever.

It is a photograph of the real thing. A generated picture of a plant cell is
a plausible-looking arrangement of shapes, and a student cannot tell which
parts of it are true. That failure mode is the same one the drawing rules and
the arithmetic checks exist to prevent, and it would be strange to spend all
that effort on the numbers and then invent the pictures.

And it is attributable. Every file carries a licence and an author, both of
which are shown. A generated image has no provenance to give.

Nothing here trusts a model with a URL. The topic goes to Wikimedia's own
search, and only a URL that Wikimedia itself returned — on a Wikimedia host,
over https — is ever handed to a browser.
"""
import re
from urllib.parse import quote

# Wikimedia asks for a real user agent identifying the application, and
# refuses anonymous library defaults. This is that.
UA = "Craxle/1.0 (https://craxle.com; learning platform) python-httpx"

API = "https://en.wikipedia.org/w/api.php"

# The only hosts a picture may come from. Wikimedia serves its files from
# upload.wikimedia.org; the rest are here because redirects between the
# project domains are normal and harmless.
_HOSTS = ("upload.wikimedia.org", "commons.wikimedia.org",
          "en.wikipedia.org", "wikimedia.org",
          # Public-domain sources, added deliberately and by exact name. A
          # picture may still only come from a host named here.
          "pubchem.ncbi.nlm.nih.gov", "images-assets.nasa.gov")

MIN_WIDTH = 240          # thumbnails smaller than this are icons, not pictures
TIMEOUT = 6.0            # a picture is a bonus; it never delays a lesson

# Subjects where a stock photograph adds nothing and often misleads: the
# search will happily return a portrait of a mathematician for "eigenvalue".
_NO_PHOTO = re.compile(
    r"\b(theorem|lemma|proof|equation|identity|inequality|algorithm|"
    r"complexity|derivative|integral|limit|matrix|eigen\w*|topology|"
    r"axiom|conjecture|polynomial|logarithm)\b", re.I)


def wanted(topic: str) -> bool:
    """Is this a topic where a photograph would actually help?

    Abstract mathematics is the clear case where it would not. Wikipedia has
    an article for every theorem and the lead image is usually a portrait of
    the person it is named after, which teaches nobody the theorem.
    """
    t = (topic or "").strip()
    return bool(t) and not _NO_PHOTO.search(t)


def _safe_url(url: str) -> str:
    """A URL is only usable if Wikimedia served it over https."""
    u = str(url or "")
    if not u.startswith("https://"):
        return ""
    host = u[8:].split("/", 1)[0].lower().split(":")[0]
    if host not in _HOSTS and not host.endswith(".wikimedia.org"):
        return ""
    return u


def _clean(html: str) -> str:
    """Wikimedia returns attribution as small HTML. Take the words only."""
    txt = re.sub(r"<[^>]+>", " ", str(html or ""))
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt[:160]


def clean(raw) -> dict:
    """Rebuild a picture from an untrusted dict, field by field.

    The same rule as every other structure in this product: nothing is passed
    through, everything is copied into a shape decided here.
    """
    if not isinstance(raw, dict):
        return {}
    url = _safe_url(raw.get("url"))
    if not url:
        return {}
    try:
        width = int(raw.get("width") or 0)
    except (TypeError, ValueError):
        width = 0
    return {
        "url": url,
        "width": width,
        "caption": str(raw.get("caption") or "")[:200],
        "author": _clean(raw.get("author")),
        "license": str(raw.get("license") or "")[:60],
        "page": _safe_url(raw.get("page")),
    }


def _parse(search_body, meta_body) -> dict:
    """The two Wikimedia responses into one picture, or nothing."""
    pages = ((search_body or {}).get("query") or {}).get("pages") or {}
    best = None
    for page in pages.values():
        thumb = page.get("thumbnail") or {}
        url = _safe_url(thumb.get("source"))
        if not url or int(thumb.get("width") or 0) < MIN_WIDTH:
            continue
        # Lowest index is Wikimedia's own best match for the search.
        if best is None or page.get("index", 99) < best.get("index", 99):
            best = {"index": page.get("index", 99), "url": url,
                    "width": int(thumb.get("width") or 0),
                    "caption": str(page.get("title") or ""),
                    "page": _safe_url(page.get("fullurl"))}
    if not best:
        return {}

    author = license_ = ""
    for page in (((meta_body or {}).get("query") or {}).get("pages")
                 or {}).values():
        for info in (page.get("imageinfo") or []):
            ext = info.get("extmetadata") or {}
            author = author or _clean((ext.get("Artist") or {}).get("value"))
            license_ = license_ or str(
                (ext.get("LicenseShortName") or {}).get("value") or "")[:60]
    best.pop("index", None)
    best["author"] = author
    best["license"] = license_
    return clean(best)


# ---- chemistry: the structure itself, drawn from the structure ----------
PUBCHEM = ("https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
           "{}/PNG?image_size=large")

# Words that mean "this topic is a substance", plus the giveaway of a formula.
_CHEM = re.compile(
    r"\b(molecul\w*|compound|structure of|formula of|reaction|acid|base|salt|"
    r"alkane|alkene|alkyne|alcohol|ester|amine|amide|ketone|aldehyde|"
    r"benzene|polymer|monomer|isomer|organic chem\w*|functional group)\b",
    re.I)

# A named substance, if the topic is plainly about one. PubChem resolves
# common names, so "table salt" and "aspirin" both work.
_LEAD = re.compile(r"^(?:the\s+)?(?:structure|formula|molecule)\s+of\s+(.+)$",
                   re.I)


def _compound(topic):
    """The substance this topic is about, or nothing.

    PubChem is a chemical index and will answer for names that are not being
    used chemically: it has an entry called "Saturn", so a lesson on the
    planet came back as a structural formula. Anything astronomical is
    refused here, and a topic with no chemical signal at all has to be a
    single word before it is even tried.
    """
    t = " ".join(str(topic or "").split())
    if _SPACE.search(t):
        return ""
    m = _LEAD.match(t)
    if m:
        t = m.group(1)
    t = t.strip(" .?!")
    # One or two words, and not a sentence about a process. A long phrase is
    # a lesson topic, not a compound, and PubChem would either miss or
    # return something surprising.
    if not t or len(t) > 40:
        return ""
    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9 ,'()\-]*$", t):
        return ""
    words = t.split()
    # A phrase is only a compound if the topic says so chemically
    # ("the structure of citric acid"). Without that signal, only a single
    # word is worth asking about — "the human heart" is not a molecule.
    if len(words) > 1 and not _CHEM.search(topic or ""):
        return ""
    return t if len(words) <= 3 else ""


async def _from_pubchem(client, topic):
    """A structural formula, or nothing. Public domain: no credit required."""
    name = _compound(topic)
    if not name:
        return {}
    try:
        r = await client.get(PUBCHEM.format(quote(name, safe="")),
                             timeout=TIMEOUT, headers={"User-Agent": UA})
        # PubChem answers 404 for anything it does not recognise as a
        # compound, which is exactly the filter wanted: no match, no picture.
        if r.status_code != 200 or "image" not in \
                r.headers.get("content-type", ""):
            return {}
        # A blank canvas is about 300 bytes. Benzene, a plain hexagon, is
        # only 800 — so the floor has to sit between them, not above both.
        if len(r.content) < 500:
            return {}
    except Exception as e:
        print(f"PubChem lookup failed for {name!r}: {type(e).__name__}: {e}")
        return {}
    return {"url": PUBCHEM.format(quote(name, safe="")), "width": 600,
            "caption": name, "author": "", "license": "", "page": ""}


# ---- astronomy and earth science: NASA's own photographs ----------------
NASA = "https://images-api.nasa.gov/search"
_SPACE = re.compile(
    r"\b(planet\w*|solar system|galax\w*|nebula|star|stellar|astronom\w*|"
    r"telescope|orbit\w*|satellite|spacecraft|rocket|launch|mars|venus|"
    r"jupiter|saturn|uranus|neptune|mercury|pluto|moon|lunar|sun|solar|"
    r"asteroid|comet|meteor|eclipse|cosmic|universe|black hole|supernova|"
    r"milky way|space station|hubble|webb|apollo|voyager|atmosphere of|"
    r"hurricane|cyclone|monsoon|glacier|volcano|earth observation)\b", re.I)


async def _from_nasa(client, topic):
    """A NASA photograph. Public domain: no credit required."""
    if not _SPACE.search(topic or ""):
        return {}
    try:
        r = await client.get(NASA, timeout=TIMEOUT, headers={"User-Agent": UA},
                             params={"q": str(topic)[:80],
                                     "media_type": "image"})
        if r.status_code != 200:
            return {}
        items = ((r.json() or {}).get("collection") or {}).get("items") or []
    except Exception as e:
        print(f"NASA lookup failed: {type(e).__name__}: {e}")
        return {}
    for it in items[:5]:
        links = it.get("links") or []
        data = (it.get("data") or [{}])[0]
        for link in links:
            href = str(link.get("href") or "")
            if not href.startswith("https://images-assets.nasa.gov/"):
                continue
            # "~thumb" is a postage stamp; ask for the medium rendition.
            href = href.replace("~thumb.", "~medium.").replace(
                "~small.", "~medium.")
            return {"url": href, "width": 800,
                    "caption": str(data.get("title") or "")[:120],
                    "author": "", "license": "", "page": ""}
    return {}


async def find(client, topic: str) -> dict:
    """One picture for a topic, or an empty dict.

    Never raises. A lesson without a photograph is a lesson; a lesson that
    failed to render because a picture service was slow is not.
    """
    if not wanted(topic):
        return {}
    q = str(topic).strip()[:120]
    if not q:
        return {}

    # Public-domain sources first. They are better pictures for the subjects
    # they cover — a structural formula is the compound, where an article's
    # lead image is whatever an editor chose — and they carry no attribution
    # obligation, so nothing appears under the picture at all.
    # NASA first. "Saturn" is unambiguously astronomical and ambiguously
    # chemical, so the more specific signal is asked first.
    for source in (_from_nasa, _from_pubchem):
        try:
            pic = clean(await source(client, q))
        except Exception as e:
            print(f"Picture source failed: {type(e).__name__}: {e}")
            continue
        if pic:
            return pic

    try:
        r = await client.get(API, timeout=TIMEOUT, headers={"User-Agent": UA},
                             params={
                                 "action": "query", "format": "json",
                                 "formatversion": "1",
                                 "generator": "search",
                                 "gsrsearch": q, "gsrlimit": "3",
                                 "gsrnamespace": "0",
                                 "prop": "pageimages|info",
                                 # "name" as well as "thumbnail": the licence
                                 # lives on the File: page and the filename is
                                 # the only way to ask for it. Without it every
                                 # picture came back uncredited and was then
                                 # discarded for being uncredited.
                                 "piprop": "thumbnail|name",
                                 "pithumbsize": "900",
                                 "inprop": "url",
                             })
        if r.status_code != 200:
            return {}
        body = r.json()
    except Exception as e:
        print(f"Picture search failed for {q!r}: {type(e).__name__}: {e}")
        return {}

    # The licence lives on the File: page, not on the article, so it is a
    # second call. Skipped rather than guessed at if it fails: an unattributed
    # image is one we do not show.
    titles = []
    for page in (((body or {}).get("query") or {}).get("pages") or {}).values():
        if page.get("pageimage"):
            titles.append("File:" + str(page["pageimage"]))
    meta = {}
    if titles:
        try:
            m = await client.get(API, timeout=TIMEOUT,
                                 headers={"User-Agent": UA},
                                 params={
                                     "action": "query", "format": "json",
                                     "formatversion": "1",
                                     "titles": "|".join(titles[:3]),
                                     "prop": "imageinfo",
                                     "iiprop": "extmetadata",
                                 })
            if m.status_code == 200:
                meta = m.json()
        except Exception:
            meta = {}

    pic = _parse(body, meta)
    # Attribution is not optional HERE. Wikimedia's files are licensed on the
    # condition that the author is named, so one that arrives without an
    # author or a licence is dropped rather than shown bare. The public-domain
    # sources above are exempt because there is genuinely nobody to credit.
    if pic and not (pic.get("author") or pic.get("license")):
        return {}
    return pic


PROMPT = ""   # nothing is asked of the model: the picture is looked up, not written
