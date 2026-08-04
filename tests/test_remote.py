"""The phone as a remote control, and keeping a lesson on the subject page.

Two features that look unrelated and are not: both exist because a board is
a screen in a room, and a lesson taught on it has nowhere to go afterwards.

The claims pinned here:

**A code is a remote, not a session.** A phone holding a pairing code can
change what is on one screen and cannot do anything else — it cannot read a
learner's record, a class list, or its own board's poll. The whole security
argument for letting an unauthenticated phone in rests on that, so it is
asserted against the live API rather than reasoned about.

**Guessing and using are limited differently.** They were one limit at first,
which is wrong in a way testing catches and reading does not: a teacher
turning pages taps far faster than anybody guessing a code, so the limit that
stops guessing stops the remote instead.

**A kept lesson is not an assignment.** An assignment is work with a deadline
that disappears when it is marked. Saving files the explanation under its
subject, where the class can read it again — and only that class.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"

import datetime as dt                              # noqa: E402
import time                                        # noqa: E402

import main                                        # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

PASS = FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {name}" + (f"  ({detail})" if detail else ""))
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


main.Base.metadata.create_all(bind=main.engine)
main.send_email = lambda *a, **k: None
stamp = int(time.time())
db = main.SessionLocal()


def account(tag):
    c = TestClient(main.app)
    email = f"rm{tag}{stamp}@example.com"
    r = c.post("/api/auth/signup", json={"name": f"Person {tag}",
                                         "email": email,
                                         "password": "RemotePass123!"})
    assert r.status_code == 200, r.text
    u = db.query(main.User).filter(main.User.email == email).first()
    u.dob = dt.date(1990, 1, 1)
    db.commit()
    return c, u


print("\nSetting up")
school = main.School(name=f"Remote School {stamp}", city="Chennai",
                     country="India", product="craxlearn")
other = main.School(name=f"Other School {stamp}", city="Delhi",
                    country="India", product="craxlearn")
db.add_all([school, other])
db.commit()

head_c, head_u = account("head")
db.add(main.TeacherAccess(user_id=head_u.id, school=school.name,
                          school_id=school.id, role="head"))
db.commit()
klass = main.Klass(name="10-B", join_code=f"RM{stamp}"[:16],
                   teacher_id=head_u.id, school=school.name,
                   school_id=school.id)
db.add(klass)
db.commit()

kid_c, kid_u = account("kid")
db.add(main.ClassMember(class_id=klass.id, user_id=kid_u.id))
db.commit()

far_c, far_u = account("far")
db.add(main.TeacherAccess(user_id=far_u.id, school=other.name,
                          school_id=other.id, role="head"))
db.commit()
far_class = main.Klass(name="10-B", join_code=f"FR{stamp}"[:16],
                       teacher_id=far_u.id, school=other.name,
                       school_id=other.id)
db.add(far_class)
db.commit()

check("a class with one student exists",
      db.query(main.ClassMember).filter(
          main.ClassMember.class_id == klass.id).count() == 1)

# ---- the board turns the remote on --------------------------------------
print("\nPairing")
r = head_c.post("/api/craxlearn/remote/open", json={})
check("the board is given a code", r.status_code == 200, r.text[:120])
code = r.json().get("code", "")
check("the code is six characters", len(code) == 6, code)
check("and has no character anybody misreads",
      not (set(code) & set("O0I1")), code)

r2 = head_c.post("/api/craxlearn/remote/open", json={})
check("asking again returns the SAME code, not a second board",
      r2.json().get("code") == code,
      f"{code} vs {r2.json().get('code')}")

# The phone: a client with no session at all.
phone = TestClient(main.app)
r = phone.post("/api/craxlearn/remote/join", json={"code": "ZZZZZZ"})
check("a code nobody is using is refused", r.status_code == 404, str(r.status_code))
r = phone.post("/api/craxlearn/remote/join", json={"code": code.lower()})
check("the real code pairs, in either case", r.status_code == 200, r.text[:120])
check("and the phone is told which board it has",
      r.json().get("board") == head_u.name, r.text[:80])

# ---- what a paired phone may do -----------------------------------------
print("\nWhat a remote may do")
r = phone.post("/api/craxlearn/remote/cmd",
               json={"code": code, "kind": "teach",
                     "payload": {"topic": "photosynthesis", "level": "Class 10"}})
check("it can say what to teach", r.status_code == 200, r.text[:120])
r = phone.post("/api/craxlearn/remote/cmd",
               json={"code": code, "kind": "slide", "payload": {"to": "next"}})
check("it can turn a page", r.status_code == 200, str(r.status_code))
r = phone.post("/api/craxlearn/remote/cmd",
               json={"code": code, "kind": "drop_database", "payload": {}})
check("anything not on the list is refused", r.status_code == 400,
      str(r.status_code))

# The whole argument for letting an unauthenticated phone in: it can change a
# screen and reach nothing else.
for path in ("/api/craxlearn/me", "/api/craxlearn/remote/poll",
             f"/api/class/{klass.id}/materials"):
    rr = phone.get(path)
    check(f"a remote cannot reach {path}", rr.status_code == 401,
          str(rr.status_code))

# ---- the board collects them --------------------------------------------
print("\nThe board collecting")
r = head_c.get("/api/craxlearn/remote/poll")
body = r.json()
check("the board is linked", body.get("linked") is True, r.text[:120])
kinds = [c["kind"] for c in body.get("cmds", [])]
check("and gets the two commands that were sent, in order",
      kinds == ["teach", "slide"], str(kinds))
check("the topic survived the trip",
      (body["cmds"][0]["payload"].get("topic") == "photosynthesis"),
      str(body["cmds"][0]["payload"]))

# A command is handed over once. A board that reloads must not replay a
# lesson's worth of a teacher's remote at the class.
again = head_c.get("/api/craxlearn/remote/poll").json()
check("a command is handed over once and once only",
      again.get("cmds") == [], str(again.get("cmds")))

# Somebody else's board is not this one.
r = far_c.get("/api/craxlearn/remote/poll")
check("another teacher's board is not linked to this code",
      r.json().get("linked") is False, r.text[:120])

# ---- guessing and using are limited differently -------------------------
print("\nLimits")
main._REMOTE_TRIES.clear()
tapping = [phone.post("/api/craxlearn/remote/cmd",
                      json={"code": code, "kind": "slide",
                            "payload": {"to": "next"}}).status_code
           for _ in range(40)]
check("forty taps in a row all go through — a teacher turning pages "
      "is not an attack", set(tapping) == {200}, str(sorted(set(tapping))))

main._REMOTE_TRIES.clear()
guesses = [phone.post("/api/craxlearn/remote/join",
                      json={"code": "AAAAAA"}).status_code
           for _ in range(20)]
check("guessing is stopped inside twenty tries", 429 in guesses,
      str(sorted(set(guesses))))

# ---- switching it off ---------------------------------------------------
print("\nSwitching off")
head_c.post("/api/craxlearn/remote/close", json={})
main._REMOTE_TRIES.clear()
r = phone.post("/api/craxlearn/remote/cmd",
               json={"code": code, "kind": "home", "payload": {}})
check("a closed board stops taking commands", r.status_code == 404,
      str(r.status_code))
r = phone.post("/api/craxlearn/remote/join", json={"code": code})
check("and the code no longer pairs", r.status_code == 404, str(r.status_code))

# ---- keeping a lesson on the subject page -------------------------------
print("\nKeeping a lesson")
LESSON = {
    "title": "Photosynthesis",
    "steps": [
        {"t": "A leaf takes in carbon dioxide and water and uses light to\n"
              "build sugar.", "where": "", "code": ""},
        {"t": "Raise the light and the rate climbs until something else\n"
              "runs short.", "where": "", "code": ""},
    ],
    "takeaway": "Light is the energy source, not the raw material.",
}
r = head_c.post("/api/craxlearn/board/save",
                json={"class_id": klass.id, "topic": "photosynthesis",
                      "title": "Photosynthesis", "subject": "Biology",
                      "note": "What we did on Tuesday.", "lesson": LESSON})
check("a teacher can keep what was taught", r.status_code == 200, r.text[:160])
mat = r.json().get("material", {})
check("it is filed as a lesson, not a link or a file",
      mat.get("kind") == "lesson", str(mat.get("kind")))
check("under the subject it was given", mat.get("subject") == "Biology",
      str(mat.get("subject")))
check("with the teaching in it, not just the title",
      "carbon dioxide" in (mat.get("body") or ""), (mat.get("body") or "")[:60])
check("and the takeaway",
      "Light is the energy source" in (mat.get("body") or ""))

r = kid_c.get(f"/api/class/{klass.id}/materials")
check("the class can read it", r.status_code == 200, r.text[:120])
kept = [m for m in r.json().get("materials", []) if m.get("kind") == "lesson"]
check("it is on their subject page", len(kept) >= 1, str(len(kept)))
check("and carries the teacher's name, so they know whose lesson it is",
      kept and kept[0].get("by") == head_u.name, str(kept[0].get("by") if kept else None))

r = far_c.post("/api/craxlearn/board/save",
               json={"class_id": klass.id, "topic": "photosynthesis",
                     "title": "Photosynthesis", "subject": "Biology",
                     "lesson": LESSON})
check("a teacher cannot file a lesson into another school's class",
      r.status_code in (403, 404), str(r.status_code))

r = head_c.post("/api/craxlearn/board/save",
                json={"class_id": klass.id, "topic": "nothing",
                      "title": "Nothing", "subject": "", "lesson": {}})
check("an empty lesson is refused rather than filed as a blank page",
      r.status_code == 400, str(r.status_code))

r = kid_c.post("/api/craxlearn/board/save",
               json={"class_id": klass.id, "topic": "x", "title": "x",
                     "lesson": LESSON})
check("a student cannot file anything on the subject page",
      r.status_code in (401, 403), str(r.status_code))

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
