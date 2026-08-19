/* Actually write the PDF, rather than read the code that writes it.
 *
 * The download bug was never visible in the source: pdfRecordOf looked
 * right, the button was wired, the handler was there. It failed at run time,
 * inside the writer, on a step that was an object — and every failure path
 * swallowed it. So this pulls the real functions out of index.html, hands
 * them the two record shapes that reach them, and checks that bytes come
 * out.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const HTML = fs.readFileSync(path.join(ROOT, "index.html"), "utf8");

/* Pull `function NAME(...){...}` out by matching braces. Nothing clever is
   needed: these are top-level declarations in one inline script. */
function grab(name) {
  const re = new RegExp("(?:async\\s+)?function\\s+" + name + "\\s*\\(");
  const at = HTML.search(re);
  if (at < 0) throw new Error("not found in index.html: " + name);
  let i = HTML.indexOf("{", at), depth = 0, inS = null, esc = false;
  for (let j = i; j < HTML.length; j++) {
    const c = HTML[j];
    if (esc) { esc = false; continue; }
    if (inS) {
      if (c === "\\") esc = true;
      else if (c === inS) inS = null;
      continue;
    }
    if (c === '"' || c === "'" || c === "`") { inS = c; continue; }
    if (c === "/" && HTML[j + 1] === "*") { j = HTML.indexOf("*/", j) + 1; continue; }
    if (c === "/" && HTML[j + 1] === "/") { j = HTML.indexOf("\n", j); continue; }
    if (c === "{") depth++;
    else if (c === "}" && --depth === 0) return HTML.slice(at, j + 1);
  }
  throw new Error("unbalanced: " + name);
}

// The browser globals these functions touch, and nothing else.
globalThis.window = globalThis;
globalThis.self = globalThis;
Object.defineProperty(globalThis, "navigator", {
  value: { userAgent: "node", platform: "node" }, configurable: true });
const said = [];
globalThis.toast = (m) => said.push(String(m));
globalThis.alert = (m) => said.push(String(m));
globalThis.fetch = async () => ({ ok: false });   // no pictures are reachable here
globalThis.document = {
  createElement: () => ({ getContext: () => null, style: {} }),
  createElementNS: () => ({ getContext: () => null }),
  head: { appendChild() {} },
  documentElement: { style: {} }
};

const { createRequire } = await import("node:module");
const require = createRequire(import.meta.url);
const jspdfMod = require(path.join(ROOT, "jspdf.umd.min.js"));
// In a browser the UMD sets window.jspdf; under node it hands back the
// module. Put it where the page's own code looks for it.
globalThis.jspdf = globalThis.jspdf || jspdfMod;

const SRC = ["pdfSafe", "pdfRecordOf", "pdfImageData", "pdfPicturesOf",
             "ensureJsPDF", "askPDFWrite", "askPDF"].map(grab).join("\n");
const saved = [];
// Indirect eval, so the declarations land as globals: a direct eval() inside
// a module keeps them to itself and nothing below can see them.
(0, eval)(SRC + "\n");
const { pdfRecordOf, askPDF } = globalThis;

/* save() is where a browser hands the file to the user, so it is the one
   thing that cannot run here. jsPDF puts its API on the instance rather than
   the prototype, so the document is wrapped on the way out instead. */
const RealJsPDF = globalThis.jspdf.jsPDF;
const caught = { bytes: 0, name: "" };
globalThis.jspdf = {
  jsPDF: function (opts) {
    const doc = new RealJsPDF(opts);
    doc.save = function (name) {
      caught.bytes = this.output("arraybuffer").byteLength;
      caught.name = name;
    };
    return doc;
  }
};

const out = [];
const run = async (label, rec) => {
  said.length = 0;
  caught.bytes = 0; caught.name = "";
  let err = "";
  try { await askPDF(rec); } catch (e) { err = String(e && e.message); }
  out.push({ label, bytes: caught.bytes, err, said: said.slice(),
             file: caught.name });
};

// What Ask produces: steps are plain lines.
await run("ask lesson", pdfRecordOf({
  title: "Photosynthesis",
  steps: ["Plants make their own food.", "It happens in the chloroplast.",
          "Water in, oxygen out — the equation is 6CO₂ + 6H₂O → C₆H₁₂O₆ + 6O₂."],
  takeaway: "Light in, sugar out."
}, { q: "how do plants eat", subject: "Biology", level: "Beginner" }));

// What the BOARD produces, and what a saved record used to hand over raw:
// steps as objects. This is the shape that threw inside the writer.
await run("board lesson, steps as objects", pdfRecordOf({
  title: "Newton's second law",
  steps: [{ t: "Force is mass times acceleration.", where: "board" },
          { t: "Double the force, double the acceleration." }],
  takeaway: "F = ma"
}, { q: "second law", subject: "Physics", level: "Advanced" }));

// The raw object shape reaching the writer WITHOUT pdfRecordOf, which is
// how the saved-download path used to call it.
await run("objects with no normalising", {
  title: "Untouched", steps: [{ t: "Still has to write." }], takeaway: ""
});

// No title at all — the filename used to fall back to a brand two rebrands old.
await run("no title", pdfRecordOf({ steps: ["One line."] }, {}));

console.log(JSON.stringify(out));
