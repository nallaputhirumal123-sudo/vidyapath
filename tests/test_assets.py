"""Every ?v= hash in an app page must match the file it points at.

The hashes exist to defeat browser caching, and they are written into the HTML
by hand. So a .js file can change while its URL does not — and then every
browser that has already loaded the page keeps serving its cached copy. The
change is committed, deployed, and running nowhere.

Nothing else catches this. The tests all read files from disk, so they pass.
The server serves the new file to anyone who asks for it, so a fetch in the
console looks right. Only a real browser with a warm cache shows the fault,
and it shows it as "the fix did not work".

Two were stale when this was written: scanner.js, carrying the LaTeX
rendering and the corrected findings list, and three3d.js, carrying the whole
computed-surface renderer. Both had been shipped. Neither was running.

Run tools/stamp_assets.py to fix.
"""
import hashlib
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASS = FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {name}" + (f"  ({detail})" if detail else ""))
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


PAGES = ["index.html", "craxlearn.html"]
refs, unstamped = [], []
for page in PAGES:
    html = io.open(os.path.join(ROOT, page), encoding="utf-8").read()
    found = re.findall(r"([a-zA-Z0-9_-]+\.js)\?v=([a-f0-9]+)", html)
    check(f"{page} stamps its scripts", len(found) >= 3, f"{len(found)} found")
    refs += [(page, n, v) for n, v in found]
    # A script loaded without a stamp is cached forever with no way to
    # bust it.
    unstamped += [f"{page}:{m}" for m in
                  re.findall(r'<script src="([^"]+)"', html)
                  if m.endswith(".js") and "?v=" not in m and "//" not in m]

for page, name, stamped in refs:
    path = os.path.join(ROOT, name)
    if not os.path.exists(path):
        check(f"{name} exists", False, "referenced but not on disk")
        continue
    with io.open(path, "rb") as fh:
        real = hashlib.sha256(fh.read()).hexdigest()[:10]
    check(f"{page}: {name} hash is current", stamped == real,
          real if stamped == real else
          f"html says {stamped}, file is {real} — run tools/stamp_assets.py")

check("no local script is loaded unstamped", not unstamped,
      ", ".join(unstamped[:4]))

print(f"\nPASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
