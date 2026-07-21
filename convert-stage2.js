/* Builds stage2.json from stage2-curriculum.js
   Run:  node convert-stage2.js                                      */
const fs = require("fs");
const { STAGE2 } = require("./stage2-curriculum.js");

const out = { tracks: [] };

STAGE2.forEach((t, ti) => {
  out.tracks.push({
    id: t.id, icon: t.icon, name: t.name, level: t.level, color: t.color,
    weeks: t.weeks, lang: t.lang, desc: t.desc, outcomes: t.outcomes,
    position: ti, audience: "stage2", quiz: [],
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
    const runnable = l.lang === "py" || l.lang === "js";
    if (runnable && !e.check)    problems.push(`${l.id}#${i + 1}: missing check`);
    if (runnable && !e.solution) problems.push(`${l.id}#${i + 1}: missing solution`);
    if (!e.q || !e.starter)      problems.push(`${l.id}#${i + 1}: missing q or starter`);
  });
}));
if (problems.length) { console.error("PROBLEMS:"); problems.forEach(p => console.error("  " + p)); process.exit(1); }

fs.writeFileSync("stage2.json", JSON.stringify(out, null, 1));
const L = out.tracks.reduce((a, t) => a + t.lessons.length, 0);
const E = out.tracks.reduce((a, t) => a + t.lessons.reduce((b, l) => b + l.exercises.length, 0), 0);
const W = out.tracks.reduce((a, t) => a + t.lessons.reduce((b, l) => b + l.worksheet.length, 0), 0);
console.log(`wrote stage2.json - ${out.tracks.length} tracks, ${L} lessons, ${E} exercises, ${W} worksheet questions`);
