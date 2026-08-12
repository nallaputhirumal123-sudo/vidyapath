"""Somebody else's 3D model, when nobody has measured one.

three3d.py builds structures from numbers — a molecule from coordinates, a
crystal from a lattice constant, a helix from crystallography. That is the
right way to show anything with a measured structure, and it is honest in a
way a downloaded mesh can never be: the geometry IS the data.

It also cannot draw a heart. Or a kidney, a jet engine, a Chola bronze, a
tractor gearbox or the human body — none of which have parameters, all of
which somebody has already modelled. Typing "human body" into 3D structures
got a paragraph explaining why there was nothing to show, which is honest
and is not a lesson.

So when there is no measured structure, the library is searched instead.

**The line between the two is never blurred.** A measured scene says
measured; one of these says who made it and under what licence, because it
is somebody's drawing of a heart and not a scan of one. A student looking at
a model of a kidney should know whether they are looking at evidence or at
an illustration — that distinction is most of what science teaching is.

**Shown where it lives, not copied.** The model is embedded from its own
host, which keeps the author credited, keeps the licence attached, costs us
no bandwidth, and means no untrusted mesh is ever parsed on a school's
board. The trade is that a network which blocks the host shows nothing —
which is why the measured scenes stay the first answer, always.
"""
import re

# Only hosts whose embed is a viewer and whose licences are stated on the
# record. Anything not on this list cannot reach a page, whatever a search
# returns — the allowlist is the security boundary, not the search filter.
HOSTS = ("sketchfab.com",)

SEARCH = "https://api.sketchfab.com/v3/search"
TIMEOUT = 8.0
MAX_RESULTS = 12

# Licences worth putting in front of a class, in the order they are
# preferred. The Sketchfab "Standard" licence permits the embed player and
# nothing else; a CC one permits the embed AND lets a teacher take the model
# away for their own use, which is the difference that matters to a school.
FREE = ("cc0", "public domain", "cc attribution", "cc-by")


def _label(v, n=90):
    s = "".join(c for c in str(v or "") if ord(c) >= 32)
    return re.sub(r"\s+", " ", s).strip()[:n]


def _embed_ok(url):
    """An embed URL on an allowed host, or nothing."""
    u = str(url or "")
    if not u.startswith("https://"):
        return ""
    host = u[8:].split("/", 1)[0].lower().split(":")[0]
    if host != "sketchfab.com" and not host.endswith(".sketchfab.com"):
        return ""
    # The embed path only. A viewer URL would put the whole site in the
    # frame, adverts and account menu and all, in front of a class.
    if "/models/" not in u or not u.rstrip("/").endswith("/embed"):
        return ""
    return u


def _thumb(m):
    """The largest thumbnail under 1000px, which is plenty for a card."""
    imgs = ((m.get("thumbnails") or {}).get("images") or [])
    best, best_w = "", 0
    for i in imgs:
        try:
            w = int(i.get("width") or 0)
        except (TypeError, ValueError):
            continue
        u = str(i.get("url") or "")
        if w > best_w and w <= 1000 and u.startswith("https://"):
            best, best_w = u, w
    return best


def clean(m):
    """One search result, rebuilt field by field. Nothing passes through."""
    if not isinstance(m, dict):
        return None
    embed = _embed_ok(m.get("embedUrl"))
    if not embed:
        return None
    # Not in front of a class, whatever it is.
    if m.get("isAgeRestricted"):
        return None
    lic = _label((m.get("license") or {}).get("label"), 40) or "Standard"
    name = _label(m.get("name"), 90)
    if not name:
        return None
    return {
        "name": name,
        "by": _label((m.get("user") or {}).get("displayName"), 60)
              or "unknown",
        "licence": lic,
        "free": any(f in lic.lower() for f in FREE),
        "embed": embed,
        "page": _embed_ok(m.get("embedUrl")) and str(
            m.get("viewerUrl") or "")[:300],
        "thumb": _thumb(m),
        # Worth showing: a two-million-triangle model is a board that stops
        # responding, and a teacher choosing between two should be told.
        "faces": max(0, min(50_000_000, int(m.get("faceCount") or 0))),
        # Kept only to match against; never shown. A model called "Untitled"
        # with the tag "kidney" is the right model.
        "tags": " ".join(_label(t.get("name"), 24)
                         for t in (m.get("tags") or [])[:20]
                         if isinstance(t, dict))[:300],
    }


def rank(q, rows):
    """Relevance first, then the licence, then whether it will open.

    Sketchfab orders by likes, which returns the same handful of spectacular
    models for every query and fills in with anything when a query has few
    real matches: "kidney" came back with a laundry machine, a manor house
    and a pub, all correctly licensed and none of them a kidney.

    So a model that matches nothing that was asked for is DROPPED rather
    than ranked last. It is the same rule the picture search learned — a
    wrong illustration is worse than no illustration, because a class
    believes it.

    Only then does the licence decide, because between two models of a
    kidney the one a teacher can also take away is the better one.
    """
    want = [w for w in re.findall(r"[a-z0-9]+", str(q or "").lower())
            if len(w) > 2 and w not in _STOP]
    if not want:
        return []
    keep = []
    for r in rows:
        words = set(re.findall(r"[a-z0-9]+", (r["name"] + " "
                                              + r.get("tags", "")).lower()))
        hit = sum(1 for w in want if w in words
                  or any(w in x or x in w for x in words if len(x) > 3))
        if not hit:
            continue
        # A model with no faces is a broken upload; one with four million is
        # a board that stops responding when a class is watching.
        usable = 1 if 100 <= r["faces"] <= 4_000_000 else 0
        r["_k"] = (-hit, -int(r["free"]), -usable, r["name"].lower())
        keep.append(r)
    keep.sort(key=lambda r: r["_k"])
    for r in keep:
        r.pop("_k", None)
    return keep


# Words that say nothing about what the model is.
_STOP = {"the", "and", "for", "with", "show", "model", "structure", "3d",
         "human", "diagram", "picture", "image", "view", "how", "does",
         "what", "why", "explain", "class", "lesson"}


def params(q, want=MAX_RESULTS):
    """The query to send. Kept here so the test can check it without a call."""
    # No sort_by, which is the whole difference between this working and not.
    #
    # Sorting by likes searches the popular models for the word, rather than
    # searching for the word: "kidney" returned one model in six, and it was
    # a full anatomy figure that happens to contain a kidney. On relevance
    # the first three results are called Kidney, Kidney and Kidney. Same for
    # mitochondrion and neuron — popularity filled the page with an anime
    # character and a neon sign, both correctly licensed.
    return {"type": "models", "q": str(q or "")[:120],
            "count": max(1, min(24, int(want))),
            "archives_flavours": "false"}


async def find(client, q, want=MAX_RESULTS):
    """Search the library. Never raises: no models is a normal answer."""
    try:
        r = await client.get(SEARCH, params=params(q, want), timeout=TIMEOUT,
                             headers={"user-agent": "craxle-edu/1.0"})
        r.raise_for_status()
        rows = (r.json() or {}).get("results") or []
    except Exception:
        return []
    out = []
    for m in rows:
        got = clean(m)
        if got:
            out.append(got)
    return rank(q, out)[:want]
