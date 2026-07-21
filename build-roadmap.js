/* Builds VidyaPath-Roadmap.html — an honest map of every topic:
   what is taught now, what is planned, and what needs tools this
   platform cannot honestly provide (with the best free alternative named).
   Run:  node build-roadmap.js                                          */
const fs = require("fs");

/* status: done | partial | planned | external
   where:  which lessons cover it (for done/partial)
   why:    honesty note (for external)
   ref:    best free resource (for external/partial)                    */
const DOMAINS = [
{ name:"Programming Foundations", items:[
  { t:"Python", s:"done", where:"Stages 1–2 · 14 lessons, 111 exercises" },
  { t:"Git & GitHub", s:"partial", where:"Stage 1 L4 setup walkthrough", ref:"Pro Git book (git-scm.com/book) — free, official" },
  { t:"Linux/Terminal", s:"partial", where:"Stage 1 L4 basics", ref:"linuxjourney.com — free, interactive" },
  { t:"APIs", s:"done", where:"Stage 2 (calling APIs) + Stage 5 (serving them)" },
]},
{ name:"Mathematics for AI", items:[
  { t:"Linear Algebra", s:"done", where:"Maths track L1 — vectors, dot products, matrix multiply by hand" },
  { t:"Statistics", s:"done", where:"Maths track L2 — spread, z-scores, correlation by hand" },
  { t:"Probability", s:"done", where:"Maths track L3 — rules, conditioning, Bayes by counting" },
  { t:"Calculus", s:"done", where:"Maths track L4 — numeric derivatives, chain rule verified in code" },
  { t:"Optimization", s:"done", where:"Maths L4 + ML L2 — gradient descent built by hand" },
]},
{ name:"Data Science", items:[
  { t:"NumPy", s:"partial", where:"Concepts in Data Analysis track; full API needs installation", ref:"numpy.org absolute beginner's guide" },
  { t:"Pandas", s:"partial", where:"Every method named alongside hand-built equivalents", ref:"Kaggle Learn pandas course — free" },
  { t:"Data Visualization", s:"done", where:"Data Analysis L4 — honest charts, text charts, matplotlib shown" },
  { t:"SQL", s:"done", where:"SQL track · 5 lessons, 40 exercises on a real database" },
  { t:"Data Cleaning", s:"done", where:"Data Analysis L1–L2 — the six problems and their fixes" },
]},
{ name:"Machine Learning", items:[
  { t:"Supervised Learning", s:"done", where:"ML track L1 — the loop built from scratch" },
  { t:"Unsupervised Learning", s:"planned", ref:"Until then: StatQuest k-means video + Kaggle clustering course" },
  { t:"Model Evaluation", s:"done", where:"ML L3 — splits, precision/recall, leakage, baselines" },
  { t:"Feature Engineering", s:"partial", where:"Leakage question in ML L3 covers the core discipline", ref:"Kaggle Learn feature engineering" },
]},
{ name:"Deep Learning", items:[
  { t:"PyTorch", s:"partial", where:"Full training loop shown and explained in ML L4; running it needs a GPU/install", ref:"pytorch.org 60-minute blitz" },
  { t:"TensorFlow", s:"external", why:"Teaching two frameworks doubles confusion; PyTorch dominates new work", ref:"tensorflow.org tutorials if a job requires it" },
  { t:"CNNs", s:"planned", ref:"Until then: CS231n notes (cs231n.github.io) — free, the best there is" },
  { t:"RNNs", s:"external", why:"Superseded by transformers for nearly all new work; learn only if maintaining legacy systems", ref:"Karpathy's 'Unreasonable Effectiveness of RNNs'" },
  { t:"Transformers", s:"done", where:"AI track L1 — attention, tokens, generation mechanics" },
]},
{ name:"Generative AI", items:[
  { t:"LLMs", s:"done", where:"AI track L1 — how they actually work" },
  { t:"Prompt Engineering", s:"done", where:"AI track L2 — production prompting with validation" },
  { t:"RAG", s:"done", where:"AI track L3 — built from scratch, retrieval debugging" },
  { t:"Fine-tuning", s:"partial", where:"When-and-why covered in ML L4", ref:"Hugging Face fine-tuning course — free" },
  { t:"Embeddings", s:"done", where:"SQL L4 + AI L3 + Maths L1 (the dot product underneath)" },
  { t:"Vector Databases", s:"done", where:"SQL track L4 — cosine similarity implemented by hand" },
]},
{ name:"AI Agents", items:[
  { t:"Tool Calling", s:"done", where:"AI track L4 — the loop, allowlists, approval gates" },
  { t:"Multi-Agent Systems", s:"planned", ref:"Build one solid single agent first; multi-agent adds failure modes before value" },
  { t:"LangChain / LangGraph", s:"external", why:"Frameworks change monthly; the concepts underneath are what this course teaches", ref:"python.langchain.com once concepts are solid" },
  { t:"MCP", s:"external", why:"A young protocol; learn after the agent fundamentals", ref:"modelcontextprotocol.io" },
]},
{ name:"Computer Vision · NLP · Speech", items:[
  { t:"Image Classification / Object Detection / Segmentation / OCR", s:"external", why:"Real CV needs GPUs and large datasets — cannot run honestly in a browser", ref:"fast.ai course — free and genuinely excellent" },
  { t:"Text Classification / NER / Translation / Summarization", s:"partial", where:"All are LLM applications now; the AI track teaches the approach", ref:"Hugging Face NLP course" },
  { t:"Speech-to-Text / TTS / Voice Assistants", s:"external", why:"API-driven work; the tutor Vidya uses browser TTS as a working demo", ref:"OpenAI Whisper docs (open source)" },
]},
{ name:"MLOps & Cloud", items:[
  { t:"Docker", s:"done", where:"AI track L5 — Dockerfile explained line by line" },
  { t:"Model Deployment", s:"done", where:"AI L5 + your own Railway deployment — you did this for real" },
  { t:"Monitoring", s:"done", where:"AI L5 — logging, drift, feedback, cost alerts" },
  { t:"CI/CD", s:"partial", where:"Git push → auto-deploy is CI/CD; you use it already", ref:"GitHub Actions docs when you need tests in the loop" },
  { t:"Kubernetes", s:"external", why:"Needs paid multi-node clusters; overkill before serious scale", ref:"kubernetes.io interactive tutorials" },
  { t:"AWS / Azure / GCP", s:"external", why:"Need accounts, cards and real money; concepts here transfer directly", ref:"Each cloud's own free-tier tutorials — pick ONE" },
]},
{ name:"AI Ethics & Security", items:[
  { t:"Bias", s:"done", where:"Stage 1 L9 (hiring example) + Maths L2 (statistical roots)" },
  { t:"Responsible AI / AI Safety", s:"done", where:"Stage 1 L9 honestly, plus guardrails throughout the agents lesson" },
  { t:"Privacy", s:"partial", where:"SQL injection, secrets handling, least privilege all covered", ref:"OWASP Top 10 for LLM applications" },
]},
{ name:"Research & Advanced", items:[
  { t:"Diffusion Models / RL / Multimodal / Robotics / Papers", s:"external", why:"Research territory — needs the mathematics degree this course honestly says it does not replace", ref:"Start with distill.pub and the fast.ai part 2 course" },
]},
{ name:"Career Preparation", items:[
  { t:"Portfolio", s:"done", where:"Career track — four projects with interviewer checklists" },
  { t:"Resume", s:"done", where:"Career track — ATS rules, positioning" },
  { t:"Interview Preparation", s:"done", where:"Career track — all four round types, worked answers" },
  { t:"Freelancing / Startup Building", s:"planned", ref:"Until then: firstround.com library, free" },
]},
];

const FEATURES = [
  { t:"Interactive coding playground", s:"done", note:"Python, JavaScript and real SQL run in the browser and self-grade" },
  { t:"AI tutor that answers questions", s:"done", note:"Vidya — context-aware guidance with voice. Rule-based by design: free, offline, no API key to leak" },
  { t:"Real-world projects", s:"done", note:"Four portfolio projects with step checklists and interviewer criteria" },
  { t:"Daily coding challenges", s:"done", note:"One shared challenge per day on the dashboard — same for everyone, so classmates can compare" },
  { t:"Certificates", s:"done", note:"Per stage, earned by passing every auto-graded exercise — not by watching" },
  { t:"Progress tracking", s:"done", note:"XP, levels, streaks, per-lesson history, admin drop-off analytics" },
  { t:"Interview preparation", s:"done", note:"Career track, including a worked system-design answer" },
  { t:"AI-generated quizzes and flashcards", s:"partial", note:"360 written Q&A pairs exist and work as flashcards; 'AI-generated' would add API cost without adding questions" },
  { t:"Hackathons", s:"skip", note:"An event, not a feature — needs a community first. Run one manually when you have 30+ active students" },
  { t:"Community discussions", s:"skip", note:"Forums with no moderation and no users become spam. Start a WhatsApp/Discord group; build in-app community only after it outgrows that" },
];

const esc = s => String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
const BADGE = {
  done:     ["✅ Taught now",   "#15803d", "#f0f9f2"],
  partial:  ["🟡 Partly",       "#a16207", "#fdf8ec"],
  planned:  ["🔜 Planned",      "#1e5fa8", "#eff6fd"],
  external: ["↗ Best elsewhere","#6b6b66", "#f6f5f2"],
  skip:     ["✋ Deliberately not", "#b4530a", "#fdf3ec"],
};

let counts = { done:0, partial:0, planned:0, external:0, skip:0 };
let body = "";

DOMAINS.forEach(d => {
  body += `<h2>${esc(d.name)}</h2><div class="items">`;
  d.items.forEach(i => {
    counts[i.s]++;
    const [label, color, bg] = BADGE[i.s];
    body += `<div class="item">
      <div class="ihead"><b>${esc(i.t)}</b>
        <span class="badge" style="color:${color};background:${bg}">${label}</span></div>
      ${i.where ? `<div class="where">${esc(i.where)}</div>` : ""}
      ${i.why   ? `<div class="why">${esc(i.why)}</div>` : ""}
      ${i.ref   ? `<div class="ref">Free resource: ${esc(i.ref)}</div>` : ""}
    </div>`;
  });
  body += `</div>`;
});

let feat = "";
FEATURES.forEach(f => {
  counts[f.s] = (counts[f.s] || 0) + 1;
  const [label, color, bg] = BADGE[f.s];
  feat += `<div class="item">
    <div class="ihead"><b>${esc(f.t)}</b>
      <span class="badge" style="color:${color};background:${bg}">${label}</span></div>
    <div class="where">${esc(f.note)}</div>
  </div>`;
});

const html = `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>VidyaPath — Honest Roadmap</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
     color:#1a1a19;background:#fff;max-width:900px;margin:0 auto;
     padding:44px 26px 80px;font-size:15.5px;line-height:1.65}
h1{font-size:34px;font-weight:800;letter-spacing:-1px}
.sub{color:#6b6b68;margin:10px 0 6px;max-width:640px}
h2{font-size:20px;font-weight:750;margin:34px 0 12px;letter-spacing:-.4px;
   border-bottom:2px solid #e3e3e0;padding-bottom:7px}
.legend{display:flex;gap:14px;flex-wrap:wrap;margin:22px 0;font-size:12.5px}
.legend span{padding:4px 11px;border-radius:99px;font-weight:600}
.items{display:grid;gap:10px}
.item{border:1px solid #e3e3e0;border-radius:10px;padding:13px 16px}
.ihead{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}
.badge{font-size:11.5px;font-weight:700;padding:3px 10px;border-radius:99px;white-space:nowrap}
.where{font-size:13px;color:#4a4a46;margin-top:5px}
.why{font-size:13px;color:#8a5a20;margin-top:5px}
.ref{font-size:12.5px;color:#1e5fa8;margin-top:4px}
.note{background:#fbfbfa;border:1px solid #e3e3e0;border-left:3px solid #c2410c;
      border-radius:0 10px 10px 0;padding:16px 20px;margin:22px 0;font-size:14px}
footer{margin-top:44px;padding-top:18px;border-top:1px solid #e3e3e0;
       font-size:12.5px;color:#8b8b85}
@media print{@page{margin:14mm}}
</style></head><body>
<h1>The Honest Roadmap</h1>
<p class="sub">Every topic from "zero to AI engineer", mapped to what VidyaPath teaches
today, what is planned, and where a topic is genuinely better learned elsewhere —
with the best free resource named. No topic is hidden and none is oversold.</p>

<div class="legend">
  <span style="color:#15803d;background:#f0f9f2">✅ Taught now · ${counts.done}</span>
  <span style="color:#a16207;background:#fdf8ec">🟡 Partly · ${counts.partial}</span>
  <span style="color:#1e5fa8;background:#eff6fd">🔜 Planned · ${counts.planned}</span>
  <span style="color:#6b6b66;background:#f6f5f2">↗ Best elsewhere · ${counts.external}</span>
  <span style="color:#b4530a;background:#fdf3ec">✋ Deliberately not · ${counts.skip}</span>
</div>

<div class="note"><b>Why "best elsewhere" is a category:</b> some topics need GPUs,
cloud accounts or hardware that a free browser platform cannot honestly provide.
Pretending to teach Kubernetes in a textbox would produce students who believe they
know Kubernetes. Naming the best free resource is more useful than a shallow imitation.</div>

${body}

<h2>Platform features</h2>
<div class="items">${feat}</div>

<footer>VidyaPath · Generated ${new Date().toISOString().slice(0,10)} ·
45 lessons, 289 verified exercises, 360 written questions currently live.</footer>
</body></html>`;

fs.writeFileSync("VidyaPath-Roadmap.html", html);
const total = Object.values(counts).reduce((a,b)=>a+b,0);
console.log(`wrote VidyaPath-Roadmap.html — ${total} items:`, counts);
