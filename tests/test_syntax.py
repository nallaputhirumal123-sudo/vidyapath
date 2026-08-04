"""Every script the browser runs must actually parse.

craxle.com served 200 and hung on "Loading…". The inline block in index.html
never ran, so nothing in it was defined and boot() never fired. Every external
module loaded perfectly, which is exactly what made it look like a server fault
when it was one line of mine:

    toast("... go straight "
          "there.");

Python joins adjacent string literals. JavaScript does not. One missing plus
sign killed a 455,000-character block and the site stopped opening for
everybody.

Nothing caught it. The Python tests all passed — they never load the page. The
asset tests passed — the file was there and its hash matched. The style and
script tests passed — they check names and rules, not grammar. A file can be
perfectly consistent and still not be a program.

So this parses them, with a real JavaScript engine rather than a regex, because
the only thing that reliably knows whether JavaScript parses is a JavaScript
parser. Node is used when it is there and the check says so plainly when it is
not — a check that silently passes because its tool is missing is worse than no
check, since it is trusted.
"""
import io
import os
import re
import subprocess
import sys
import glob
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {name}" + (f"  ({detail})" if detail else ""))
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def have_node():
    try:
        subprocess.run(["node", "--version"], capture_output=True, timeout=20,
                       check=True)
        return True
    except Exception:
        return False


def parses(source, label):
    """Ask node whether this is valid JavaScript. Returns (ok, message)."""
    fd, path = tempfile.mkstemp(suffix=".js")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(source)
        r = subprocess.run(["node", "--check", path],
                           capture_output=True, text=True, timeout=90)
        if r.returncode == 0:
            return True, ""
        err = (r.stderr or "").strip().splitlines()
        # The useful part is the file:line and the SyntaxError, not the stack.
        keep = [ln for ln in err
                if "SyntaxError" in ln or re.search(r"\.js:\d+", ln)]
        return False, " | ".join(keep[:3])[:260] or (err[0] if err else "?")
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


print("\nthe tool this check depends on")
node = have_node()
check("node is available to parse with", node,
      "without it this test cannot tell a broken script from a working one, "
      "and a check that passes because its tool is missing is worse than none")
if not node:
    print(f"\nPASSED {PASS}   FAILED {FAIL}")
    sys.exit(1)

PAGES = [p for p in ("index.html", "craxlearn.html", "admin.html")
         if os.path.exists(p)]
markup = "".join(io.open(p, encoding="utf-8", errors="replace").read()
                 for p in PAGES)

print("\nthe scripts the browser loads on their own")
loaded, orphans = [], []
for f in sorted(glob.glob("*.js")):
    (loaded if f in markup else orphans).append(f)
for f in loaded:
    src = io.open(f, encoding="utf-8", errors="replace").read()
    ok, why = parses(src, f)
    check(f"{f} parses", ok, why)

# A file no page loads cannot break the site, so it does not fail this. It is
# still worth saying out loud: _j.js has been in the repo since 2023, is
# referenced by nothing, and does not parse. Reporting it as a broken script
# would be wrong, and saying nothing would leave the next person wondering why
# the count does not match the directory.
if orphans:
    print(f"  note  {len(orphans)} script(s) no page loads: "
          + ", ".join(orphans))

print("\nand the inline blocks inside the pages")
INLINE = re.compile(r'<script(?![^>]*\ssrc=)[^>]*>([\s\S]*?)</script>', re.I)
for page in ("index.html", "craxlearn.html", "admin.html"):
    if not os.path.exists(page):
        continue
    html = io.open(page, encoding="utf-8", errors="replace").read()
    blocks = [b for b in INLINE.findall(html) if len(b.strip()) > 40]
    check(f"{page} has script to check", bool(blocks), f"{len(blocks)} blocks")
    for i, b in enumerate(blocks):
        # A JSON-LD or template block is not JavaScript and must not be
        # reported as broken JavaScript.
        if re.match(r"^\s*[\[{]", b.strip()) and "function" not in b:
            continue
        ok, why = parses(b, f"{page}#{i}")
        check(f"{page} inline block {i} parses ({len(b):,} chars)", ok, why)

print(f"\nPASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
