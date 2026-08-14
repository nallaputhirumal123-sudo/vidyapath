"""Where a learner's code runs, and what it can reach from there.

A child is invited to type code into a box and press Run. Everything below
follows from taking that literally.

**It does not run in the page.** Both labs used to: JavaScript through
`new Function(code)()`, Python through Pyodide loaded into the same window.
That window is this application's origin — the session cookie, every API
route, the DOM, and whatever is on screen belonging to somebody else. The
cookie is httponly, so code cannot READ it, and it does not need to:

    fetch("/api/teacher/class/12/roster", {credentials: "include"})

sends it anyway and acts as whoever is signed in. On a personal laptop that
is the learner. On the machine wired to the classroom board, signed in as
the teacher for the period, it is the teacher — their register, their marks,
anything they can POST. A pupil at the board during a lesson is exactly the
person standing in front of that box.

**So: an iframe with sandbox="allow-scripts" and NOT allow-same-origin.**
Those two words together are the whole fix, and adding the second undoes it
completely — "allow-same-origin allow-scripts" is a common pairing and it is
the same as no sandbox at all. What the frame gets is a unique opaque
origin: no cookies, no localStorage, no parent document, and a fetch to
/api/... that is cross-origin, uncredentialed and refused.

**And a CSP, because an opaque origin still has a network.** Nothing in the
frame is worth stealing, so exfiltration is not the worry — being a beacon
is. Without it, code typed into an exercise box can call any host on the
internet, from a school's machines, in the school's name.

**The runtime is served from this site.** Python in a browser is a 14 MB
download that came from a public CDN on first use, and a school network that
blocks the CDN is most of the reason this product exists.
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

SB_ALL = io.open(os.path.join(ROOT, "sandbox.js"), encoding="utf-8").read()
# Comments stripped before anything is looked for.
#
# Every one of these files EXPLAINS the mistake it is avoiding — "adding
# allow-same-origin here would undo the entire file", "it used to run here:
# new Function(code)()" — so a plain search finds the warning and reports
# the thing being warned against. The prose is the most valuable part of
# this codebase and it must not be able to fail a test about the code.
_CUT = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)
SB = _CUT.sub(" ", SB_ALL)
FRAME_ALL = io.open(os.path.join(ROOT, "sandbox-frame.html"),
                    encoding="utf-8").read()
FRAME = _CUT.sub(" ", re.sub(r"<!--.*?-->", " ", FRAME_ALL, flags=re.S))
MAIN = io.open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
IDX = io.open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
BOARD = io.open(os.path.join(ROOT, "craxlearn.html"), encoding="utf-8").read()
P, F = [], []


def ck(name, cond, why=""):
    print(("PASS " if cond else "FAIL ") + name + (" — " + why if why else ""),
          flush=True)
    (P if cond else F).append(name)


print("\nthe code does not run in the page")
ck("the frame is sandboxed", 'setAttribute("sandbox", "allow-scripts")' in SB)
ck("and allow-same-origin is nowhere near it",
   "allow-same-origin" not in SB and "allow-same-origin" not in FRAME,
   "those two together are the same as no sandbox at all, and it is the "
   "one mistake that would undo the whole file silently")
for bad, why in (("allow-forms", "a form can post out of the frame"),
                 ("allow-popups", "a popup escapes the sandbox's rules"),
                 ("allow-top-navigation", "it can replace the page itself"),
                 ("allow-modals", "it can hold the tab with a dialog")):
    ck("nor " + bad, bad not in SB, why)
ck("no learner code is executed in the app's own window",
   "new Function(" not in _CUT.sub(" ", IDX).split("function runPython")[0][-4000:],
   "this is where it used to happen, and the cookie went with it")

print("\nan opaque origin still has a network, so it is told where it may go")
CSP = re.search(r'http-equiv="Content-Security-Policy"[^>]*content="([^"]*)"',
                FRAME_ALL, re.S)
ck("the runner carries a policy", bool(CSP))
POL = " ".join(CSP.group(1).split()) if CSP else ""
ck("everything is refused by default", "default-src 'none'" in POL,
   "an allowlist that starts from nothing is the only kind worth having")
ck("it may talk to this site and the runtime's CDN, and nowhere else",
   "connect-src 'self' https://cdn.jsdelivr.net" in POL,
   "code in an exercise box could otherwise beacon to any host on the "
   "internet, from a school's machines, in the school's name")
ck("images, frames and everything else stay closed",
   "img-src" not in POL and "default-src 'none'" in POL)
ck("scripts come from the same two places",
   "script-src 'self'" in POL and "https://cdn.jsdelivr.net" in POL)
ck("eval is allowed, and that is the feature not a hole",
   "'unsafe-eval'" in POL and "'wasm-unsafe-eval'" in POL,
   "running the learner's code IS the product; the sandbox attribute is "
   "what makes it safe, and the policy closes the network it cannot")

print("\nresults come back on a channel nobody else holds")
ck("a MessageChannel, not window messages", "new MessageChannel()" in SB,
   "an opaque origin cannot be named in postMessage's targetOrigin, so "
   '"*" would be the only option and any frame could then answer for it')
ck("the port is handed over once", "[chan.port2]" in SB)
ck("and the frame only ever answers on it",
   "PORT.postMessage" in FRAME and "parent.postMessage" not in FRAME)

print("\nan endless loop is survivable")
ck("every run has a deadline", "LIMIT_MS" in SB)
ck("the frame is thrown away rather than reasoned with", "drop(lang)" in SB,
   "a loop cannot be interrupted from outside a frame")
ck("and the next run gets a clean one",
   "if (!FRAMES[lang]) FRAMES[lang] = build(lang)" in SB,
   "which also throws away whatever the last program left behind")

print("\nthe Python runtime is served from this site")
ck("the frame asks here first", '"/pyodide/"' in FRAME_ALL)
ck("with the CDN behind it", "cdn.jsdelivr.net/pyodide" in FRAME_ALL,
   "for a deployment where the files did not ship")
for f in ("pyodide.js", "pyodide.asm.js", "pyodide.asm.wasm",
          "python_stdlib.zip", "pyodide-lock.json"):
    ck("it ships " + f, os.path.isfile(os.path.join(ROOT, "pyodide", f)))
ck("the route exists", '@app.get("/pyodide/{filename}.{ext}")' in MAIN)
ck("a .wasm is served as a .wasm",
   '".wasm": "application/wasm"' in MAIN,
   "the streaming compiler refuses any other type outright")
ck("and it is readable from an origin-less frame",
   '"Access-Control-Allow-Origin": "*"' in
   MAIN.split('@app.get("/pyodide/{filename}.{ext}")')[1].split("\n@app.")[0],
   "the sandbox has no origin, so every request it makes is cross-origin; "
   "the runtime's own fetch for the wasm fails without this")
ck("nothing outside the directory can be reached",
   "path.parent != root" in
   MAIN.split('@app.get("/pyodide/{filename}.{ext}")')[1].split("\n@app.")[0])

print("\nthe runner has a real URL, which is what makes Python work at all")
# Built from srcdoc the document URL is "about:srcdoc", and Pyodide throws
# when it is loaded there: it resolves its own asset paths against the
# document and there is nothing to resolve against. The name loadPyodide was
# left defined with no value, the call three lines later said "not a
# function", and the lab reported that the runtime could not be downloaded.
# The network was never the problem.
ck("the frame is a page, not a string", 'f.src = FRAME_SRC' in SB)
ck("and srcdoc is gone", "f.srcdoc" not in SB)
ck("the loader checks what it got before calling it",
   'typeof loadPyodide !== "function"' in FRAME_ALL,
   "a script that loads and then throws leaves the NAME defined and the "
   "value undefined, which reads three lines later as a network fault")
ck("and says which of the two went wrong",
   "did not start" in FRAME_ALL and "not usually the" in FRAME_ALL)

print("\n" + ("PASSED %d   FAILED %d" % (len(P), len(F))))
if F:
    for name in F:
        print("  FAILED: " + name)
    sys.exit(1)
