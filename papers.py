"""Published research on a topic, for the reader who wants further than the
lesson goes.

A school lesson is bounded by a syllabus, and it should be — teaching past
what a class is examined on is how a period gets lost. But somebody in that
room is going to want to know where this actually goes, and the honest
answer to "is there more?" is a real paper with a real author on it, not a
longer paragraph from a model.

arXiv, because the terms permit exactly this. It has a documented public
API, no key, and asks only that clients identify themselves and do not
hammer it — all of which is cheap to honour. It is also a preprint server,
which is the important caveat and is said on screen: these are papers as
submitted, most not yet refereed.

**What it is NOT for.** It does not build the lesson. Nothing here reaches
the model, and no fact from a paper is taught: a lesson is what a class is
examined on, and a preprint is somebody's argument. This produces a short
list of titles and links, shown under the lesson, for a reader who chooses
to follow one.

**Coverage is narrow and stated.** arXiv is physics, mathematics, computer
science, quantitative biology, statistics, electrical engineering and
economics. It has essentially nothing on history, law, literature, school
biology or clinical medicine — so a lesson on the Mughals or the nephron
gets nothing rather than something irrelevant, and asking is skipped
entirely for those subjects rather than asked and thrown away.
"""
import re
from xml.etree import ElementTree as ET

API = "http://export.arxiv.org/api/query"
UA = "Craxle/1.0 (https://craxle.com; learning platform) python-httpx"
TIMEOUT = 8.0
NS = {"a": "http://www.w3.org/2005/Atom"}

# The fields arXiv actually holds. Asking it about the Mughal empire returns
# whatever shares a word with it, confidently, so the question is not asked
# at all unless the topic looks like something it covers.
_IN_SCOPE = re.compile(
    r"\b(physic\w*|quantum|relativ\w*|particle|nuclear|thermodynamic\w*|"
    r"optic\w*|electromagnet\w*|astronom\w*|astrophys\w*|cosmolog\w*|"
    r"mathemat\w*|algebra|geometry|topolog\w*|calculus|probabilit\w*|"
    r"statistic\w*|number theory|graph theory|cryptograph\w*|"
    r"comput\w*|algorithm\w*|machine learning|neural|deep learning|"
    r"artificial intelligence|data structur\w*|database\w*|network\w*|"
    r"robotic\w*|software|program\w*|informatics|"
    r"genom\w*|bioinformatic\w*|molecular dynamic\w*|protein folding|"
    r"econom\w*|econometric\w*|game theory|finance|market\w*|"
    r"signal processing|control theory|semiconductor\w*|photonic\w*|"
    r"material science|nanotech\w*|fluid dynamic\w*|chaos)\b", re.I)


def in_scope(topic: str) -> bool:
    """Is this a field arXiv genuinely holds papers in?"""
    return bool(_IN_SCOPE.search(str(topic or "")))


def _clean(text: str, limit: int = 300) -> str:
    return " ".join(str(text or "").split())[:limit]


async def find(client, topic: str, want: int = 3) -> list:
    """A few papers on this topic, or [].

    Never raises. Further reading is a bonus at the foot of a lesson; a
    lesson that failed to render because a preprint server was slow is not
    a trade anybody would make.
    """
    q = _clean(topic, 120)
    if not q or not in_scope(q):
        return []
    try:
        r = await client.get(
            API, timeout=TIMEOUT, headers={"User-Agent": UA},
            params={"search_query": f"all:{q}",
                    "start": 0,
                    "max_results": max(1, min(int(want or 3), 5)),
                    # Most cited would be better and arXiv does not offer it.
                    # Relevance is its own default and the honest second
                    # choice; sorting by date would put a lesson's further
                    # reading at the mercy of whatever was posted yesterday.
                    "sortBy": "relevance"})
        if r.status_code != 200:
            return []
        root = ET.fromstring(r.text)
    except Exception as e:
        print(f"arXiv lookup failed: {type(e).__name__}: {e}")
        return []

    out = []
    for entry in root.findall("a:entry", NS):
        title = _clean((entry.findtext("a:title", "", NS) or ""), 200)
        link = (entry.findtext("a:id", "", NS) or "").strip()
        if not title or not link.startswith("http"):
            continue
        # https, always: the id comes back as http and this goes into a page
        # served over https, where a mixed-content link is a dead link.
        link = "https://" + link.split("://", 1)[1]
        authors = [_clean(a.findtext("a:name", "", NS), 80)
                   for a in entry.findall("a:author", NS)]
        authors = [a for a in authors if a][:3]
        out.append({
            "title": title,
            "url": link,
            # Three names and "and others" — a paper with two hundred
            # authors is real and a wall of them is not a reading list.
            "by": ", ".join(authors) + (" and others"
                                        if len(entry.findall("a:author", NS))
                                        > len(authors) else ""),
            "when": (entry.findtext("a:published", "", NS) or "")[:10],
            "summary": _clean(entry.findtext("a:summary", "", NS), 260),
        })
        if len(out) >= want:
            break
    return out
