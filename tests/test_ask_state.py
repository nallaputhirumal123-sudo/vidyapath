"""The Axle Pro board, and the second question.

Reported: "if i ask a new question after asking one in the axle pro board, it
shows the same previous question again when i go back and come".

It did, and the cause is that this screen is described by TWO states. `ASK`
is the plain answer; `SB` is the Pro board. `renderAsk` shows the BOARD
whenever SB holds a lesson — so asking a second question set ASK, left SB
exactly as it was, and the screen went on showing the first lesson under the
second question's heading. Nothing on the way out of the page cleared it
either, which is why leaving and coming back did not help: it was never a
stale render, it was a state nobody owned.

Two more of the same shape came out of scanning around it, and both are worse
on a board at the front of a room than on a laptop:

**Read aloud survived navigation.** Nothing ended the loop when the page
changed, so a teacher who pressed Read and then opened the register had the
board reciting photosynthesis over the top of it — with Stop now on a screen
they had left. It is the one control somebody needs in a hurry.

**A note with no lesson had no key.** `sbNoteKey` returned the bare prefix
"sbnote_", one shared bucket, so every note written before a lesson was on
the board overwrote the last and then surfaced under the next lesson that
also had no topic.

Read from the source rather than driven, for the same reason as
test_board_tiles: these are three lines in a file of ten thousand, and three
lines are exactly what drifts back.
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = io.open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
P, F = [], []


def ck(n, c, d=""):
    print(("PASS " if c else "FAIL ") + n + (f" — {d}" if d else ""),
          flush=True)
    (P if c else F).append(n)


print("\na new question replaces what is on the board")
m = re.search(r"async function askSubmit\(raw\)\{(.*?)\n\}", IDX, re.S)
ck("askSubmit is findable", bool(m))
body = m.group(1) if m else ""
ck("it clears the Pro board's lesson", "SB.lesson=null" in body,
   "renderAsk shows the BOARD whenever SB holds one")
ck("and its topic", 'SB.topic=""' in body,
   "the heading came from ASK and the lesson from SB, so they disagreed")
ck("and the trail it was drilled down", "SB.trail=[]" in body)
ck("and stops it talking", "SB.speaking=false" in body,
   "the old lesson read aloud over the new one being fetched")

print("\nbut the board's OWN follow-up is not a new question")
ck("it drills through sbTeach", "sbTeach(SB.topic.replace" in IDX,
   "asking INTO the lesson on the board must not wipe the board")
ck("which sets SB itself", re.search(r"async function sbTeach\(topic,keepTrail\)", IDX)
   is not None)

print("\nleaving the page stops it talking")
m2 = re.search(r"function render\(\)\{(.*?)const v=S\.view;(.*?)if\(v\.page===\"home\"\)",
               IDX, re.S)
ck("render is findable", bool(m2))
guard = m2.group(2) if m2 else ""
ck("navigation away from ask cancels speech",
   'v.page !== "ask"' in guard and "speechSynthesis.cancel()" in guard,
   "Stop was on a screen the teacher had already left")
ck("both voices, not just one",
   "ASK.speaking = false" in guard and "SB.speaking = false" in guard)

print("\na note is kept with its lesson, or not at all")
ck("an empty topic gives no key",
   'return of ? "sbnote_" + of : "";' in IDX,
   '"sbnote_" on its own is one bucket every keyless note fell into')
ck("the question is the fallback before that",
   "SB.topic || ASK.question" in IDX)
ck("and saving with no key is refused rather than silently merged",
   "if(!key){ toast(" in IDX)

print("\nwhat must NOT have been broken")
# The Pro board and the plain answer are separate on purpose: exiting the
# board should leave the plain answer you already had.
ck("sbExit still clears only the board",
   re.search(r"function sbExit\(\)\{[^}]*SB\.lesson=null", IDX, re.S) is not None
   and not re.search(r"function sbExit\(\)\{[^}]*ASK\.lesson=null", IDX, re.S),
   "leaving the board is not the same as throwing away the answer")
ck("out-of-order replies are still dropped", "SB.seq" in IDX,
   "two lessons in flight, the slower first one landing last")

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
