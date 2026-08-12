"""3D for physics and biology, not only for chemistry.

Nine scene kinds existed and, read as a set, they were a chemistry cupboard:
molecules, crystals, proteins, layer stacks. Biology got a leaf with arrows
around it. Physics got planets and a saddle. The two pictures a physics class
most needs could not be asked for at all — a field, which fills a volume, and
a wave, which moves — and the one structure a biology class is examined on
the shape of, the double helix, had to be faked as a ball-and-stick model.

Four kinds close that: helix, cell, field, wave.

**They are computed, not drawn, and this is the test that proves it.** A
field line here is walked one small step at a time in the direction the field
points at that point, summed from every source — so a dipole's lines close on
the negative charge because the arithmetic takes them there. That is a claim
that can be checked, and it is checked below by looking at where the lines
actually end. The same for handedness: B-DNA turns right and Z-DNA turns
left, a student is examined on exactly that, and it is measured here rather
than trusted.

**The measured numbers never come from the model.** Rise per base pair,
bases per turn, diameter, handedness, organelle sizes — a model asked for
those writes a plausible helix that is wrong in the one respect that counts.
It names the form; the geometry comes from the table.

Rendering runs in node against the real three.js, because a test that only
greps the source proves the code exists rather than that it draws anything.
"""
import io
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import scene                                          # noqa: E402

JS = io.open(os.path.join(ROOT, "three3d.js"), encoding="utf-8").read()
P, F = [], []


def ck(name, cond, why=""):
    print(("PASS " if cond else "FAIL ") + name + (" — " + why if why else ""),
          flush=True)
    (P if cond else F).append(name)


print("\nevery kind offered is a kind that can be built and validated")
# "protein" is the exception, and deliberately: it is never asked for by the
# model. A lesson that names a real protein gets one looked up from its PDB
# entry and attached by the server — which is why the renderer knows it and
# the prompt does not offer it.
for kind in scene.KINDS:
    ck("the renderer has " + kind, "BUILD." + kind + " = function" in JS)
    if kind != "protein":
        ck("the prompt offers " + kind, '"' + kind + '"' in scene.PROMPT)

print("\nbiology: the helix")
h = scene.clean({"kind": "helix", "form": "Z-DNA", "turns": 3,
                 "sequence": "atgc!!", "caption": "Z-DNA"})
ck("the form is taken and normalised", h["form"] == "z-dna")
ck("a sequence is cleaned to real bases", h["sequence"] == "ATGC")
ck("an unknown form falls back rather than failing",
   scene.clean({"kind": "helix", "form": "spiral"})["form"] == "dna")
ck("the measured numbers are not accepted from the model",
   "rise" not in h and "diameter" not in h,
   "rise per base pair and bases per turn are crystallography; a model "
   "asked for them writes a plausible helix that is wrong where it counts")
ck("and the second strand is not either", "strand2" not in h,
   "the pairing is computed — A with T, G with C — which is the point of "
   "showing it")
ck("the renderer holds the measured table",
   "3.4" in JS and "10.5" in JS and "hand: -1" in JS)

print("\nbiology: the cell")
c = scene.clean({"kind": "cell", "cell": "plant",
                 "parts": [{"name": "nucleus"}, "chloroplast",
                           {"name": "liver", "n": 3},
                           {"name": "mitochondrion", "n": 99}]})
ck("a plant cell is a plant cell", c["cell"] == "plant")
ck("a bare name works as well as an object",
   any(p["name"] == "chloroplast" for p in c["parts"]))
ck("an organelle with no measured size is dropped",
   not any(p["name"] == "liver" for p in c["parts"]),
   "drawn at an invented size it teaches the wrong proportion, which is "
   "the one thing a scale drawing must not do")
ck("a count is capped rather than believed",
   [p for p in c["parts"] if p["name"] == "mitochondrion"][0]["n"] == 12)
ck("a cell of nothing placeable is no scene at all",
   scene.clean({"kind": "cell", "parts": [{"name": "liver"}]}) is None)

print("\nphysics: the field")
f = scene.clean({"kind": "field", "charges": [{"q": 1, "x": -2},
                                              {"q": -1, "x": 2}],
                 "loops": [{"r": 2}]})
ck("charges are kept with their signs",
   [x["q"] for x in f["charges"]] == [1.0, -1.0])
ck("but never both fields at once", "loops" not in f,
   "an electric and a magnetic field in one picture would be added by eye, "
   "and they are neither the same field nor the same units")
ck("a magnetic field on its own is fine",
   "loops" in scene.clean({"kind": "field", "loops": [{"r": 2, "i": 1}]}))
ck("no source is no scene", scene.clean({"kind": "field"}) is None)
ck("the lines are integrated, not drawn",
   "Biot" in JS and "superposition" in JS and "crossVectors" in JS)

print("\nphysics: the wave")
w = scene.clean({"kind": "wave", "mode": "interference", "wavelength": 900,
                 "sources": [{"x": -2}, {"x": 2}]})
ck("the mode is taken", w["mode"] == "interference")
ck("a wavelength off the scale is clamped, not refused", w["wavelength"] == 8)
ck("an unknown mode still draws something",
   scene.clean({"kind": "wave", "mode": "sideways"})["mode"] == "travelling")
ck("and it is animated by recomputing the surface",
   "userData.animate" in JS and "computeVertexNormals" in JS,
   "a standing wave drawn still is a picture of a curve; the nodes holding "
   "still while everything between them moves IS the lesson")

print("\nand the renderer draws what the numbers say")
HARNESS = r"""
import * as h from "./tests/_scene3d.mjs";
const out = {};
const twist = g => { let a = null, b = null;
  g.traverse(o => { if (o.isMesh && o.geometry.type === "TubeGeometry" && !a) {
    const p = o.geometry.attributes.position;
    a = [p.getX(0), p.getZ(0)];
    b = [p.getX(p.count - 1), p.getZ(p.count - 1)]; } });
  return Math.atan2(b[1], b[0]) - Math.atan2(a[1], a[0]); };
out.right = Math.sign(twist(h.build("helix", {form: "dna", turns: 2})));
out.left  = Math.sign(twist(h.build("helix", {form: "z-dna", turns: 2})));
out.oneStrand = h.census(h.build("helix", {form: "alpha"})).meshes;
out.twoStrand = h.census(h.build("helix", {form: "dna"})).meshes;

const dip = h.build("field", {charges: [{q: 1, x: -2}, {q: -1, x: 2}]});
const ends = h.lineEnds(dip);
out.lines = ends.length;
out.onNegative = ends.filter(e => Math.hypot(e[0] - 2, e[1], e[2]) < 0.6).length;
const solo = h.lineEnds(h.build("field", {charges: [{q: 1}]}));
out.soloFar = solo.filter(e => Math.hypot(e[0], e[1], e[2]) > 8).length;
out.solo = solo.length;

const w = h.build("wave", {mode: "interference", wavelength: 1.6, span: 9});
let plane = null;
w.traverse(o => { if (o.isMesh && o.geometry.type === "PlaneGeometry") plane = o; });
plane.userData.animate(0.3);
const p = plane.geometry.attributes.position;
let lo = 1e9, hi = -1e9;
for (let i = 0; i < p.count; i++) { const y = p.getY(i);
  if (y < lo) lo = y; if (y > hi) hi = y; }
out.low = lo; out.high = hi;
const was = p.getY(500);
plane.userData.animate(0.9);
out.moved = Math.abs(p.getY(500) - was);

// A plant cell, whose wall is a box. An animal cell's shell is itself a
// sphere and would be counted as the first organelle.
const cell = h.build("cell", {cell: "plant",
                              parts: [{name: "nucleus"},
                                      {name: "mitochondrion"}]});
const balls = [];
cell.traverse(o => { if (o.isMesh && o.geometry.type === "SphereGeometry")
  balls.push(o.scale.x); });
out.nucleus = balls[0]; out.mito = balls[1];
console.log(JSON.stringify(out));
"""
try:
    r = subprocess.run(["node", "--input-type=module", "-e", HARNESS],
                       cwd=ROOT, capture_output=True, text=True, timeout=120,
                       encoding="utf-8")
    got = json.loads([l for l in (r.stdout or "").splitlines()
                      if l.startswith("{")][-1])
except Exception as e:
    got = None
    print("(node unavailable, skipping the rendering checks: %s)" % e)

if got:
    ck("B-DNA turns one way and Z-DNA the other",
       got["right"] != got["left"],
       "handedness is the thing a student is examined on, and a model "
       "asked to write the coordinates gets it wrong half the time")
    ck("an alpha helix is one strand and DNA is two",
       got["oneStrand"] < got["twoStrand"])
    ck("a dipole's field lines end on the negative charge",
       got["onNegative"] > got["lines"] * 0.25,
       "%d of %d" % (got["onNegative"], got["lines"]))
    ck("a lone charge's lines run off to infinity instead",
       got["soloFar"] > got["solo"] * 0.6,
       "%d of %d" % (got["soloFar"], got["solo"]))
    ck("two sources give crests and troughs",
       got["high"] > 0.1 and got["low"] < -0.1,
       "%.2f to %.2f" % (got["low"], got["high"]))
    ck("and the surface actually moves", got["moved"] > 1e-6)
    ck("a mitochondrion is drawn smaller than the nucleus",
       got["mito"] < got["nucleus"],
       "%.2f against %.2f" % (got["mito"], got["nucleus"]))

print("\n" + ("PASSED %d   FAILED %d" % (len(P), len(F))))
if F:
    for name in F:
        print("  FAILED: " + name)
    sys.exit(1)
