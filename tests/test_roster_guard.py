"""A class register must not be collectable by guessing codes.

/api/craxlearn/code is unauthenticated on purpose: the point is a login a
nine-year-old can do, with no password to lose. The cost, stated in its own
docstring, is that a valid code returns the first names of every unclaimed
child in that class.

That was an acceptable trade only while a code was hard to find, and it was
not. VP- plus four characters from a 32-letter alphabet is 1,048,576 codes and
nothing stopped anybody working through them — at a hundred guesses a second
the whole space falls in under three hours, and what falls out is the names of
children. Under the DPDP Act that is children's personal data disclosed
without consent.

What is pinned:

**A classroom is never slowed down.** The limits have to sit above real use or
they are a bug that only shows up on the first morning of term.

**A sweep is.** Bursts stop quickly; sustained wrong guesses stop for an hour.

**Rotating addresses does not evade it.** X-Forwarded-For is written by the
client, so a per-address limit alone is theatre. The global ceiling is the part
that cannot be rotated around.

**Codes issued from now on are six characters**, and codes already printed and
handed to children still work.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"   # local test database; refused on a deployment
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"

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
c = TestClient(main.app)


def clear():
    main._CODE_TRIES.clear()
    main._CODE_FAILS.clear()


def guess(code, ip="203.0.113.9"):
    return c.post("/api/craxlearn/code", json={"code": code},
                  headers={"x-forwarded-for": ip})


# a real class to prove the guard does not block real use
db = main.SessionLocal()
klass = main.Klass(name=f"Guard {stamp}", join_code=main._gen_join_code(db),
                   school="Test School", teacher_id=0)
db.add(klass)
db.commit()
db.refresh(klass)
db.add(main.RosterName(class_id=klass.id, name="Ravi K", claimed_by=0))
db.commit()
REAL = klass.join_code

print("\nnew codes are harder to guess")
check("a new class code is six characters", len(REAL) - 3 == 6, REAL)
check("that is a thousandfold bigger space", 32 ** 6 // 32 ** 4 == 1024,
      f"{32**6:,} against {32**4:,}")
old = main.Klass(name=f"Old {stamp}", join_code=f"VP-{stamp % 10000:04d}"[:9],
                 school="Test School", teacher_id=0)
db.add(old)
db.commit()
db.add(main.RosterName(class_id=old.id, name="Asha B", claimed_by=0))
db.commit()
clear()
check("a four-character code already handed out still works",
      guess(old.join_code).status_code == 200,
      "changing the length must not strand a printed code")

print("\na real classroom is not slowed down")
clear()
codes = [guess(REAL).status_code for _ in range(main._CODE_PER_MIN - 1)]
check("repeated correct sign-ins are allowed",
      all(x == 200 for x in codes), f"{len(codes)} in a row")
check("and the register comes back",
      "Ravi K" in guess(REAL).text)

print("\na burst is stopped")
clear()
seen = [guess("VP-ZZZZZZ").status_code for _ in range(main._CODE_PER_MIN + 4)]
check("a burst of guesses ends in 429", 429 in seen,
      f"stopped after {seen.index(429)} tries")
check("it does not answer 404 once throttled",
      seen[-1] == 429, str(seen[-3:]))

print("\nwrong codes are remembered for longer than a minute")
clear()
for i in range(main._CODE_FAILS_PER_IP + 2):
    # spread across the per-minute window so the burst limit is not what
    # stops this — the point is the hourly failure count
    main._CODE_TRIES.clear()
    r = guess(f"VP-QQ{i:04d}")
    if r.status_code == 429:
        break
check("an address that keeps guessing wrong is cut off",
      r.status_code == 429, f"after {i} wrong codes")
main._CODE_TRIES.clear()
check("and stays cut off even with the burst window clear",
      guess("VP-AAAAAA").status_code == 429)
check("a correct code from that address is refused too",
      guess(REAL).status_code == 429,
      "otherwise the block is trivially probed around")

print("\nrotating addresses does not evade it")
clear()
blocked_at = None
for i in range(main._CODE_FAILS_GLOBAL + 40):
    main._CODE_TRIES.clear()
    # a fresh address every single time, which is the whole attack
    r = guess(f"VP-RR{i:04d}", ip=f"198.51.100.{i % 256}")
    if r.status_code == 429:
        blocked_at = i
        break
check("a sweep from many addresses is still stopped",
      blocked_at is not None, f"after {blocked_at} guesses")
check("the ceiling is the global one, not the per-address one",
      blocked_at is not None and blocked_at >= main._CODE_FAILS_PER_IP,
      f"{blocked_at} >= {main._CODE_FAILS_PER_IP}")

print("\nhow long a full sweep would now take")
per_hour = main._CODE_FAILS_GLOBAL
old_space, new_space = 32 ** 4, 32 ** 6
check("unguarded, the old space fell in an afternoon",
      old_space / 100 / 3600 < 3,
      f"{old_space / 100 / 3600:.1f} hours at 100 guesses a second")
check("the guard alone already turns that into months",
      old_space / per_hour / 24 > 60,
      f"{old_space / per_hour / 24:.0f} days")
check("the new one takes over a century",
      new_space / per_hour / 24 / 365 > 100,
      f"{new_space / per_hour / 24 / 365:.0f} years")

print("\nclaiming a name is guarded as well")
clear()
seen = [c.post("/api/craxlearn/claim",
               json={"code": "VP-YYYYYY", "roster_id": 1},
               headers={"x-forwarded-for": "203.0.113.44"}).status_code
        for _ in range(main._CODE_PER_MIN + 3)]
check("guessing at the claim route is throttled too", 429 in seen,
      "otherwise the guard is bypassed by using the other endpoint")

clear()
print(f"\nPASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
