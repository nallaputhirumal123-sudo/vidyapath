/* Builds VidyaPath-Syllabus.html — a one-page shareable course outline.
   Generated from the real curriculum files so it can never drift.
   Run:  node build-syllabus.js                                        */
const fs = require("fs");

const SUPERSEDED = new Set(["sql", "data", "ml", "llm", "basics", "python"]);
const esc = s => String(s == null ? "" : s)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

const load = f => {
  if (!fs.existsSync(f)) return { tracks: [] };
  const d = JSON.parse(fs.readFileSync(f, "utf8"));
  d.tracks = d.tracks.filter(t => !SUPERSEDED.has(t.id));
  return d;
};

const STAGES = [
  { file:"school.json", n:1, icon:"🌱", name:"Absolute Beginner",
    who:"Class 8-12, or any adult who has never coded",
    time:"7 weeks at 1 hour a day",
    end:"You can write a program that makes decisions, repeats work, and handles lists of data." },
  { file:"stage2.json", n:2, icon:"📘", name:"Getting Fluent in Python",
    who:"Anyone who has finished Stage 1",
    time:"5 weeks",
    end:"You write Python the way working programmers write it, and can process real messy text and records." },
  { file:"stage3a.json", n:3, icon:"🗄️", name:"Databases & SQL",
    who:"After Stage 2",
    time:"4 weeks",
    end:"You can query a real database confidently. This skill alone qualifies you for Data Analyst roles." },
  { file:"stage3b.json", n:4, icon:"📊", name:"Data Analysis",
    who:"After SQL",
    time:"3 weeks",
    end:"You can take a messy real dataset, clean it honestly, and report findings without misleading anyone." },
  { file:"stage4.json", n:5, icon:"📈", name:"Machine Learning & AI Engineering",
    who:"After data analysis",
    time:"10 weeks",
    end:"You understand how models learn, and can build and cost a real AI application." },
  { file:"curriculum.json", n:6, icon:"🧰", name:"Other Languages & Career",
    who:"Optional, alongside or after",
    time:"6 weeks",
    end:"Web development, campus placement preparation, portfolio projects and interview practice." },
];

let stagesHtml = "", totals = { lessons:0, exercises:0, worksheet:0, tracks:0 };

STAGES.forEach(stage => {
  const data = load(stage.file);
  if (!data.tracks.length) return;

  let sl = 0, se = 0, sw = 0;
  data.tracks.forEach(t => t.lessons.forEach(l => {
    sl++; se += (l.exercises || []).length || (l.lab && l.lab.prompt ? 1 : 0);
    sw += (l.worksheet || []).length;
  }));
  totals.lessons += sl; totals.exercises += se;
  totals.worksheet += sw; totals.tracks += data.tracks.length;

  const tracksHtml = data.tracks.map(t => `
    <div class="track">
      <div class="track-head">
        <span class="ti">${t.icon}</span>
        <div>
          <h3>${esc(t.name)}</h3>
          <div class="tmeta">${t.lessons.length} lessons &middot; ${esc(t.lang)} &middot; ${t.weeks} weeks</div>
        </div>
      </div>
      <p class="tdesc">${esc(t.desc)}</p>
      ${(t.outcomes || []).length ? `
        <div class="outcomes"><b>You will be able to:</b>
          <ul>${t.outcomes.map(o => `<li>${esc(o)}</li>`).join("")}</ul></div>` : ""}
      <details class="lessons"><summary>See all ${t.lessons.length} lessons</summary>
        <ol>${t.lessons.map(l => {
          const n = (l.exercises || []).length;
          return `<li>${esc(l.title)}
            <span class="lmeta">${l.mins} min${n ? ` &middot; ${n} exercises` : ""}</span></li>`;
        }).join("")}</ol>
      </details>
    </div>`).join("");

  stagesHtml += `
  <section class="stage">
    <div class="shead">
      <div class="sn">STAGE ${stage.n}</div>
      <h2>${stage.icon} ${esc(stage.name)}</h2>
      <div class="sbar">
        <span><b>Who</b> ${esc(stage.who)}</span>
        <span><b>Length</b> ${esc(stage.time)}</span>
        <span><b>Content</b> ${sl} lessons, ${se} exercises</span>
      </div>
      <div class="send"><b>By the end:</b> ${esc(stage.end)}</div>
    </div>
    ${tracksHtml}
  </section>`;
});

const html = `<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>VidyaPath — Course Syllabus</title>
<style>
:root{--bg:#fff;--paper:#faf9f7;--line:#e2e0dc;--text:#1a1a19;--muted:#6b6b66;
      --accent:#c2410c;--blue:#1e5fa8;--green:#15803d;--r:9px}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
     font-size:16px;line-height:1.7;max-width:940px;margin:0 auto;padding:46px 30px 90px}
h1,h2,h3{letter-spacing:-.5px}

.cover{border-bottom:3px solid var(--text);padding-bottom:28px;margin-bottom:10px}
.cover h1{font-size:40px;font-weight:800;line-height:1.1}
.cover h1 span{color:var(--accent)}
.cover .sub{font-size:19px;color:var(--muted);margin-top:12px;max-width:660px}
.nums{display:flex;gap:32px;flex-wrap:wrap;margin-top:26px}
.nums div b{display:block;font-size:27px;font-weight:800}
.nums div span{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.9px}

.box{background:var(--paper);border:1px solid var(--line);border-radius:var(--r);padding:22px 26px;margin:26px 0}
.box h4{font-size:16px;margin-bottom:9px}
.box ul{margin-left:20px}.box li{margin-bottom:5px}
.box.warn{background:#fff8f0;border-color:#f0d0b0}
.box.good{background:#f2f9f4;border-color:#c3e0cc}

.stage{margin-top:46px}
.shead{border-bottom:2px solid var(--line);padding-bottom:16px;margin-bottom:20px}
.sn{font-size:11px;font-weight:800;letter-spacing:1.4px;color:var(--accent)}
.shead h2{font-size:29px;font-weight:800;margin:4px 0 12px}
.sbar{display:flex;gap:26px;flex-wrap:wrap;font-size:13.5px;color:var(--muted);
      padding:11px 0;border-top:1px solid var(--line)}
.sbar b{color:var(--text);font-weight:600;margin-right:5px}
.send{font-size:14.5px;background:#eff6fd;border-left:3px solid var(--blue);
      padding:11px 15px;border-radius:0 var(--r) var(--r) 0;margin-top:10px}

.track{border:1px solid var(--line);border-radius:var(--r);padding:20px 22px;margin-bottom:14px}
.track-head{display:flex;gap:13px;align-items:flex-start}
.ti{font-size:23px;line-height:1.2}
.track h3{font-size:18px;font-weight:700}
.tmeta{font-size:12.5px;color:var(--muted)}
.tdesc{margin:11px 0;color:#3d3d3a;font-size:14.5px}
.outcomes{background:var(--paper);border-radius:var(--r);padding:13px 17px;font-size:14px}
.outcomes ul{margin:6px 0 0 19px}.outcomes li{margin-bottom:3px}
.lessons{margin-top:12px}
.lessons summary{cursor:pointer;font-size:13.5px;color:var(--blue);
  padding:6px 12px;background:var(--paper);border:1px solid var(--line);
  border-radius:6px;display:inline-block;user-select:none}
.lessons ol{margin:12px 0 0 22px;font-size:14px}
.lessons li{margin-bottom:5px}
.lmeta{color:var(--muted);font-size:12px}

table{width:100%;border-collapse:collapse;font-size:14.5px;margin:14px 0}
th{text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.8px;
   color:var(--muted);padding:9px 10px;border-bottom:2px solid var(--line)}
td{padding:10px;border-bottom:1px solid var(--line);vertical-align:top}
.yes{color:var(--green);font-weight:600}
.no{color:var(--accent);font-weight:600}

footer{margin-top:60px;padding-top:22px;border-top:1px solid var(--line);
       font-size:13px;color:var(--muted)}
@media print{
  body{font-size:11pt;padding:0}
  .lessons summary{display:none}
  .lessons ol{display:block}
  .stage{page-break-inside:auto}
  .shead{page-break-after:avoid}
  @page{margin:15mm}
}
</style></head><body>

<div class="cover">
  <h1>Learn to Code,<br>Then Build with <span>AI</span></h1>
  <p class="sub">A complete route from never having written a line of code
     through to building and deploying real AI applications. Nothing assumed at any point.</p>
  <div class="nums">
    <div><b>6</b><span>Stages</span></div>
    <div><b>${totals.lessons}</b><span>Lessons</span></div>
    <div><b>${totals.exercises}</b><span>Exercises</span></div>
    <div><b>${totals.worksheet}</b><span>Written questions</span></div>
    <div><b>~9</b><span>Months</span></div>
  </div>
</div>

<div class="box good">
  <h4>How this course is different</h4>
  <ul>
    <li><b>Everything is taught here.</b> No "go watch a video" gaps. Each idea is explained
        from zero with worked examples showing every step.</li>
    <li><b>You write code from lesson one.</b> Real Python and real SQL run in your browser
        and mark themselves. No setup needed to begin.</li>
    <li><b>Every lesson has 6-8 exercises</b>, rising from easy to hard, plus a written
        worksheet you can print for offline or classroom use.</li>
    <li><b>It is honest about difficulty.</b> The course tells you when something is genuinely
        hard, when a technique is the wrong choice, and what the limits of the tools are.</li>
  </ul>
</div>

${stagesHtml}

<section class="stage">
  <div class="shead">
    <div class="sn">IMPORTANT</div>
    <h2>What this course does and does not cover</h2>
  </div>

  <p style="margin-bottom:14px">Being clear about this matters. "Learning AI" means very different
     things to different people, and courses that promise everything usually deliver nothing.</p>

  <table>
    <thead><tr><th style="width:52%">Skill</th><th>Covered?</th></tr></thead>
    <tbody>
      <tr><td>Programming from absolute zero</td><td class="yes">Yes, fully</td></tr>
      <tr><td>Python to a professional standard</td><td class="yes">Yes, fully</td></tr>
      <tr><td>Databases and SQL</td><td class="yes">Yes, fully</td></tr>
      <tr><td>Cleaning and analysing real data</td><td class="yes">Yes, fully</td></tr>
      <tr><td>How machine learning actually works</td><td class="yes">Yes, built by hand</td></tr>
      <tr><td>How language models generate text</td><td class="yes">Yes, mechanically</td></tr>
      <tr><td>Building AI applications (RAG, agents, prompting)</td><td class="yes">Yes, fully</td></tr>
      <tr><td>Controlling what an AI system costs to run</td><td class="yes">Yes &mdash; rarely taught elsewhere</td></tr>
      <tr><td>Evaluating models honestly, avoiding false results</td><td class="yes">Yes, in depth</td></tr>
      <tr><td>Training a large language model from scratch</td><td class="no">No</td></tr>
      <tr><td>University-level linear algebra and calculus</td><td class="no">No &mdash; concepts only</td></tr>
      <tr><td>AI research and publishing papers</td><td class="no">No</td></tr>
      <tr><td>Large-scale MLOps and distributed training</td><td class="no">No &mdash; introduced only</td></tr>
      <tr><td>Specialist computer vision or speech</td><td class="no">No</td></tr>
    </tbody>
  </table>

  <div class="box warn">
    <h4>So can a student "build AI" after this?</h4>
    <p style="margin-bottom:11px"><b>Yes &mdash; if "building AI" means building AI products.</b>
       That is what almost every AI job actually involves: taking existing models and building
       reliable, affordable systems around them. Retrieval systems, agents, classifiers, data
       pipelines, deployed services. A student finishing this course can do that work.</p>
    <p style="margin-bottom:11px"><b>No &mdash; if "building AI" means creating something like ChatGPT
       from nothing.</b> That requires a research team, years of specialised mathematics, and
       tens of millions of dollars of computing power. Roughly a few thousand people worldwide
       do that job. No online course puts anyone there, and any course claiming otherwise is
       selling something.</p>
    <p><b>The honest framing:</b> this course takes you from zero to genuinely employable in AI
       engineering, which is where the actual jobs are. If a student later wants research, this
       is still the right foundation &mdash; they would then add a mathematics degree and a
       master's on top.</p>
  </div>
</section>

<section class="stage">
  <div class="shead">
    <div class="sn">AFTER THE COURSE</div>
    <h2>Four projects that get interviews</h2>
  </div>
  <p style="margin-bottom:14px">Finishing lessons is not enough. Employers want evidence.
     Each project below needs a live link, a public repository, and a written explanation of
     the hardest decision you made.</p>
  <table>
    <tbody>
      <tr><td><b>1. Data cleaning and dashboard</b><br>
        <span style="color:var(--muted);font-size:13.5px">Take a messy public dataset, clean it,
        find three real insights, publish a dashboard</span></td>
        <td style="width:30%">After Stage 4</td></tr>
      <tr><td><b>2. Deployed prediction API</b><br>
        <span style="color:var(--muted);font-size:13.5px">Train a model, wrap it in an API,
        containerise it, deploy it with a working URL</span></td>
        <td>After Stage 5</td></tr>
      <tr><td><b>3. Question-answering system with citations</b><br>
        <span style="color:var(--muted);font-size:13.5px">RAG over a real document set that cites
        its sources and admits when it does not know</span></td>
        <td>After Stage 5</td></tr>
      <tr><td><b>4. An agent that does one useful thing</b><br>
        <span style="color:var(--muted);font-size:13.5px">A multi-step task completed end to end,
        with step limits, approvals and cost tracking</span></td>
        <td>After Stage 5</td></tr>
    </tbody>
  </table>
</section>

<footer>
  VidyaPath &middot; Free to copy, print and photocopy for teaching.<br>
  Salary figures, tool prices and job-market conditions change constantly &mdash;
  always check current sources before making decisions based on them.
</footer>
</body></html>`;

fs.writeFileSync("VidyaPath-Syllabus.html", html);
console.log("wrote VidyaPath-Syllabus.html");
console.log(`  ${totals.tracks} tracks, ${totals.lessons} lessons, ${totals.exercises} exercises, ${totals.worksheet} written questions`);
console.log(`  ${Math.round(html.length / 1024)} KB`);
