/* Builds stage3a.json from stage3a-curriculum.js
   Run:  node convert-stage3a.js                                     */
const fs = require("fs");
const { STAGE3A } = require("./stage3a-curriculum.js");

const out = { tracks: [] };

STAGE3A.forEach((t, ti) => {
  out.tracks.push({
    id: t.id, icon: t.icon, name: t.name, level: t.level, color: t.color,
    weeks: t.weeks, lang: t.lang, desc: t.desc, outcomes: t.outcomes,
    position: ti, audience: "stage3a", quiz: [],
    lessons: t.lessons.map((l, li) => ({
      id: l.id, title: l.title, mins: l.mins, lang: l.lang, position: li,
      content: l.content, videos: [], refs: [], lab: {},
      exercises: l.exercises.map(e => ({
        q: e.q, starter: e.starter, hint: e.hint || "",
        solution: e.solution || "", answer: e.answer || "", check: e.check || null,
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
    // A fill-in-the-blank exercise must differ from its solution.
    // Demonstration exercises ("run this and see") legitimately match.
    if (e.starter.includes("____") && e.starter === e.solution)
      problems.push(`${l.id}#${i + 1}: has a blank but starter equals solution`);
  });
}));
if (problems.length) { console.error("PROBLEMS:"); problems.forEach(p => console.error("  " + p)); process.exit(1); }

fs.writeFileSync("stage3a.json", JSON.stringify(out, null, 1));
const L = out.tracks.reduce((a, t) => a + t.lessons.length, 0);
const E = out.tracks.reduce((a, t) => a + t.lessons.reduce((b, l) => b + l.exercises.length, 0), 0);
const W = out.tracks.reduce((a, t) => a + t.lessons.reduce((b, l) => b + l.worksheet.length, 0), 0);
console.log(`wrote stage3a.json - ${out.tracks.length} track, ${L} lessons, ${E} exercises, ${W} worksheet questions`);
