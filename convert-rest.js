/* Builds stage3b.json and stage4.json, then verifies every exercise.
   Run:  node convert-rest.js                                        */
const fs = require("fs");
const { STAGE3B } = require("./stage3b-curriculum.js");
const { STAGE4 }  = require("./stage4-curriculum.js");
const { MATH }    = require("./math-curriculum.js");

// Maths belongs at the front of the ML/AI stage
const STAGE4_ALL = [...MATH, ...STAGE4];

function build(source, audience, outFile) {
  const out = { tracks: [] };
  source.forEach((t, ti) => {
    out.tracks.push({
      id: t.id, icon: t.icon, name: t.name, level: t.level, color: t.color,
      weeks: t.weeks, lang: t.lang, desc: t.desc, outcomes: t.outcomes,
      position: ti, audience: audience, quiz: [],
      lessons: t.lessons.map((l, li) => ({
        id: l.id, title: l.title, mins: l.mins, lang: l.lang, position: li,
        content: l.content, videos: [], refs: [], lab: {},
        exercises: l.exercises.map(e => ({
          q: e.q, starter: e.starter, hint: e.hint || "",
          solution: e.solution || "", answer: e.answer || "",
          check: e.check || null,
        })),
        worksheet: l.worksheet || [],
      })),
    });
  });

  const problems = [];
  out.tracks.forEach(t => t.lessons.forEach(l => {
    if (!l.exercises.length) problems.push(`${l.id}: no exercises`);
    if (!l.worksheet.length) problems.push(`${l.id}: no worksheet`);
    l.exercises.forEach((e, i) => {
      if (!e.check)    problems.push(`${l.id}#${i + 1}: missing check`);
      if (!e.solution) problems.push(`${l.id}#${i + 1}: missing solution`);
      if (!e.q || !e.starter) problems.push(`${l.id}#${i + 1}: missing q or starter`);
    });
  }));
  if (problems.length) { console.error("PROBLEMS in " + outFile + ":");
    problems.forEach(p => console.error("  " + p)); process.exit(1); }

  fs.writeFileSync(outFile, JSON.stringify(out, null, 1));
  const L = out.tracks.reduce((a, t) => a + t.lessons.length, 0);
  const E = out.tracks.reduce((a, t) => a + t.lessons.reduce((b, l) => b + l.exercises.length, 0), 0);
  const W = out.tracks.reduce((a, t) => a + t.lessons.reduce((b, l) => b + l.worksheet.length, 0), 0);
  console.log(`${outFile}: ${out.tracks.length} tracks, ${L} lessons, ${E} exercises, ${W} worksheet questions`);
  return out;
}

build(STAGE3B, "stage3b", "stage3b.json");
build(STAGE4_ALL, "stage4", "stage4.json");

/* export every solution for python verification */
const all = [];
[...STAGE3B, ...STAGE4_ALL].forEach(t => t.lessons.forEach(l =>
  l.exercises.forEach((e, i) => all.push({ id: l.id + "#" + (i + 1), code: e.solution }))));
fs.writeFileSync("/tmp/rest.json", JSON.stringify(all));
console.log("exported " + all.length + " solutions for verification");
