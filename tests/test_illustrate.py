"""Every step of a lesson gets something to look at, or keeps its words.

"Axle Pro board is all text." It was: one photograph was fetched for the
topic and shown on step one, and every step after it was prose. A lesson that
technically has an image and shows it once is fairly described as having
none.

The pass that fixes it cannot be tested through the live board — that needs a
model call and an API key — so the picture search is stubbed here and the
PASS ITSELF is exercised: which steps it asks about, what it asks, what it
attaches, and the four things it refuses to do. Those are the parts that were
wrong, and they are all decisions made in our own code rather than by the
model or by Wikimedia.

The refusals matter more than the attachments. A lesson with no picture is
ordinary; a lesson illustrated with the wrong machine teaches the wrong
machine, and the same photograph three times reads as a fault because it is
one.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"

import main                                         # noqa: E402
import images as _images                            # noqa: E402

P, F = [], []


def ck(n, c, d=""):
    print(("PASS " if c else "FAIL ") + n + (f" — {d}" if d else ""),
          flush=True)
    (P if c else F).append(n)


def run(coro):
    # asyncio.run, not get_event_loop: from Python 3.12 there is no implicit
    # loop in the main thread and get_event_loop raises rather than making
    # one.
    return asyncio.run(coro)


class Finder:
    """Stands in for the open catalogues, and records what it was asked."""

    def __init__(self, answers=None, always=None):
        self.asked = []
        self.answers = answers or {}
        self.always = always

    async def find(self, client, query):
        self.asked.append(query)
        if self.always is not None:
            return dict(self.always)
        return dict(self.answers.get(query, {}) or {})


def illustrate(lesson, topic, finder, asked=""):
    real = _images.find
    _images.find = finder.find
    try:
        return run(main._illustrate(None, lesson, topic, asked))
    finally:
        _images.find = real


print("\nevery step that has nothing gets asked about")
lesson = {"title": "Refraction", "steps": [
    {"t": "What refraction is\nLight bends."},
    {"t": "Refractive index\nn = c / v."},
    {"t": "Total internal reflection\nPast the critical angle."},
]}
f = Finder(always={"url": "https://upload.wikimedia.org/a.jpg",
                   "caption": "A"})
n = illustrate(lesson, "refraction of light", f)
ck("it does not stop at the first step", n >= 1, str(n))
ck("and it asks with the step's OWN heading, not the topic again",
   "What refraction is" in f.asked, str(f.asked[:4]))

print("\nthe same photograph is never used twice")
# A finder that returns one picture for everything is the worst case and the
# likeliest: three steps of one topic all match the same article.
ck("only one step keeps it", n == 1,
   f"{n} steps got the identical url — a repeat reads as a fault")

print("\na step that already SHOWS something is left alone")
lesson2 = {"title": "T", "steps": [
    {"t": "One\nwords", "scene": {"kind": "molecule"}},
    {"t": "Two\nwords", "draw": {"kind": "plot"}},
    {"t": "Three\nwords", "sketch": {"kind": "x"}},
    {"t": "Four\nwords"},
]}
f2 = Finder(always={"url": "https://upload.wikimedia.org/b.jpg"})
illustrate(lesson2, "t", f2)
ck("a 3D scene is not replaced by a photograph",
   "photo" not in lesson2["steps"][0],
   "a diagram built from the lesson's own numbers beats a stock picture")
ck("nor a drawing", "photo" not in lesson2["steps"][1])
ck("nor a sketch", "photo" not in lesson2["steps"][2])
ck("the one with nothing does get one", "photo" in lesson2["steps"][3])

print("\nthe search widens rather than asking once")
# A heading nothing has a picture of. It should fall back to the topic, and
# then to what the learner actually asked.
lesson3 = {"title": "T", "steps": [{"t": "The apparatus\nSet it up."}]}
f3 = Finder(answers={"photosynthesis":
                     {"url": "https://upload.wikimedia.org/c.jpg"}})
illustrate(lesson3, "photosynthesis", f3, asked="how do leaves make food")
ck("the heading is tried first", f3.asked[0] == "The apparatus", str(f3.asked))
ck("then the heading with the topic",
   any("The apparatus" in q and "photosynthesis" in q for q in f3.asked),
   str(f3.asked))
ck("then the topic on its own", "photosynthesis" in f3.asked, str(f3.asked))
ck("and the step ends up with the picture that was found",
   (lesson3["steps"][0].get("photo") or {}).get("url", "").endswith("c.jpg"),
   str(lesson3["steps"][0].get("photo")))

print("\nand it stops when there is genuinely nothing")
lesson4 = {"title": "T", "steps": [{"t": "Abstract thing\nwords"}]}
f4 = Finder()          # finds nothing, ever
got = illustrate(lesson4, "some topic", f4)
ck("no picture is attached", got == 0 and "photo" not in lesson4["steps"][0],
   "a lesson with no picture is ordinary; the wrong one teaches the wrong "
   "thing")
ck("but it did try more than once before giving up", len(f4.asked) >= 2,
   str(f4.asked))

print("\na formula is not searched for")
# "n = c / v" is a step heading only in the sense that it is the first line.
# Searching an encyclopaedia for it finds nothing and wastes the widening.
ck("a heading of symbols is not used as a query",
   main._step_heading({"t": "n = c / v\nmore words"}) == "",
   "the fallbacks are for headings, not equations")
ck("a real heading is", main._step_heading({"t": "Total internal reflection\nx"})
   == "Total internal reflection")

print("\nhow far down a lesson it goes")
long_lesson = {"title": "T", "steps": [{"t": f"Head {i}\nwords"}
                                       for i in range(20)]}
f5 = Finder()
illustrate(long_lesson, "t", f5)
ck("a twenty-step lesson does not fire twenty lookups",
   len(f5.asked) <= main.ILLUSTRATE_MAX * 4,
   f"{len(f5.asked)} queries for {main.ILLUSTRATE_MAX} steps")

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
