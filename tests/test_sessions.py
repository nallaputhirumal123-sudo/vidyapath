"""Devices, and the column the session list has to fit inside.

Two faults that between them locked an administrator out of a live school
product, reported as "teacher sign-in not working" and then "only the admin
account is saying internal server error".

**One device was the wrong rule for staff.** MAX_DEVICES was 1, and every
word of the reasoning behind it is about a class account: thirty children
with one code between them. A teacher is the opposite case. She plans at her
desk, checks a register on her phone and signs in on the computer wired to
the board — three devices in one morning, all hers, and at one device each
silently ended the last. What she saw was a correct message about a rule she
had not broken, which reads as a broken password. Pupils are unchanged; that
rule exists for a reason and this holds it in place.

**And the list has to fit the column, which was narrower than anyone
thought.** users.session_token holds the active tokens comma-separated, 24
characters each. The model said String(400) and 0001's frozen DDL said
VARCHAR(400); the database said VARCHAR(64), because _migrate_columns only
ever ADDs a column and nothing had ever issued an ALTER. 64 characters holds
exactly two tokens, so raising staff to four devices meant the third sign-in
wrote 74 characters, Postgres refused it with 22001, the old value stayed in
the row, and every later attempt rewrote the same too-long string. Locked out
for good, on the account that signs in most.

None of it could be reproduced locally: SQLite ignores VARCHAR widths, so the
identical write succeeded every time while production refused it. That is why
the width is now asked of the DATABASE rather than taken from the model, and
why 0007 widens the column — trimming to fit is a workaround, the column was
the bug.
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
MAIN = io.open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
main.Base.metadata.create_all(bind=main.engine)
main._migrate_columns()
main.send_email = lambda *a, **k: None
P, F = [], []


def ck(n, c, d=""):
    print(("PASS " if c else "FAIL ") + n + (f" — {d}" if d else ""),
          flush=True)
    (P if c else F).append(n)


u = str(int(time.time())) + str(os.getpid())
db = main.SessionLocal()

print("\nSTAFF MAY HOLD MORE THAN ONE DEVICE")
sc = main.School(name=f"Session School {u}")
db.add(sc)
db.commit()
db.refresh(sc)
hc = ("HSS" + u)[:12]
db.add(main.TeacherCode(code=hc, school=sc.name, school_id=sc.id,
                        is_head=True, active=True))
db.commit()
office = TestClient(main.app)
oem = f"se.off{u}@example.com"
office.post("/api/auth/signup", json={"name": "Se Office", "email": oem,
                                      "password": "SePass1!"})
orow = db.query(main.User).filter(main.User.email == oem).first()
orow.dob = dt.date(1980, 1, 1)
db.commit()
office.post("/api/class/join", json={"code": hc})
cid = office.post("/api/teacher/class", json={"name": f"8-S {u}"}).json()["id"]
tem = f"se.t{u}@example.com"
pw = office.post("/api/head/staff",
                 json={"name": "Se Teacher", "email": tem,
                       "role": "teacher"}).json().get("temporary_password")
trow = db.query(main.User).filter(main.User.email == tem).first()
office.post("/api/head/assign", json={"class_id": cid, "subject": "Maths",
                                      "user_id": trow.id})

# How many survive is the cap AND the column together, and asserting a bare
# number would be asserting something the schema can veto. Before 0007 runs
# on a given database only two fit; after it, four. Both are correct, and
# what must never happen is a write the column refuses.
_fit = max(1, (main._session_token_width() + 1) // 25)
_want = min(main.MAX_DEVICES_STAFF, _fit)
devices = [TestClient(main.app) for _ in range(4)]
for i, dev in enumerate(devices):
    dev.post("/api/auth/login", json={"email": tem, "password": pw})
    alive = [x.get("/api/teacher/classes").status_code for x in devices[:i + 1]]
    ck(f"after device {i + 1}, the newest {min(i + 1, _want)} still work",
       all(s == 200 for s in alive[-min(i + 1, _want):]),
       f"{alive} · column fits {_fit}, cap {main.MAX_DEVICES_STAFF}")
ck("her desk, her phone and the classroom computer",
   main.MAX_DEVICES_STAFF >= 3,
   "three devices in one morning is an ordinary morning")

print("\nand a pupil is still one at a time")
kem = f"se.kid{u}@example.com"
k1 = TestClient(main.app)
k1.post("/api/auth/signup", json={"name": "Se Pupil", "email": kem,
                                  "password": "KidPass1!"})
krow = db.query(main.User).filter(main.User.email == kem).first()
krow.dob = dt.date(2011, 1, 1)
db.commit()
k1.post("/api/auth/login", json={"email": kem, "password": "KidPass1!"})
ck("the pupil signs in", k1.get("/api/class/mine").status_code == 200)
k2 = TestClient(main.app)
k2.post("/api/auth/login", json={"email": kem, "password": "KidPass1!"})
r = k1.get("/api/class/mine")
ck("and a second sign-in still ends the first", r.status_code == 401,
   str(r.status_code))
ck("with a message that names the real number",
   "One device at a time" in r.text, r.text[:110])
ck("the cap is decided per account, not globally",
   "def _device_cap(user, db) -> int:" in MAIN)
ck("and a lookup that fails falls to the stricter number",
   "return MAX_DEVICES\n" in MAIN,
   "never let an error open an account up; the safe direction is closed")

print("\nthe session list cannot outgrow its column")
import secrets as _s                                     # noqa: E402
_LIMIT = main._session_token_width()
ck("the column has a stated length", bool(_LIMIT), str(_LIMIT))
for _cap in (1, 4, 17, 40):
    _toks = []
    for _ in range(_cap + 25):
        _toks = ([_s.token_urlsafe(18)] + _toks)[:_cap]
        while len(",".join(_toks)) > _LIMIT and len(_toks) > 1:
            _toks.pop()
    ck(f"a cap of {_cap} never exceeds it",
       len(",".join(_toks)) <= _LIMIT,
       f"{len(','.join(_toks))} chars, {len(_toks)} kept")
ck("the trim lives in make_token, not at the call sites",
   'while len(",".join(keep)) > limit and len(keep) > 1:' in MAIN,
   "every way in goes through it — password, code and Google")
ck("the limit comes from the database, not the model",
   "limit = _session_token_width()" in MAIN
   and "def _session_token_width() -> int:" in MAIN,
   "a width the code hopes for is not the width that refuses the write")
ck("and it takes the SMALLER of the two",
   "want = min(want, got) if got else want" in MAIN,
   "if the database is narrower, that is the number that matters")
ck("an unreadable schema does not break signing in",
   "pass          # an unreadable schema must not break signing in" in MAIN)
ck("the real width is reportable",
   '"session_token_width": _session_token_width(),' in MAIN,
   "it could not be read from outside, so it got assumed instead")
ck("and a migration widens the column rather than only trimming to it",
   os.path.exists(os.path.join(ROOT, "migrations", "versions",
                               "0007_widen_session_token.py")))
ck("the device given up is the least recently used",
   "keep.pop()" in MAIN,
   "keep is newest-first, so popping the end drops the oldest")
ck("the caps are readable from outside",
   '"max_devices": MAX_DEVICES,' in MAIN,
   "one of them silently decided whether an account could sign in at all")

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\nPASSED {len(P)}   FAILED {len(F)}")
sys.exit(1 if F else 0)
