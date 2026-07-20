/* Converts curriculum.js (with JS closures) → curriculum.json (declarative, DB-seedable).
   Run once: node convert.js   */
const fs = require("fs");
const { CURRICULUM, PATHS } = new Function(
  fs.readFileSync("curriculum.js", "utf8") + "; return {CURRICULUM, PATHS};"
)();

/* Declarative equivalents of every original check() closure.
   all   : every regex must match the output   (flags: im)
   none  : no regex may match
   lines : trimmed non-empty output lines must equal these, in order
   minLines : minimum count of non-empty lines                            */
const CHECKS = {
  b2:  { all: ["80\\.75", "True"] },
  b3:  { lines: ["A", "B", "C", "F"] },
  p1:  { all: ["Asha", "90\\.0", "67\\.5", "97\\.0"] },
  p2:  { all: ["88", "91", "76"], none: ["abc"] },
  p3:  { all: ["1500", "Insufficient"] },
  p4:  { all: ["- python", "- sql", "- git"] },
  p5:  { all: ["All tests passed"] },
  s2:  { all: ["Asha - Python", "Ravi - SQL", "Asha - SQL"] },
  s4:  { all: ["about tea", "0\\.9\\d"] },
  jc3: { lines: ["1", "none"] },
  ds1: { all: ["76\\.\\d\\d", "4"] },
  ds2: { all: ["Chennai\\s*93", "Pune\\s*75"] },
  ml1: { all: ["step 5"] },
  ml2: { all: ["0\\.8", "0\\.66", "0\\.72"] },
  ml3: { all: ["1\\.5", "^\\s*0\\s*$"] },
  ai1: { all: ["2[0-9]"], minLines: 2 },
  ai2: { all: ["amount|invalid"] },
  ai3: { all: ["leave"], minLines: 2 },
  ai4: { all: ["Total:\\s*38"] },
  j1:  { all: ["Asha", "Meena"], none: ["Ravi"] },
  j2:  { all: ["<tr>", "Asha", "88", "</tr>"] },
  j3:  { all: ["Score:\\s*91"] },
};

const out = { tracks: [], paths: PATHS };
let missing = [];

CURRICULUM.forEach((t, ti) => {
  const track = {
    id: t.id, icon: t.icon, name: t.name, level: t.level, color: t.color,
    weeks: t.weeks, lang: t.lang, desc: t.desc, outcomes: t.outcomes,
    position: ti, quiz: t.quiz, lessons: [],
  };
  t.lessons.forEach((l, li) => {
    const runnable = l.lang === "py" || l.lang === "js";
    if (runnable && !CHECKS[l.id]) missing.push(l.id);
    track.lessons.push({
      id: l.id, title: l.title, mins: l.mins, lang: l.lang, position: li,
      content: l.content,
      videos: l.videos || [],
      refs: l.refs || [],
      lab: {
        prompt: l.lab.prompt,
        starter: l.lab.starter,
        hint: l.lab.hint || "",
        solution: l.lab.solution || "",
        answer: l.lab.answer || "",
        check: runnable ? CHECKS[l.id] : null,
      },
    });
  });
  out.tracks.push(track);
});

if (missing.length) { console.error("MISSING CHECK SPECS:", missing); process.exit(1); }

fs.writeFileSync("curriculum.json", JSON.stringify(out, null, 1));
console.log("wrote curriculum.json —", out.tracks.length, "tracks,",
  out.tracks.reduce((a, t) => a + t.lessons.length, 0), "lessons");

/* ---- verify the declarative specs behave like the original closures ---- */
function evalCheck(spec, output) {
  if (!spec) return true;
  const lines = output.split("\n").map(s => s.trim()).filter(Boolean);
  if (spec.lines) {
    if (lines.length < spec.lines.length) return false;
    for (let i = 0; i < spec.lines.length; i++) if (lines[i] !== spec.lines[i]) return false;
  }
  if (spec.minLines && lines.length < spec.minLines) return false;
  for (const p of spec.all || []) if (!new RegExp(p, "im").test(output)) return false;
  for (const p of spec.none || []) if (new RegExp(p, "im").test(output)) return false;
  return true;
}
module.exports = { evalCheck };

/* self-test against the JS labs whose solutions we can run here */
let checked = 0, failed = 0;
CURRICULUM.forEach(t => t.lessons.forEach(l => {
  if (l.lang !== "js" || !l.lab.solution) return;
  let o = "";
  const log = (...a) => { o += a.map(v => typeof v === "string" ? v : JSON.stringify(v)).join(" ") + "\n"; };
  try { new Function("console", l.lab.solution)({ log }); } catch (e) { return; }
  setTimeout(() => {
    const spec = evalCheck(CHECKS[l.id], o), orig = l.lab.check(o);
    checked++;
    if (spec !== orig) { failed++; console.error("MISMATCH", l.id, "spec:", spec, "orig:", orig); }
    if (checked === 3) console.log("js spec/closure agreement:", failed ? failed + " mismatches" : "all match");
  }, 450);
}));
