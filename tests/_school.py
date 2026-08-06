"""Making a teacher who can actually sign in, once, for every suite.

A subject code is a board code now. It opens one class and one subject on a
classroom board and signs nobody in, because it is read off that board by
every child in the room. A teacher's identity is their address and their own
password, and the office issues the password once when it creates them.

Nine suites had their own copy of "make a teacher and get a session", and
every one of them went through the subject code. Nine copies is how a rule
change becomes nine near-identical edits, one of which is subtly different
and passes for the wrong reason — so it is written here instead.

Import it as `from _school import teacher_on` after the usual sys.path line;
`tests/` is on the path because the suites are run from their own directory.
"""
import time

from fastapi.testclient import TestClient


def make_staff(main, office, name, role="teacher", email=None):
    """Create a member of staff and return (client, user_id, email, password).

    `office` is a signed-in school-admin client. The password comes back from
    the route exactly once, which is the whole point of it: the office reads
    it out or writes it down, and there is no second copy anywhere.
    """
    email = email or f"{name.lower().replace(' ', '')}{int(time.time()*1000) % 10**9}@example.com"
    r = office.post("/api/head/staff",
                    json={"name": name, "email": email, "role": role})
    assert r.status_code == 200, r.text
    d = r.json()
    pw = d.get("temporary_password") or ""
    assert pw, f"no password came back: {d}"
    c = TestClient(main.app)
    lr = c.post("/api/auth/login", json={"email": email, "password": pw})
    assert lr.status_code == 200, lr.text
    return c, d["user_id"], email, pw


def teacher_on(main, office, cid, subject, name):
    """A teacher holding one subject in one class, signed in.

    The way a school actually does it: the office creates the subject, creates
    the person, puts one on the other, and hands over a password. The subject
    code that comes out of it is for a BOARD and is not used here.
    """
    slot = office.post(f"/api/head/class/{cid}/slot",
                       json={"subject": subject, "teacher_id": 0}).json()
    c, uid, email, pw = make_staff(main, office, name)
    r = office.post("/api/head/assign",
                    json={"class_id": cid, "subject": subject,
                          "user_id": uid})
    assert r.status_code == 200, r.text
    return c, uid, slot.get("code", ""), slot.get("id", 0)
