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


# Words that carry no subject. A title matching only these is not a match.
_STOP = {
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "and", "or",
    "with", "from", "by", "is", "are", "was", "were", "be", "how", "what",
    "why", "when", "which", "who", "does", "do", "did", "its", "it", "this",
    "that", "these", "those", "as", "into", "than", "then", "there", "here",
    "explain", "example", "examples", "simply", "simpler", "deeper", "detail",
    "details", "walk", "through", "concrete", "worked", "end", "step",
    "steps", "show", "give", "me", "us", "you", "your", "learn", "lesson",
    "topic", "about", "more", "much", "one", "specifically", "beginner",
    "expert", "practice", "exercises", "mistakes", "common", "avoid",
    "matter", "matters", "real", "work", "used", "answers", "explained",
    "want", "would", "need", "know", "understand", "please",
}


def subject_of(topic: str) -> str:
    """What the lesson is actually about, without the instruction on the end.

    "Show an example" and its five siblings do not ask a new question, they
    extend the old one — the topic becomes "aircraft gearbox - walk through
    one concrete worked example end to end". Searching for a picture of that
    sentence is how a gearbox lesson ended up illustrated with a crane.
    """
    t = str(topic or "")
    # The tutor's own separator, and the follow-up form.
    for sep in ("\u2014", " - ", " \u2013 "):
        if sep in t:
            t = t.split(sep)[0]
    for sep in ("specifically:", "Specifically:"):
        if sep in t:
            t = t.split(sep)[0]
    return " ".join(t.split()).strip(" -\u2014:,.")


def _words(text):
    """The words in a phrase that carry any subject at all."""
    return {w for w in re.findall(r"[a-z0-9]+", str(text or "").lower())
            if len(w) > 2 and w not in _STOP}


def _matches(word, words):
    """Is this word present in that set, allowing plurals and stems?"""
    for other in words:
        if word.rstrip("s") == other.rstrip("s"):
            return True
        if len(word) >= 5 and len(other) >= 5 and word[:4] == other[:4]:
            return True
    return False


def relevant(query: str, title: str) -> bool:
    """Does this article have anything to do with what was asked?

    Wikimedia always returns its best match, and its best match for a poor
    query is still a confident article with a good photograph. Requiring one
    real word in common is a low bar that a crane fails for a gearbox.
    """
    q, t = _words(query), _words(title)
    if not q:
        return False

    # The head noun has to match, not just any word.
    #
    # English puts the head of a compound last: an "aircraft gearbox" is a
    # gearbox, and "Nimitz-class aircraft carrier" shares "aircraft" with it
    # while being an entirely different object. Requiring the head means a
    # gearbox lesson gets a gearbox or nothing, which is the right trade —
    # no picture is ordinary, the wrong machine teaches the wrong machine.
    # ONE definition of the head, and it is head_noun() below.
    #
    # This used to take the raw last word, which is the rule head_noun()
    # exists to correct — and the two disagreed exactly where it mattered.
    # "Plant cell structure" gave head "structure", so the article on Plant
    # cell was thrown out as not being about it; "refraction of light" gave
    # "light" and threw out Refraction. Both are the right article, both were
    # discarded, and the log said so in a sentence that read as if the
    # search had gone wrong.
    head = head_noun(query)
    if head and not _matches(head, t):
        return False
    if q & t:
        return True
    # Plurals and shared stems, so "gears" matches "gear" and "gearbox"
    # matches "gearing" — an article on epicyclic gearing is a good picture
    # for an aircraft gearbox, and rejecting it would throw away a real
    # match to avoid a crane. Four characters of a five-letter-plus word is
    # a stem in practice; anything shorter starts matching by accident.
    for a in q:
        for b in t:
            if a.rstrip("s") == b.rstrip("s"):
                return True
            if len(a) >= 5 and len(b) >= 5 and a[:4] == b[:4]:
                return True
    return False


# Words that end a phrase without being what it is about. "Plant cell
# structure" is about a plant cell; "refraction diagram" is about refraction.
# Taking the last word as the head made the article on Structure beat the
# article on Plant cell, which is the wrong picture by a wide margin.
_GENERIC_TAIL = {
    "structure", "structures", "diagram", "diagrams", "example", "examples",
    "type", "types", "kind", "kinds", "property", "properties", "process",
    "processes", "method", "methods", "definition", "meaning", "overview",
    "introduction", "basics", "concept", "concepts", "principle",
    "principles", "explanation", "summary", "notes", "formula", "formulas",
    "equation", "equations", "problem", "problems", "question", "questions",
    # All of these are how a teacher writes a topic and none of them is ever
    # the thing a picture should be of. "The parts of a flower" searched for
    # "parts". Deliberately NOT here: "law", "laws" — "Newton's laws of
    # motion" would reduce to "newton" and return a portrait of the man,
    # which is the exact failure this list exists to prevent.
    "part", "parts", "function", "functions", "feature", "features",
    "component", "components", "stage", "stages", "step", "steps",
    "use", "uses", "application", "applications", "importance", "role",
}


def head_noun(query: str) -> str:
    """The word a phrase is ABOUT.

    English usually puts it last — an "aircraft gearbox" is a gearbox — and
    that rule alone was the whole test. It fails in two ordinary ways, and
    both of them are how a teacher writes a topic:

      "refraction of light"  a prepositional phrase qualifies what came
                             BEFORE it. This is about refraction, and taking
                             the last word chose the article on Light.
      "plant cell structure" a generic tail noun is not the subject either.
                             This chose Structure.

    So the phrase is cut at the first preposition and generic tails are
    dropped, and what is left ends in the actual head.
    """
    def keep(s):
        return [w for w in re.findall(r"[a-z0-9]+", s)
                if len(w) > 2 and w not in _STOP]

    t = " " + " ".join(str(query or "").lower().split()) + " "
    before, after = t, ""
    for sep in (" of ", " in ", " for ", " with ", " from ", " about ",
                " between ", " during ", " under "):
        if sep in t:
            before, after = t.split(sep)[0], t.split(sep, 1)[1]
            break

    words = keep(before)
    # "the structure of the human heart" is about the HEART.
    #
    # Cutting at the preposition is right for "refraction of light", because
    # refraction is a real subject. It is wrong when everything before the
    # preposition is a generic — there the qualifier IS the subject, and the
    # old rule returned "structure", searched for that, and found nothing a
    # biology class could use. A heart, a flower and a cell all failed this
    # way, which is most of what a school actually asks for a picture of.
    if after and all(w in _GENERIC_TAIL for w in words):
        words = keep(after)

    while len(words) > 1 and words[-1] in _GENERIC_TAIL:
        words.pop()
    return words[-1] if words else ""


def score(query: str, title: str) -> float:
    """How well an article title answers a query. 0 means not at all.

    `relevant()` answers yes or no, and taking Wikimedia's own first result
    and then asking that question was throwing away the case this is for: a
    query of several words where the best article is third in the list. For
    "total internal reflection" Wikimedia's own ranking is fine; for
    "refractive index of crown glass" it is a lottery, and the lottery was
    being played with one ticket.

    So every candidate is scored and the best one wins. The scale is not
    important — only the ordering, and the floor below which nothing is good
    enough to show.

    What earns points:
      the head noun matching        the single strongest signal in English,
                                    since a compound's head is its last word
      each other query word matched a query of five words matching four of
                                    them is a better answer than one matching
                                    two, which is the whole of what "match
                                    more than a few words" means
      the title being short         "Refraction" beats "Refraction in
                                    nonlinear optical media" for a lesson
                                    about refraction; a long title is a
                                    narrower subject
    """
    q_words = [w for w in re.findall(r"[a-z0-9]+", str(query or "").lower())
               if len(w) > 2 and w not in _STOP]
    if not q_words:
        return 0.0
    t_words = _words(title)
    if not t_words:
        return 0.0

    head = head_noun(query)
    if head and not _matches(head, t_words):
        # Without the head noun it is a different object, however many other
        # words it shares. "Nimitz-class aircraft carrier" for "aircraft
        # gearbox" is the case this exists to refuse.
        return 0.0

    hit = sum(1 for w in q_words if _matches(w, t_words))
    covered = hit / float(len(q_words))
    # A title made almost entirely of the query's own words is the article
    # about exactly that thing.
    focus = hit / float(len(t_words))
    return 1.0 + covered * 2.0 + focus


# Below this a candidate is not worth showing. The head noun alone scores
# 1 + 1/len(q) + focus, so a one-word query that matches scores well over it
# and a five-word query matching only its head does not.
SCORE_FLOOR = 1.9


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


def _parse(search_body, meta_body, query="") -> dict:
    """The two Wikimedia responses into one picture, or nothing."""
    pages = ((search_body or {}).get("query") or {}).get("pages") or {}
    best, best_score = None, -1.0
    for page in pages.values():
        thumb = page.get("thumbnail") or {}
        url = _safe_url(thumb.get("source"))
        if not url or int(thumb.get("width") or 0) < MIN_WIDTH:
            continue
        title = str(page.get("title") or "")
        # Scored against the query, not taken on Wikimedia's own ranking.
        # Its first result is the best ARTICLE for the words; we want the
        # best article for the SUBJECT, and for a query of several words
        # those are regularly not the same one. Wikimedia's order breaks
        # ties, which is the right thing for it to do.
        sc = score(query, title) if query else 0.0
        sc -= page.get("index", 99) * 1e-4
        if sc > best_score:
            best, best_score = {
                "url": url,
                "width": int(thumb.get("width") or 0),
                "caption": title,
                "page": _safe_url(page.get("fullurl")),
            }, sc
    if not best or best_score < SCORE_FLOOR:
        return {}

    author = license_ = ""
    for page in (((meta_body or {}).get("query") or {}).get("pages")
                 or {}).values():
        for info in (page.get("imageinfo") or []):
            ext = info.get("extmetadata") or {}
            author = author or _clean((ext.get("Artist") or {}).get("value"))
            license_ = license_ or str(
                (ext.get("LicenseShortName") or {}).get("value") or "")[:60]
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


# The canonical name PubChem holds for a compound, used to confirm that what
# came back is what was asked for.
PUBCHEM_TITLE = ("https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
                 "{}/property/Title/JSON")
PUBCHEM_CID = ("https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/"
               "{}/PNG?image_size=large")


def _same_substance(asked, title):
    """Does PubChem's canonical name agree with what was asked for?

    The database carries millions of depositor synonyms and short words
    collide with them: "git" resolves to a triazole carbamate and "react" to
    Levonorgestrel. Both return a real, correct picture of a real compound
    that has nothing to do with the lesson.

    A canonical Title is the name a chemist would use, so the asked-for name
    should be in it — "Caffeine" contains "caffeine", "D-Glucose" contains
    "glucose". The IUPAC mouthful for CID 162394498 contains no "git".
    """
    a = " ".join(str(asked or "").lower().split())
    t = " ".join(str(title or "").lower().split())
    if not a or not t:
        return False
    if a in t or t in a:
        return True
    # Sulfuric acid is titled "Sulfuric Acid"; citric acid, "Citric Acid".
    # Compare word by word so ordering and hyphens do not matter.
    aw = set(re.findall(r"[a-z0-9]+", a))
    tw = set(re.findall(r"[a-z0-9]+", t))
    return bool(aw) and aw <= tw


async def _from_pubchem(client, topic):
    """A structural formula, or nothing. Public domain: no credit required."""
    name = _compound(topic)
    if not name:
        return {}
    try:
        # Ask what it resolves to before asking for a picture of it.
        r = await client.get(PUBCHEM_TITLE.format(quote(name, safe="")),
                             timeout=TIMEOUT, headers={"User-Agent": UA})
        # PubChem answers 404 for anything it cannot resolve at all.
        if r.status_code != 200:
            return {}
        props = ((r.json() or {}).get("PropertyTable") or {}).get(
            "Properties") or []
        if not props:
            return {}
        cid = props[0].get("CID")
        title = str(props[0].get("Title") or "")
        if not cid or not _same_substance(name, title):
            print(f"PubChem resolved {name!r} to {title[:60]!r} — "
                  f"not the same thing, so no picture")
            return {}

        url = PUBCHEM_CID.format(int(cid))
        img = await client.get(url, timeout=TIMEOUT,
                               headers={"User-Agent": UA})
        if img.status_code != 200 or "image" not in \
                img.headers.get("content-type", ""):
            return {}
        # A blank canvas is about 300 bytes. Benzene, a plain hexagon, is
        # only 800 — so the floor has to sit between them, not above both.
        if len(img.content) < 500:
            return {}
    except Exception as e:
        print(f"PubChem lookup failed for {name!r}: {type(e).__name__}: {e}")
        return {}
    return {"url": url, "width": 600, "caption": title or name,
            "author": "", "license": "", "page": ""}


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
    # Search what the lesson is about, not the instruction appended to it.
    q = subject_of(topic)[:120]
    if not q or not wanted(q):
        return {}

    # Only sources whose picture is OF the thing that was asked about.
    #
    # PubChem generates the structure from the compound, so glucose returns
    # glucose and cannot return anything else. NASA catalogues photographs
    # against the object in them. Both are exact by construction rather than
    # by an editor's judgement about what best introduces an article, and
    # both are public domain, so no credit line appears at all.
    #
    # NASA first: "Saturn" is unambiguously astronomical and ambiguously
    # chemical, so the more specific signal is asked first.
    # NASA only.
    #
    # PubChem was here too and is now gone. It is a chemical index with
    # millions of depositor synonyms, and short words collide with them:
    # "git" resolved to a triazole carbamate, "react" to Levonorgestrel.
    # Verifying the canonical title against the query fixed those and then
    # rejected caffeine, aspirin and benzene as well — the tightening that
    # stops the wrong answers also stops the right ones, and every question
    # became a new special case.
    #
    # NASA catalogues its photographs against the object in them, so a
    # search for Saturn returns Saturn. It has not produced a wrong picture
    # once. Everything it does not cover gets no photograph, and relies on
    # the canvas sketch and the 3D scene, both of which are built from the
    # lesson's own values and cannot be about something else.
    for source in (_from_nasa,):
        try:
            pic = clean(await source(client, q))
        except Exception as e:
            print(f"Picture source failed: {type(e).__name__}: {e}")
            continue
        if pic:
            return pic

    # Then Wikimedia, for everything NASA does not cover — which is nearly
    # everything a school teaches.
    #
    # This was switched off after "aircraft engine" returned a photograph of
    # an aeroplane. That reasoning was sound and the conclusion was too
    # strong. "Aircraft engine" IS the right article; its lead image is an
    # aeroplane because an editor picked the picture that best introduces the
    # article, and introducing an article is not the same job as showing the
    # subject. But NASA covers astronomy and earth observation and nothing
    # else, so switching Wikimedia off did not trade some wrong pictures for
    # fewer wrong pictures — it traded them for almost NO pictures, on a
    # board whose whole job is showing a class what a thing looks like.
    # Photosynthesis, the human heart and a benzene ring all returned
    # nothing, and a biology lesson with no picture of a heart is not a
    # cautious lesson, it is a worse one.
    #
    # What makes it acceptable is what the picture arrives WITH. Every one
    # carries the article title as its caption and its author and licence
    # underneath, both shown. A reader who sees an aeroplane captioned
    # "Aircraft engine" can tell what happened; the failure is visible rather
    # than silent, which is the most that can honestly be claimed for a
    # general encyclopaedia's lead images.
    #
    # The guards that survived all of this still run: the query is cut to its
    # head noun, eight titles are scored rather than three, anything under
    # the floor is refused, and a file with no author or licence is dropped
    # rather than shown bare.
    try:
        r = await client.get(API, timeout=TIMEOUT, headers={"User-Agent": UA},
                             params={
                                 "action": "query", "format": "json",
                                 "formatversion": "1",
                                 "generator": "search",
                                 # Eight, not three. The best article for a
                                 # multi-word query is regularly not the
                                 # first one, and the cost of looking at
                                 # five more titles is nothing — they arrive
                                 # in the same response.
                                 "gsrsearch": q, "gsrlimit": "8",
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

    pic = _parse(body, meta, q)
    # The scorer has already refused anything below the floor, and the floor
    # is what "has nothing to do with the question" means in numbers. This
    # stays as the second gate because the two disagree at the margin and the
    # stricter of them should win: a lesson with no photograph is ordinary,
    # a lesson illustrated with the wrong machine teaches the wrong machine.
    if pic and not relevant(q, pic.get("caption")):
        print(f"Picture for {q!r} discarded: "
              f"{pic.get('caption')!r} is not about it")
        return {}
    # Attribution is not optional HERE. Wikimedia's files are licensed on the
    # condition that the author is named, so one that arrives without an
    # author or a licence is dropped rather than shown bare. The public-domain
    # sources above are exempt because there is genuinely nobody to credit.
    if pic and not (pic.get("author") or pic.get("license")):
        return {}
    return pic


PROMPT = ""   # nothing is asked of the model: the picture is looked up, not written
