"""Restamp the ?v= hash on every script the app pages load.

Those hashes exist to defeat browser caching, and they are written into the
HTML by hand — so the moment a .js file changes without its hash being
updated, the URL stays the same, every browser that has ever loaded the page
serves its cached copy, and the change reaches nobody. The fix looks deployed.
The tests pass, because tests read the file from disk.

That is not hypothetical. scanner.js and three3d.js were both found stale:
the scanner's LaTeX rendering and the surface renderer had been shipped and
were never actually running in anyone's browser.

Run this after touching any of those files, or let tests/test_assets.py catch
it — it fails on exactly this.
"""
import hashlib
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Every page that loads a module of its own. craxlearn.html shares the board
# modules with index.html, so a stale hash there is the same fault in a room
# full of learners rather than on one job seeker's laptop.
HTMLS = ["index.html", "craxlearn.html"]

PATTERN = re.compile(r"([a-zA-Z0-9_-]+\.js)\?v=([a-f0-9]+)")


def digest(path):
    with io.open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:10]


def main(write=True):
    rc = 0
    for name in HTMLS:
        rc |= stamp_one(os.path.join(ROOT, name), name, write)
    return rc


def stamp_one(html_path, label, write=True):
    if not os.path.exists(html_path):
        print(f"  !! {label} is not on disk")
        return 1
    src = io.open(html_path, encoding="utf-8").read()
    changed, missing = [], []

    def swap(m):
        name, old = m.group(1), m.group(2)
        path = os.path.join(ROOT, name)
        if not os.path.exists(path):
            missing.append(name)
            return m.group(0)
        new = digest(path)
        if new != old:
            changed.append((name, old, new))
        return f"{name}?v={new}"

    out = PATTERN.sub(swap, src)
    for name in missing:
        print(f"  !! {name} is referenced but not on disk")
    for name, old, new in changed:
        print(f"  {name}: {old} -> {new}")
    if not changed:
        print(f"  {label}: every asset hash already matches its file")
    if write and changed:
        io.open(html_path, "w", encoding="utf-8", newline="").write(out)
        print(f"  {label} restamped ({len(changed)} changed)")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main(write="--check" not in sys.argv))
