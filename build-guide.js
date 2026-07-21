/* ==========================================================================
   Builds VidyaPath-Complete-Guide.html
   One self-contained file: every stage, every lesson, every exercise,
   every worksheet. No server, no internet, no dependencies.
   Run:  node build-guide.js
   ========================================================================== */
const fs = require("fs");

const esc = s => String(s == null ? "" : s)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

/* Tracks superseded by a rewritten version — skipped so nothing appears twice */
const SUPERSEDED = new Set(["sql", "data", "ml", "llm", "basics", "python"]);

const load = f => {
  if (!fs.existsSync(f)) return { tracks: [] };
  const d = JSON.parse(fs.readFileSync(f, "utf8"));
  d.tracks = d.tracks.filter(t => !SUPERSEDED.has(t.id));
  return d;
};

const STAGES = [
  { file: "school.json",     n: 1, icon: "🌱", name: "Absolute Beginner",
    blurb: "You have never written a line of code. Every idea taught from zero in plain everyday language, with worked examples showing every step." },
  { file: "stage2.json",     n: 2, icon: "📘", name: "Getting Fluent",
    blurb: "You can write basic programs. Now handle text properly, structure real data, and write Python the way working programmers write it." },
  { file: "stage3a.json",    n: 3, icon: "🗄️", name: "Databases & SQL",
    blurb: "The highest-paying skill for the least effort. Every query here runs for real against a live database. SQL alone qualifies you for data analyst work." },
  { file: "stage3b.json",    n: 4, icon: "📊", name: "Data Analysis",
    blurb: "Take messy real data, clean it honestly, find something true in it, and report it without misleading anybody. This plus SQL is a Data Analyst job." },
  { file: "stage4.json",     n: 5, icon: "📈", name: "Maths, Machine Learning & AI Engineering",
    blurb: "The maths first — vectors, statistics, Bayes and derivatives, all built by hand in code. Then the learning loop itself, prompting, retrieval, agents and the cost control that is most of the real job." },
  { file: "curriculum.json", n: 6, icon: "🧰", name: "Other Languages & Career",
    blurb: "JavaScript and the web, Java and C for placements, portfolio projects and interview preparation." },
];

let toc = "", body = "";
let counts = { lessons: 0, exercises: 0, worksheet: 0, tracks: 0 };
let lessonNo = 0;

STAGES.forEach(stage => {
  const data = load(stage.file);
  if (!data.tracks.length) return;

  const stageLessons = data.tracks.reduce((a, t) => a + t.lessons.length, 0);
  const stageEx = data.tracks.reduce((a, t) =>
    a + t.lessons.reduce((b, l) => b + ((l.exercises || []).length || (l.lab && l.lab.prompt ? 1 : 0)), 0), 0);

  toc += `<div class="toc-stage">Stage ${stage.n} &middot; ${stage.icon} ${esc(stage.name)}
            <span class="toc-meta">${stageLessons} lessons</span></div>`;

  body += `<section class="stage" id="stage${stage.n}">
    <div class="stage-head">
      <div class="stage-n">STAGE ${stage.n}</div>
      <h1>${stage.icon} ${esc(stage.name)}</h1>
      <p>${esc(stage.blurb)}</p>
      <div class="stage-stats">${data.tracks.length} tracks &middot; ${stageLessons} lessons &middot; ${stageEx} exercises</div>
    </div>`;

  data.tracks.forEach(track => {
    counts.tracks++;
    toc += `<div class="toc-track">${track.icon} ${esc(track.name)}</div>`;

    body += `<div class="track">
      <h2 id="tr-${track.id}">${track.icon} ${esc(track.name)}</h2>
      <p class="track-desc">${esc(track.desc)}</p>
      ${(track.outcomes || []).length ? `
        <div class="outcomes"><b>By the end of this track you will be able to:</b>
          <ul>${track.outcomes.map(o => `<li>${esc(o)}</li>`).join("")}</ul></div>` : ""}
    </div>`;

    track.lessons.forEach(lesson => {
      lessonNo++;
      counts.lessons++;

      const exs = (lesson.exercises && lesson.exercises.length)
        ? lesson.exercises
        : (lesson.lab && (lesson.lab.prompt || lesson.lab.starter))
          ? [{ q: lesson.lab.prompt, starter: lesson.lab.starter, hint: lesson.lab.hint,
               solution: lesson.lab.solution, answer: lesson.lab.answer }]
          : [];
      counts.exercises += exs.length;
      counts.worksheet += (lesson.worksheet || []).length;

      toc += `<a class="toc-lesson" href="#L${lessonNo}">
                <span class="toc-num">${lessonNo}</span>${esc(lesson.title)}</a>`;

      body += `<article class="lesson" id="L${lessonNo}">
        <div class="lesson-head">
          <div class="lesson-num">Lesson ${lessonNo}</div>
          <h3>${esc(lesson.title)}</h3>
          <div class="lesson-meta">${track.icon} ${esc(track.name)} &middot; ${lesson.mins} min read
            ${exs.length ? ` &middot; ${exs.length} exercise${exs.length === 1 ? "" : "s"}` : ""}
            ${(lesson.worksheet || []).length ? ` &middot; ${lesson.worksheet.length} worksheet questions` : ""}</div>
        </div>

        <div class="notes">${lesson.content}</div>`;

      /* ---- references (stage 3 only) ---- */
      const links = [...(lesson.videos || []), ...(lesson.refs || [])];
      if (links.length) {
        body += `<div class="links"><b>Extra reading (optional — the notes above are complete)</b>
          <ul>${links.map(r => `<li><a href="${esc(r.u)}" target="_blank" rel="noopener">${esc(r.t)}</a></li>`).join("")}</ul></div>`;
      }

      /* ---- exercises ---- */
      if (exs.length) {
        body += `<div class="ex-block"><h4>Practice — ${exs.length} exercise${exs.length === 1 ? "" : "s"}</h4>
          <p class="ex-intro">Type these out yourself. Do not read the solution until you have genuinely tried.
             Struggling for ten minutes teaches more than reading for an hour.</p>`;

        exs.forEach((e, i) => {
          body += `<div class="ex">
            <div class="ex-q"><span class="ex-n">${i + 1}</span><div>${e.q || ""}</div></div>
            ${e.starter ? `<pre class="starter"><code>${esc(e.starter)}</code></pre>` : ""}
            ${e.hint ? `<details class="dd hint"><summary>Show hint</summary><div>${esc(e.hint)}</div></details>` : ""}
            ${e.solution ? `<details class="dd sol"><summary>Show solution</summary><pre><code>${esc(e.solution)}</code></pre></details>` : ""}
            ${e.answer ? `<details class="dd sol"><summary>Show model answer</summary><div class="ans">${esc(e.answer)}</div></details>` : ""}
          </div>`;
        });
        body += `</div>`;
      }

      /* ---- worksheet ---- */
      if ((lesson.worksheet || []).length) {
        body += `<div class="ws-block"><h4>Written worksheet — ${lesson.worksheet.length} questions</h4>
          <p class="ex-intro">Answer these on paper, in your own words. Writing an explanation out is the fastest way to find out whether you actually understood it.</p>`;
        lesson.worksheet.forEach((w, i) => {
          body += `<div class="ws">
            <div class="ws-q"><span class="ex-n">${i + 1}</span><div>${esc(w.q)}</div></div>
            <details class="dd"><summary>Show answer</summary><div class="ans">${esc(w.a)}</div></details>
          </div>`;
        });
        body += `</div>`;
      }

      body += `</article>`;
    });
  });

  body += `</section>`;
});

/* ====================== PAGE ====================== */
const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>VidyaPath — Complete Study Guide</title>
<style>
:root{
  --bg:#ffffff;--paper:#fbfbfa;--line:#e3e3e0;--text:#1a1a19;--muted:#6b6b68;
  --accent:#c2410c;--accent2:#1e5fa8;--green:#15803d;--code:#f5f5f3;--r:8px;
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--text);
     font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
     font-size:16px;line-height:1.7;-webkit-font-smoothing:antialiased}
code,pre{font-family:"SF Mono",Menlo,Consolas,"Liberation Mono",monospace}
a{color:var(--accent2)}

/* ---------- layout ---------- */
.wrap{display:flex;max-width:1500px;margin:0 auto}
.side{width:310px;flex-shrink:0;border-right:1px solid var(--line);
      height:100vh;position:sticky;top:0;overflow-y:auto;background:var(--paper)}
.main{flex:1;min-width:0;padding:0 46px 90px}

.brand{padding:22px 20px 16px;border-bottom:1px solid var(--line)}
.brand h1{font-size:19px;font-weight:800;letter-spacing:-.4px}
.brand h1 span{color:var(--accent)}
.brand p{font-size:11.5px;color:var(--muted);margin-top:2px}
.searchbox{padding:12px 16px;border-bottom:1px solid var(--line)}
.searchbox input{width:100%;padding:8px 11px;border:1px solid var(--line);
  border-radius:6px;font-size:13.5px;font-family:inherit;outline:none;background:#fff}
.searchbox input:focus{border-color:var(--accent)}
.toc{padding:8px 0 40px}
.toc-stage{padding:16px 18px 7px;font-size:10.5px;font-weight:800;
  text-transform:uppercase;letter-spacing:.9px;color:var(--accent);
  display:flex;justify-content:space-between;align-items:baseline}
.toc-meta{font-weight:500;color:var(--muted);letter-spacing:0;text-transform:none}
.toc-track{padding:9px 18px 4px;font-size:12.5px;font-weight:700;color:var(--text)}
.toc-lesson{display:flex;gap:9px;padding:5px 18px 5px 22px;font-size:13px;
  color:var(--muted);text-decoration:none;line-height:1.45}
.toc-lesson:hover{background:#f0efec;color:var(--text)}
.toc-num{color:#b0b0ac;font-size:11px;min-width:17px;padding-top:2px}

/* ---------- cover ---------- */
.cover{padding:70px 0 40px;border-bottom:3px solid var(--text);margin-bottom:16px}
.cover h1{font-size:44px;font-weight:800;letter-spacing:-1.6px;line-height:1.08}
.cover h1 span{color:var(--accent)}
.cover .tag{font-size:18px;color:var(--muted);margin-top:12px;max-width:640px}
.cover .nums{display:flex;gap:34px;margin-top:30px;flex-wrap:wrap}
.cover .nums div b{display:block;font-size:29px;font-weight:800;letter-spacing:-1px}
.cover .nums div span{font-size:11.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.8px}
.howto{background:var(--paper);border:1px solid var(--line);border-radius:var(--r);
       padding:22px 26px;margin:26px 0 10px}
.howto b{display:block;margin-bottom:9px;font-size:15px}
.howto ul{margin-left:19px;color:#3a3a38;font-size:14.5px}
.howto li{margin-bottom:6px}

/* ---------- stage ---------- */
.stage-head{padding:52px 0 22px;border-bottom:2px solid var(--line);margin-bottom:12px}
.stage-n{font-size:11px;font-weight:800;letter-spacing:1.4px;color:var(--accent)}
.stage-head h1{font-size:33px;font-weight:800;letter-spacing:-1px;margin:5px 0 9px}
.stage-head p{color:var(--muted);max-width:660px}
.stage-stats{font-size:12.5px;color:var(--muted);margin-top:11px;
  padding-top:11px;border-top:1px solid var(--line)}

/* ---------- track ---------- */
.track h2{font-size:23px;font-weight:750;letter-spacing:-.5px;margin:40px 0 7px}
.track-desc{color:var(--muted);max-width:700px}
.outcomes{background:var(--paper);border-left:3px solid var(--accent);
  padding:14px 18px;border-radius:0 var(--r) var(--r) 0;margin:14px 0 6px;font-size:14.5px}
.outcomes ul{margin:7px 0 0 19px}
.outcomes li{margin-bottom:3px}

/* ---------- lesson ---------- */
.lesson{padding:36px 0;border-bottom:1px solid var(--line)}
.lesson-head{margin-bottom:22px}
.lesson-num{font-size:10.5px;font-weight:800;letter-spacing:1.2px;color:var(--accent)}
.lesson-head h3{font-size:26px;font-weight:750;letter-spacing:-.7px;margin:4px 0 5px}
.lesson-meta{font-size:12.5px;color:var(--muted)}

.notes h3{font-size:19px;font-weight:700;margin:28px 0 9px;letter-spacing:-.3px}
.notes h4{font-size:15.5px;font-weight:700;margin:20px 0 7px;color:var(--accent)}
.notes p{margin-bottom:13px}
.notes ul{margin:0 0 15px 22px}
.notes li{margin-bottom:6px}
.notes pre{background:var(--code);border:1px solid var(--line);border-radius:var(--r);
  padding:15px 17px;overflow-x:auto;font-size:13.5px;line-height:1.62;margin-bottom:15px}
.notes code{background:var(--code);padding:2px 6px;border-radius:4px;font-size:14px}
.notes pre code{background:none;padding:0}
.callout{border-left:3px solid var(--accent2);background:#eff6fd;
  padding:14px 18px;border-radius:0 var(--r) var(--r) 0;margin-bottom:15px}

.links{background:var(--paper);border:1px solid var(--line);border-radius:var(--r);
  padding:15px 18px;margin:20px 0;font-size:14px}
.links ul{margin:8px 0 0 19px}
.links li{margin-bottom:4px}

/* ---------- exercises ---------- */
.ex-block,.ws-block{margin-top:32px;padding-top:22px;border-top:2px solid var(--line)}
.ex-block h4,.ws-block h4{font-size:17px;font-weight:750;margin-bottom:5px}
.ex-intro{font-size:13.5px;color:var(--muted);margin-bottom:18px;max-width:640px}
.ex,.ws{margin-bottom:20px;padding-bottom:16px;border-bottom:1px solid #efefec}
.ex:last-child,.ws:last-child{border-bottom:none}
.ex-q,.ws-q{display:flex;gap:12px;margin-bottom:9px}
.ex-n{background:var(--accent);color:#fff;width:23px;height:23px;border-radius:50%;
  display:flex;align-items:center;justify-content:center;font-size:12px;
  font-weight:700;flex-shrink:0;margin-top:2px}
.starter{background:var(--code);border:1px solid var(--line);border-radius:var(--r);
  padding:13px 16px;overflow-x:auto;font-size:13.5px;line-height:1.6;margin:0 0 9px 35px}
.dd{margin-left:35px;margin-bottom:6px}
.dd summary{cursor:pointer;font-size:13px;color:var(--accent2);
  padding:5px 11px;background:var(--paper);border:1px solid var(--line);
  border-radius:5px;display:inline-block;user-select:none}
.dd summary:hover{border-color:var(--accent2)}
.dd[open] summary{margin-bottom:8px}
.dd>div,.dd>pre{border-left:3px solid var(--line);padding:11px 15px;
  background:var(--paper);border-radius:0 var(--r) var(--r) 0;font-size:14px}
.dd>pre{overflow-x:auto;font-size:13.5px;line-height:1.6}
.hint>div{border-left-color:var(--accent)}
.sol>pre,.sol>div{border-left-color:var(--green)}
.ans{white-space:pre-wrap;font-size:14px;line-height:1.65}

.hidden{display:none!important}
.nores{padding:40px;text-align:center;color:var(--muted)}
.top{position:fixed;right:24px;bottom:24px;background:var(--text);color:#fff;
  width:42px;height:42px;border-radius:50%;display:flex;align-items:center;
  justify-content:center;text-decoration:none;font-size:17px;opacity:.82}
.top:hover{opacity:1}

@media(max-width:1000px){
  .side{display:none}
  .main{padding:0 20px 60px}
  .cover h1{font-size:31px}
}
@media print{
  .side,.top,.searchbox{display:none}
  .main{padding:0}
  body{font-size:11pt}
  .dd{display:none}            /* hide solutions when printing worksheets */
  .lesson{page-break-inside:auto}
  .lesson-head{page-break-after:avoid}
  .notes pre{page-break-inside:avoid}
  a{color:var(--text);text-decoration:none}
  @page{margin:16mm}
}
</style>
</head>
<body>
<div class="wrap">
  <nav class="side">
    <div class="brand"><h1>Vidya<span>Path</span></h1><p>Complete Study Guide</p></div>
    <div class="searchbox"><input id="q" placeholder="Search lessons..." autocomplete="off"/></div>
    <div class="toc" id="toc">${toc}</div>
  </nav>

  <main class="main">
    <div class="cover">
      <h1>Learn to Code,<br>Then Build with <span>AI</span></h1>
      <p class="tag">One continuous route from never having written a line of code
         through to job-ready AI engineering. Everything taught in full — no video required.</p>
      <p style="margin-top:22px">
        <button id="guideTour" style="font-family:inherit;font-size:15px;padding:12px 24px;
          border:none;border-radius:10px;cursor:pointer;font-weight:650;
          background:linear-gradient(135deg,#e8892a,#c2410c);color:#fff">
          ▶ Let Vidya explain this course</button>
      </p>
      <div class="nums">
        <div><b>${counts.lessons}</b><span>Lessons</span></div>
        <div><b>${counts.exercises}</b><span>Exercises</span></div>
        <div><b>${counts.worksheet}</b><span>Worksheet questions</span></div>
        <div><b>${counts.tracks}</b><span>Tracks</span></div>
        <div><b>6</b><span>Stages</span></div>
      </div>
      <div class="howto">
        <b>How to use this guide</b>
        <ul>
          <li><b>Go in order.</b> Every lesson assumes the ones before it and nothing else. Skipping ahead is the main reason people give up.</li>
          <li><b>Read the notes, then close them.</b> Try to explain the idea out loud before moving to the exercises. If you cannot, read it again.</li>
          <li><b>Type every exercise yourself.</b> Do not copy-paste, and do not open the solution until you have genuinely tried. Ten minutes of being stuck teaches more than an hour of reading.</li>
          <li><b>Do the written worksheets on paper.</b> Explaining something in your own words is the fastest way to discover you did not really understand it.</li>
          <li><b>To run the code:</b> install Python from python.org, or use any free online Python editor. Stage 1 Lesson 4 covers the full setup.</li>
          <li><b>To print:</b> press Ctrl+P. Solutions and answers are hidden automatically, so it prints as a clean worksheet.</li>
          <li><b>Two hours a day, six days a week</b> takes you through all three stages in roughly eight months.</li>
        </ul>
      </div>
    </div>
    <div id="content">${body}</div>
    <div class="nores hidden" id="nores">No lessons match that search.</div>
  </main>
</div>
<a class="top" href="#" title="Back to top">&uarr;</a>

<script>
${["tutor.js", "presenter.js"]
   .filter(f => fs.existsSync(f))
   .map(f => fs.readFileSync(f, "utf8").replace(/<\/script>/gi, "<\\/script>"))
   .join("\n\n")}
</script>
<script>
/* The guide has no live TRACKS object, so give the tour real numbers */
window.TRACKS = [{ lessons: new Array(${counts.lessons}).fill(0).map(function () {
  return { exercises: new Array(Math.round(${counts.exercises} / ${counts.lessons})).fill(0) };
}) }];

var tourBtn = document.getElementById("guideTour");
if (tourBtn) tourBtn.onclick = function () {
  if (window.Presenter) Presenter.tour();
};

/* start the tutor and let it read whichever lesson is on screen */
if (window.Tutor) {
  Tutor.init();
  setTimeout(function () {
    Tutor.say("Hello. I am Vidya, your guide. Open any lesson and I can read the notes aloud for you. Tap me any time.", [
      { label: "Read this page aloud", primary: true, onClick: function () {
          var vis = Array.prototype.filter.call(
            document.querySelectorAll(".lesson"),
            function (l) {
              var r = l.getBoundingClientRect();
              return r.top < window.innerHeight && r.bottom > 0;
            })[0];
          Tutor.readAloud(vis ? vis.querySelector(".notes") : null);
      }}
    ]);
  }, 1000);

  /* offer to read whichever lesson the reader scrolls to */
  var lastSpoken = null, scrollTimer = null;
  window.addEventListener("scroll", function () {
    clearTimeout(scrollTimer);
    scrollTimer = setTimeout(function () {
      var vis = Array.prototype.filter.call(
        document.querySelectorAll(".lesson:not(.hidden)"),
        function (l) {
          var r = l.getBoundingClientRect();
          return r.top < 200 && r.bottom > 200;
        })[0];
      if (!vis || vis.id === lastSpoken) return;
      lastSpoken = vis.id;
      var title = vis.querySelector("h3");
      if (!title) return;
      Tutor.say("You are now on: " + title.textContent, [
        { label: "Read this lesson aloud", primary: true, onClick: function () {
            Tutor.readAloud(vis.querySelector(".notes"));
        }}
      ]);
    }, 1200);
  });
}
</script>
<script>
var q = document.getElementById("q");
var lessons = document.querySelectorAll(".lesson");
var tocLinks = document.querySelectorAll(".toc-lesson");
var nores = document.getElementById("nores");

q.addEventListener("input", function () {
  var term = q.value.trim().toLowerCase();
  var shown = 0;

  if (!term) {
    lessons.forEach(function (el) { el.classList.remove("hidden"); });
    tocLinks.forEach(function (el) { el.classList.remove("hidden"); });
    document.querySelectorAll(".stage-head,.track,.cover,.toc-stage,.toc-track")
      .forEach(function (el) { el.classList.remove("hidden"); });
    nores.classList.add("hidden");
    return;
  }

  document.querySelectorAll(".cover,.stage-head,.track,.toc-stage,.toc-track")
    .forEach(function (el) { el.classList.add("hidden"); });

  lessons.forEach(function (el, i) {
    var hit = el.textContent.toLowerCase().indexOf(term) !== -1;
    el.classList.toggle("hidden", !hit);
    if (tocLinks[i]) tocLinks[i].classList.toggle("hidden", !hit);
    if (hit) shown++;
  });

  nores.classList.toggle("hidden", shown > 0);
});
</script>
</body>
</html>`;

fs.writeFileSync("VidyaPath-Complete-Guide.html", html);
console.log("wrote VidyaPath-Complete-Guide.html");
console.log("  " + counts.tracks + " tracks, " + counts.lessons + " lessons, "
  + counts.exercises + " exercises, " + counts.worksheet + " worksheet questions");
console.log("  " + Math.round(html.length / 1024) + " KB, fully self-contained");
