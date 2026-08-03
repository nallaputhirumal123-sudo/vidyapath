"""The stylesheets are built by joining arrays of strings — so check they parse.

scanner.js builds its CSS from a list of fragments, and a rule is spread over
several entries. Inserting a new rule after the line that starts .scans put it
*inside* .scans, producing "border:1px solid #3fae6a;background:...;.scwarn{"
— which silently kills both rules. The browser says nothing, the page just
looks slightly wrong, and nothing in the test suite would have noticed.

Brace balance is a crude check and it catches exactly that mistake, which is
the one this construction invites.
"""
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


def balanced(css):
    depth = 0
    for ch in css:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                return False, "a closing brace with nothing open"
    return depth == 0, ("" if depth == 0 else f"{depth} rule(s) left unclosed")


def joined_css(path):
    """The CSS a file builds from an array of string fragments."""
    src = open(os.path.join(ROOT, path), encoding="utf-8").read()
    m = re.search(r"var CSS = \[(.*?)\]\.join\(\"\"\);", src, re.S)
    if not m:
        return None
    parts = re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1))
    return "".join(p.encode().decode("unicode_escape") for p in parts)


for path in ("scanner.js", "lab.js"):
    css = joined_css(path)
    if css is None:
        print(f"  ..    {path} has no joined CSS array, skipping")
        continue
    ok, why = balanced(css)
    check(f"{path} stylesheet is balanced", ok, why)
    # A fragment landing inside another rule shows up as a selector where a
    # property should be. This is the exact shape of the bug.
    stray = re.findall(r"[;{]\s*\.[a-zA-Z][\w-]*\s*\{", css)
    check(f"{path} has no rule nested inside another",
          not stray, str(stray[:3]))

# index.html's CSS is written literally, but the same insert-by-line edits
# happen there, so it gets the same check.
html = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
blocks = re.findall(r"<style[^>]*>(.*?)</style>", html, re.S)
check("index.html has a stylesheet", bool(blocks), f"{len(blocks)} block(s)")
for i, b in enumerate(blocks):
    ok, why = balanced(b)
    check(f"index.html <style> #{i + 1} is balanced", ok, why)

# The rules the checks depend on must actually exist, or a finding is
# rendered as unstyled text and reads as part of the lesson.
for sel in (".sb-checked", ".mfrac", ".mnum", ".mden"):
    check(f"index.html defines {sel}", sel + "{" in html.replace("\n", ""),
          "")
sc = joined_css("scanner.js") or ""
for sel in (".scwarn", ".scans"):
    check(f"scanner.js defines {sel}", sel + "{" in sc)

print(f"\nPASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
