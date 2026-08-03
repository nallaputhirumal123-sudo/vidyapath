"""Names used in the page that nothing defines.

The board was unusable for days because a dead-code sweep deleted SB_LENSES
while two places still referenced it. Every board render threw ReferenceError
on the first reference, so the assignment to innerHTML never ran and the DOM
kept its previous content — the "Building your lesson..." placeholder. The
lesson had already arrived; the server had answered from cache in ten
milliseconds.

Nothing caught it. The request looked perfect, every other surface worked
because each has its own render, and the error only ever reached a console.
Days were spent on the server, which was innocent throughout.

A ReferenceError on a module-level constant is exactly what a static check
finds for free. This looks for SHOUTING_CASE names — the convention this file
uses for its lookup tables, which is what a cleanup sweep is most likely to
mistake for dead weight — and fails if one is used but never declared.
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


def scripts_of(path):
    src = open(os.path.join(ROOT, path), encoding="utf-8").read()
    if path.endswith(".html"):
        return "\n".join(re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>",
                                    src, re.S))
    return src


def code_only(src):
    """Source with comments and string bodies removed.

    Without this the scan reads prose: ATP, NADPH, MOSFET and ADNOC are words
    in lesson text and comments, not identifiers, and reporting them buries
    the one name that actually matters. Template literals keep their ${...}
    holes, because that is real code and is exactly where SB_LENSES was used.
    """
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    src = re.sub(r"(?m)^\s*//.*$", " ", src)

    out, i, n = [], 0, len(src)
    while i < n:
        ch = src[i]
        if ch in "\"'":
            i += 1
            while i < n and src[i] != ch:
                i += 2 if src[i] == "\\" else 1
            i += 1
            out.append(' "" ')
        elif ch == "`":
            i += 1
            while i < n and src[i] != "`":
                if src[i] == "\\":
                    i += 2
                    continue
                # ${...} is code and is kept, brace-balanced.
                if src[i] == "$" and i + 1 < n and src[i + 1] == "{":
                    depth, j = 1, i + 2
                    while j < n and depth:
                        if src[j] == "{":
                            depth += 1
                        elif src[j] == "}":
                            depth -= 1
                        j += 1
                    out.append(" " + src[i + 2:j - 1] + " ")
                    i = j
                    continue
                i += 1
            i += 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


# Built-ins and browser globals that are legitimately never declared here.
KNOWN = {
    "JSON", "Math", "Object", "Array", "String", "Number", "Boolean", "Date",
    "Map", "Set", "Promise", "RegExp", "Error", "TypeError", "SyntaxError",
    "URL", "URLSearchParams", "FormData", "FileReader", "Blob", "Image",
    "AbortController", "Intl", "NaN", "Infinity", "DOMParser", "Path2D",
    "WebSocket", "Notification", "MutationObserver", "IntersectionObserver",
    "ResizeObserver", "SpeechSynthesisUtterance", "AudioContext", "Audio",
    "CustomEvent", "Event", "XMLHttpRequest", "TextDecoder", "TextEncoder",
    "OK", "URI", "HTML", "PDF", "AI", "UI", "API", "CSS", "SVG", "DOM", "ID",
}

DECL = re.compile(r"\b(?:const|let|var|function|class)\s+([A-Z][A-Z0-9_]{2,})\b")

# A use that must resolve: a SHOUTING_CASE name being read as a table —
# NAME.map(...), NAME[key], NAME(...). That is how every lookup table in this
# codebase is consumed, and it is exactly how SB_LENSES and SB_LENS_ICON were
# used when they were deleted.
#
# Deliberately not "any capitalised word". Regex literals and object keys are
# full of them, and a check that reports GST and DOCX alongside the one real
# fault is a check people stop reading.
USE = re.compile(r"(?<![.\w$])([A-Z][A-Z0-9_]{2,})\s*[.\[(]")

for path in ("index.html", "scanner.js", "lab.js", "sketch.js", "draw.js",
             "three3d.js"):
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        continue
    raw = scripts_of(path)
    src = code_only(raw)
    # Declarations are read from the RAW source on purpose.
    #
    # code_only() strips strings by scanning for quote characters, which a
    # regex literal like /['"]/ desynchronises — everything after it is then
    # treated as string and dropped. That made four perfectly good tables
    # look undeclared. Being lenient here only ever makes the test miss a
    # fault; being lenient about *uses* is what would make it lie.
    declared = set(DECL.findall(raw))
    declared |= set(re.findall(r"\b([A-Z][A-Z0-9_]{2,})\s*=", raw))
    declared |= set(re.findall(r"window\.([A-Z][A-Z0-9_]{2,})", raw))
    used = set(USE.findall(src))
    missing = sorted(used - declared - KNOWN)
    # Other files may define it; check the whole front end before failing.
    if missing:
        everything = "\n".join(
            code_only(scripts_of(p)) for p in
            ("index.html", "scanner.js", "lab.js", "sketch.js", "draw.js",
             "three3d.js")
            if os.path.exists(os.path.join(ROOT, p)))
        elsewhere = (set(DECL.findall(everything))
                     | set(re.findall(r"\b([A-Z][A-Z0-9_]{2,})\s*=", everything))
                     | set(re.findall(r"window\.([A-Z][A-Z0-9_]{2,})",
                                      everything)))
        missing = sorted(set(missing) - elsewhere)
    check(f"{path}: every SHOUTING_CASE name is defined", not missing,
          ", ".join(missing[:6]))

# The specific casualty, named so a re-deletion is unmistakable rather than
# just a count changing.
html = scripts_of("index.html")
for name in ("SB_LENSES", "SB_LENS_ICON"):
    check(f"{name} is defined", bool(
        re.search(r"\b(?:const|let|var)\s+" + name + r"\b", html)),
        "the board cannot render without it")
    check(f"{name} is still used", html.count(name) > 1)

print(f"\nPASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
