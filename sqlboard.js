/* The SQL smart board.
 *
 * Its own file rather than another few hundred lines inside index.html, which
 * is already 395KB and hard enough to move around in.
 *
 * The one structural rule here: the shell is rendered when the exercise
 * changes, and nothing else. Everything that updates while you are working —
 * results, verdict, plan, diagram — is written into its own container. A
 * board that re-rendered the whole panel on each run would take the focus and
 * the cursor position out of the textarea mid-sentence, which is the fastest
 * way to make an editor feel broken.
 */
(function () {
  "use strict";

  var SQ = {
    board: null,      // what /api/sql/board returned
    ex: null,         // the exercise on screen
    result: null,     // last run
    verdict: null,    // last mark
    tab: "result",    // result | plan | join
    plan: null,
    join: null,
    walk: null,       // the free, deterministic account of the last run
    walkOpen: false,
    lesson: null,     // the AI explanation, stepped and drawn
    busy: false,
    ai: "",           // an error from the tutor, shown as itself
    aiBusy: false,
    speaking: false,
    listening: false,
    recog: null,
  };
  window.SQ = SQ;

  var esc = window.esc || function (s) {
    return String(s).replace(/[&<>]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c];
    });
  };
  var $ = function (s) { return document.querySelector(s); };

  /* ------------------------------------------------------------------ *
   * styles
   * ------------------------------------------------------------------ */
  var CSS = [
    ".sqlwrap{display:grid;grid-template-columns:210px minmax(0,1fr);gap:16px}",
    // A grid track sized 1fr refuses to go narrower than its content, so the
    // wide result tables pushed the whole board past the right edge of the
    // page instead of scrolling inside their own box. minmax(0,1fr) is what
    // lets the column shrink and hand the overflow to .sqlgrid.
    "@media(max-width:900px){.sqlwrap{grid-template-columns:minmax(0,1fr)}}",
    ".sqlwrap>*{min-width:0}",
    ".sqlside{font-size:12px}",
    ".sqltab{border:1px solid var(--line,#2a2a2a);border-radius:10px;",
    "  padding:9px 10px;margin-bottom:8px;background:var(--panel,#151515)}",
    ".sqltab b{display:block;font-size:12.5px;margin-bottom:4px}",
    ".sqltab code{display:block;color:var(--muted,#8a8a8a);font-size:11px;",
    "  line-height:1.55;word-break:break-word}",
    ".sqled{width:100%;min-height:132px;font-family:ui-monospace,Menlo,Consolas,monospace;",
    "  font-size:13.5px;line-height:1.6;padding:12px 13px;border-radius:12px;",
    "  border:1px solid var(--line,#2a2a2a);background:var(--panel2,#0f0f0f);",
    "  color:var(--text,#eee);resize:vertical;tab-size:2}",
    ".sqled:focus{outline:none;border-color:var(--accent,#ffb020)}",
    ".sqlbar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:10px 0}",
    ".sqlchips{display:flex;gap:6px;margin-bottom:10px;flex-wrap:wrap}",
    ".sqlchip{font-size:12px;padding:5px 11px;border-radius:999px;cursor:pointer;",
    "  border:1px solid var(--line,#2a2a2a);background:transparent;color:inherit}",
    ".sqlchip.on{border-color:var(--accent,#ffb020);color:var(--accent,#ffb020)}",
    ".sqlgrid{overflow-x:auto;border:1px solid var(--line,#2a2a2a);border-radius:10px}",
    ".sqlgrid table{border-collapse:collapse;width:100%;font-size:12.5px;",
    "  font-family:ui-monospace,Menlo,Consolas,monospace}",
    ".sqlgrid th{text-align:left;padding:7px 11px;background:var(--panel2,#0f0f0f);",
    "  border-bottom:1px solid var(--line,#2a2a2a);white-space:nowrap;font-weight:700}",
    ".sqlgrid td{padding:6px 11px;border-bottom:1px solid var(--line,#1e1e1e);",
    "  white-space:nowrap}",
    ".sqlgrid tr:last-child td{border-bottom:none}",
    ".sqlnull{color:var(--dim,#666);font-style:italic}",
    ".sqlmsg{border-radius:10px;padding:11px 13px;font-size:13px;line-height:1.6;",
    "  margin-bottom:10px;border:1px solid}",
    ".sqlmsg.good{border-color:#3fae6a;background:rgba(63,174,106,.10)}",
    ".sqlmsg.bad{border-color:#d9534f;background:rgba(217,83,79,.10)}",
    ".sqlmsg.warn{border-color:var(--accent,#ffb020);background:rgba(255,176,32,.10)}",
    ".sqlmeta{font-size:11.5px;color:var(--muted,#8a8a8a);margin-top:7px}",
    ".sqlskill{margin-bottom:9px;font-size:11.5px}",
    ".sqlskill-t{display:flex;gap:8px;align-items:baseline;margin-bottom:3px}",
    ".sqlskill-t span{flex:1;line-height:1.35}",
    ".sqlskill-t b{font-size:11px;color:var(--muted,#8a8a8a)}",
    ".sqlskill i{height:4px;border-radius:99px;background:var(--line,#2a2a2a);",
    "  overflow:hidden;font-style:normal;display:block}",
    ".sqlskill i>u{display:block;height:100%;background:var(--accent,#ffb020);",
    "  text-decoration:none;transition:width .4s ease}",
    ".sqlplan{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12.5px;",
    "  line-height:1.8}",
    ".sqlplan .scan{color:#e0864a}",
    ".sqlplan .search{color:#3fae6a}",

    /* the tutor */
    ".sqltutor{margin:12px 0}",
    ".sqlask{flex:1;min-width:160px;font-size:13px;padding:9px 12px;",
    "  border-radius:10px;border:1px solid var(--line,#2a2a2a);",
    "  background:var(--panel2,#0f0f0f);color:var(--text,#eee)}",
    ".sqlask:focus{outline:none;border-color:var(--accent,#ffb020)}",
    ".sqllesson{border:1px solid var(--line,#2a2a2a);border-radius:12px;",
    "  padding:13px;margin-bottom:12px}",
    ".sqlstep{display:flex;gap:10px;font-size:13px;line-height:1.65;",
    "  padding:8px;border-radius:9px;margin-bottom:3px;transition:background .2s}",
    ".sqlstep.on{background:rgba(255,176,32,.13)}",
    ".sqlstep-n{flex:0 0 21px;height:21px;border-radius:50%;font-size:11px;",
    "  display:flex;align-items:center;justify-content:center;font-weight:800;",
    "  background:var(--panel2,#0f0f0f);border:1px solid var(--line,#2a2a2a)}",
    ".sqlstep-n.sm{flex-basis:auto;width:auto;padding:0 7px;border-radius:99px;",
    "  font-size:10px;letter-spacing:.4px}",
    ".sqlcode{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px;",
    "  background:var(--panel2,#0f0f0f);border:1px solid var(--line,#2a2a2a);",
    "  border-radius:8px;padding:9px 11px;margin:7px 0 0;overflow-x:auto;",
    "  white-space:pre-wrap}",

    /* the pipeline: real rows, one stage at a time */
    ".sqlwalk{border:1px solid var(--line,#2a2a2a);border-radius:12px;",
    "  padding:11px 13px;margin-bottom:12px}",
    ".sqlwalk>summary{cursor:pointer;font-size:13px;font-weight:700;",
    "  list-style:none}",
    ".sqlwalk>summary::-webkit-details-marker{display:none}",
    ".sqlwalk>summary::before{content:'▸ ';color:var(--accent,#ffb020)}",
    ".sqlwalk[open]>summary::before{content:'▾ '}",
    ".sqlstage{margin:12px 0 0;animation:sqlin .34s ease both}",
    "@keyframes sqlin{from{opacity:0;transform:translateY(7px)}",
    "  to{opacity:1;transform:none}}",
    "@media(prefers-reduced-motion:reduce){.sqlstage{animation:none}}",
    ".sqlstage-h{display:flex;align-items:baseline;gap:9px;margin-bottom:3px;",
    "  font-size:13px}",
    ".sqlcount{font-size:11.5px;color:var(--muted,#8a8a8a);font-weight:700}",
    ".sqldrop{font-size:11px;font-weight:700;color:#d9534f}",
    ".sqlgrow{font-size:11px;font-weight:700;color:#e0864a}",
    ".sqlsame{font-size:11px;color:var(--dim,#666)}",
    ".sqlgrid tr.gone td{opacity:.42;text-decoration:line-through;",
    "  background:rgba(217,83,79,.09)}",

    /* the join, as its two tables */
    ".sqljoin2{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);",
    "  gap:12px}",
    "@media(max-width:760px){.sqljoin2{grid-template-columns:minmax(0,1fr)}}",
    ".sqljrow{cursor:default}",
    ".sqljrow.lit td{background:rgba(63,174,106,.16)}",
    ".sqljrow.lonely td{background:rgba(217,83,79,.10)}",
    ".sqltag{font-size:10px;font-weight:700;color:#d9534f;white-space:nowrap}"
  ].join("");

  function styles() {
    if (document.getElementById("sqlboard-css")) return;
    var s = document.createElement("style");
    s.id = "sqlboard-css";
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  /* ------------------------------------------------------------------ *
   * loading
   * ------------------------------------------------------------------ */
  async function load(keepSql) {
    styles();
    SQ.busy = true;
    paintShell();
    try {
      SQ.board = await api.get("/api/sql/board");
      if (!SQ.ex || !keepSql) SQ.ex = SQ.board.next || SQ.board.exercises[0];
    } catch (e) {
      SQ.board = null;
      SQ.error = e.message || "Could not open the board.";
    }
    SQ.busy = false;
    paintShell();
  }

  function pick(id) {
    var ex = (SQ.board.exercises || []).filter(function (x) { return x.id === id; })[0];
    if (!ex) return;
    SQ.ex = ex;
    SQ.result = SQ.verdict = SQ.plan = SQ.join = null;
    SQ.ai = "";
    SQ.tab = "result";
    SQ.freeRun = false;
    paintShell();
  }

  /* ------------------------------------------------------------------ *
   * the shell — rendered on exercise change, not on every run
   * ------------------------------------------------------------------ */
  function paintShell() {
    var host = $("#main");
    if (!host) return;

    if (SQ.busy && !SQ.board) {
      host.innerHTML = '<div class="card">Opening the board…</div>';
      return;
    }
    if (!SQ.board) {
      host.innerHTML = '<div class="card">' + esc(SQ.error || "Could not open the board.") +
        '</div>';
      return;
    }

    var b = SQ.board, ex = SQ.ex;
    var saved = (b.history[ex.id] || {});

    host.innerHTML =
      '<div class="row" style="justify-content:space-between;align-items:baseline;' +
      'margin-bottom:6px">' +
        '<h2 style="margin:0">🗄️ SQL board</h2>' +
        '<div style="font-size:12.5px;color:var(--muted)" id="sqlDone">' +
          b.done + " of " + b.total + " solved</div>" +
      "</div>" +
      '<p style="font-size:13px;color:var(--muted);margin:0 0 16px;max-width:60ch">' +
        "Every query here runs for real against the sample database on the left, " +
        "and is marked on the rows it returns — not on how you wrote it. Running " +
        "and marking are free and always will be: they cost us nothing." +
      "</p>" +

      '<div class="sqlwrap">' +
        '<div class="sqlside">' + sideHtml() + "</div>" +
        "<div>" +
          '<div class="sqlchips">' + chipsHtml() + "</div>" +

          '<div class="card" style="padding:14px">' +
            '<div style="font-size:13.5px;font-weight:750;margin-bottom:3px">' +
              esc(ex.title) + "</div>" +
            '<div style="font-size:13px;line-height:1.65;margin-bottom:10px">' +
              esc(ex.ask) + "</div>" +

            '<textarea class="sqled" id="sqlEd" spellcheck="false" ' +
              'placeholder="SELECT …">' + esc(saved.code || "") + "</textarea>" +

            '<div class="sqlbar">' +
              '<button class="btn" id="sqlCheck">Check my answer</button>' +
              '<button class="btn ghost sm" id="sqlRun">Just run it</button>' +
              '<button class="btn ghost sm" id="sqlHint">Hint</button>' +
              (ex.visual ? '<button class="btn ghost sm" id="sqlPic">' +
                "Show me the join</button>" : "") +
              '<button class="btn ghost sm" id="sqlPlan">Query plan</button>' +
              '<span style="flex:1"></span>' +
              '<span style="font-size:11.5px;color:var(--muted)">Ctrl+Enter runs</span>' +
            "</div>" +

            '<div id="sqlOut"></div>' +
          "</div>" +
        "</div>" +
      "</div>";

    wire();
    paintOut();
  }

  function sideHtml() {
    var h = '<div class="eyebrow" style="margin:0 0 7px">The database</div>';
    (SQ.board.schema || []).forEach(function (t) {
      h += '<div class="sqltab"><b>' + esc(t.table) +
        ' <span style="color:var(--dim);font-weight:400">· ' + t.rows +
        " rows</span></b><code>" + esc(t.columns.join(", ")) + "</code></div>";
    });
    h += '<div class="eyebrow" style="margin:16px 0 7px">Where you are</div>';
    // Name on its own line. Squeezed onto one row beside the bar, every label
    // truncated to "Grouping, an…" — a progress list nobody can read the
    // labels of is just a row of bars.
    (SQ.board.skills || []).forEach(function (s) {
      var pc = s.total ? Math.round((s.done / s.total) * 100) : 0;
      h += '<div class="sqlskill">' +
        '<div class="sqlskill-t"><span>' + esc(s.name) + "</span>" +
        "<b>" + s.done + "/" + s.total + "</b></div>" +
        '<i><u style="width:' + pc + '%"></u></i></div>';
    });
    return h;
  }

  function chipsHtml() {
    return (SQ.board.exercises || []).map(function (x) {
      var st = SQ.board.history[x.id] || {};
      var mark = st.solved ? "✓ " : (st.tries ? "· " : "");
      return '<button class="sqlchip' + (x.id === SQ.ex.id ? " on" : "") +
        '" data-sqlex="' + esc(x.id) + '">' + mark + esc(x.title) + "</button>";
    }).join("");
  }

  /* ------------------------------------------------------------------ *
   * the output area — the only thing that repaints while you work
   * ------------------------------------------------------------------ */
  function paintOut() {
    var out = $("#sqlOut");
    if (!out) return;
    var h = "";

    if (SQ.hint) {
      h += '<div class="sqlmsg warn">' + esc(SQ.ex.hint) + "</div>";
    }

    if (SQ.verdict) {
      var v = SQ.verdict;
      h += '<div class="sqlmsg ' + (v.correct ? "good" : "bad") + '">' +
        (v.correct ? "✓ " : "") + esc(v.why) +
        (!v.correct && v.expected_count !== undefined
          ? '<div class="sqlmeta">The answer has ' + v.expected_count +
            " row" + (v.expected_count === 1 ? "" : "s") + ".</div>"
          : "") +
        "</div>";
    }

    // The tutor row is always here, not only after a wrong answer: the most
    // useful question a learner asks is usually not "why is this wrong" but
    // "why does this work", and that one has nowhere to go if the controls
    // only appear on failure.
    h += tutorBarHtml();

    if (SQ.lesson) h += lessonHtml(SQ.lesson);
    if (SQ.ai) h += '<div class="sqlmsg bad">' + esc(SQ.ai) + "</div>";

    if (SQ.walk && SQ.walk.ok) h += walkHtml(SQ.walk);

    if (SQ.tab === "plan" && SQ.plan) h += planHtml();
    else if (SQ.tab === "join" && SQ.join) h += joinHtml();
    else if (SQ.result) h += resultHtml();

    out.innerHTML = h;
    wireOut();
  }

  /* ---- the tutor: explain, speak, and ask in your own words ---------- */
  function tutorBarHtml() {
    var left = SQ.board.explain_left;
    return '<div class="sqltutor">' +
      '<div class="sqlbar" style="margin:0 0 8px">' +
        '<button class="btn ghost sm" id="sqlWhy"' +
          (SQ.aiBusy ? " disabled" : "") + ">" +
          (SQ.aiBusy ? "Thinking…" : "🎓 Explain my query") + "</button>" +
        '<button class="btn ghost sm" id="sqlSpeak"' +
          (SQ.lesson ? "" : " disabled") + ">" +
          (SQ.speaking ? "◼ Stop" : "🔊 Read it to me") + "</button>" +
        '<button class="btn ghost sm" id="sqlMic"' +
          (SQ.listening ? ' style="border-color:var(--accent)"' : "") + ">" +
          (SQ.listening ? "● Listening…" : "🎤 Ask by voice") + "</button>" +
        '<span style="flex:1"></span>' +
        (left !== null && left !== undefined
          ? '<span style="font-size:11.5px;color:var(--muted)">' + left +
            " free left</span>" : "") +
      "</div>" +
      '<div class="sqlbar" style="margin:0">' +
        '<input class="sqlask" id="sqlQ" placeholder="Ask anything — ' +
          'why is my total too high?" maxlength="300">' +
        '<button class="btn sm" id="sqlAsk"' + (SQ.aiBusy ? " disabled" : "") +
          ">Ask</button>" +
      "</div></div>";
  }

  /* A stepped explanation with its sketches. Same shape the main smart board
   * uses, so sbDiagramHTML draws it — nodes and index pairs from the model,
   * never markup, and the picture is built here in the browser. */
  function lessonHtml(l) {
    var h = '<div class="sqllesson"><div class="sqlmeta" ' +
      'style="margin:0 0 8px">' + esc(l.title || "") + "</div>";
    (l.steps || []).forEach(function (s, i) {
      h += '<div class="sqlstep" data-step="' + i + '">' +
        '<div class="sqlstep-n">' + (i + 1) + "</div><div>" +
        (s.where ? '<div class="sqlmeta" style="margin:0 0 3px">' +
          esc(s.where) + "</div>" : "") +
        "<div>" + esc(s.t || "") + "</div>" +
        (s.code ? '<pre class="sqlcode">' + esc(s.code) + "</pre>" : "") +
        "</div></div>";
    });
    if (l.takeaway) {
      h += '<div class="sqlmsg good" style="margin:10px 0 0">' +
        esc(l.takeaway) + "</div>";
    }
    if ((l.deeper || []).length) {
      h += '<div class="sqlchips" style="margin:10px 0 0">' +
        l.deeper.map(function (d) {
          return '<button class="sqlchip" data-sqlq="' + esc(d) + '">' +
            esc(d) + "</button>";
        }).join("") + "</div>";
    }
    return h + "</div>";
  }

  /* The free one, and the one that does the actual teaching.
   *
   * Not a drawing of a query — the query's own rows, at each stage it really
   * passed through. Ten customers become five after WHERE and you can see
   * which five left, because the ones that left are still on screen with a
   * line through them. A diagram of a pipeline says "WHERE filters rows". This
   * says "WHERE removed Ravi, Priya and Sam, and here they are." */
  function walkHtml(w) {
    var h = '<details class="sqlwalk"' + (SQ.walkOpen ? " open" : "") +
      "><summary>What your query did to your rows</summary>";

    var st = w.stages || [];
    st.forEach(function (s, i) {
      var prev = i ? st[i - 1] : null;
      var delta = "";
      if (prev && prev.count !== null && s.count !== null) {
        var d = prev.count - s.count;
        delta = d > 0
          ? '<span class="sqldrop">− ' + d + " row" + (d === 1 ? "" : "s") +
            "</span>"
          : (d < 0
            ? '<span class="sqlgrow">+ ' + (-d) + " row" +
              (d === -1 ? "" : "s") + "</span>"
            : '<span class="sqlsame">no change</span>');
      }
      h += '<div class="sqlstage" style="animation-delay:' + (i * 90) + 'ms">' +
        '<div class="sqlstage-h"><b>' + esc(s.label) + "</b>" +
        '<span class="sqlcount">' + (s.count === null ? "?" : s.count) +
        " row" + (s.count === 1 ? "" : "s") + "</span>" + delta + "</div>" +
        '<div class="sqlmeta" style="margin:0 0 7px">' + esc(s.note) + "</div>" +
        stageTable(s, st[i + 1]) +
        "</div>";
    });

    w.steps.forEach(function (s) {
      h += '<div class="sqlstep"><div class="sqlstep-n sm">' +
        esc(s.label.split(" ")[0]) + "</div><div>" + esc(s.note) +
        "</div></div>";
    });
    (w.notes || []).forEach(function (n) {
      h += '<div class="sqlmsg warn" style="margin:8px 0 0">' + esc(n) +
        "</div>";
    });
    return h + "</details>";
  }

  /* One stage's rows. Where the next stage has the same columns, the rows it
   * is about to lose are marked here rather than simply missing from the next
   * table — a row that vanishes between two tables is a puzzle, and a row
   * struck through in front of you is an explanation. */
  function stageTable(s, next) {
    var gone = {};
    if (next && next.columns.join("|") === s.columns.join("|")) {
      var keep = {};
      next.rows.forEach(function (r) { keep[JSON.stringify(r)] = 1; });
      s.rows.forEach(function (r, i) {
        if (!keep[JSON.stringify(r)]) gone[i] = 1;
      });
      // Only trustworthy while both stages are shown in full; past the display
      // limit a row can be absent here and present further down the result.
      if (next.shown < next.count) gone = {};
    }
    var h = '<div class="sqlgrid"><table><thead><tr>';
    s.columns.forEach(function (c) { h += "<th>" + esc(c) + "</th>"; });
    h += "</tr></thead><tbody>";
    s.rows.forEach(function (row, i) {
      h += '<tr class="' + (gone[i] ? "gone" : "") + '">';
      row.forEach(function (v) {
        h += "<td>" + (v === null ? '<span class="sqlnull">NULL</span>'
          : esc(v)) + "</td>";
      });
      h += "</tr>";
    });
    h += "</tbody></table></div>";
    if (s.shown < s.count) {
      h += '<div class="sqlmeta">first ' + s.shown + " of " + s.count +
        "</div>";
    }
    return h;
  }

  function resultHtml() {
    var r = SQ.result;
    if (!r.ok) return '<div class="sqlmsg bad">' + esc(r.error) + "</div>";
    if (!r.rows.length) {
      return '<div class="sqlmsg warn">That ran without error and matched no ' +
        "rows. An empty result is a real answer — but if you expected some, " +
        "the WHERE is usually the place to look.</div>";
    }
    var h = '<div class="sqlgrid"><table><thead><tr>';
    r.columns.forEach(function (c) { h += "<th>" + esc(c) + "</th>"; });
    h += "</tr></thead><tbody>";
    r.rows.forEach(function (row) {
      h += "<tr>";
      row.forEach(function (v) {
        h += "<td>" + (v === null
          ? '<span class="sqlnull">NULL</span>' : esc(v)) + "</td>";
      });
      h += "</tr>";
    });
    h += "</tbody></table></div>";
    h += '<div class="sqlmeta">' + r.count + " row" + (r.count === 1 ? "" : "s") +
      " in " + r.ms + " ms" +
      (r.truncated ? " · only the first " + r.count + " are shown" : "") + "</div>";
    return h;
  }

  function planHtml() {
    var p = SQ.plan;
    if (!p.ok) return '<div class="sqlmsg bad">' + esc(p.error) + "</div>";
    var h = '<div class="sqlgrid" style="padding:11px 13px"><div class="sqlplan">';
    p.steps.forEach(function (s) {
      var cls = /^\s*SCAN/.test(s) ? "scan" : (/SEARCH/.test(s) ? "search" : "");
      h += '<div class="' + cls + '">' + esc(s) + "</div>";
    });
    h += "</div></div>";
    h += '<div class="sqlmsg warn" style="margin-top:10px">' + esc(p.reading) +
      "</div>";
    return h;
  }

  /* What the JOIN did, as the two tables themselves.
   *
   * Hovering a row on the left lights up the rows on the right it matched, so
   * the pairing is something you interrogate rather than something you are
   * shown. The rows with no partner are tagged in place: those are exactly
   * what INNER JOIN throws away and LEFT JOIN keeps, and that one difference
   * is most of what JOIN questions are actually testing. */
  function joinHtml() {
    var j = SQ.join;
    if (!j.ok) return '<div class="sqlmsg bad">' + esc(j.error) + "</div>";

    var mates = {};        // left row index -> right row indexes
    j.pairs.forEach(function (p) {
      (mates[p[0]] = mates[p[0]] || []).push(p[1]);
    });
    var lonelyL = {};
    j.unmatched_left.forEach(function (i) { lonelyL[i] = 1; });
    var lonelyR = {};
    j.unmatched_right.forEach(function (i) { lonelyR[i] = 1; });

    function side(t, which, lonely) {
      var h = '<div><div class="sqlmeta" style="margin:0 0 5px"><b>' +
        esc(t.table) + "</b> · joined on " + esc(t.key) + "</div>" +
        '<div class="sqlgrid"><table><thead><tr>';
      t.columns.forEach(function (c) { h += "<th>" + esc(c) + "</th>"; });
      h += '<th style="width:1%"></th></tr></thead><tbody>';
      t.rows.forEach(function (row, i) {
        h += '<tr class="sqljrow' + (lonely[i] ? " lonely" : "") +
          '" data-side="' + which + '" data-i="' + i + '">';
        row.forEach(function (v) {
          h += "<td>" + (v === null ? '<span class="sqlnull">NULL</span>'
            : esc(v)) + "</td>";
        });
        h += "<td>" + (lonely[i] ? '<span class="sqltag">no match</span>' : "") +
          "</td></tr>";
      });
      return h + "</tbody></table></div></div>";
    }

    // Stashed for the hover handler, which needs the pairing after render.
    SQ.mates = mates;

    return '<div class="sqlmsg warn" style="margin-bottom:10px">' +
      esc(j.reading) + "</div>" +
      '<div class="sqljoin2">' + side(j.left, "l", lonelyL) +
      side(j.right, "r", lonelyR) + "</div>" +
      '<div class="sqlmeta">Point at a row on the left to light up the rows ' +
      "it matches on the right.</div>";
  }

  /* ------------------------------------------------------------------ *
   * actions
   * ------------------------------------------------------------------ */
  function sql() {
    var ed = $("#sqlEd");
    return ed ? ed.value : "";
  }

  async function run() {
    SQ.tab = "result"; SQ.verdict = null; SQ.ai = "";
    SQ.result = { ok: true, columns: [], rows: [], count: 0, ms: 0 };
    try {
      SQ.result = await api.post("/api/sql/run", { sql: sql() });
      SQ.walk = SQ.result.walk;
    } catch (e) {
      SQ.result = { ok: false, error: e.message || "Could not run that." };
      SQ.walk = null;
    }
    paintOut();
  }

  async function check() {
    SQ.tab = "result"; SQ.ai = "";
    try {
      var v = await api.post("/api/sql/check",
        { exercise: SQ.ex.id, sql: sql() });
      SQ.verdict = v;
      SQ.result = v.result;
      SQ.walk = v.walk;
      // Keep the sidebar and the chips honest without a full reload.
      SQ.board.skills = v.skills;
      SQ.board.done = v.done;
      var st = SQ.board.history[SQ.ex.id] || { tries: 0 };
      st.tries = (st.tries || 0) + 1;
      if (v.correct) st.solved = true;
      SQ.board.history[SQ.ex.id] = st;
      var side = document.querySelector(".sqlside");
      if (side) side.innerHTML = sideHtml();
      var chips = document.querySelector(".sqlchips");
      if (chips) chips.innerHTML = chipsHtml();
      // The tally in the header is part of that same update. Left out, it sat
      // on "0 of 13 solved" while the tick appeared on the exercise beside it.
      var tally = document.getElementById("sqlDone");
      if (tally) tally.textContent = SQ.board.done + " of " + SQ.board.total +
        " solved";
      if (v.correct && v.next && typeof toast === "function") {
        toast("Solved. Next up: " + v.next.title);
      }
    } catch (e) {
      SQ.verdict = null;
      SQ.result = { ok: false, error: e.message || "Could not check that." };
    }
    paintOut();
  }

  async function showPlan() {
    SQ.tab = "plan";
    SQ.plan = null;
    paintOut();
    try {
      SQ.plan = await api.post("/api/sql/plan", { sql: sql() });
    } catch (e) {
      SQ.plan = { ok: false, error: e.message || "No plan for that." };
    }
    paintOut();
  }

  async function showJoin() {
    SQ.tab = "join";
    if (!SQ.join) {
      try {
        SQ.join = await api.get("/api/sql/join/" + encodeURIComponent(SQ.ex.id));
      } catch (e) {
        SQ.join = { ok: false, error: e.message || "No diagram for this one." };
      }
    }
    paintOut();
  }

  async function tutor(path, body) {
    stopSpeaking();
    SQ.aiBusy = true; SQ.ai = ""; SQ.lesson = null;
    paintOut();
    try {
      var r = await api.post(path, body);
      SQ.lesson = r.lesson;
      if (!r.cached && SQ.board.explain_left) SQ.board.explain_left -= 1;
    } catch (e) {
      SQ.ai = e.message || "The tutor is not available right now.";
    }
    SQ.aiBusy = false;
    paintOut();
    // Speak it without being asked. Somebody who pressed the microphone was
    // holding a conversation, not reading a page, and making them press play
    // afterwards breaks the one thing they chose.
    if (SQ.lesson && SQ.spokeIn) { SQ.spokeIn = false; speak(); }
  }

  function explain() {
    if (!sql().trim()) { SQ.ai = "Write a query first."; return paintOut(); }
    tutor("/api/sql/explain", { exercise: SQ.ex.id, sql: sql() });
  }

  function ask(q) {
    q = (q || "").trim();
    if (!q) return;
    tutor("/api/sql/ask", { exercise: SQ.ex.id, sql: sql(), question: q });
  }

  /* ---- speech ------------------------------------------------------- *
   * Reading is done step by step, with the step being read highlighted, so
   * a listener can follow where the voice is rather than losing their place
   * in a block of text that is talking about itself. speakChunks belongs to
   * the main board; reusing it means one set of voice-picking and one set of
   * Chrome truncation workarounds rather than two that drift.               */
  function stopSpeaking() {
    SQ.speaking = false;
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    document.querySelectorAll(".sqlstep.on").forEach(function (el) {
      el.classList.remove("on");
    });
  }

  async function speak() {
    if (SQ.speaking) { stopSpeaking(); return paintOut(); }
    if (!SQ.lesson) return;
    if (!window.speechSynthesis) {
      SQ.ai = "This browser cannot read text aloud.";
      return paintOut();
    }
    SQ.speaking = true;
    paintOut();

    var steps = SQ.lesson.steps || [];
    for (var i = 0; i < steps.length; i++) {
      if (!SQ.speaking) break;
      var el = document.querySelector('.sqlstep[data-step="' + i + '"]');
      if (el) {
        document.querySelectorAll(".sqlstep.on").forEach(function (x) {
          x.classList.remove("on");
        });
        el.classList.add("on");
        el.scrollIntoView({ block: "center", behavior: "smooth" });
      }
      await speakChunks(steps[i].t || "", { cancelled: function () {
        return !SQ.speaking;
      } });
    }
    if (SQ.speaking && SQ.lesson.takeaway) {
      await speakChunks(SQ.lesson.takeaway, { cancelled: function () {
        return !SQ.speaking;
      } });
    }
    stopSpeaking();
    paintOut();
  }

  function mic() {
    var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      SQ.ai = "This browser cannot listen. Type the question instead.";
      return paintOut();
    }
    if (SQ.listening && SQ.recog) { SQ.recog.stop(); return; }
    stopSpeaking();
    var r = new SR();
    SQ.recog = r;
    r.lang = "en-IN";
    r.interimResults = false;
    r.maxAlternatives = 1;
    r.onresult = function (ev) {
      var t = ev.results[0][0].transcript;
      SQ.listening = false;
      SQ.spokeIn = true;          // asked by voice, so answer by voice
      var box = document.getElementById("sqlQ");
      if (box) box.value = t;
      paintOut();
      ask(t);
    };
    r.onerror = function () { SQ.listening = false; paintOut(); };
    r.onend = function () { SQ.listening = false; paintOut(); };
    SQ.listening = true;
    paintOut();
    r.start();
  }

  function wireOut() {
    var m = { sqlWhy: explain, sqlSpeak: speak, sqlMic: mic };
    Object.keys(m).forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.onclick = m[id];
    });
    var go = document.getElementById("sqlAsk");
    var box = document.getElementById("sqlQ");
    if (go) go.onclick = function () { ask(box ? box.value : ""); };
    if (box) {
      box.onkeydown = function (e) {
        if (e.key === "Enter") { e.preventDefault(); ask(box.value); }
      };
    }
    document.querySelectorAll("[data-sqlq]").forEach(function (el) {
      el.onclick = function () { ask(el.dataset.sqlq); };
    });
    var w = document.querySelector(".sqlwalk");
    if (w) w.ontoggle = function () { SQ.walkOpen = w.open; };

    // The join tables: light up what a row matched.
    document.querySelectorAll('.sqljrow[data-side="l"]').forEach(function (el) {
      el.onmouseenter = el.onclick = function () {
        document.querySelectorAll(".sqljrow.lit").forEach(function (x) {
          x.classList.remove("lit");
        });
        el.classList.add("lit");
        (SQ.mates[el.dataset.i] || []).forEach(function (i) {
          var t = document.querySelector('.sqljrow[data-side="r"][data-i="' +
            i + '"]');
          if (t) t.classList.add("lit");
        });
      };
    });
  }

  function wire() {
    var ed = $("#sqlEd");
    if (ed) {
      ed.onkeydown = function (e) {
        if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); run(); }
        // Tab indents rather than leaving the editor. Shift+Tab still escapes,
        // so the board stays reachable by keyboard alone.
        if (e.key === "Tab" && !e.shiftKey) {
          e.preventDefault();
          var s = ed.selectionStart, t = ed.value;
          ed.value = t.slice(0, s) + "  " + t.slice(ed.selectionEnd);
          ed.selectionStart = ed.selectionEnd = s + 2;
        }
      };
    }
    var m = {
      sqlRun: run, sqlCheck: check, sqlPlan: showPlan, sqlPic: showJoin,
      sqlHint: function () { SQ.hint = !SQ.hint; paintOut(); }
    };
    Object.keys(m).forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.onclick = m[id];
    });
    document.querySelectorAll("[data-sqlex]").forEach(function (el) {
      el.onclick = function () { pick(el.dataset.sqlex); };
    });
  }

  window.renderSqlBoard = function () { load(false); };
})();
