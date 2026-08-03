"""A real photograph to go with the drawing, from Wikimedia.

Every picture on this site so far has been drawn from numbers — canvas
sketches and procedural 3D. That was the right default and it stays: a
diagram built from the lesson's own values cannot show something the lesson
did not say. But a diagram of a mitochondrion is not a mitochondrion, and for
a great many topics the thing itself is what somebody needs to see.

Wikimedia was chosen over an image-generation model for three reasons, in
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
          "en.wikipedia.org", "wikimedia.org")

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
    # Attribution is not optional. Without an author and a licence there is
    # nothing to credit, so the picture is not used.
    if pic and not (pic.get("author") or pic.get("license")):
        return {}
    return pic


PROMPT = ""   # nothing is asked of the model: the picture is looked up, not written
