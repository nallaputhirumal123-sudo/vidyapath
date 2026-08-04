/* The test at the end of a lesson.
 *
 * /api/quiz/make and /api/quiz/mark have been live and tested with nothing
 * calling them, which is the same as not having them. This is the button.
 *
 * Three question shapes, rendered differently because they ask for different
 * things: options to pick, a gap to type into, and pairs to join. The joining
 * one is a set of dropdowns rather than dragging — a drag target on a
 * classroom board being used with a finger, at the front of a room, is a
 * fiddly way to answer a question that is about knowledge rather than aim.
 *
 * Marked on the server, which costs nothing: it is arithmetic. Doing it here
 * would be faster still and would put the answers one View Source away from a
 * class that has just been told there is a test.
 */
(function () {
  "use strict";

  var QZ = { qs: null, answers: {}, marked: null, busy: false, topic: "" };
  window.QZ = QZ;

  var esc = window.esc || function (s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  };

  var CSS = [
    ".qz{border:1px solid var(--line,#2a2a2a);border-radius:14px;",
    "  padding:15px 16px;margin-top:16px;background:var(--panel2,#0f0f0f)}",
    ".qz h3{margin:0 0 3px;font-size:15.5px}",
    ".qz .qzsub{font-size:12.5px;color:var(--muted,#8a8a8a);margin-bottom:14px}",
    ".qzq{padding:13px 0;border-top:1px solid var(--line,#1e1e1e)}",
    ".qzq:first-of-type{border-top:none;padding-top:4px}",
    ".qzq .ask{font-size:14px;font-weight:650;line-height:1.6;",
    "  margin-bottom:9px}",
    ".qzopt{display:block;width:100%;text-align:left;font-size:16px;",
    "  padding:9px 12px;border-radius:9px;margin-bottom:6px;cursor:pointer;",
    "  border:1px solid var(--line,#2a2a2a);background:transparent;",
    "  color:inherit;line-height:1.5}",
    ".qzopt:hover{border-color:var(--accent,#ffb020)}",
    ".qzopt.on{border-color:var(--accent,#ffb020);",
    "  background:rgba(255,176,32,.10)}",
    ".qzopt.right{border-color:#3fae6a;background:rgba(63,174,106,.14)}",
    ".qzopt.wrong{border-color:#d9534f;background:rgba(217,83,79,.12)}",
    ".qzgap{font-size:16px;padding:8px 11px;border-radius:9px;",
    "  border:1px solid var(--line,#2a2a2a);background:var(--bg,#0b0d10);",
    "  color:inherit;min-width:150px}",
    ".qzpair{display:flex;gap:9px;align-items:center;margin-bottom:7px;",
    "  flex-wrap:wrap}",
    ".qzpair .lft{flex:0 0 auto;font-weight:650;font-size:13.5px}",
    ".qzpair select{flex:1 1 180px;font-size:16px;padding:7px 9px;",
    "  border-radius:9px;border:1px solid var(--line,#2a2a2a);",
    "  background:var(--bg,#0b0d10);color:inherit;min-width:0}",
    ".qzwhy{font-size:12.5px;line-height:1.65;margin-top:7px;",
    "  color:var(--body,#ccc)}",
    ".qzscore{font-size:15px;font-weight:800;padding:11px 14px;",
    "  border-radius:11px;margin-top:13px}",
    ".qzall{border:1px solid #3fae6a;background:rgba(63,174,106,.12)}",
    ".qzsome{border:1px solid var(--accent,#ffb020);",
    "  background:rgba(255,176,32,.10)}"
  ].join("");

  function styles() {
    if (document.getElementById("qz-css")) return;
    var s = document.createElement("style");
    s.id = "qz-css";
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  /* The lesson as plain text, which is what the question writer reads.
     Taken from whichever board is showing, so the same button works on
     Axle Pro and on a plain answer. */
  function lessonText(l) {
    if (!l) return "";
    var out = [];
    (l.steps || []).forEach(function (st) {
      out.push(typeof st === "string" ? st : (st.t || ""));
      if (st && st.code) out.push(st.code);
    });
    if (l.takeaway) out.push(l.takeaway);
    return out.join("\n").slice(0, 12000);
  }

  async function make() {
    var l = (window.SB && SB.lesson) || (window.ASK && ASK.lesson);
    if (!l) { toast("Ask something first."); return; }
    styles();
    QZ.qs = null; QZ.answers = {}; QZ.marked = null; QZ.busy = true;
    QZ.topic = (window.SB && SB.topic) || (window.ASK && ASK.question) ||
               l.title || "";
    paint();
    try {
      var r = await api.post("/api/quiz/make", {
        topic: QZ.topic.slice(0, 300),
        lesson: lessonText(l),
        level: (window.ASK && ASK.level) || "Intermediate"
      });
      QZ.qs = r.questions || [];
    } catch (e) {
      QZ.qs = null;
      toast((e && e.message) || "Could not build a test just now.");
    }
    QZ.busy = false;
    paint();
  }

  function qHTML(q, i) {
    var m = QZ.marked && QZ.marked.detail && QZ.marked.detail[i];
    var h = '<div class="qzq"><div class="ask">' + (i + 1) + ". " +
            esc(q.q || q.text || "") + "</div>";

    if (q.kind === "choice") {
      (q.options || []).forEach(function (o, k) {
        var cls = "qzopt";
        if (QZ.marked) {
          if (k === q.answer) cls += " right";
          else if (QZ.answers[i] === k) cls += " wrong";
        } else if (QZ.answers[i] === k) cls += " on";
        h += '<button class="' + cls + '" data-qz="' + i + '" data-opt="' +
             k + '"' + (QZ.marked ? " disabled" : "") + ">" + esc(o) +
             "</button>";
      });
    } else if (q.kind === "blank") {
      h = '<div class="qzq"><div class="ask">' + (i + 1) + ". " +
          esc(q.text || "") + "</div>";
      h += '<input class="qzgap" data-qzgap="' + i + '" value="' +
           esc(QZ.answers[i] || "") + '" placeholder="the missing word"' +
           (QZ.marked ? " disabled" : "") + ">";
      if (QZ.marked && m && !m.correct) {
        h += '<div class="qzwhy">The answer was <b>' + esc(q.answer) +
             "</b>.</div>";
      }
    } else if (q.kind === "match") {
      var rights = (q.pairs || []).map(function (p) { return p.right; });
      // Shuffled once per render would reshuffle on every keystroke, so the
      // order is fixed by position instead — deterministic, and still not
      // the answer order.
      var shown = rights.slice().sort();
      (q.pairs || []).forEach(function (p, k) {
        var chosen = (QZ.answers[i] || {})[p.left] || "";
        h += '<div class="qzpair"><span class="lft">' + esc(p.left) +
             '</span><select data-qzpair="' + i + '" data-left="' +
             esc(p.left) + '"' + (QZ.marked ? " disabled" : "") + ">" +
             '<option value="">— choose —</option>' +
             shown.map(function (r) {
               return '<option value="' + esc(r) + '"' +
                 (chosen === r ? " selected" : "") + ">" + esc(r) +
                 "</option>";
             }).join("") + "</select>";
        if (QZ.marked) {
          h += '<span>' + (chosen === p.right ? "✓" : "✕ " + esc(p.right)) +
               "</span>";
        }
        h += "</div>";
      });
    }

    if (QZ.marked && q.why) {
      h += '<div class="qzwhy">' + (m && m.correct ? "✓ " : "✕ ") +
           esc(q.why) + "</div>";
    }
    return h + "</div>";
  }

  function paint() {
    var host = document.getElementById("qzBox");
    if (!host) return;
    if (QZ.busy) {
      host.innerHTML = '<div class="qz"><div class="qzsub">' +
        "Writing the questions…</div></div>";
      return;
    }
    if (!QZ.qs) { host.innerHTML = ""; return; }
    if (!QZ.qs.length) {
      host.innerHTML = '<div class="qz"><div class="qzsub">' +
        "No usable questions came back. Try again.</div></div>";
      return;
    }

    var h = '<div class="qz"><h3>Check what landed</h3>' +
      '<div class="qzsub">' + QZ.qs.length + " questions on " +
      esc(QZ.topic.slice(0, 60)) + ". Picking, recalling and joining — " +
      "they test different things.</div>";
    QZ.qs.forEach(function (q, i) { h += qHTML(q, i); });

    if (QZ.marked) {
      var all = QZ.marked.score === QZ.marked.total;
      h += '<div class="qzscore ' + (all ? "qzall" : "qzsome") + '">' +
        QZ.marked.score + " of " + QZ.marked.total + " right" +
        (all ? " — that has landed."
             : " — the ones marked show what they should have said.") +
        "</div>" +
        '<button class="btn ghost sm" data-qzagain="1" ' +
        'style="margin-top:10px">Try another test</button>';
    } else {
      h += '<button class="btn" data-qzmark="1" style="margin-top:12px">' +
        "Mark it</button>";
    }
    host.innerHTML = h + "</div>";
  }

  async function mark() {
    if (!QZ.qs) return;
    try {
      QZ.marked = await api.post("/api/quiz/mark", {
        questions: QZ.qs, answers: QZ.answers
      });
    } catch (e) {
      toast((e && e.message) || "Could not mark that.");
      return;
    }
    paint();
  }

  document.addEventListener("click", function (e) {
    var t = e.target;
    if (!t.closest) return;
    var opt = t.closest("[data-opt]");
    if (opt) {
      QZ.answers[+opt.dataset.qz] = +opt.dataset.opt;
      paint();
      return;
    }
    if (t.closest("[data-qzmark]")) { mark(); return; }
    if (t.closest("[data-qzagain]")) { make(); return; }
  });

  document.addEventListener("input", function (e) {
    var g = e.target.closest && e.target.closest("[data-qzgap]");
    if (g) { QZ.answers[+g.dataset.qzgap] = g.value; return; }
  });

  document.addEventListener("change", function (e) {
    var p = e.target.closest && e.target.closest("[data-qzpair]");
    if (!p) return;
    var i = +p.dataset.qzpair;
    QZ.answers[i] = QZ.answers[i] || {};
    QZ.answers[i][p.dataset.left] = p.value;
  });

  window.QuizUI = { make: make };
})();
