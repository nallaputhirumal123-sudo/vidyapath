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


# ---------------------------------------------------------------------------
# A file that is not there must say so.
#
# The 404 handler is also the single-page fallback, so every unmatched path
# was answered with index.html and a 200 -- including /typo.js. A browser
# then parses 700KB of HTML as JavaScript, the inline script dies on the
# first tag, and the entire application goes blank over one mistyped src,
# while the network tab shows a confident green 200.
#
# Client routes never carry a file extension, which is what makes it safe to
# split the two apart on exactly that.
import os as _os                                               # noqa: E402

_os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
_os.environ["ALLOW_SQLITE"] = "1"
_os.environ["JOBS_ENABLED"] = "0"
_os.environ.setdefault("JWT_SECRET", "d" * 40)
_os.environ["DOTENV_PATH"] = "nonexistent.env"
sys.path.insert(0, ROOT)          # this file otherwise only reads from disk
import main as _main                                           # noqa: E402
from fastapi.testclient import TestClient                      # noqa: E402

_C = TestClient(_main.app)

for _p in ("/nope.js", "/missing.css", "/gone.png", "/absent.woff2"):
    _r = _C.get(_p)
    check(f"{_p} is a 404, not the whole app", _r.status_code == 404,
          f"{_r.status_code}, {len(_r.content)} bytes")
    check(f"{_p} does not return HTML",
          "text/html" not in _r.headers.get("content-type", ""),
          _r.headers.get("content-type", ""))

# ...and the fallback still does its job, or every deep link breaks.
for _p in ("/careers", "/home", "/some/deep/client/route"):
    _r = _C.get(_p)
    check(f"{_p} still gets the app", _r.status_code == 200
          and "text/html" in _r.headers.get("content-type", ""),
          str(_r.status_code))

# A file that IS there is untouched by any of this.
_r = _C.get("/mock.js")
check("a real script is still served", _r.status_code == 200
      and len(_r.content) > 1000, str(_r.status_code))


print(f"\nPASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
