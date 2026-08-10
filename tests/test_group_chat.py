"""A subject's discussion, read the way a class already knows how to read.

It was a forum: a stack of question cards, each with its replies indented
underneath, newest question at the top. That shape is right for a message
board read by strangers over weeks. A class is not that. Thirty people who
see each other every day, talking about one subject, use a group chat — and
reading one is a skill every child in the room already has and nobody has to
be taught.

What changed, and why each part is the way it is:

**Oldest at the top, newest at the bottom, pinned to the bottom on open.**
The API sends threads newest-first because that is what a forum lists. Read
that way a reply appears above the message it answers, which is not a
conversation. So the whole subject is flattened into one chronological run
and the view opens where the last thing said is.

**A reply quotes its parent instead of being indented under it.**
Indentation nests without limit and stops fitting on a phone at about the
second level. A quote carries the thread AND lets the reply be read on its
own, which is what somebody scrolling back actually needs.

**The sender's name only when the sender changes.** Six messages from one
person with their name over every one is a wall of their name.

**Both sides render the same thing.** The teacher's screen was a different
forum from the pupils'. A teacher answering a class should be looking at
what the class is looking at.
"""
import io
import os
import sys
import time
import datetime as dt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"

import main                                        # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = io.open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
main.Base.metadata.create_all(bind=main.engine)
main._migrate_columns()
main.send_email = lambda *a, **k: None
P, F = [], []


def ck(n, c, d=""):
    print(("PASS " if c else "FAIL ") + n + (f" — {d}" if d else ""),
          flush=True)
    (P if c else F).append(n)


print("\nit is a chat, not a forum")
ck("messages are bubbles in a scrolling run", ".chat-row{" in IDX
   and ".chat-b{" in IDX)
ck("your own are on the other side", ".chat-row.me{justify-content:flex-end}"
   in IDX)
ck("with a day rule between days", ".chat-day{" in IDX
   and 'h += `<div class="chat-day">' in IDX)
ck("Today and Yesterday are named, not dated",
   'if(same(d, today)) return "Today";' in IDX,
   "nobody reads their own morning as a date")
ck("and the composer is at the bottom, where the thumb is",
   ".chat-bar{" in IDX)

print("\nread in the order it was said")
ck("threads and replies are flattened into one run",
   "function chatFlatten(threads)" in IDX)
ck("sorted oldest first",
   'out.sort((a,b)=>String(a.at||"").localeCompare(String(b.at||"")));' in IDX,
   "the API sends newest-first, which puts a reply above the message it "
   "answers")
ck("and it opens at the newest", "function chatToEnd()" in IDX,
   "a chat that opens at the top is one you must scroll before you can read "
   "what you came for")

print("\na reply quotes what it answers")
ck("the quote is inside the reply's own bubble", ".chat-q{" in IDX
   and "quote:{who:t.who, body:t.body}" in IDX)
ck("nothing is indented under anything",
   "border-left:2px solid var(--line,#2a2a2a)" not in IDX.split(
       "async function discPaint")[-1],
   "indentation nests without limit and stops fitting at about level two")
ck("tapping a message answers it",
   'GCHAT.replyTo=m.id;' in IDX or "GCHAT.replyTo = m.id;" in IDX)
ck("the chosen message is shown above the box",
   "function chatReplyBar()" in IDX)
ck("and there is a way out of replying",
   'data-cls="chatcancel"' in IDX and 'k==="chatcancel"' in IDX,
   "otherwise it is a state you enter and cannot leave, and the next "
   "message lands under a question you had stopped meaning to answer")

print("\nsmall things that make it read as a chat")
ck("the name appears only when the speaker changes",
   "const showWho = !mine && m.who !== lastWho;" in IDX)
ck("a new day reintroduces everybody", 'lastWho = "";' in IDX)
ck("the teacher is marked", 'm.from_staff?\' <span class="t">· teacher' in IDX)
ck("Enter sends and shift+Enter is a new line",
   'if(e.key === "Enter" && !e.shiftKey)' in IDX)
ck("and sending no longer raises a banner over the message",
   'toast("Asked. Your teacher will see it.")' not in IDX,
   "in a chat the message appearing IS the confirmation")

print("\nand both sides see the same thing")
ck("the pupil's subject page uses it", 'chatHTML(threads, {cid:cid,' in IDX)
ck("and so does the teacher's class page",
   "box.innerHTML = chatHTML(threads, {cid:cid, canDelete:true," in IDX,
   "a teacher answering a class should be looking at what the class sees")

print("\nthe server already carried everything a chat needs")
u = str(int(time.time())) + str(os.getpid())
db = main.SessionLocal()
sc = main.School(name=f"Chat School {u}")
db.add(sc)
db.commit()
db.refresh(sc)
hc = ("HCH" + u)[:12]
db.add(main.TeacherCode(code=hc, school=sc.name, school_id=sc.id,
                        is_head=True, active=True))
db.commit()
t = TestClient(main.app)
tem = f"chatt{u}@example.com"
t.post("/api/auth/signup",
       json={"name": "Chat Teacher", "email": tem, "password": "ChatPass1!"})
trow = db.query(main.User).filter(main.User.email == tem).first()
trow.dob = dt.date(1985, 1, 1)
db.commit()
t.post("/api/class/join", json={"code": hc})
cid = t.post("/api/teacher/class", json={"name": f"7-C {u}"}).json()["id"]

r = t.post(f"/api/class/{cid}/discussion",
           json={"body": "Welcome to Biology.", "subject": "Biology"})
ck("a message posts", r.status_code == 200, r.text[:80])
pid = (r.json() or {}).get("id") or 0
r = t.post(f"/api/class/{cid}/discussion",
           json={"body": "Reading for Friday.", "subject": "Biology",
                 "parent_id": pid})
ck("and a reply to it posts", r.status_code == 200, r.text[:80])

d = t.get(f"/api/class/{cid}/discussion?subject=Biology").json()
th = d.get("threads") or []
ck("each message says when it was said",
   bool(th) and bool(th[0].get("at")), str(th[:1])[:90])
ck("and who said it", bool(th) and bool(th[0].get("who")))
ck("and whether it was mine", bool(th) and th[0].get("mine") is True,
   "which side of the chat it goes on")
ck("and whether it came from staff",
   bool(th) and th[0].get("from_staff") is True)
ck("replies read oldest first",
   bool(th) and len(th[0].get("replies") or []) == 1,
   "a conversation read backwards is not one")

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\nPASSED {len(P)}   FAILED {len(F)}")
sys.exit(1 if F else 0)
