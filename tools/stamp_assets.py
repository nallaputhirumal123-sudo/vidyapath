"""Restamp the ?v= hash on every script index.html loads.

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
HTML = os.path.join(ROOT, "index.html")

PATTERN = re.compile(r"([a-zA-Z0-9_-]+\.js)\?v=([a-f0-9]+)")


def digest(path):
    with io.open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:10]


def main(write=True):
    src = io.open(HTML, encoding="utf-8").read()
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
        print("  every asset hash already matches its file")
    if write and changed:
        io.open(HTML, "w", encoding="utf-8", newline="").write(out)
        print(f"  index.html restamped ({len(changed)} changed)")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main(write="--check" not in sys.argv))
