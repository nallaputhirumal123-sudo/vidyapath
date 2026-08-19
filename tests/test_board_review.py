"""The board stopped waiting for a second model call in front of a class.

Building a board lesson is the slowest request this product makes. The main
call runs at THINK_HARD, and stacked behind it — after the lesson was already
written, parsed, checked and sitting in the server — was `_review_lesson`: a
whole second model call, reading the lesson back looking for the kind of
error the arithmetic checks cannot see.

The teacher watched a blank board through all of it, for a lesson that
existed.

It has its own route now, asked for once the lesson is on the screen, exactly
as `/api/ask/review` already was. Two properties have to hold for that move
to be safe rather than merely faster:

**The deterministic checks stay where they were.** They read the constants,
the arithmetic and the units, they cost nothing, and a lesson with a wrong
constant in it must never reach the cache in the first place. Only the model
call moved.

**A critical finding still deletes the cached row.** The row is written by
the time the review runs now, and caching is what turns one wrong lesson into
every class's wrong lesson.

**And the key is recomputed, never accepted.** A qkey handed in by the caller
would make this endpoint a way to ask the server to delete somebody else's
cached row — the keys are readable strings, not opaque hashes.
"""
import inspect
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("DATABASE_URL", "sqlite:///./vidyapath.db")
os.environ.setdefault("ALLOW_SQLITE", "1")

import main                                              # noqa: E402

IDX = io.open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
CRX = io.open(os.path.join(ROOT, "craxlearn.html"), encoding="utf-8").read()
BUILD = inspect.getsource(main.board_lesson)
REV = inspect.getsource(main.board_lesson_review)
P, F = [], []


def ck(name, cond, why=""):
    print(("PASS " if cond else "FAIL ") + name + (" — " + why if why else ""),
          flush=True)
    (P if cond else F).append(name)


print("\nthe lesson no longer waits for the second model")
ck("building does not review",
   "await _review_lesson(" not in BUILD,
   "a whole model call stacked on the slowest request this product makes, "
   "after the lesson already existed")
ck("and says where it went", "/api/board/lesson/review" in BUILD)
ck("the review has a route of its own",
   any(getattr(r, "path", "") == "/api/board/lesson/review"
       for r in main.app.routes))

print("\nbut the free checks still stand between a lesson and the cache")
ck("the deterministic checks still run before caching",
   BUILD.index("_check_lesson(") < BUILD.index("verdict[\"cache\"]"),
   "they read the constants and the arithmetic, they cost nothing, and a "
   "lesson with a wrong constant must not be written at all")
ck("a failed check still refuses to cache",
   'if not verdict["cache"]:' in BUILD)
ck("and says so in the trace", '"built, not cached (failed a check)"' in BUILD)
ck("the trace still names the phase it now measures", '_tr.phase("checks")'
   in BUILD)

print("\nthe review keeps the caching rule it inherited")
ck("a critical finding deletes the cached lesson",
   "db.delete(row)" in REV,
   "the row is written by the time this runs, and caching is what turns one "
   "wrong lesson into every class's wrong lesson")
ck("it never fails the caller",
   REV.count('"state": "unchecked"') >= 2,
   "a checker that is down must not put an error on a board in front of a "
   "class")
ck("a failure rolls back rather than leaving the session broken",
   "db.rollback()" in REV)

print("\nand the key is recomputed here, not taken from the caller")
ck("no qkey is accepted",
   "qkey" not in inspect.getsource(main.BoardReviewIn),
   "the keys are readable strings, so a caller-supplied one would be a way "
   "to ask this endpoint to delete another scope's row")
ck("it is rebuilt from the scope, the level and the class",
   '_cl.key(_scope_of(db, user), "board"' in REV
   and '_grade_of(klass)' in REV,
   "two spellings of this key would leave the flagged lesson cached and "
   "nobody would notice")
ck("the class comes from the board's token, not the request",
   'grant.get("class_id")' in REV)
ck("and the board's own auth is what guards it",
   "Depends(_learner_or_board)" in REV)

print("\nboth boards ask for it after the lesson is up")
for name, src, call in (("craxle.com", IDX, "/api/board/lesson/review"),
                        ("the classroom board", CRX,
                         "/api/board/lesson/review")):
    ck(name + " asks for the review", call in src)

I_AT = IDX.index("SB.lesson=r.lesson")
ck("craxle.com draws the lesson before asking",
   I_AT < IDX.index('"/api/board/lesson/review"'))
ck("and does not await it", ".then(rev=>" in IDX)
ck("a superseded question is not marked",
   "if(seq!==SB.seq || !SB.lesson) return;" in IDX,
   "by the time it lands the teacher may have asked something else")
ck("a cached lesson is not reviewed again",
   "if(!r.cached && SB.lesson" in IDX,
   "it was reviewed when it was written; doing it again is a model call for "
   "a lesson nobody is waiting on")

ck("the classroom board paints before asking",
   CRX.index("paintLesson();") < CRX.index('"/api/board/lesson/review"'))
ck("it repaints only when there is something to show",
   "if(rev && rev.findings && rev.findings.length){" in CRX)
ck("a superseded question is not marked there either",
   "if(mine !== TEACHING || !LESSON) return;" in CRX)
ck("and its failure is silence",
   ".catch(function(){});" in CRX)

print("\n" + ("PASSED %d   FAILED %d" % (len(P), len(F))))
if F:
    for name in F:
        print("  FAILED: " + name)
    sys.exit(1)
