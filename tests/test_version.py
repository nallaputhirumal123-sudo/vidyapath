"""The version has to move when the code does.

VERSION sat at 6.8.3 across forty commits, and I read it, concluded production
was behind, and told the user none of the day's work was deployed. It had all
been live for hours. The commit field beside it said so — I read the wrong one.

A version string that does not change is worse than no version string: it does
not merely fail to inform, it actively misleads somebody trying to work out
what is running. So this pins the two facts that would have stopped me:

**The version is a real version.** Three numbers, so it can be compared.

**The commit is what actually identifies a build.** It comes from the deploy
environment and is the field to trust when the two disagree — which is exactly
the case that caught me out.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["JOBS_ENABLED"] = "0"

import main                                        # noqa: E402

PASS = FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {name}" + (f"  ({detail})" if detail else ""))
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


raw = io.open("VERSION", encoding="utf-8").read().strip()

print("\nthe version file")
check("it is a comparable version", bool(re.fullmatch(r"\d+\.\d+\.\d+", raw)),
      raw)
check("main.py reads it rather than hard-coding one", main.VERSION == raw,
      f"{main.VERSION!r} vs {raw!r}")
check("it is not the value that went stale for forty commits",
      raw != "6.8.3",
      "a version that never moves misleads anybody trying to work out what "
      "is running")

print("\nwhat actually identifies a build")
check("a commit is reported alongside it", hasattr(main, "GIT_SHA"))
check("it comes from the deploy environment, not the file",
      "RAILWAY_GIT_COMMIT_SHA" in io.open("main.py", encoding="utf-8").read(),
      "when the two disagree the commit is the one to trust")
check("and it falls back to something honest rather than a fake sha",
      main.GIT_SHA == "local" or re.fullmatch(r"[0-9a-f]{7}", main.GIT_SHA),
      main.GIT_SHA)

print(f"\nPASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
