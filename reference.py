"""A wider base to answer from, for the subjects our corpus does not hold.

`corpus.db` is 7,523 passages and every one of them is from this site's own
coding and CS tracks. That is the right thing to prefer where it covers the
question, and it covers a narrow slice of what people ask: a B.Tech
thermodynamics question, a medical question about the nephron, a chemistry
question about titration all retrieve nothing, and the board answers those
from the model's own memory with no source behind it at all.

NCERT is the plan and remains the plan — four hundred books, ingested into the
on-disk index, which is a long data job and not something a request can do.
This is what stands in the gap meanwhile, and it is not a stopgap in any
embarrassing sense: an encyclopaedia article about the thing being asked is a
better source than nothing, it is openly licensed, and the model is told to
follow it rather than improvise around it.

Three decisions worth stating.

**Only Wikipedia's own extract.** Not a search engine, not a scrape, not a
page fetched and stripped. The REST summary endpoint returns an article's
lead as plain text, which is the shape a prompt wants and nothing more.
Nothing here follows a link, and no URL a model produced is ever fetched.

**It never overrides our own material.** Where the corpus has the answer this
is not asked for, and where both exist the site's own lesson wins: a learner
who reads the lesson and then asks the board must not be told something
different by the same site.

**It is free and it is cached.** No model call, one HTTP request, and the
lesson it feeds is cached against its question — so a class of thirty asking
the same thing pays for one lookup between them.
"""
import asyncio
import re

API = "https://en.wikipedia.org/api/rest_v1/page/summary/"
SEARCH = "https://en.wikipedia.org/w/api.php"
UA = "Craxle/1.0 (https://craxle.com; teaching)"
TIMEOUT = 6.0
MIN_CHARS = 220          # shorter than this is a stub, not an answer
MAX_CHARS = 2400         # a lead section, not a whole article

_WS = re.compile(r"\s+")
_SIGNPOST_TITLE = re.compile(r"\b(disambiguation|list of|index of|outline of)\b",
                             re.I)
_SIGNPOST_TEXT = re.compile(r"\bmay refer to\b|\bmay also refer to\b", re.I)


def _clean(text):
    return _WS.sub(" ", str(text or "")).strip()[:MAX_CHARS]


def _usable(data):
    """Is this an article about a thing, or a signpost to other articles?

    Disambiguation and list pages are the two that look like answers and are
    not. "Mercury may refer to:" is a worse source than silence, because the
    model will happily write a confident lesson out of it.
    """
    if not isinstance(data, dict):
        return False
    if str(data.get("type") or "standard") != "standard":
        return False
    if _SIGNPOST_TITLE.search(str(data.get("title") or "")):
        return False
    extract = str(data.get("extract") or "")
    if len(extract) < MIN_CHARS:
        return False
    if _SIGNPOST_TEXT.search(extract[:220]):
        return False
    return True


async def _summary(client, title):
    """One article's lead, or None. Never raises."""
    try:
        r = await client.get(API + str(title).replace(" ", "_"),
                             timeout=TIMEOUT, headers={"User-Agent": UA})
        if r.status_code != 200:
            return None
        data = r.json()
    except Exception:
        return None
    if not _usable(data):
        return None
    return {
        "title": str(data.get("title") or title)[:160],
        "text": _clean(data.get("extract")),
        "url": str(((data.get("content_urls") or {}).get("desktop") or {})
                   .get("page") or "")[:300],
    }


async def _titles(client, query, n=3):
    """What Wikipedia thinks the question is about, best first."""
    try:
        r = await client.get(SEARCH, timeout=TIMEOUT,
                             headers={"User-Agent": UA},
                             params={"action": "query", "format": "json",
                                     "list": "search", "srsearch": query,
                                     "srlimit": str(n), "srnamespace": "0"})
        if r.status_code != 200:
            return []
        hits = ((r.json() or {}).get("query") or {}).get("search") or []
    except Exception:
        return []
    return [str(h.get("title") or "") for h in hits if h.get("title")]


async def find(client, question, want=2):
    """Reference passages bearing on a question, or [].

    Never raises. A lesson without a source is a lesson; a lesson that failed
    to render because an encyclopaedia was slow is not.
    """
    q = " ".join(str(question or "").split())[:300]
    if len(q) < 4:
        return []
    titles = await _titles(client, q, n=want + 1)
    if not titles:
        return []
    got = await asyncio.gather(
        *[_summary(client, t) for t in titles[:want + 1]],
        return_exceptions=True)
    out, seen = [], set()
    for item in got:
        if not isinstance(item, dict):
            continue
        key = item["title"].lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= want:
            break
    return out


def as_source(passages, limit=2):
    """The passages, shaped for a prompt.

    Named for what they are. Our own material and this are trusted
    differently and the instruction has to say which is which: our lesson
    decides the notation and the worked order, this decides the facts where
    we have no lesson at all.
    """
    if not passages:
        return ""
    parts = ["[{}]\n{}".format(p["title"], p["text"])
             for p in passages[:limit]]
    return (
        "REFERENCE MATERIAL on this, from Wikipedia:\n\n"
        + "\n\n---\n\n".join(parts)
        + "\n\nUse it for the facts, the definitions and the names. Do not"
          " copy its sentences — it is written as an encyclopaedia and you"
          " are teaching on a board. Where it disagrees with our own course"
          " material above, our material wins. Where it does not cover what"
          " was asked, answer normally and do not pretend it did.\n")


def credits(passages, limit=2):
    """Where the facts came from, for the reader.

    Wikipedia is CC BY-SA. A lesson built from an article and shown with no
    indication of that is not a lesson we are entitled to show, and a reader
    who wants to check something has nowhere to go.
    """
    out = []
    for p in (passages or [])[:limit]:
        if p.get("url"):
            out.append({"title": p["title"], "url": p["url"],
                        "license": "CC BY-SA 4.0"})
    return out
