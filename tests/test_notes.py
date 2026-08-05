"""Keeping something, and finding it again.

Two categories, because they are two different things and a person revising the
night before an exam should not have to open several to work out which is
which:

    Class notes         what the learner typed against a lesson
    Saved explanations  the lesson itself, kept on purpose

The rules that break quietly, which is why they are pinned here:

**A saved lesson must not ride on every page load.** /api/progress hands the
client every note a user owns, every time the site opens. A typed note is a few
hundred bytes. A saved lesson is several kilobytes, so twenty of them would put
a third of a megabyte on the wire to draw a page nobody asked for. Saved bodies
are deliberately absent from that payload.

**A lesson must not be truncated into it.** The store capped every non-resume
note at 5000 characters. A lesson past that would be cut mid-JSON and stored
looking fine — and would fail when it was READ, long after the person was told
it saved. That is the worst possible place to discover it.

**One person's notes are their own.** They are keyed by user, and the fetch
route takes a key from the URL, which is exactly the shape that leaks somebody
else's if it is not filtered by owner too.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"   # local test database; refused on a deployment
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"

import json                                        # noqa: E402
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


def account(tag):
    c = TestClient(main.app)
    r = c.post("/api/auth/signup", json={"name": f"Note {tag}",
                                         "email": f"nt{tag}{stamp}@example.com",
                                         "password": "NotePass123!"})
    assert r.status_code == 200, r.text
    return c


def saved(title, topic, steps):
    return json.dumps({"title": title, "topic": topic,
                       "when": "2026-08-04T10:00:00",
                       "lesson": {"title": title, "steps": steps,
                                  "takeaway": "."}})


a = account("a")
b = account("b")

STEPS = [{"t": "Water crosses a membrane towards the salt.",
          "where": "", "code": "", "lang": ""}]

print("\nsaving and finding")
r = a.post("/api/note", json={"key": "sbsave_osmosis",
                              "value": saved("Osmosis", "osmosis", STEPS)})
check("a lesson can be kept", r.status_code == 200, r.text[:80])

r = a.get("/api/notes/saved")
items = r.json().get("items", [])
check("it comes back in the list", any(i["title"] == "Osmosis" for i in items))
check("the list carries no bodies",
      all("lesson" not in i for i in items),
      "titles and dates only")

r = a.get("/api/notes/saved/sbsave_osmosis")
check("opening it returns the lesson",
      r.status_code == 200 and r.json()["lesson"]["steps"][0]["t"].startswith("Water"))

print("\norder")
# The client does no sorting of its own, so if the server does not order
# these the list is in whatever order the rows came back — which looks
# arbitrary to somebody scanning for the thing they kept this morning.
for k, when in (("sbsave_older", "2026-07-01T09:00:00"),
                ("sbsave_newer", "2026-08-03T09:00:00")):
    a.post("/api/note", json={"key": k, "value": json.dumps(
        {"title": k, "topic": k, "when": when,
         "lesson": {"title": k, "steps": STEPS, "takeaway": "."}})})
order = [i["key"] for i in a.get("/api/notes/saved").json()["items"]]
check("newest is listed first",
      order.index("sbsave_newer") < order.index("sbsave_older"), str(order))

print("\nwhat rides on every page load")
prog = a.get("/api/progress").json()
check("saved lessons stay out of progress",
      not any(k.startswith("sbsave_") for k in prog.get("notes", {})),
      "they would be sent on every page load")

a.post("/api/note", json={"key": "sbnote_osmosis", "value": "ask about turgor"})
prog = a.get("/api/progress").json()
check("typed notes still arrive with progress",
      prog["notes"].get("sbnote_osmosis") == "ask about turgor")

print("\nthe cap")
big = saved("Long", "long", [{"t": "x" * 40000, "where": "", "code": "",
                              "lang": ""}])
check("a real lesson exceeds the old 5000 cap", len(big) > 5000, f"{len(big)}b")
a.post("/api/note", json={"key": "sbsave_long", "value": big})
r = a.get("/api/notes/saved/sbsave_long")
check("it survives storage whole",
      r.status_code == 200 and len(r.json()["lesson"]["steps"][0]["t"]) == 40000,
      "truncated JSON would fail on read, not on save")

a.post("/api/note", json={"key": "sbnote_big", "value": "y" * 9000})
kept = main.SessionLocal().query(main.Note).filter(
    main.Note.k == "sbnote_big").first()
check("a typed note is still held to 5000", len(kept.v) == 5000,
      f"{len(kept.v)}b — the raised cap is only for saved lessons")

print("\nwhose notes they are")
r = b.get("/api/notes/saved")
check("another account sees none of them",
      not r.json()["items"], r.text[:60])
r = b.get("/api/notes/saved/sbsave_osmosis")
check("and cannot open one by naming its key", r.status_code == 404,
      f"got {r.status_code}")

print("\nremoving")
a.post("/api/note", json={"key": "sbsave_osmosis", "value": ""})
r = a.get("/api/notes/saved")
check("removing takes it out of the list",
      not any(i["key"] == "sbsave_osmosis" for i in r.json()["items"]))

print("\nwhen storage went wrong")
db = main.SessionLocal()
u = db.query(main.User).filter(main.User.email == f"nta{stamp}@example.com").first()
db.add(main.Note(user_id=u.id, k="sbsave_broken", v='{"title":"Cut off'))
db.commit()
r = a.get("/api/notes/saved")
check("a corrupt row does not break the list",
      r.status_code == 200, f"got {r.status_code}")
r = a.get("/api/notes/saved/sbsave_broken")
check("and says so plainly when opened", r.status_code == 422,
      f"got {r.status_code}")

r = a.get("/api/notes/saved/sbnote_osmosis")
check("a typed note is not fetchable as a saved one",
      r.status_code == 400, f"got {r.status_code}")

print(f"\nPASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
