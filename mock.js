/* Practising the interview out loud, and being marked on what you said.
 *
 * The prep sheet next door tells somebody what to say. This is where they
 * find out whether they can actually say it — which is a different skill,
 * and the one that gets tested in the room. Reading a model answer and
 * believing you could have produced it is the oldest self-deception in
 * interview preparation.
 *
 * **The microphone never leaves the machine.** Recognition is the browser's
 * own (voice.js), speech is the browser's own, and only the finished
 * transcript is posted for marking. That is a cost decision as much as a
 * privacy one: a paid speech API bills per second of somebody thinking, and
 * thinking is the most open-ended thing in this feature. An hour of practice
 * costs what a minute does.
 *
 * **Marking one answer is one model call, deliberately.** A keyword rubric
 * cannot tell "I led the migration" from "I watched the migration", and that
 * distinction is the whole of interview feedback. What is kept cheap
 * instead: the prompt is small, the reply is capped, pace and fillers are
 * counted here and handed over as fact rather than paid for, and the same
 * answer to the same question is served from cache. The cost is shown on
 * the button before it is spent, because a feature that quietly burns a
 * daily allowance is one people stop trusting.
 *
 * **Where the questions come from.** Three sources, most specific first:
 * one round of one posting, the whole posting read against the resume, or
 * the canned guide for a role family. The first two are the paid product
 * and are anchored to a real job description and a real company; the last
 * is free and is what somebody with no application in flight practises on.
 *
 * **What "past data" means here, exactly.** The company panel counts our own
 * postings and the prep sheets already written against them. It is not
 * reported interview questions off a reviews site — we do not hold those and
 * do not collect them — and the panel says so in its own words, because a
 * round list invented by a model and shown as what a company does is the one
 * failure here that would cost somebody a real interview.
 */
(function (global) {
  "use strict";

  var M = {
    /* setup → asking → answering → scoring → scored → done */
    mode: "setup",
    src: "category",        // "category" | "job" | "jd"
    jd: "", jdCompany: "", jdTitle: "",   // a posting pasted in by hand
    // The job itself, not its family. Nobody interviews for "Software
    // engineering"; they interview for Backend Engineer or BIM Coordinator,
    // and the questions for those two have almost nothing in common.
    role: "", roleQ: "", roleList: [], roleBusy: false, families: [],
    cat: "", catLabel: "",
    jobId: 0, jobTitle: "", company: "",
    round: "",              // the round being practised, "" = a mixed set
    qs: [], i: 0,           // the question set and where we are in it
    typed: false,           // typing instead of talking (or no recogniser)
    draft: "",              // the typed answer
    heard: "", live: "", secs: 0, hush: 0,
    stats: null, score: null, scoring: false, err: "",
    session: [],            // every marked answer this sitting, for the recap
    readAloud: true,
    co: null, coBusy: false,     // what we know about the company
    guide: null, guideBusy: false,
    jobs: [], jobsBusy: false,
    quota: null,                 // what marking will cost this account
    startedAt: 0
  };
  global.Mock = M;

  function repaint() {
    if (typeof renderCareers === "function") renderCareers();
  }

  /* esc() escapes & < > but not quotes, which is fine for text between tags
     and not fine inside an attribute. Company names and job titles come off
     crawled postings and round names come from a model, so a double quote in
     one of them is a question of when, not whether — and it would break out
     of the attribute it sits in. */
  function escAttr(v) { return esc(v).replace(/"/g, "&quot;"); }

  function canTalk() {
    return !!(global.Voice && global.Voice.supported());
  }

  /* ---- the question set -------------------------------------------- */
  /* Flattened out of whatever the prep endpoint returned, so the trainer
     below does not care which of the three shapes it came from. */
  function fromGuide(data) {
    var out = [];
    if (!data) return out;

    // One round of one posting: the deepest source, with a real model answer.
    if (data.round && data.round.questions) {
      data.round.questions.forEach(function (q) {
        if (q && q.q) out.push({ q: q.q, why: q.why || "",
                                 model: q.answer || "",
                                 round: data.round.round || M.round });
      });
      return out;
    }
    // The whole posting, read against the resume.
    var g = data.guide;
    if (g && g.rounds && g.rounds.length) {
      g.rounds.forEach(function (r) {
        if (M.round && r.name !== M.round) return;
        (r.questions || []).forEach(function (q) {
          if (q && q.q) out.push({ q: q.q, why: q.why || "",
                                   model: q.answer_with || "",
                                   round: r.name || "" });
        });
      });
      return out;
    }
    // The canned guide for a role family. Strings, no model answer — the
    // marker still has the question and what it is testing is implicit.
    (data.questions || []).forEach(function (q) {
      if (typeof q === "string" && q.trim()) {
        out.push({ q: q.trim(), why: "", model: "", round: "" });
      }
    });
    return out;
  }

  /* The roles, searched or listed by family. Free and instant -- a
     catalogue and a GROUP BY, no model call -- so it can run on every
     keystroke without anybody paying for browsing. */
  M.loadRoles = async function () {
    M.roleBusy = true; repaint();
    try {
      var p = new URLSearchParams({ limit: "40" });
      if (M.roleQ.trim()) p.set("q", M.roleQ.trim());
      else if (M.cat) p.set("category", M.cat);
      var d = await api.get("/api/interview/roles?" + p);
      M.roleList = d.roles || [];
      M.families = d.families || M.families;
    } catch (e) {
      M.roleList = [];
    }
    M.roleBusy = false;
    repaint();
  };

  M.loadQuestions = async function () {
    M.guideBusy = true; M.err = ""; repaint();
    try {
      // A pasted posting is a POST, because a job description is longer
      // than a query string should carry and this is the one somebody
      // actually has an interview for.
      if (M.src === "jd") {
        var data0 = await api.post("/api/interview/jd", {
          jd: M.jd, company: M.jdCompany, title: M.jdTitle });
        M.guide = data0;
        M.qs = fromGuide(data0);
        if (!M.qs.length) {
          M.err = "No questions came back for that description.";
        }
        M.guideBusy = false;
        return repaint();
      }
      // A named job gets questions written for that job, cached on the
      // title alone -- so the first person to practise for it pays and
      // everybody after them gets it free, for ever.
      if (M.src === "category" && M.role) {
        var dr = await api.post("/api/interview/role", { role: M.role });
        M.guide = dr;
        M.qs = fromGuide(dr);
        if (!M.qs.length) M.err = "No questions came back for that job.";
        M.guideBusy = false;
        return repaint();
      }
      var p = new URLSearchParams();
      if (M.src === "job" && M.jobId) {
        p.set("job_id", String(M.jobId));
        if (M.round) p.set("round", M.round);
      } else if (M.cat) {
        p.set("category", M.cat);
      }
      var data = await api.get("/api/interview/guide?" + p);
      M.guide = data;
      M.qs = fromGuide(data);
      if (!M.qs.length) {
        M.err = "No questions came back for that. Try another round, or " +
                "practise the role family instead.";
      }
    } catch (e) {
      M.err = e.message || "Could not load the questions.";
      M.qs = [];
    }
    M.guideBusy = false;
    repaint();
  };

  /* ---- the company, from what we actually hold ---------------------- */
  M.loadCompany = async function () {
    if (!M.jobId && !M.company) return;
    M.coBusy = true; repaint();
    try {
      var p = new URLSearchParams();
      if (M.jobId) p.set("job_id", String(M.jobId));
      else p.set("company", M.company);
      M.co = await api.get("/api/interview/company?" + p);
    } catch (e) {
      M.co = { error: e.message || "Could not read the company." };
    }
    M.coBusy = false;
    repaint();
  };

  /* The jobs worth practising against: the ones this person is actually in
     the middle of. Applying and then practising for something else is not a
     thing anybody does. */
  M.loadJobs = async function () {
    M.jobsBusy = true; repaint();
    try {
      var t = await api.get("/api/jobs/tracked");
      // In pipeline order, not tracker order: somebody with an interview
      // booked is practising for that one, and it should not be below six
      // jobs they merely saved.
      var rank = { interviewing: 0, applied: 1, saved: 2, viewed: 3 };
      M.jobs = ((t && t.tracks) || [])
        .filter(function (r) {
          return r.job_id && rank[r.status] !== undefined;
        })
        .sort(function (a, b) { return rank[a.status] - rank[b.status]; })
        .map(function (r) {
          return { id: r.job_id, title: r.title || "", company: r.company || "",
                   status: r.status };
        })
        .slice(0, 25);
    } catch (e) {
      M.jobs = [];
    }
    M.jobsBusy = false;
    repaint();
  };

  /* ---- running one question ----------------------------------------- */
  M.begin = async function () {
    // Somebody who typed a job we do not list still gets that job's
    // questions. Refusing because it is not in the catalogue would be
    // refusing the one person who knows exactly what they want.
    if (M.src === "category" && !M.role && M.roleQ.trim().length >= 3) {
      M.role = M.roleQ.trim();
    }
    await M.loadQuestions();
    if (!M.qs.length) return;
    M.i = 0; M.session = []; M.startedAt = Date.now();
    M.ask();
  };

  M.ask = function () {
    M.mode = "asking";
    M.heard = ""; M.live = ""; M.secs = 0; M.hush = 0;
    M.stats = null; M.score = null; M.err = ""; M.draft = "";
    repaint();
    var cur = M.qs[M.i];
    if (M.readAloud && cur && global.Voice && global.Voice.speak) {
      global.Voice.speak(cur.q).then(function () {
        // Straight into listening once the question has been read, the way a
        // real interviewer stops talking and looks at you. Only if nothing
        // has moved on in the meantime.
        if (M.mode === "asking" && !M.typed) M.answer();
      });
    }
  };

  M.answer = function () {
    var cur = M.qs[M.i];
    if (!cur) return;
    if (M.typed || !canTalk()) {
      M.typed = true;
      M.mode = "answering";
      return repaint();
    }
    M.mode = "answering";
    M.heard = ""; M.live = ""; M.secs = 0; M.hush = 0;
    global.Voice.dictate({
      onChange: function (s) {
        M.heard = s.text || "";
        M.live = s.live || "";
        M.secs = s.seconds || 0;
        M.hush = s.hush || 0;
        if (s.error) M.err = s.error;
        paintLive();
      },
      // Zero: only the button ends it. Somebody mid-thought has not finished
      // answering, and a recogniser that decides otherwise is the reason
      // practising against most tools feels like being interrupted.
      maxHush: 0
    });
    repaint();
  };

  /* The live panel repaints itself rather than the whole page — re-rendering
     careers on every interim word would fight the browser for the main
     thread while somebody is talking. */
  function paintLive() {
    var box = document.getElementById("mkLive");
    if (box) {
      box.innerHTML = liveInnerHTML();
      box.scrollTop = box.scrollHeight;
    }
    var m = document.getElementById("mkMeter");
    if (m) m.innerHTML = meterHTML();
  }

  M.stopAnswer = async function () {
    var cur = M.qs[M.i];
    if (!cur) return;
    var stats;
    if (M.typed) {
      var t = (document.getElementById("mkType") || {}).value || M.draft || "";
      stats = global.Voice && global.Voice.answerStats
        ? global.Voice.answerStats(t, Math.max(1, (Date.now() - (M.startedAt || Date.now())) / 1000))
        : { text: t, words: t.trim() ? t.trim().split(/\s+/).length : 0,
            seconds: 0, wpm: 0, fillers: 0 };
      // Typed, so pace is not a real measurement and must not be marked as
      // one. Reporting 0 words per minute as delivery would be a lie about
      // something the candidate never did.
      stats.seconds = 0; stats.wpm = 0;
    } else {
      stats = global.Voice.endDictation() || { text: M.heard };
    }
    M.stats = stats;
    M.heard = stats.text || "";
    await M.mark();
  };

  M.mark = async function () {
    var cur = M.qs[M.i];
    if (!cur) return;
    M.mode = "scoring"; M.scoring = true; M.err = ""; repaint();
    try {
      M.score = await api.post("/api/interview/mock", {
        question: cur.q,
        answer: M.heard,
        why: cur.why || "",
        model_answer: cur.model || "",
        job_id: M.src === "job" ? M.jobId : 0,
        jd: M.src === "jd" ? M.jd : "",
        company: M.src === "jd" ? M.jdCompany : "",
        category: M.cat || "",
        company: M.src === "jd" ? M.jdCompany : M.company,
        round: cur.round || M.round || "",
        seconds: (M.stats && M.stats.seconds) || 0,
        words: (M.stats && M.stats.words) || 0,
        fillers: (M.stats && M.stats.fillers) || 0
      });
      M.session.push({
        q: cur.q, round: cur.round || "", answer: M.heard,
        // The guide's own answer travels with the entry, so the recap PDF
        // still has something to show for a question that was marked too
        // short to score.
        model: cur.model || "",
        stats: M.stats || null, score: M.score
      });
    } catch (e) {
      M.err = e.message || "Could not mark that.";
      M.score = null;
    }
    M.scoring = false;
    M.mode = M.score ? "scored" : "answering";
    repaint();
    // Hearing the better answer is most of the value — reading it and
    // thinking "yes, obviously" is not the same as hearing how it sounds at
    // the pace you would have to say it.
    var say = M.score && (M.score.model_answer || (cur && cur.model));
    if (M.score && M.readAloud && say && global.Voice.speak) {
      global.Voice.speak(say);
    }
  };

  M.next = function () {
    if (global.Voice && global.Voice.hushNow) global.Voice.hushNow();
    if (M.i + 1 >= M.qs.length) { M.mode = "done"; return repaint(); }
    M.i += 1;
    M.ask();
  };

  M.quit = function () {
    if (global.Voice) {
      if (global.Voice.dictating && global.Voice.dictating()) global.Voice.endDictation();
      if (global.Voice.hushNow) global.Voice.hushNow();
    }
    M.mode = M.session.length ? "done" : "setup";
    repaint();
  };

  M.restart = function () {
    M.mode = "setup"; M.qs = []; M.i = 0; M.session = [];
    M.score = null; M.stats = null; M.heard = ""; M.err = "";
    repaint();
  };

  /* ---- the recap, as a PDF ------------------------------------------ */
  /* Everything that was said and everything it was marked at, in one file.
     The point of a debrief is to reread it the night before, and a scorecard
     that only exists inside a tab is gone the moment the tab is. */
  M.pdf = async function () {
    if (!M.session.length) return;
    try {
      await ensureJsPDF();
    } catch (e) {
      if (typeof toast === "function") toast("Could not load the PDF tool.");
      return;
    }
    var jsPDF = window.jspdf.jsPDF;
    var doc = new jsPDF({ unit: "pt", format: "a4" });
    var M0 = 48, W = doc.internal.pageSize.getWidth() - M0 * 2;
    var H = doc.internal.pageSize.getHeight();
    var y = 62;                       // clears the craxle.com header band
    var safe = pdfSafe || function (s) { return String(s == null ? "" : s); };

    function room(h) { if (y + (h || 0) > H - 46) { doc.addPage(); y = 62; } }
    function write(t, size, opt) {
      opt = opt || {};
      doc.setFont("helvetica", opt.bold ? "bold" : "normal");
      doc.setFontSize(size);
      doc.setTextColor(opt.color || "#1a1a1a");
      doc.splitTextToSize(safe(t), opt.w || W).forEach(function (line) {
        room(size * 1.15);
        doc.text(line, opt.x || M0, y);
        y += size * 1.4;
      });
    }
    function rule() {
      room(10); doc.setDrawColor(43, 58, 91); doc.setLineWidth(1.1);
      doc.line(M0, y, M0 + W, y); y += 12;
    }

    var scored = M.session.filter(function (s) { return s.score; });
    var avg = scored.length
      ? Math.round(scored.reduce(function (a, s) { return a + (s.score.score || 0); }, 0) / scored.length)
      : 0;

    write("Mock interview — what you said and how it marked", 17, { bold: true, color: "#2b3a5b" });
    var head = M.src === "job" && M.jobTitle
      ? M.jobTitle + (M.company ? " · " + M.company : "")
      : (M.catLabel || "General interview practice");
    write(head + (M.round ? "  ·  " + M.round + " round" : ""), 10.5, { color: "#555" });
    write(new Date().toLocaleString() + "   ·   " + M.session.length +
          " question" + (M.session.length === 1 ? "" : "s") +
          "   ·   average " + avg + "/100", 9.5, { color: "#777" });
    y += 6; rule();

    M.session.forEach(function (s, n) {
      var sc = s.score || {};
      room(40);
      write((n + 1) + ". " + s.q, 12.5, { bold: true, color: "#2b3a5b" });
      write("Marked " + (sc.score || 0) + "/100" +
            (s.stats && s.stats.seconds
              ? "   ·   " + s.stats.seconds + "s, " + s.stats.words + " words, " +
                s.stats.wpm + " wpm, " + s.stats.fillers + " fillers"
              : (s.stats ? "   ·   typed, " + s.stats.words + " words" : "")),
            9.5, { color: "#777" });
      y += 3;
      if (sc.verdict) write(sc.verdict, 10.5, { bold: true });
      if (s.answer) {
        y += 3;
        write("You said:", 9.5, { bold: true, color: "#555" });
        write(s.answer, 9.5, { color: "#444", x: M0 + 10, w: W - 10 });
      }
      (sc.covered || []).forEach(function (c) { write("+  " + c, 9.5, { color: "#1d6b3f", x: M0 + 10, w: W - 10 }); });
      (sc.missed || []).forEach(function (c) { write("–  " + c, 9.5, { color: "#9a3412", x: M0 + 10, w: W - 10 }); });
      if (sc.structure) write("Shape: " + sc.structure, 9.5, { color: "#444" });
      if (sc.delivery) write("Delivery: " + sc.delivery, 9.5, { color: "#444" });
      var modelText = sc.model_answer || s.model || "";
      if (modelText) {
        y += 3;
        write("Say it like this:", 9.5, { bold: true, color: "#2b3a5b" });
        write(modelText, 10, { color: "#1a1a1a", x: M0 + 10, w: W - 10 });
      }
      if (sc.followup) write("They would then ask: " + sc.followup, 9.5, { color: "#555" });
      y += 10; rule();
    });

    // Stamped on every page at the end rather than as each page is started:
    // pages are added from inside room() whenever the text runs off the
    // bottom, so there is no single place that knows a page has begun.
    // A recap gets reread the night before an interview and forwarded to
    // people; it should say where it came from on every sheet.
    var pages = doc.internal.getNumberOfPages();
    for (var pn = 1; pn <= pages; pn++) {
      doc.setPage(pn);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(8.5);
      doc.setTextColor("#2b3a5b");
      // Once per page, and once only. A name repeated in a header AND a
      // footer on every sheet stops reading as a source and starts reading
      // as an advertisement, which is not what somebody wants in their hand
      // the night before an interview.
      doc.text("craxle.com", M0, 30);
      doc.setFont("helvetica", "normal");
      doc.setTextColor("#8a8a8a");
      doc.text("Mock interview recap", M0 + 62, 30);
      doc.text("Page " + pn + " of " + pages, M0 + W, 30, { align: "right" });
      doc.setDrawColor(210, 214, 222);
      doc.setLineWidth(0.6);
      doc.line(M0, 36, M0 + W, 36);
    }

    var name = (M.src === "job" && M.jobTitle ? M.jobTitle : (M.catLabel || "interview"));
    doc.save(name.replace(/[^a-z0-9]+/gi, "-").toLowerCase().slice(0, 40) +
             "-mock-interview.pdf");
  };

  /* ---- painting ------------------------------------------------------ */
  function scoreColour(n) {
    if (n >= 80) return "var(--ok)";
    if (n >= 50) return "var(--accent)";
    return "#e05a5a";
  }

  function meterHTML() {
    var st = global.Voice && global.Voice.answerStats
      ? global.Voice.answerStats(M.heard + " " + M.live, M.secs) : null;
    if (!st) return "";
    // Pace only once there is enough of it to mean anything. A number that
    // reads 220 wpm off four words is noise being shown as feedback.
    var pace = (st.words >= 25 && M.secs >= 8) ? st.wpm + " wpm" : "";
    return '<span>' + M.secs + 's</span>' +
      '<span>' + st.words + ' words</span>' +
      (pace ? '<span>' + pace + '</span>' : '') +
      (st.fillers ? '<span style="color:var(--warn)">' + st.fillers + ' filler' +
        (st.fillers === 1 ? '' : 's') + '</span>' : '') +
      (M.hush >= 3 ? '<span style="color:var(--dim)">still listening…</span>' : '');
  }

  function liveInnerHTML() {
    if (!M.heard && !M.live) {
      return '<span style="color:var(--dim)">Listening. Take your time — a ' +
             'pause will not end your answer.</span>';
    }
    return esc(M.heard) +
      (M.live ? ' <span style="color:var(--dim)">' + esc(M.live) + '</span>' : '');
  }

  function companyHTML() {
    if (M.coBusy) return '<div style="font-size:12.5px;color:var(--dim)">Reading what we hold on them…</div>';
    var c = M.co;
    if (!c || c.error) return "";
    var bits = [];
    if (c.rounds && c.rounds.length) {
      bits.push('<div class="eyebrow" style="margin:10px 0 4px">Rounds seen in prep for this company</div>' +
        '<div class="ask-chips">' + c.rounds.map(function (r) {
          return '<button class="ask-chip ' + (M.round === r.name ? "on" : "") +
            '" data-mkround="' + escAttr(r.name) + '">' + esc(r.name) +
            ' <b style="opacity:.7">' + r.n + '</b></button>';
        }).join("") + '</div>');
    }
    if (c.history && c.history.length) {
      bits.push('<div class="eyebrow" style="margin:10px 0 4px">Your history with them</div>' +
        '<div style="font-size:12.5px;color:var(--body);line-height:1.7">' +
        c.history.map(function (h) {
          return esc(h.title) + ' — <b>' + esc(h.label) + '</b>' +
            (h.when ? ' <span style="color:var(--dim)">' + esc(h.when) + '</span>' : '');
        }).join("<br>") + '</div>');
    }
    return '<div class="card" style="margin-bottom:12px">' +
      '<div class="row" style="gap:8px;align-items:baseline;flex-wrap:wrap">' +
      '<b style="font-size:15px">' + esc(c.company || "") + '</b>' +
      '<span style="font-size:12.5px;color:var(--muted)">' + (c.openings || 0) +
      ' open role' + (c.openings === 1 ? '' : 's') + ' on the board</span></div>' +
      bits.join("") +
      '<div style="font-size:11px;color:var(--dim);margin-top:10px;line-height:1.5">' +
      esc(c.basis || "") + '</div></div>';
  }

  /* Families, then the jobs inside one, then a search across all of them.
     Six families was a shelf; this is what is on it. Board titles carry the
     number of openings, because "Data Engineer (36 open)" is a different
     suggestion from one with none. */
  function rolePickerHTML() {
    var fams = (M.families || []).slice().sort(function (a, b) {
      return (b.n || 0) - (a.n || 0);
    });
    var chips = fams.map(function (f) {
      return '<button class="ask-chip ' + (M.cat === f.id ? "on" : "") +
        '" data-mkcat="' + escAttr(f.id) + '" data-mklabel="' +
        escAttr(f.label) + '">' + esc(f.label) + '</button>';
    }).join("");

    // Nothing picked and nothing typed: show the fields only. A list of
    // every role in the catalogue, ordered by how short its name is, is not
    // a starting point -- it opened on "Chef, SDET, Rider, Driver".
    var list = (!M.cat && !M.roleQ.trim())
      ? '<div style="font-size:12.5px;color:var(--dim);padding:6px 0">' +
        'Pick a field, or search for the job by name.</div>'
      : M.roleBusy
      ? '<div style="font-size:12.5px;color:var(--dim);padding:6px 0">Looking…</div>'
      : (M.roleList.length
        ? '<div class="ask-chips" style="margin-top:8px">' +
          M.roleList.map(function (r) {
            return '<button class="ask-chip ' +
              (M.role === r.role ? "on" : "") + '" data-mkrole="' +
              escAttr(r.role) + '">' + esc(r.role) +
              (r.openings ? ' <b style="opacity:.7">' + r.openings +
                ' open</b>' : "") + "</button>";
          }).join("") + "</div>"
        : (M.roleQ.trim()
          ? '<div style="font-size:12.5px;color:var(--dim);padding:6px 0">' +
            'No job by that name. Type it in full and press Start — the ' +
            'questions are written from the title either way.</div>'
          : '<div style="font-size:12.5px;color:var(--dim);padding:6px 0">' +
            'Pick a field above, or search for the job by name.</div>'));

    return '<input id="mkRoleQ" placeholder="Search a job title — network ' +
      'engineer, BIM coordinator, data analyst…" value="' + escAttr(M.roleQ) +
      '" style="width:100%;margin-bottom:10px"/>' +
      (M.roleQ.trim() ? "" : '<div class="ask-chips">' + chips + "</div>") +
      list +
      '<div style="font-size:11.5px;color:var(--dim);margin-top:10px">' +
      (M.role
        ? 'Practising for <b style="color:var(--accent)">' + esc(M.role) +
          '</b>. The questions are written for this job and shared with ' +
          'everyone practising for it, so they cost nothing after the first time.'
        : 'Questions written for the job itself, not for its whole field.') +
      "</div>";
  }

  function setupHTML() {
    var talk = canTalk();
    var jobRows = M.jobsBusy
      ? '<div style="font-size:12.5px;color:var(--dim)">Loading your applications…</div>'
      : (M.jobs.length
        ? '<div class="ask-chips">' + M.jobs.map(function (j) {
            return '<button class="ask-chip ' + (M.jobId === j.id ? "on" : "") +
              '" data-mkjob="' + j.id + '" data-mktitle="' + escAttr(j.title) +
              '" data-mkco="' + escAttr(j.company) + '">' + esc(j.title) +
              ' <span style="opacity:.7">· ' + esc(j.company) + '</span></button>';
          }).join("") + '</div>'
        : '<div style="font-size:12.5px;color:var(--dim)">No saved or applied ' +
          'jobs yet. Save one from the board and it will show up here to ' +
          'practise against.</div>');

    var cats = ((M.guide && M.guide.categories) || []).map(function (c) {
      return '<button class="ask-chip ' + (M.cat === c.id ? "on" : "") +
        '" data-mkcat="' + escAttr(c.id) + '" data-mklabel="' + escAttr(c.label) + '">' +
        esc(c.label) + '</button>';
    }).join("");

    return '' +
      '<div class="card" style="margin-bottom:12px;border-color:var(--accent)">' +
        '<div class="eyebrow" style="margin:0 0 4px">Practise out loud</div>' +
        '<b style="font-size:16px">A mock interview that answers back</b>' +
        '<div style="font-size:13.5px;color:var(--body);margin-top:6px;line-height:1.6">' +
        'It asks the question out loud, listens while you answer, and marks what ' +
        'you actually said — what landed, what was missing, how it was built, and ' +
        'how it sounded. Then it shows you the answer you should have given, in ' +
        'your own words.</div>' +
        (talk
          ? '<div style="font-size:12px;color:var(--dim);margin-top:8px">Your ' +
            'microphone stays on this device. Only the text of your answer is ' +
            'sent to be marked.</div>'
          : '<div style="font-size:12.5px;color:var(--warn);margin-top:8px">This ' +
            'browser cannot listen — Chrome on desktop or Android can. You can ' +
            'still type your answers and have them marked the same way.</div>') +
      '</div>' +

      '<div class="card" style="margin-bottom:12px">' +
        '<div class="eyebrow" style="margin:0 0 6px">1 · What are you practising for?</div>' +
        '<div class="ask-chips" style="margin-bottom:10px">' +
          '<button class="ask-chip ' + (M.src === "job" ? "on" : "") + '" data-mksrc="job">' +
            'A job I have applied to</button>' +
          '<button class="ask-chip ' + (M.src === "jd" ? "on" : "") + '" data-mksrc="jd">' +
            'Paste a job description</button>' +
          '<button class="ask-chip ' + (M.src === "category" ? "on" : "") + '" data-mksrc="category">' +
            'A role in general</button>' +
        '</div>' +
        (M.src === "jd"
          ? '<textarea id="mkJd" class="pj-note" style="min-height:150px;' +
            'width:100%" placeholder="Paste the whole job description here — ' +
            'responsibilities, requirements, the lot. The questions are ' +
            'written from it.">' + esc(M.jd) + '</textarea>' +
            '<div class="row" style="gap:8px;margin-top:8px;flex-wrap:wrap">' +
            '<input id="mkJdCo" placeholder="Company (optional)" value="' +
            escAttr(M.jdCompany) + '" style="flex:1;min-width:160px"/>' +
            '<input id="mkJdTitle" placeholder="Job title (optional)" value="' +
            escAttr(M.jdTitle) + '" style="flex:1;min-width:160px"/></div>' +
            '<div style="font-size:11.5px;color:var(--dim);margin-top:8px">' +
            'For the interview you actually have. The board holds a hundred ' +
            'thousand postings and none of them is the one you are sitting ' +
            'on Thursday. Part of a paid plan.</div>'
          : M.src === "job"
          ? jobRows +
            '<div style="font-size:11.5px;color:var(--dim);margin-top:8px">Questions ' +
            'are written from that job description and your resume, so they ask ' +
            'about what this employer actually wants. Part of a paid plan.</div>'
          : rolePickerHTML()) +
      '</div>' +

      (M.src === "job" && M.jobId ? companyHTML() : "") +

      '<div class="card" style="margin-bottom:12px">' +
        '<div class="eyebrow" style="margin:0 0 6px">2 · How you want it to run</div>' +
        '<label style="display:flex;gap:8px;align-items:center;font-size:13.5px;cursor:pointer">' +
          '<input type="checkbox" data-mkaloud ' + (M.readAloud ? "checked" : "") + '> ' +
          'Read the questions out loud, and read the better answer back' +
        '</label>' +
        (talk
          ? '<label style="display:flex;gap:8px;align-items:center;font-size:13.5px;' +
            'cursor:pointer;margin-top:8px">' +
            '<input type="checkbox" data-mktyped ' + (M.typed ? "checked" : "") + '> ' +
            'Type my answers instead of speaking them</label>'
          : "") +
        '<div style="font-size:11.5px;color:var(--dim);margin-top:10px;line-height:1.5">' +
        'Marking an answer uses one AI request from your allowance — the same ' +
        'as one apply kit. Nothing is spent until you finish an answer, and ' +
        'the same answer to the same question is never charged twice.</div>' +
      '</div>' +

      /* Said here, before anybody speaks. A free plan has no AI requests at
         all, and discovering that at the end of a forty-five second answer
         is the worst moment to discover it. */
      (M.canMark() ? "" :
        '<div class="card" style="margin-bottom:12px;border-color:var(--warn)">' +
        '<b style="font-size:14px">Marking is part of a paid plan</b>' +
        '<div style="font-size:13px;color:var(--body);margin-top:5px;line-height:1.6">' +
        'Your plan has no AI requests left, so an answer cannot be marked. ' +
        'The questions, the prep sheet and hearing them read out stay free — ' +
        'you can still run the whole session, you just will not get a score ' +
        'at the end of each answer.</div></div>') +

      (M.err ? '<div class="card" style="color:#e05a5a;font-size:13px">' + esc(M.err) + '</div>' : "") +

      '<button class="btn" data-mkstart ' +
        ((M.src === "job" && !M.jobId)
          || (M.src === "category" && !M.role && !M.roleQ.trim())
          || (M.src === "jd" && M.jd.trim().length < 80) ? "disabled" : "") +
        ' style="width:100%">' +
        (M.guideBusy ? "Writing your questions…" : "Start the mock interview →") +
      '</button>';
  }

  function runHTML() {
    var cur = M.qs[M.i];
    if (!cur) return "";
    var head = '<div class="row" style="gap:8px;align-items:baseline;flex-wrap:wrap;margin-bottom:10px">' +
      '<span class="pill" style="background:var(--accent);color:#1a1205;font-weight:800">' +
      'QUESTION ' + (M.i + 1) + ' OF ' + M.qs.length + '</span>' +
      (cur.round ? '<span style="font-size:12.5px;color:var(--muted)">' + esc(cur.round) + '</span>' : "") +
      '<button class="btn ghost sm" data-mkquit style="margin-left:auto">End session</button></div>';

    var q = '<div class="card" style="margin-bottom:12px;border-color:var(--accent)">' +
      '<div style="font-size:16.5px;font-weight:650;line-height:1.45">' + esc(cur.q) + '</div>' +
      (cur.why ? '<div style="font-size:12px;color:var(--dim);margin-top:6px">They are ' +
        'testing: ' + esc(cur.why) + '</div>' : "") +
      (M.readAloud && M.mode === "asking"
        ? '<div style="font-size:12px;color:var(--muted);margin-top:8px">Reading it out…</div>' : "") +
      '</div>';

    if (M.mode === "asking") {
      return head + q + '<button class="btn" data-mkanswer style="width:100%">' +
        (M.typed ? "Type my answer" : "Start answering →") + '</button>';
    }

    if (M.mode === "answering") {
      if (M.typed) {
        return head + q +
          '<div class="card" style="margin-bottom:12px">' +
          '<textarea id="mkType" class="pj-note" style="min-height:140px;width:100%" ' +
          'placeholder="Answer as you would say it out loud.">' + esc(M.draft) + '</textarea>' +
          '</div>' +
          (M.err ? '<div class="card" style="color:#e05a5a;font-size:13px;margin-bottom:10px">' +
            esc(M.err) + '</div>' : "") +
          '<button class="btn" data-mkdone style="width:100%">Mark this answer →</button>';
      }
      return head + q +
        '<div class="card" style="margin-bottom:12px">' +
          '<div class="row" style="gap:12px;align-items:center;margin-bottom:8px">' +
            '<span style="display:inline-flex;width:10px;height:10px;border-radius:50%;' +
            'background:#e05a5a;box-shadow:0 0 0 4px rgba(224,90,90,.18)"></span>' +
            '<b style="font-size:13.5px">Listening</b>' +
            '<span id="mkMeter" class="row" style="gap:12px;margin-left:auto;' +
            'font-size:12px;color:var(--muted)">' + meterHTML() + '</span>' +
          '</div>' +
          '<div id="mkLive" style="font-size:14px;line-height:1.7;color:var(--body);' +
          'max-height:220px;overflow:auto;background:var(--panel2);border-radius:8px;' +
          'padding:12px 14px">' + liveInnerHTML() + '</div>' +
        '</div>' +
        (M.err ? '<div class="card" style="color:#e05a5a;font-size:13px;margin-bottom:10px">' +
          esc(M.err) + '</div>' : "") +
        '<button class="btn" data-mkdone style="width:100%">I have finished answering →</button>';
    }

    if (M.mode === "scoring") {
      return head + q + '<div class="card"><div style="color:var(--dim);font-size:13.5px">' +
        'Marking what you said…</div></div>';
    }

    // scored
    var s = M.score || {};
    var mine = M.stats || {};
    return head + q +
      '<div class="card" style="margin-bottom:12px">' +
        '<div class="row" style="gap:12px;align-items:center;flex-wrap:wrap">' +
          '<div style="font-size:30px;font-weight:800;color:' + scoreColour(s.score || 0) + '">' +
            (s.score || 0) + '<span style="font-size:14px;color:var(--dim)">/100</span></div>' +
          '<div style="font-size:14px;font-weight:650;flex:1;min-width:200px;line-height:1.5">' +
            esc(s.verdict || "") + '</div>' +
        '</div>' +
        (mine.seconds
          ? '<div style="font-size:12px;color:var(--dim);margin-top:8px">' +
            mine.seconds + 's · ' + mine.words + ' words · ' + mine.wpm + ' wpm · ' +
            mine.fillers + ' filler' + (mine.fillers === 1 ? '' : 's') + '</div>'
          : "") +
        (s.cached ? '<div style="font-size:11.5px;color:var(--dim);margin-top:6px">' +
          'You had already been marked on this exact answer, so this one was free.</div>' : "") +
      '</div>' +

      ((s.covered || []).length || (s.missed || []).length
        ? '<div class="card" style="margin-bottom:12px">' +
          (s.covered || []).map(function (c) {
            return '<div style="font-size:13.5px;color:var(--body);line-height:1.6;margin-bottom:6px">' +
              '<b style="color:var(--ok)">✓</b> ' + esc(c) + '</div>';
          }).join("") +
          (s.missed || []).map(function (c) {
            return '<div style="font-size:13.5px;color:var(--body);line-height:1.6;margin-bottom:6px">' +
              '<b style="color:var(--warn)">✕</b> ' + esc(c) + '</div>';
          }).join("") +
          '</div>' : "") +

      ((s.structure || s.delivery)
        ? '<div class="card" style="margin-bottom:12px">' +
          (s.structure ? '<div style="font-size:13.5px;color:var(--body);line-height:1.6">' +
            '<b style="color:var(--accent)">Shape:</b> ' + esc(s.structure) + '</div>' : "") +
          (s.delivery ? '<div style="font-size:13.5px;color:var(--body);line-height:1.6;margin-top:6px">' +
            '<b style="color:var(--accent)">Delivery:</b> ' + esc(s.delivery) + '</div>' : "") +
          '</div>' : "") +

      (M.heard ? '<div class="card" style="margin-bottom:12px">' +
        '<div class="eyebrow" style="margin:0 0 4px">What you said</div>' +
        '<div style="font-size:13px;color:var(--muted);line-height:1.65">' + esc(M.heard) + '</div>' +
        '</div>' : "") +

      /* The marker's model answer when there is one; the guide's own
         otherwise. A too-short answer is short-circuited before any model
         call, so it comes back with no model answer at all -- and the
         screen then showed a score, a scolding, and nothing to learn from,
         which is the one moment somebody most needs to see what the answer
         was. The question set already carries it, so this costs nothing. */
      ((s.model_answer || (cur && cur.model)) ? '<div class="card" style="margin-bottom:12px;' +
        'border-left:3px solid var(--ok)">' +
        '<div class="eyebrow" style="margin:0 0 4px">Say it like this</div>' +
        '<div style="font-size:14px;color:var(--body);line-height:1.7">' +
        esc(s.model_answer || (cur && cur.model) || "") + '</div>' +
        (global.Voice && global.Voice.supported()
          ? '<button class="btn ghost sm" data-mkspeak style="margin-top:10px">' +
            '🔊 Hear it</button>' : "") +
        '</div>' : "") +

      (s.followup ? '<div class="card" style="margin-bottom:12px">' +
        '<div style="font-size:13px;color:var(--muted)"><b>They would then ask:</b> ' +
        esc(s.followup) + '</div></div>' : "") +

      '<div class="row" style="gap:8px">' +
        '<button class="btn ghost" data-mkretry style="flex:1">Answer it again</button>' +
        '<button class="btn" data-mknext style="flex:2">' +
        (M.i + 1 >= M.qs.length ? "Finish and see the recap →" : "Next question →") +
        '</button>' +
      '</div>';
  }

  function doneHTML() {
    var scored = M.session.filter(function (s) { return s.score; });
    var avg = scored.length
      ? Math.round(scored.reduce(function (a, s) { return a + (s.score.score || 0); }, 0) / scored.length)
      : 0;
    var worst = scored.slice().sort(function (a, b) {
      return (a.score.score || 0) - (b.score.score || 0);
    })[0];

    return '<div class="card" style="margin-bottom:12px;border-color:var(--accent)">' +
        '<div class="eyebrow" style="margin:0 0 4px">Session over</div>' +
        '<div class="row" style="gap:14px;align-items:center;flex-wrap:wrap">' +
          '<div style="font-size:32px;font-weight:800;color:' + scoreColour(avg) + '">' +
            avg + '<span style="font-size:14px;color:var(--dim)">/100</span></div>' +
          '<div style="font-size:13.5px;color:var(--body);flex:1;min-width:200px">' +
            'across ' + scored.length + ' answer' + (scored.length === 1 ? '' : 's') +
            (worst ? '. Weakest was “' + esc((worst.q || "").slice(0, 70)) + '”.' : '.') +
          '</div>' +
        '</div>' +
      '</div>' +

      (scored.length ? '<div class="card" style="margin-bottom:12px">' +
        scored.map(function (s, n) {
          return '<div style="display:flex;gap:10px;align-items:baseline;padding:7px 0;' +
            (n ? 'border-top:1px solid var(--line)' : '') + '">' +
            '<b style="color:' + scoreColour(s.score.score || 0) + ';min-width:34px">' +
            (s.score.score || 0) + '</b>' +
            '<span style="font-size:13px;color:var(--body);line-height:1.5">' +
            esc(s.q) + '</span></div>';
        }).join("") + '</div>' : "") +

      '<div class="row" style="gap:8px">' +
        '<button class="btn ghost" data-mkpdf style="flex:1">⬇ Download the recap (PDF)</button>' +
        '<button class="btn" data-mkrestart style="flex:1">Practise again</button>' +
      '</div>';
  }

  M.html = function () {
    if (M.mode === "setup") return setupHTML();
    if (M.mode === "done") return doneHTML();
    return runHTML();
  };

  /* The start button, enabled or not, WITHOUT a repaint.
     Repainting would rebuild the textarea somebody is typing into and throw
     away their cursor, so the one attribute that actually changes is set
     directly. This is why the button sat greyed out under a fully pasted
     job description: M.jd only updated on blur, and nothing re-rendered the
     button, so the disabled attribute survived from the first paint. */
  function syncStart() {
    var b = document.querySelector("[data-mkstart]");
    if (b) b.disabled = M.jd.trim().length < 80;
  }

  /* ---- clicks -------------------------------------------------------- */
  /* One handler, delegated from the careers page, so index.html needs to
     know about exactly one function here rather than a dozen. */
  M.click = function (e) {
    var t = e.target;
    var hit = function (attr) { return t.closest("[" + attr + "]"); };
    var el;

    if ((el = hit("data-mksrc"))) {
      M.src = el.dataset.mksrc;
      M.err = "";
      if (M.src === "job" && !M.jobs.length && !M.jobsBusy) M.loadJobs();
      if (M.src === "category" && !(M.guide && M.guide.categories)) {
        api.get("/api/interview/guide").then(function (g) {
          M.guide = g; repaint();
        }).catch(function () {});
      }
      repaint(); return true;
    }
    if ((el = hit("data-mkcat"))) {
      M.cat = el.dataset.mkcat;
      M.catLabel = el.dataset.mklabel || "";
      M.role = ""; M.roleQ = "";
      M.loadRoles();
      repaint(); return true;
    }
    if ((el = hit("data-mkrole"))) {
      // Tapping the chosen one again clears it, so a wrong pick is not a
      // trap.
      var rn = el.dataset.mkrole;
      M.role = (M.role === rn) ? "" : rn;
      repaint(); return true;
    }
    if ((el = hit("data-mkjob"))) {
      M.jobId = +el.dataset.mkjob;
      M.jobTitle = el.dataset.mktitle || "";
      M.company = el.dataset.mkco || "";
      M.round = ""; M.co = null;
      M.loadCompany();
      repaint(); return true;
    }
    if ((el = hit("data-mkround"))) {
      // Tapping the round again clears it — practising one round is a
      // filter, and a filter you cannot take off is a trap.
      var nm = el.dataset.mkround;
      M.round = (M.round === nm) ? "" : nm;
      repaint(); return true;
    }
    if (hit("data-mkstart")) { M.begin(); return true; }
    if (hit("data-mkanswer")) { M.answer(); return true; }
    if (hit("data-mkdone")) { M.stopAnswer(); return true; }
    if (hit("data-mknext")) { M.next(); return true; }
    if (hit("data-mkquit")) { M.quit(); return true; }
    if (hit("data-mkrestart")) { M.restart(); return true; }
    if (hit("data-mkpdf")) { M.pdf(); return true; }
    if (hit("data-mkretry")) {
      M.score = null; M.stats = null; M.heard = ""; M.draft = "";
      if (global.Voice && global.Voice.hushNow) global.Voice.hushNow();
      M.answer(); return true;
    }
    if (hit("data-mkspeak")) {
      if (global.Voice && global.Voice.speak && M.score) {
        var c0 = M.qs[M.i];
        global.Voice.speak(M.score.model_answer || (c0 && c0.model) || "");
      }
      return true;
    }
    return false;
  };

  /* Checkboxes are a change, not a click. Keeping them here rather than in
     the page means all of the trainer's input handling lives in one file. */
  M.change = function (e) {
    var t = e.target;
    if (t.matches && t.matches("[data-mkaloud]")) {
      M.readAloud = !!t.checked;
      if (!M.readAloud && global.Voice && global.Voice.hushNow) global.Voice.hushNow();
      return true;
    }
    if (t.matches && t.matches("[data-mktyped]")) {
      M.typed = !!t.checked;
      return true;
    }
    if (t.id === "mkType") { M.draft = t.value; return true; }
    if (t.id === "mkJd") { M.jd = t.value; syncStart(); return true; }
    if (t.id === "mkRoleQ") {
      M.roleQ = t.value;
      // Debounced: a search on every keystroke would repaint the box being
      // typed into and take the cursor with it.
      clearTimeout(M._roleT);
      M._roleT = setTimeout(function () { M.loadRoles(); }, 260);
      return true;
    }
    if (t.id === "mkJdCo") { M.jdCompany = t.value; return true; }
    if (t.id === "mkJdTitle") { M.jdTitle = t.value; return true; }
    return false;
  };

  /* Can this account afford to be marked at all? A free plan has no AI
     requests, so marking is not something it can do — and finding that out
     AFTER talking for forty-five seconds is the worst possible moment.
     Asked once, when the tab opens, so the setup screen can say it plainly
     before anybody speaks. */
  M.canMark = function () {
    if (!M.quota) return true;          // unknown: do not nag, let the server rule
    if (M.quota.plan === "pro") return true;
    return (M.quota.limit === null) || (M.quota.left || 0) > 0;
  };

  /* Opening the tab for the first time needs the category list, which is the
     free guide with no arguments. */
  M.open = function () {
    if (!M.guide && !M.guideBusy) {
      M.guideBusy = true;
      api.get("/api/interview/guide").then(function (g) {
        M.guide = g; M.guideBusy = false; repaint();
      }).catch(function () { M.guideBusy = false; });
    }
    if (!M.roleList.length && !M.roleBusy) M.loadRoles();
    if (!M.quota) {
      api.get("/api/billing/me").then(function (b) {
        M.quota = (b && b.quota) || null;
        if (M.quota && b.plan) M.quota.plan = b.plan;
        repaint();
      }).catch(function () {});
    }
  };
})(window);
