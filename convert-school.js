/* Builds school.json from school-curriculum.js
   Run:  node convert-school.js                                     */
const fs = require("fs");
const { SCHOOL } = require("./school-curriculum.js");

const out = { tracks: [] };

SCHOOL.forEach((t, ti) => {
  const track = {
    id: t.id, icon: t.icon, name: t.name, level: t.level, color: t.color,
    weeks: t.weeks, lang: t.lang, desc: t.desc, outcomes: t.outcomes,
    position: ti,          // school tracks sort first, before the graduate ones
    audience: "school",
    quiz: [],
    lessons: [],
  };

  t.lessons.forEach((l, li) => {
    track.lessons.push({
      id: l.id,
      title: l.title,
      mins: l.mins,
      lang: l.lang,
      position: li,
      content: l.content,
      videos: [],
      refs: [],
      lab: {},                       // school lessons use exercises, not a single lab
      exercises: l.exercises.map(e => ({
        q: e.q,
        starter: e.starter,
        hint: e.hint || "",
        solution: e.solution || "",
        answer: e.answer || "",
        check: e.check || null,
      })),
      worksheet: l.worksheet || [],
    });
  });

  out.tracks.push(track);
});

/* ---- sanity checks --------------------------------------------------- */
const problems = [];
out.tracks.forEach(t => t.lessons.forEach(l => {
  if (!l.exercises.length) problems.push(`${l.id}: no exercises`);
  if (!l.worksheet.length) problems.push(`${l.id}: no worksheet`);
  l.exercises.forEach((e, i) => {
    const runnable = l.lang === "py" || l.lang === "js";
    if (runnable && !e.check)    problems.push(`${l.id}#${i + 1}: missing check`);
    if (runnable && !e.solution) problems.push(`${l.id}#${i + 1}: missing solution`);
    if (!runnable && !e.answer)  problems.push(`${l.id}#${i + 1}: missing answer`);
    if (!e.q || !e.starter)      problems.push(`${l.id}#${i + 1}: missing q or starter`);
  });
}));

if (problems.length) {
  console.error("PROBLEMS FOUND:");
  problems.forEach(p => console.error("  " + p));
  process.exit(1);
}

fs.writeFileSync("school.json", JSON.stringify(out, null, 1));

const L = out.tracks.reduce((a, t) => a + t.lessons.length, 0);
const E = out.tracks.reduce((a, t) => a + t.lessons.reduce((b, l) => b + l.exercises.length, 0), 0);
const W = out.tracks.reduce((a, t) => a + t.lessons.reduce((b, l) => b + l.worksheet.length, 0), 0);
console.log(`wrote school.json - ${out.tracks.length} tracks, ${L} lessons, ${E} exercises, ${W} worksheet questions`);
