/* The scanner: photograph anything you are stuck on.
 *
 * Kept out of the SQL board on purpose. The board is one subject with a
 * database behind it; this is any subject at all, and mixing them would make
 * both harder to explain on the home page.
 *
 * The camera flow is the one that already works in the edu product, for the
 * same reasons it was built there: the shot is held for confirmation instead
 * of being sent straight off, because a blurred photo should cost a retake
 * rather than a model call and a confident wrong answer; and the camera is
 * released the moment the shot is taken, because a viewfinder still running
 * behind an answer drains the battery and worries people.
 */
(function () {
  "use strict";

  var SC = {
    view: "idle",     // idle | cam | shot | busy | answer
    stream: null,
    shot: null,       // object URL of the held frame
    shotFile: null,
    scan: null,
    key: "",
    msg: "",
    recent: [],
    course: null,
    courseBusy: false,
    quiz: {},         // questionId -> chosen option index
    open: {}          // moduleIndex -> expanded
  };
  window.SC = SC;

  // How deep to go. Not a subject list — a subject list would always be
  // missing somebody's, and this product does not have one. Depth is the
  // thing that actually changes what a good course on a topic looks like.
  var DEPTHS = [
    ["curious", "Just curious"],
    ["undergrad", "Undergraduate"],
    ["masters", "Master's"],
    ["phd", "PhD / research"],
    ["applied", "For work"]
  ];
  SC.depth = "undergrad";

  var esc = window.esc || function (s) {
    return String(s).replace(/[&<>]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c];
    });
  };
  /* The host's selector when it offers one, or the document's.
   *
   * index.html has a single #main and answers this with querySelector, so
   * nothing changes there. craxlearn.html has up to four spaces and no
   * element called #main at all — it answers "#main" with whichever space
   * is being drawn into, which is what lets this module render into a pane
   * without knowing panes exist. Without this the module quietly found
   * nothing and drew nothing. */
  var $ = window.$ || function (s) { return document.querySelector(s); };

  var CSS = [
    ".scwrap{max-width:760px}",
    ".scstage{border:1px solid var(--line,#2a2a2a);border-radius:16px;",
    "  overflow:hidden;background:var(--panel2,#0f0f0f);position:relative;",
    "  aspect-ratio:4/3;display:flex;align-items:center;justify-content:center}",
    ".scstage video,.scstage img{width:100%;height:100%;object-fit:cover;",
    "  display:block}",
    /* The guide the question gets lined up inside. The crop below uses these
       same numbers — send the whole photo and the model helpfully answers the
       question next to the one they meant. */
    ".scframe{position:absolute;left:8%;top:29%;width:84%;height:42%;",
    "  border:2px dashed rgba(255,176,32,.85);border-radius:10px;",
    "  pointer-events:none}",
    ".scframe::after{content:'line the question up inside here';",
    "  position:absolute;left:0;right:0;bottom:-24px;text-align:center;",
    "  font-size:11px;color:var(--accent,#ffb020)}",
    ".scidle{text-align:center;padding:28px 20px;color:var(--muted,#8a8a8a);",
    "  font-size:13.5px;line-height:1.6}",
    ".scbar{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}",
    ".scread{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12.5px;",
    "  line-height:1.65;white-space:pre-wrap;word-break:break-word;",
    "  background:var(--panel2,#0f0f0f);border:1px solid var(--line,#2a2a2a);",
    "  border-radius:10px;padding:11px 13px;max-height:230px;overflow:auto}",
    ".scstep{display:flex;gap:11px;padding:10px 0;border-top:1px solid ",
    "  var(--line,#2a2a2a)}",
    ".scstep:first-child{border-top:none}",
    ".scstep-n{flex:0 0 22px;height:22px;border-radius:50%;font-size:11px;",
    "  display:flex;align-items:center;justify-content:center;font-weight:800;",
    "  background:rgba(255,176,32,.16);color:var(--accent,#ffb020)}",
    ".scstep h4{margin:0 0 3px;font-size:13.5px;font-weight:750}",
    ".scstep p{margin:0;font-size:13px;line-height:1.7;color:var(--body,#ccc)}",
    ".scwork{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12.5px;",
    "  white-space:pre-wrap;background:var(--panel2,#0f0f0f);",
    "  border:1px solid var(--line,#2a2a2a);border-radius:8px;",
    "  padding:9px 11px;margin:7px 0 0;overflow-x:auto}",
    ".scans{border:1px solid #3fae6a;background:rgba(63,174,106,.10);",
    "  border-radius:12px;padding:13px;margin-top:14px;font-size:14px;",
    "  line-height:1.65}",
    ".scwarn{border:1px solid #d9534f;background:rgba(217,83,79,.12);",
    "  border-radius:10px;padding:11px 13px;font-size:13px;line-height:1.6;",
    "  margin-top:10px;font-weight:600}",
    ".scwarn b{display:block;margin-bottom:5px}",
    ".scwarn i{display:block;font-style:normal;font-size:11.5px;opacity:.75;",
    "  margin-top:6px;font-weight:400}",
    ".sctag{display:inline-block;font-size:11px;font-weight:700;padding:3px 9px;",
    "  border-radius:999px;background:rgba(255,176,32,.14);",
    "  color:var(--accent,#ffb020);margin-right:6px}",

    /* the offer, and the course it opens */
    ".scoffer{border:1px solid var(--accent,#ffb020);border-radius:14px;",
    "  padding:15px;margin-top:16px;",
    "  background:linear-gradient(180deg,rgba(255,176,32,.09),transparent)}",
    ".scoffer b{display:block;font-size:14.5px;margin-bottom:4px}",
    ".scoffer p{margin:0 0 11px;font-size:13px;color:var(--muted,#8a8a8a);",
    "  line-height:1.6}",
    ".sccourse{margin-top:18px}",
    ".scmod{border:1px solid var(--line,#2a2a2a);border-radius:12px;",
    "  margin-bottom:10px;overflow:hidden}",
    ".scmod>summary{cursor:pointer;padding:12px 14px;font-size:14px;",
    "  font-weight:700;list-style:none;display:flex;gap:9px;align-items:baseline}",
    ".scmod>summary::-webkit-details-marker{display:none}",
    ".scmod>summary::before{content:'▸';color:var(--accent,#ffb020)}",
    ".scmod[open]>summary::before{content:'▾'}",
    ".scmod-b{padding:0 14px 14px}",
    ".sclesson{border-top:1px solid var(--line,#2a2a2a);padding:13px 0}",
    ".sclesson h4{margin:0 0 6px;font-size:13.5px;font-weight:750}",
    ".sclesson p{margin:0 0 8px;font-size:13px;line-height:1.75;",
    "  color:var(--body,#ccc)}",
    ".scmini{font-size:11px;font-weight:700;letter-spacing:.5px;",
    "  text-transform:uppercase;color:var(--dim,#666);margin:10px 0 4px}",

    /* self-tests */
    ".scquiz{border:1px solid var(--line,#2a2a2a);border-radius:10px;",
    "  padding:12px;margin-top:11px;background:var(--panel2,#0f0f0f)}",
    ".scquiz .q{font-size:13px;font-weight:650;margin-bottom:9px;line-height:1.55}",
    ".scopt{display:block;width:100%;text-align:left;font-size:12.5px;",
    "  padding:8px 11px;border-radius:8px;margin-bottom:5px;cursor:pointer;",
    "  border:1px solid var(--line,#2a2a2a);background:transparent;",
    "  color:inherit;line-height:1.5}",
    ".scopt:hover{border-color:var(--accent,#ffb020)}",
    ".scopt.right{border-color:#3fae6a;background:rgba(63,174,106,.13)}",
    ".scopt.wrong{border-color:#d9534f;background:rgba(217,83,79,.12)}",
    ".scwhy{font-size:12.5px;line-height:1.65;margin-top:7px;",
    "  color:var(--body,#ccc)}",
    ".scscore{font-size:12px;font-weight:700;color:var(--muted,#8a8a8a);",
    "  margin-top:9px}",

    /* where a 3D model would go */
    ".scscene{border:1px solid var(--line,#2a2a2a);border-radius:10px;",
    "  overflow:hidden;background:var(--panel2,#0f0f0f);min-height:120px}",
    ".td-fail{padding:16px;font-size:12.5px;color:var(--muted,#8a8a8a);",
    "  line-height:1.6}",
    ".sc3d{border:1px dashed var(--line,#2a2a2a);border-radius:10px;",
    "  padding:12px;margin-top:10px;font-size:12.5px;line-height:1.6;",
    "  color:var(--muted,#8a8a8a)}",
    ".sc3d b{color:var(--text,#eee)}",

    ".screcent{display:flex;align-items:center;gap:10px;width:100%;",
    "  text-align:left;border:1px solid var(--line,#2a2a2a);border-radius:10px;",
    "  padding:9px 12px;margin-bottom:6px;background:transparent;color:inherit;",
    "  cursor:pointer;font-size:13px}",
    ".screcent:hover{border-color:var(--accent,#ffb020)}"
  ].join("");

  function styles() {
    if (document.getElementById("scanner-css")) return;
    var s = document.createElement("style");
    s.id = "scanner-css";
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  /* ------------------------------------------------------------------ *
   * camera
   * ------------------------------------------------------------------ */
  async function startCam() {
    SC.msg = "";
    try {
      SC.stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" }, width: { ideal: 1600 } },
        audio: false
      });
      SC.view = "cam";
    } catch (e) {
      // A laptop with no camera, or permission refused. Say which, and leave
      // the file picker working — for that person it is the whole feature,
      // not a degraded mode.
      SC.view = "idle";
      SC.msg = (e && e.name === "NotAllowedError")
        ? "The camera was blocked. Allow it in your browser settings, or choose a photo instead."
        : "No camera available here — choose a photo instead.";
    }
    paint();
  }

  function stopCam() {
    if (SC.stream) {
      SC.stream.getTracks().forEach(function (t) { t.stop(); });
      SC.stream = null;
    }
  }

  function grab() {
    var v = $("#scVid");
    if (!v || !v.videoWidth) return;
    // Crop to the guide. The percentages match .scframe above.
    var W = v.videoWidth, H = v.videoHeight;
    var cv = document.createElement("canvas");
    cv.width = Math.round(W * 0.84);
    cv.height = Math.round(H * 0.42);
    cv.getContext("2d").drawImage(v, W * 0.08, H * 0.29, W * 0.84, H * 0.42,
      0, 0, cv.width, cv.height);
    cv.toBlob(function (b) {
      if (b) hold(new File([b], "scan.jpg", { type: "image/jpeg" }));
    }, "image/jpeg", 0.86);
  }

  function hold(file) {
    SC.shotFile = file;
    if (SC.shot) URL.revokeObjectURL(SC.shot);
    SC.shot = URL.createObjectURL(file);
    SC.msg = "";
    stopCam();               // not needed while they look at what they took
    SC.view = "shot";
    paint();
  }

  function retake() {
    if (SC.shot) URL.revokeObjectURL(SC.shot);
    SC.shot = null; SC.shotFile = null; SC.msg = "";
    startCam();
  }

  async function send() {
    if (!SC.shotFile) return;
    SC.view = "busy"; SC.msg = ""; SC.scan = null; SC.course = null;
    SC.quiz = {}; paint();
    var fd = new FormData();
    fd.append("image", SC.shotFile);
    try {
      var r = await api.upload("/api/scan", fd);
      SC.scan = r.scan;
      SC.key = r.key || "";
      if (typeof recordAsk === "function" && r.scan && r.scan.readable) {
        recordAsk(r.scan.subject || (r.scan.read || "").slice(0, 60), "scan");
      }
      if (!r.scan.readable) {
        SC.msg = r.scan.next ||
          "That did not come out readable. Try again with more light.";
      }
      loadRecent();
    } catch (e) {
      SC.msg = e.message || "Could not read that photo.";
    }
    stopCam();
    if (SC.shot) URL.revokeObjectURL(SC.shot);
    SC.shot = null; SC.shotFile = null;
    SC.view = SC.scan && SC.scan.readable ? "answer" : "idle";
    paint();
  }

  async function loadRecent() {
    try {
      SC.recent = (await api.get("/api/scan/recent")).recent || [];
    } catch (e) { SC.recent = []; }
    paint();
  }

  async function reopen(key) {
    SC.view = "busy"; SC.course = null; SC.quiz = {}; paint();
    try {
      var r = await api.get("/api/scan/" + encodeURIComponent(key));
      SC.scan = r.scan; SC.key = r.key; SC.view = "answer";
    } catch (e) {
      SC.msg = e.message || "Could not reopen that."; SC.view = "idle";
    }
    paint();
  }

  /* ------------------------------------------------------------------ *
   * the course offer
   * ------------------------------------------------------------------ */
  async function buildCourse() {
    if (!SC.scan) return;
    SC.courseBusy = true; SC.msg = ""; paint();
    // A course takes many seconds to build and usually contains a 3D lesson.
    // Fetching the diagram library now means it is ready when the reader
    // reaches that lesson, rather than starting the download at the moment
    // they are looking at the space where the diagram should be.
    if (window.Three3D && window.Three3D.preload) window.Three3D.preload();
    try {
      var r = await api.post("/api/course", {
        topic: SC.scan.subject || SC.scan.read.slice(0, 120),
        level: SC.depth,
        context: SC.scan.read.slice(0, 1000)
      });
      SC.course = r.course;
      SC.courseTopic = SC.scan.subject || SC.scan.read.slice(0, 120);
      SC.open = { 0: true };
      indexAnswers(r.course);
      await loadCourseProgress();
    } catch (e) {
      SC.msg = e.message || "Could not build that course.";
    }
    SC.courseBusy = false;
    paint();
  }

  /* Which option is right, per question id.
   *
   * Built from the course when it arrives rather than during render, which
   * was the first attempt and did not work: the restore ran before anything
   * had been drawn, so the index was empty and nothing was ever restored. */
  function indexAnswers(course) {
    SC.answers = {};
    (course.modules || []).forEach(function (m, mi) {
      (m.lessons || []).forEach(function (l, li) {
        if (l.check) SC.answers["m" + mi + "l" + li] = l.check.answer;
      });
      (m.exam || []).forEach(function (q, qi) {
        SC.answers["m" + mi + "e" + qi] = q.answer;
      });
    });
  }

  /* What this person has already answered on this course. Only the ones
     they got right count as done — the server decides that, and this only
     restores what it recorded. */
  async function loadCourseProgress() {
    try {
      var r = await api.get("/api/course/progress?topic=" +
        encodeURIComponent(SC.courseTopic || ""));
      Object.keys(r.answered || {}).forEach(function (id) {
        // The chosen option is not stored, only whether it was right, so a
        // restored answer shows as the correct one when it was and as the
        // first wrong option when it was not. The score is what matters and
        // the score is exact.
        var right = (SC.answers || {})[id];
        if (right === undefined) return;
        SC.quiz[id] = r.answered[id].correct ? right
          : (right === 0 ? 1 : 0);
      });
    } catch (e) { /* a missing history is not an error */ }
  }

  /* ------------------------------------------------------------------ *
   * render
   * ------------------------------------------------------------------ */
  function paint() {
    styles();
    var host = $("#main");
    if (!host) return;
    // Every repaint replaces the elements the renderers were drawing into,
    // so their contexts have to go with them or they leak one per repaint.
    dropScenes();

    host.innerHTML =
      '<div class="scwrap">' +
      '<h2 style="margin:0 0 4px">📷 Scan a problem</h2>' +
      '<p style="font-size:13px;color:var(--muted);margin:0 0 16px;' +
      'max-width:58ch">Photograph anything you are stuck on — a question, a ' +
      'derivation, a snippet of code, an error on a screen, a page of notes. ' +
      'Any subject. You get it read back, worked through step by step, and ' +
      'the answer last.</p>' +
      stageHtml() +
      (SC.msg ? '<div class="scans" style="border-color:#d9534f;' +
        'background:rgba(217,83,79,.10)">' + esc(SC.msg) + "</div>" : "") +
      (SC.scan && SC.scan.readable ? answerHtml() : "") +
      (SC.course ? courseHtml() : "") +
      recentHtml() +
      "</div>";

    var v = $("#scVid");
    if (v && SC.stream) { v.srcObject = SC.stream; v.play().catch(function () {}); }
    wire();
    mountScenes();
  }

  function stageHtml() {
    var body;
    if (SC.view === "cam") {
      body = '<video id="scVid" playsinline muted></video>' +
        '<div class="scframe"></div>';
    } else if (SC.view === "shot") {
      body = '<img src="' + SC.shot + '" alt="the photo you just took">';
    } else if (SC.view === "busy") {
      body = '<div class="scidle">Reading it…</div>';
    } else if (SC.view === "answer") {
      return "";               // the answer replaces the viewfinder entirely
    } else {
      body = '<div class="scidle">Point your camera at the problem, or ' +
        "choose a photo you already have.</div>";
    }

    var bar;
    if (SC.view === "cam") {
      bar = '<button class="btn" id="scShoot">Take the photo</button>' +
        '<button class="btn ghost" id="scCancel">Cancel</button>';
    } else if (SC.view === "shot") {
      bar = '<button class="btn" id="scUse">Use this photo</button>' +
        '<button class="btn ghost" id="scRetake">Retake</button>';
    } else if (SC.view === "busy") {
      bar = "";
    } else {
      bar = '<button class="btn" id="scOpen">Open the camera</button>' +
        '<button class="btn ghost" id="scPick">Choose a photo</button>' +
        '<input type="file" id="scFile" accept="image/*" hidden>';
    }
    return '<div class="scstage">' + body + "</div>" +
      '<div class="scbar">' + bar + "</div>";
  }

  /* Maths written as maths. mathText comes from the main page; if it is ever
     not there, fall back to the escaped text rather than failing to render. */
  function mt(x) {
    var t = esc(x);
    try { return window.mathText ? window.mathText(t) : t; }
    catch (e) { return t; }
  }

  function answerHtml() {
    var s = SC.scan;
    var kindName = { worked: "Worked problem", code: "Code", error: "Error",
      concept: "Concept", other: "Scan" }[s.kind] || "Scan";
    var h = '<div style="margin-top:4px">' +
      '<span class="sctag">' + esc(kindName) + "</span>" +
      (s.subject ? '<span class="sctag">' + esc(s.subject) + "</span>" : "") +
      (s.lang ? '<span class="sctag">' + esc(s.lang) + "</span>" : "") +
      "</div>";

    // What they asked, shown back before anything else — so a misread is
    // obvious immediately rather than after they have trusted the answer.
    h += '<div class="scmini">What you asked</div>' +
      '<div class="scread">' + mt(s.read) + "</div>";

    h += '<div class="scmini" style="margin-top:14px">Worked through</div>';
    s.steps.forEach(function (st, i) {
      h += '<div class="scstep"><div class="scstep-n">' + (i + 1) + "</div><div>" +
        (st.heading ? "<h4>" + esc(st.heading) + "</h4>" : "") +
        (st.teach ? "<p>" + mt(st.teach) + "</p>" : "") +
        (st.working ? '<div class="scwork">' + mt(st.working) + "</div>" : "") +
        "</div></div>";
    });

    if (s.answer) {
      h += '<div class="scans"><b>Answer</b><br>' + mt(s.answer) + "</div>";
    }
    /* Substitution disagreed with the stated answer. Said plainly, and next
       to the answer rather than at the bottom, because the moment that
       matters is the one just before somebody writes it down. */
    /* Substitution or a constant check disagreed with what is written above.
       Said plainly, and next to the answer rather than at the bottom, because
       the moment that matters is the one just before somebody writes it down.
       A list, not a sentence: there can be more than one, and joining them
       with commas ran two different problems into a single unreadable line. */
    if (s.findings && s.findings.length) {
      h += '<div class="scwarn"><b>\u26a0 Checked automatically \u2014 these ' +
        "did not add up:</b>" +
        s.findings.map(function (f) { return "<div>\u2022 " + mt(f) + "</div>"; })
          .join("") +
        "<i>This answer was not saved for anyone else.</i></div>";
    }
    if (s.next) {
      h += '<p style="font-size:12.5px;color:var(--muted);margin-top:9px">' +
        esc(s.next) + "</p>";
    }

    h += '<div class="scbar"><button class="btn ghost sm" id="scAgain">' +
      "Scan another</button>" +
      '<button class="btn ghost sm" id="scPdf">⬇ Download PDF</button>' +
      '<button class="btn ghost sm" id="scSave">⬇ Plain text</button>' +
      '<span class="sctag" style="background:rgba(63,174,106,.14);' +
      'color:#3fae6a">✓ Saved to your account</span></div>';

    // The offer. This is the point of the whole page: an answer solves today,
    // a course means they are not back here next week with the same thing.
    if (!SC.course) {
      var what = s.subject || "this";
      h += '<div class="scoffer"><b>Shall I teach you ' + esc(what) +
        " properly?</b>" +
        "<p>Not another answer — a full course built around what you just got " +
        "stuck on, in order, with a worked example, a self-test after every " +
        "lesson and an exam at the end of each part, so you can check you " +
        "actually have it.</p>" +
        // Depth, chosen rather than guessed. The same topic is a different
        // course for someone meeting it in second year and someone who needs
        // it for a thesis, and getting that wrong wastes the whole thing —
        // too shallow is useless, too deep is unreadable.
        '<div class="scmini" style="margin-top:0">Take me to</div>' +
        '<div class="sqlchips" style="margin-bottom:11px">' +
        DEPTHS.map(function (d) {
          return '<button class="sqlchip' + (SC.depth === d[0] ? " on" : "") +
            '" data-depth="' + d[0] + '">' + esc(d[1]) + "</button>";
        }).join("") + "</div>" +
        '<button class="btn" id="scCourse"' + (SC.courseBusy ? " disabled" : "") +
        ">" + (SC.courseBusy ? "Building your course…" : "Yes, build it") +
        "</button></div>";
    }
    return h;
  }

  function courseHtml() {
    var c = SC.course;
    var lessons = c.modules.reduce(function (a, m) {
      return a + m.lessons.length;
    }, 0);
    var h = '<div class="sccourse"><div class="scmini">Your course</div>' +
      '<h3 style="margin:0 0 5px">' + esc(c.title) + "</h3>" +
      '<p style="font-size:13px;line-height:1.7;color:var(--body);margin:0 0 8px">' +
      esc(c.why) + "</p>" +
      '<div style="font-size:12px;color:var(--muted);margin-bottom:12px">' +
      c.modules.length + " parts · " + lessons + " lessons · about " +
      c.hours + " hour" + (c.hours === 1 ? "" : "s") +
      (c.prereq.length ? " · assumes you know " + esc(c.prereq.join(", ")) : "") +
      "</div>";

    c.modules.forEach(function (m, mi) {
      h += '<details class="scmod" data-mod="' + mi + '"' +
        (SC.open[mi] ? " open" : "") + "><summary><span>" +
        esc(m.name) + "</span></summary><div class=\"scmod-b\">" +
        (m.goal ? '<p style="font-size:12.5px;color:var(--muted);margin:0">' +
          esc(m.goal) + "</p>" : "");

      m.lessons.forEach(function (l, li) {
        h += '<div class="sclesson"><h4>' + esc(l.name) + "</h4>" +
          "<p>" + esc(l.teach) + "</p>" +
          (l.example ? '<div class="scmini">Example</div><div class="scwork">' +
            esc(l.example) + "</div>" : "") +
          (l.scene ? sceneHtml(mi, li, l.scene) : "") +
          (l.visual && !l.scene ? visualHtml(l.visual) : "") +
          (l.practice ? '<div class="scmini">Your turn</div>' +
            '<p style="margin:0">' + esc(l.practice) + "</p>" : "") +
          (l.trap ? '<div class="scmini">Where people go wrong</div>' +
            '<p style="margin:0">' + esc(l.trap) + "</p>" : "") +
          (l.check ? quizHtml(l.check, "m" + mi + "l" + li) : "") +
          "</div>";
      });

      if ((m.exam || []).length) {
        h += '<div class="scmini" style="margin-top:14px">End-of-part exam · ' +
          m.exam.length + " questions</div>";
        m.exam.forEach(function (q, qi) {
          h += quizHtml(q, "m" + mi + "e" + qi);
        });
        h += examScoreHtml(m, mi);
      }
      h += "</div></details>";
    });

    if (c.after) {
      h += '<div class="scans" style="border-color:var(--line);' +
        'background:transparent"><b>After this</b><br>' + esc(c.after) +
        "</div>";
    }
    return h + "</div>";
  }

  function quizHtml(q, id) {
    var picked = SC.quiz[id];
    var done = picked !== undefined;
    var h = '<div class="scquiz"><div class="q">' + esc(q.q) + "</div>";
    q.options.forEach(function (o, i) {
      var cls = "";
      if (done) {
        if (i === q.answer) cls = " right";
        else if (i === picked) cls = " wrong";
      }
      h += '<button class="scopt' + cls + '" data-quiz="' + id +
        '" data-opt="' + i + '"' + (done ? " disabled" : "") + ">" +
        esc(o) + "</button>";
    });
    if (done && q.why) {
      h += '<div class="scwhy">' +
        (picked === q.answer ? "✓ " : "✗ ") + esc(q.why) + "</div>";
    }
    return h + "</div>";
  }

  function examScoreHtml(m, mi) {
    var total = m.exam.length, done = 0, right = 0;
    m.exam.forEach(function (q, qi) {
      var p = SC.quiz["m" + mi + "e" + qi];
      if (p !== undefined) { done++; if (p === q.answer) right++; }
    });
    if (!done) return "";
    return '<div class="scscore">' + right + " of " + done + " right" +
      (done < total ? " · " + (total - done) + " to go"
        : (right === total ? " — that part is solid."
          : " — worth rereading the lessons you missed.")) + "</div>";
  }

  /* Only reached when the lesson wanted 3D and the scene builders could not
     honestly draw it — an organ, a whole cell, anything organic. Saying so
     and naming what to look at beats drawing three ellipsoids and calling
     them a heart, which would teach the wrong shape. */
  function visualHtml(v) {
    if (v.want !== "3d") return "";
    return '<div class="sc3d">🧊 <b>Best seen in 3D: ' + esc(v.of) + "</b>" +
      (v.look_for ? "<br>" + esc(v.look_for) : "") + "</div>";
  }

  /* A real scene. Mounted after the HTML is in the document, and only when it
     scrolls into view: a course with nine 3D lessons would otherwise open
     nine WebGL contexts at once, and browsers cap those and start killing the
     oldest — which looks like the first diagram going randomly black. */
  function sceneHtml(mi, li, s) {
    return '<div class="sc3dbox"><div class="scmini" style="margin:10px 0 4px">' +
      esc(s.caption || "Turn it with your finger, pinch to zoom") + "</div>" +
      '<div class="scscene" data-scene="' + mi + "_" + li + '"></div></div>';
  }

  var mounted = {};

  function mountScenes() {
    if (!window.Three3D || !SC.course) return;
    document.querySelectorAll(".scscene").forEach(function (el) {
      var id = el.dataset.scene;
      if (mounted[id] || el.dataset.on) return;
      var io = new IntersectionObserver(function (es) {
        if (!es[0].isIntersecting) return;
        io.disconnect();
        el.dataset.on = "1";
        var p = id.split("_");
        var m = SC.course.modules[+p[0]];
        var l = m && m.lessons[+p[1]];
        if (!l || !l.scene) return;
        Three3D.mount(el, l.scene).then(function (d) { mounted[id] = d; });
      }, { rootMargin: "180px" });
      io.observe(el);
    });
  }

  function dropScenes() {
    Object.keys(mounted).forEach(function (k) {
      try { mounted[k](); } catch (e) {}
    });
    mounted = {};
  }

  function recentHtml() {
    if (!SC.recent.length) return "";
    return '<div class="scmini" style="margin-top:26px">Lately</div>' +
      SC.recent.slice(0, 8).map(function (r) {
        return '<button class="screcent" data-open="' + esc(r.key) + '">' +
          '<span style="flex:1;overflow:hidden;text-overflow:ellipsis;' +
          'white-space:nowrap">' + esc(r.title) + "</span>" +
          '<span style="font-size:11px;color:var(--dim)">' +
          esc(r.subject || r.kind || "") + "</span></button>";
      }).join("") +
      '<button class="btn ghost sm" id="scClear" style="margin-top:6px">' +
      "Clear these</button>";
  }

  /* ------------------------------------------------------------------ *
   * wiring
   * ------------------------------------------------------------------ */
  /* The same PDF the board produces, with the Craxle header on every page.
     A scan is the thing people most want on paper — it is homework they were
     stuck on — and it was going out as a .txt while the board next door had
     a proper export sitting there unused. */
  function pdf() {
    var s = SC.scan;
    if (!s) return;
    var steps = s.steps.map(function (st, i) {
      return (i + 1) + ". " + (st.heading ? st.heading + " — " : "") +
        (st.teach || "") + (st.working ? "\n" + st.working : "");
    });
    if (s.answer) steps.push("Answer: " + s.answer);
    if (s.next) steps.push("Next: " + s.next);
    if (typeof askPDF === "function") {
      askPDF({ q: s.read, subject: s.subject || "Scan", level: s.kind,
               title: s.subject || "Scanned problem", steps: steps,
               takeaway: s.answer || "" });
      return;
    }
    /* This module runs on the board as well, and the board has no askPDF —
       it is defined in index.html and nothing loads it there. So "Download
       PDF" quietly fell through to the plain-text export, and a teacher who
       pressed it got a .txt with no explanation. That reads as a broken
       button, which is exactly what it was.
       A print view is the honest fallback: every browser turns one into a
       PDF, and it needs nothing this page does not already have. */
    printable(s, steps);
  }

  /* Opened as a document rather than built as a file. The one thing to get
     right is that the window is opened SYNCHRONOUSLY inside the click —
     opening it after an await is a pop-up the browser blocks, silently. */
  function printable(s, steps) {
    var esc = function (t) {
      return String(t == null ? "" : t).replace(/&/g, "&amp;")
        .replace(/</g, "&lt;").replace(/>/g, "&gt;");
    };
    var w = window.open("", "_blank");
    if (!w) {
      alert("Your browser blocked the print window. Allow pop-ups for this "
        + "site, or use Plain text.");
      return;
    }
    var title = s.subject || "Scanned problem";
    w.document.write(
      "<!doctype html><meta charset=\"utf-8\"><title>" + esc(title) +
      "</title><style>" +
      "body{font:15px/1.6 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;" +
      "max-width:44rem;margin:2.5rem auto;padding:0 1.5rem;color:#111}" +
      "h1{font-size:1.5rem;margin:0 0 .2rem}" +
      ".sub{color:#666;font-size:.8rem;margin-bottom:1.6rem}" +
      "h2{font-size:.72rem;letter-spacing:.12em;text-transform:uppercase;" +
      "color:#666;margin:1.6rem 0 .4rem}" +
      "pre{white-space:pre-wrap;font:inherit;margin:0 0 1rem}" +
      ".ans{border:1px solid #cbd5c0;background:#f4f8f0;border-radius:8px;" +
      "padding:.8rem 1rem;margin-top:1rem}" +
      "footer{margin-top:2.5rem;color:#888;font-size:.72rem;" +
      "border-top:1px solid #eee;padding-top:.8rem}" +
      "@media print{body{margin:0}}</style>" +
      "<h1>" + esc(title) + "</h1>" +
      "<div class=\"sub\">Craxle — craxle.com</div>" +
      "<h2>What you asked</h2><pre>" + esc(s.read || "") + "</pre>" +
      "<h2>Worked through</h2>" +
      steps.map(function (t) { return "<pre>" + esc(t) + "</pre>"; }).join("") +
      (s.answer ? "<div class=\"ans\"><b>Answer</b><br>" + esc(s.answer) +
                  "</div>" : "") +
      "<footer>Saved from Craxle — craxle.com</footer>");
    w.document.close();
    w.focus();
    /* After the document has laid out, or the first page prints blank. */
    setTimeout(function () { try { w.print(); } catch (e) {} }, 250);
  }

  function download() {
    var s = SC.scan;
    if (!s) return;
    var L = ["Craxle — craxle.com", "", (s.subject || "Scan"), "",
      "WHAT YOU ASKED", s.read, "", "WORKED THROUGH"];
    s.steps.forEach(function (st, i) {
      L.push("", (i + 1) + ". " + (st.heading || ""));
      if (st.teach) L.push(st.teach);
      if (st.working) L.push(st.working);
    });
    if (s.answer) L.push("", "ANSWER", s.answer);
    if (s.next) L.push("", s.next);
    L.push("", "Saved from Craxle — craxle.com");
    var b = new Blob([L.join("\n")], { type: "text/plain;charset=utf-8" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(b);
    a.download = "craxle-" + (s.subject || "scan")
      .replace(/[^a-z0-9]+/gi, "-").toLowerCase().slice(0, 40) + ".txt";
    /* In the document before it is clicked. A detached anchor works in
       Chrome and does nothing at all in Firefox, which is a download button
       that silently fails on somebody else's browser and works on yours. */
    a.style.display = "none";
    document.body.appendChild(a);
    a.click();
    setTimeout(function () {
      URL.revokeObjectURL(a.href);
      if (a.parentNode) a.parentNode.removeChild(a);
    }, 4000);
  }

  function wire() {
    var m = {
      scOpen: startCam,
      scShoot: grab,
      scCancel: function () { stopCam(); SC.view = "idle"; paint(); },
      scUse: send,
      scRetake: retake,
      scAgain: function () {
        SC.scan = null; SC.course = null; SC.quiz = {}; SC.view = "idle";
        paint();
      },
      scSave: download,
      scPdf: pdf,
      scCourse: buildCourse,
      scPick: function () { var f = $("#scFile"); if (f) f.click(); },
      scClear: async function () {
        if (!confirm("Clear your recent scans? The answers stay available if " +
          "you scan the same thing again.")) return;
        try { await api.del("/api/scan/recent"); SC.recent = []; } catch (e) {}
        paint();
      }
    };
    Object.keys(m).forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.onclick = m[id];
    });

    var f = $("#scFile");
    if (f) f.onchange = function () { if (f.files[0]) hold(f.files[0]); };

    document.querySelectorAll("[data-open]").forEach(function (el) {
      el.onclick = function () { reopen(el.dataset.open); };
    });
    document.querySelectorAll("[data-quiz]").forEach(function (el) {
      el.onclick = function () {
        var id = el.dataset.quiz, pick = parseInt(el.dataset.opt, 10);
        if (SC.quiz[id] !== undefined) return;      // answered once
        SC.quiz[id] = pick;
        paint();
        // Recorded server-side, so the score survives closing the tab. Fire
        // and forget: a lost row is better than a click that appears to do
        // nothing because the network was slow.
        var right = SC.answers && SC.answers[id];
        api.post("/api/course/progress", {
          topic: SC.courseTopic || (SC.course && SC.course.title) || "course",
          lesson: id,
          correct: right !== undefined && pick === right
        }).catch(function () {});
      };
    });
    document.querySelectorAll(".scmod").forEach(function (el) {
      el.ontoggle = function () { SC.open[el.dataset.mod] = el.open; };
    });
    document.querySelectorAll("[data-depth]").forEach(function (el) {
      el.onclick = function () { SC.depth = el.dataset.depth; paint(); };
    });
  }

  window.renderScanner = function () {
    styles();
    if (SC.view === "cam") { SC.view = "idle"; stopCam(); }
    paint();
    loadRecent();
  };
  // Leaving the page with the camera still running is a battery drain and,
  // reasonably, alarming.
  window.addEventListener("hashchange", function () {
    stopCam(); dropScenes();
  });
  window.addEventListener("pagehide", stopCam);
})();
