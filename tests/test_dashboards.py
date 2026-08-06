"""An administrator's screen and a teacher's screen are not the same screen.

They were, very nearly, and the reason was underneath: `staff` meant "teacher
OR school admin", one flag for two jobs, so both got one dashboard. On top of
that the teacher's own class screen carried the office's controls — the class
code to hand out, a form to put any colleague on any subject, and the box for
typing the school's register — while a learner's Ask Axle sidebar carried the
teacher's, offering "Teach from a PDF" and "Save to a class" to a child.

None of that is a security hole on its own; every route refused. It is worse
in a duller way: three different people were shown a control that does not
belong to them and, on pressing it, told so. A screen that offers what it
will not do teaches people to distrust the screen.

This suite reads the pages rather than driving them — the permissions are
tested for real in test_walls.py, and what is pinned HERE is that no door is
drawn that the server would not open. It is the pairing that matters: every
gate below has a route behind it in that file.
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P, F = [], []


def ck(n, c, d=""):
    print(("PASS " if c else "FAIL ") + n + (f" — {d}" if d else ""),
          flush=True)
    (P if c else F).append(n)


IDX = io.open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
MAIN = io.open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()

print("\nthe three roles have three names, not two")
ck("there is a word for the office", "function isOffice()" in IDX)
ck("and a word for somebody who teaches", "function teaches()" in IDX)
ck("and teaching is explicitly NOT the office",
   re.search(r"function teaches\(\)\s*\{\s*return isStaff\(\) && !isOffice\(\)",
             IDX) is not None,
   "the whole bug was one flag meaning both")
ck("a platform admin is never office-only",
   re.search(r"function isOffice\(\)\s*\{\s*return !!USER && !USER\.is_admin",
             IDX) is not None,
   "support that cannot be given is not support")

print("\na learner is not offered a teacher's tools")
m = re.search(r"\$\{teaches\(\) \? `(.{0,400}?)` : \"\"\}", IDX, re.S)
ck("the teaching buttons sit behind teaches()", m is not None)
if m:
    ck("Teach from a PDF is one of them", "Teach from a PDF" in m.group(1),
       m.group(1)[:80])
    ck("and so is Save to a class", "Save to a class" in m.group(1))
ck("but Draw on the screen stays for everybody",
   "data-sbink" in IDX
   and (not m or "data-sbink" not in m.group(1)),
   "drawing on your own screen is nobody's permission")
ck("and so does keeping an explanation",
   "data-sbkeep" in IDX and (not m or "data-sbkeep" not in m.group(1)),
   "a learner keeping their own notes is what this was built for")

print("\nthe office's controls are not on a teacher's class screen")
ck("the class screen knows which of the two is looking",
   "const OFFICE = isOffice() || USER.is_admin;" in IDX)
ck("the code to hand out is the office's",
   "${OFFICE ? `<p class=\"sub\">One code:" in IDX)
ck("so is putting a colleague on a subject",
   re.search(r"\$\{OFFICE \? `\s*<div class=\"eyebrow\">Teachers</div>", IDX)
   is not None)
ck("and so is typing the register",
   'data-cls="rosadd"' in IDX
   and IDX.index('data-cls="rosadd"') > IDX.index("const OFFICE ="))
ck("a teacher still SEES the register",
   "office types it" in IDX,
   "marking is impossible without knowing who is in the class")
ck("but is drawn none of the buttons that change it",
   "const EDITABLE = isOffice() || (USER && USER.is_admin);" in IDX)

print("\nand every gate above has a wall behind it")
# A drawn door and an open door are different questions, and this file only
# answers the first. These are the routes that answer the second, named here
# so that removing one is caught by the suite that draws its button.
ck("the office does not teach", "def teaching_user(" in MAIN)
ck("nor ask the AI", "def axle_user(" in MAIN)
ck("and the question is asked once, in one place",
   "def is_office_only(" in MAIN)
ck("study material is gated on teaching, not on being staff",
   MAIN.count("Depends(teaching_user)") >= 2,
   str(MAIN.count("Depends(teaching_user)")))
ck("and so is the board, through the dependency it shares",
   "return teaching_user(user, db), None" in MAIN,
   "board_or_teacher calls it rather than declaring it, because a board "
   "token has to be read before any of this")
ck("the register is the office's",
   "def set_roster(cid: int, body: RosterIn, user: User = Depends(head_user)"
   in MAIN)
ck("and material is filed under a subject its author holds",
   "subject = _board_subject(db, cid, user, body.subject)" in MAIN,
   "same class, somebody else's subject — a role check never catches it")

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
