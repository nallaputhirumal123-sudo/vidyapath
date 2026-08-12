"""The open 3D library: what may be shown, in what order, and where it fits.

three3d builds structures from numbers, and cannot draw a heart. So when
nothing measured exists the library is searched — and three things have to
hold or it does more harm than the empty answer it replaced.

**It must be the thing that was asked for.** Sorted by popularity, "kidney"
came back with a laundry machine, a manor house and a pub: all correctly
licensed, none of them a kidney. A model matching nothing in the query is
dropped rather than ranked last, which is the rule the picture search
already learned — a class believes what it is shown.

**It must say it is a drawing.** A measured scene is evidence; this is
somebody's sculpture of a heart. The maker and the licence stay on screen
the whole time it is up, which is a licence condition for CC-BY and the
honest thing regardless.

**And nothing but a viewer may reach the page.** The allowlist is the
security boundary, not the search filter: an embed URL on an allowed host,
on the embed path, or it does not exist.
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import models3d                                        # noqa: E402

BOARD = io.open(os.path.join(ROOT, "craxlearn.html"), encoding="utf-8").read()
P, F = [], []


def ck(name, cond, why=""):
    print(("PASS " if cond else "FAIL ") + name + (" — " + why if why else ""),
          flush=True)
    (P if cond else F).append(name)


def row(name, embed, lic="CC Attribution", faces=20000, tags=""):
    return {"name": name, "embedUrl": embed, "faceCount": faces,
            "license": {"label": lic}, "user": {"displayName": "somebody"},
            "tags": [{"name": t} for t in tags.split()] if tags else [],
            "thumbnails": {"images": [
                {"width": 720, "url": "https://media.sketchfab.com/x.jpg"}]}}


OK_EMBED = "https://sketchfab.com/models/abc123/embed"

print("\nonly a viewer, only from an allowed host")
ck("an embed on the allowed host is kept",
   models3d.clean(row("Heart", OK_EMBED))["embed"] == OK_EMBED)
for bad, why in (
        ("http://sketchfab.com/models/a/embed", "not https"),
        ("https://evil.example.com/models/a/embed", "not the host"),
        ("https://sketchfab.com.evil.example/models/a/embed",
         "the host is a prefix of a different host"),
        ("https://sketchfab.com/3d-models/heart-abc123", "the whole site"),
        ("https://sketchfab.com/models/abc123", "not the embed path"),
        ("javascript:alert(1)", "not a URL at all"),
        ("", "nothing")):
    ck("refused: " + why, models3d.clean(row("Heart", bad)) is None)

print("\nand nothing that should not be in front of a class")
_ar = row("Heart", OK_EMBED)
_ar["isAgeRestricted"] = True
ck("an age-restricted model is dropped", models3d.clean(_ar) is None)
ck("a model with no name is dropped",
   models3d.clean(row("", OK_EMBED)) is None)

print("\nit must be the thing that was asked for")
_rows = [models3d.clean(r) for r in [
    row("Kidney", OK_EMBED, "CC0 Public Domain"),
    row("HL2 Inspired - Laundry machine 1", OK_EMBED),
    row("Magical manor", OK_EMBED),
    row("Kidney cross-section", OK_EMBED, "Standard"),
]]
_out = models3d.rank("kidney", _rows)
ck("the ones that match come back",
   [r["name"] for r in _out] == ["Kidney", "Kidney cross-section"],
   "sorted by popularity this query returned a laundry machine, a manor "
   "house and a pub — all correctly licensed and none of them a kidney")
ck("and a free licence wins between two that match",
   _out[0]["licence"].lower().startswith("cc0"),
   "between two models of a kidney, the one a teacher can also take away")
ck("a tag counts as a match",
   len(models3d.rank("mitochondrion",
                     [models3d.clean(row("Untitled", OK_EMBED,
                                         tags="mitochondrion biology"))])) == 1,
   'a model called "Untitled" tagged mitochondrion is the right model')
ck("a query of nothing but filler matches nothing",
   models3d.rank("show me the 3d model", _rows) == [],
   "otherwise every lesson gets whatever the catalogue felt like")

print("\nthe query asks for relevance, not for the popular models")
_p = models3d.params("kidney")
ck("no sort_by is sent", "sort_by" not in _p,
   "sorting by likes searches the popular models for the word rather than "
   "searching for the word")
ck("the count is bounded", 1 <= _p["count"] <= 24)
ck("and the query is capped", len(models3d.params("x" * 400)["q"]) <= 120)

print("\nwhat reaches the screen says what it is")
_CREDIT = BOARD.split('mdlcredit">')[1][:300]
ck("the credit carries the maker and the licence",
   "esc(m.by)" in _CREDIT and "esc(m.licence)" in _CREDIT,
   "CC-BY requires the attribution to stay with the work, and a class "
   "should be able to see whose model they are being taught from")
ck("and says plainly that it is not a measurement",
   "a model, not a measurement" in BOARD,
   "a measured scene is evidence; this is somebody's drawing of a heart, "
   "and a student should know which they are looking at")
ck("the frame is sandboxed and cannot reach this origin",
   'sandbox="allow-scripts allow-same-origin allow-popups"' in BOARD,
   "same-origin here means the model host's own origin, not ours")
ck("nothing is downloaded and no mesh is parsed here",
   "gltf" not in BOARD.lower() and "STLLoader" not in BOARD)

print("\nand it fits on the screen it is shown on")
# A minimum height on the frame put the row of thumbnails past the bottom of
# a laptop screen, and the viewer clips what does not fit — so the way to
# pick a different model was simply not there.
_CSS = BOARD.split(".mdlwrap{")[1].split("@media (max-height")[0]
ck("only the frame stretches",
   "flex:1 1 auto;width:100%;min-height:0" in _CSS,
   "a minimum height on it pushed the picker off the bottom of the viewer, "
   "which clips")
ck("the credit and the picker keep their own size",
   _CSS.count("flex:0 0 auto") >= 2)
ck("and the wrapper can shrink", "min-height:0" in _CSS.split("}")[0])
ck("a laptop lid gets the pictures without the names",
   "@media (max-height:900px)" in BOARD,
   "six near-identical titles took a quarter of the viewer to say Human "
   "Heart 1 through Human Heart 6")

print("\n" + ("PASSED %d   FAILED %d" % (len(P), len(F))))
if F:
    for name in F:
        print("  FAILED: " + name)
    sys.exit(1)
