"""Signing out of a class-code account must not destroy it.

A child taps their name and is signed in. There is no email that can receive
anything and no password anybody holds — the account is reachable ONLY by
tapping that name again. So the register hiding names that had been claimed
was not a cosmetic choice: it meant signing out was permanent, and the class
said "everybody on this register has already signed in", which was true and
useless.

What this suite pins down is that the second tap lands on the SAME account,
not a new one beside it. A child who signs out and gets a fresh empty account
with their own name on it has lost their work just as completely as one who
cannot get in at all — and it looks like it worked, which is worse.
"""
import os, sys, time
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main as m
from fastapi.testclient import TestClient

P, F = [], []
def ck(n, c, d=""):
    (P if c else F).append(n + (f" — {d}" if d else ""))

stamp = int(time.time())
db = m.SessionLocal()

# A school, a class, a register of three.
k = m.Klass(name=f"Rejoin {stamp}", school="Rejoin School",
            join_code=f"VP-RJ{stamp % 10000:04d}", teacher_id=0)
db.add(k); db.commit(); db.refresh(k)
CODE = k.join_code
CID = k.id
for nm in ("Asha Rao", "Bharat Singh", "Chitra Nair"):
    db.add(m.RosterName(class_id=CID, name=nm, claimed_by=0))
db.commit()
db.close()

A = TestClient(m.app)

# ---------- first time in ----------
r = A.post("/api/craxlearn/code", json={"code": CODE})
ck("the code finds the class", r.status_code == 200, str(r.status_code))
d = r.json()
ck("the register is ready", d.get("roster_ready") is True)
ck("all three names are offered", len(d.get("names", [])) == 3,
   str(len(d.get("names", []))))
ck("nobody is marked as returning yet",
   all(not n.get("taken") for n in d["names"]))

asha = [n for n in d["names"] if n["name"] == "Asha Rao"][0]
r = A.post("/api/craxlearn/claim", json={"code": CODE, "roster_id": asha["id"]})
ck("tapping a name signs you in", r.status_code == 200, r.text[:120])
ck("a first claim is not flagged as a return", r.json().get("returning") is False)

me = A.get("/api/auth/me")
ck("the session is real", me.status_code == 200, str(me.status_code))
UID = me.json().get("id")
ck("signed in under that name", me.json().get("name") == "Asha Rao",
   str(me.json().get("name")))

# Something of hers, posted through the route a child actually uses, so
# "the same account" is checked against real work and not a hand-made row.
ASKED = f"Why does a straw look bent in water {stamp}"
r = A.post(f"/api/class/{CID}/discussion",
           json={"subject": "Science", "body": ASKED})
ck("she can ask something in her class", r.status_code == 200, r.text[:140])

# ---------- out ----------
A.post("/api/auth/logout")
ck("logging out ends the session", A.get("/api/auth/me").status_code in (401, 403),
   str(A.get("/api/auth/me").status_code))

# ---------- and back in ----------
# This is the whole bug. Before the fix the register came back with two names
# and Asha was not one of them.
r = A.post("/api/craxlearn/code", json={"code": CODE})
d2 = r.json()
ck("the register still offers every name", len(d2.get("names", [])) == 3,
   str(len(d2.get("names", []))))
back = [n for n in d2["names"] if n["name"] == "Asha Rao"]
ck("her own name is still on the list", len(back) == 1,
   "the register hid it, so she is locked out")
ck("her name is marked as one that has been here before",
   bool(back and back[0].get("taken")))
ck("names nobody took are not marked",
   all(not n["taken"] for n in d2["names"] if n["name"] != "Asha Rao"))

# Everything below needs her name to still be offered. Without this guard the
# suite raised IndexError here and printed a traceback instead of the list of
# failures — which is the wrong way to report the one bug it exists to catch.
if not back:
    print("\n".join("PASS " + x for x in P))
    print("\n".join("FAIL " + x for x in F))
    print("FAIL she cannot get back in at all — nothing below could be checked")
    print(f"\n{len(P)} passed, {len(F) + 1} failed")
    sys.exit(1)

r = A.post("/api/craxlearn/claim", json={"code": CODE, "roster_id": back[0]["id"]})
ck("tapping it again signs her back in", r.status_code == 200, r.text[:140])
ck("and says it is a return", r.json().get("returning") is True)

me2 = A.get("/api/auth/me")
ck("signed in again", me2.status_code == 200, str(me2.status_code))
ck("SAME account, not a new one with the same name",
   me2.json().get("id") == UID, f"{me2.json().get('id')} vs {UID}")

# Her work is still hers.
db = m.SessionLocal()
post = db.query(m.ClassPost).filter(m.ClassPost.body == ASKED).first()
ck("what she wrote is still on the account she came back to",
   post is not None and post.user_id == UID,
   f"{getattr(post, 'user_id', None)} vs {UID}")
# Counted against THIS class, not by name. The development database holds
# an Asha Rao from every suite that ever needed a student, so counting the
# name counts other people's test data and fails on a correct fix.
n_here = (db.query(m.ClassMember)
            .filter(m.ClassMember.class_id == CID,
                    m.ClassMember.user_id == UID).count())
ck("signing back in did not add her to the class twice", n_here == 1,
   str(n_here))
n_members = db.query(m.ClassMember).filter(m.ClassMember.class_id == CID).count()
ck("she is the only child in the class so far", n_members == 1, str(n_members))
db.close()

# ---------- the class is still hers ----------
cl = A.get("/api/class/mine")
ck("she is still in the class", cl.status_code == 200 and
   any(c.get("id") == CID for c in (cl.json().get("classes") or cl.json() or [])),
   cl.text[:140])

# ---------- a name nobody has taken still works normally ----------
b = [n for n in d2["names"] if n["name"] == "Bharat Singh"][0]
B = TestClient(m.app)
r = B.post("/api/craxlearn/claim", json={"code": CODE, "roster_id": b["id"]})
ck("an untouched name still claims fresh", r.status_code == 200, r.text[:120])
ck("and is not a return", r.json().get("returning") is False)
ck("which is a different account",
   B.get("/api/auth/me").json().get("id") != UID)

db = m.SessionLocal()
ck("the class now holds exactly the two children who signed in",
   db.query(m.ClassMember).filter(m.ClassMember.class_id == CID).count() == 2)
db.close()

# ---------- the guards still hold ----------
r = A.post("/api/craxlearn/code", json={"code": "VP-NOPE99"})
ck("a wrong code is still refused", r.status_code == 404, str(r.status_code))
r = A.post("/api/craxlearn/claim", json={"code": CODE, "roster_id": 99999999})
ck("a name from another class is still refused", r.status_code == 404,
   str(r.status_code))

# A class-code account is still shut out of the job half, returning or not.
ck("a returning child still cannot reach the job board",
   A.get("/api/jobs?limit=5").status_code in (401, 402, 403),
   str(A.get("/api/jobs?limit=5").status_code))

print("\n".join("PASS " + x for x in P))
print("\n".join("FAIL " + x for x in F))
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
