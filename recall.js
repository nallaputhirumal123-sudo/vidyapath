/* Bring it back — the thing an assistant cannot do for you.
 *
 * Ask a chat assistant to explain recursion and it will do it better than any
 * lesson here. Then it forgets you, and by Thursday so do you. It has no
 * record of what you could not do on Monday and no reason to ask you again —
 * and that, not the quality of the explanation, is why people finish a
 * conversation certain they have learned something and cannot reproduce it a
 * week later. The explanation was never the hard part.
 *
 * Two rules, and they are the whole screen:
 *
 *   1. NEVER ANSWER FIRST. The question arrives without its answer, and the
 *      server does not send one until an attempt has been posted — the rule
 *      lives there rather than here, because a rule the page enforces is a
 *      rule anybody can skip by opening the network tab. Recognising an
 *      answer and being able to produce one are different skills, and only
 *      the second is the one anybody came for.
 *
 *   2. IT COMES BACK. Right and the gap widens; wrong and it is tomorrow.
 *
 * **You mark yourself, on purpose.** Anki has run on exactly this for fifteen
 * years: somebody who has just tried to produce something knows perfectly
 * well whether they could. Where an answer is a fact — a quiz option — the
 * server marks it instead, because asking somebody to grade themselves on
 * something a string comparison can settle invites the kindest possible
 * marking at exactly the wrong moment.
 *
 * Nothing here costs a model call. It is a table and a date, which is why it
 * can run for everybody on every visit — and why it gets better the longer
 * somebody uses it, which no single conversation ever does.
 */
(function (global) {
  "use strict";

  var R = {
    items: [], i: 0,
    due: 0, total: 0, solid: 0, nextAt: null, note: "",
    busy: false, err: "",
    shown: false,        // has the answer been released for this card
    attempt: "",
    result: null,        // what came back from marking
    done: false,
    adding: false, aQ: "", aA: "", aT: "",
    // Fetched at least once. Without it the render below re-fetches on every
    // repaint whenever the list is empty -- and since a fetch repaints, an
    // empty list span an infinite loop that sat on "Loading..." for ever.
    loaded: false
  };
  global.Revise = R;

  function repaint() {
    if (typeof render === "function") render();
  }

  R.load = async function () {
    R.busy = true; R.err = ""; repaint();
    try {
      var d = await api.get("/api/recall/due?limit=20");
      R.items = d.items || [];
      R.due = d.due || 0;
      R.total = d.total || 0;
      R.solid = d.solid || 0;
      R.nextAt = d.next_at || null;
      R.note = d.note || "";
      R.i = 0; R.shown = false; R.attempt = ""; R.result = null;
      R.done = !R.items.length;
    } catch (e) {
      R.err = e.message || "Could not load your revision.";
      R.items = [];
    }
    R.loaded = true;
    R.busy = false;
    repaint();
  };

  function card() { return R.items[R.i] || null; }

  /* The attempt is posted before the answer is asked for, which is what
     makes the answer worth seeing. */
  R.mark = async function (verdict) {
    var c = card();
    if (!c) return;
    var box = document.getElementById("rvAttempt");
    if (box) R.attempt = box.value || "";
    R.busy = true; repaint();
    try {
      R.result = await api.post("/api/recall/answer", {
        id: c.id, attempt: R.attempt, verdict: verdict || ""
      });
      R.shown = true;
    } catch (e) {
      R.err = e.message || "Could not save that.";
    }
    R.busy = false;
    repaint();
  };

  R.next = function () {
    R.shown = false; R.attempt = ""; R.result = null; R.err = "";
    if (R.i + 1 >= R.items.length) { R.done = true; return repaint(); }
    R.i += 1;
    repaint();
  };

  R.drop = async function () {
    var c = card();
    if (!c) return;
    try { await api.del("/api/recall/" + c.id); } catch (e) {}
    R.items.splice(R.i, 1);
    R.due = Math.max(0, R.due - 1);
    R.shown = false; R.attempt = ""; R.result = null;
    if (R.i >= R.items.length) R.done = true;
    repaint();
  };

  /* Adding your own. The list fills itself from what you get wrong, but the
     other half of revision is the thing you just read and know perfectly
     well you will not remember on Friday. */
  R.add = async function () {
    var q = (document.getElementById("rvNewQ") || {}).value || "";
    var a = (document.getElementById("rvNewA") || {}).value || "";
    var t = (document.getElementById("rvNewT") || {}).value || "";
    if (!q.trim()) { R.err = "Write the question first."; return repaint(); }
    R.busy = true; R.err = ""; repaint();
    try {
      await api.post("/api/recall/add", {
        kind: "ask", topic: t.trim(), prompt: q.trim(), expect: a.trim(),
        source: "added by hand"
      });
      R.adding = false; R.aQ = ""; R.aA = ""; R.aT = "";
      R.busy = false;
      await R.load();
      return;
    } catch (e) {
      R.err = e.message || "Could not keep that.";
    }
    R.busy = false; repaint();
  };

  function adderHTML() {
    if (!R.adding) {
      return '<button class="btn ghost sm" data-rvadd>+ Ask me something ' +
        'later</button>';
    }
    return '<div class="card" style="margin-bottom:12px">' +
      '<div class="eyebrow" style="margin:0 0 6px">Something to be asked later</div>' +
      '<input id="rvNewT" placeholder="Topic (optional)" value="' +
        escAttr(R.aT) + '" style="width:100%;margin-bottom:8px"/>' +
      '<textarea id="rvNewQ" class="pj-note" style="min-height:70px;width:100%" ' +
        'placeholder="The question. Write it as a question, not a heading — ' +
        'you cannot be tested on a heading.">' + esc(R.aQ) + '</textarea>' +
      '<textarea id="rvNewA" class="pj-note" style="min-height:70px;width:100%;' +
        'margin-top:8px" placeholder="The answer you want to be able to ' +
        'produce.">' + esc(R.aA) + '</textarea>' +
      (R.err ? '<div style="color:#e05a5a;font-size:13px;margin-top:8px">' +
        esc(R.err) + '</div>' : '') +
      '<div class="row" style="gap:8px;margin-top:10px">' +
        '<button class="btn ghost" data-rvcancel>Cancel</button>' +
        '<button class="btn" data-rvsave style="flex:1">Keep it</button>' +
      '</div></div>';
  }

  function escAttr(v) { return esc(v).replace(/"/g, "&quot;"); }

  function whenNext(iso) {
    if (!iso) return "";
    var days = Math.round((new Date(iso) - Date.now()) / 86400000);
    if (days <= 0) return "later today";
    if (days === 1) return "tomorrow";
    return "in " + days + " days";
  }

  function strengthBar(n) {
    var out = "";
    for (var i = 0; i < 6; i++) {
      out += '<span style="display:inline-block;width:14px;height:5px;' +
        'border-radius:3px;margin-right:3px;background:' +
        (i < n ? "var(--ok)" : "var(--line)") + '"></span>';
    }
    return out;
  }

  /* ---- the screen --------------------------------------------------- */
  function headerHTML() {
    return '<div class="h1">🔁 Bring it back</div>' +
      '<p class="sub">The things you could not do yet. Try each one before ' +
      'you look at the answer — recognising an answer and being able to ' +
      'produce one are different skills, and only the second one is the ' +
      'reason you are here.</p>' +
      '<div class="row" style="gap:20px;margin-bottom:18px;flex-wrap:wrap">' +
        '<div><div style="font-size:24px;font-weight:800;color:var(--accent)">' +
          R.due + '</div><div style="font-size:11.5px;color:var(--muted)">' +
          'due now</div></div>' +
        '<div><div style="font-size:24px;font-weight:800">' + R.total +
          '</div><div style="font-size:11.5px;color:var(--muted)">' +
          'being remembered</div></div>' +
        '<div><div style="font-size:24px;font-weight:800;color:var(--ok)">' +
          R.solid + '</div><div style="font-size:11.5px;color:var(--muted)">' +
          'solid</div></div>' +
      '</div>';
  }

  function emptyHTML() {
    return headerHTML() +
      '<div class="card" style="border-color:var(--ok)">' +
        '<b style="font-size:16px">Nothing to revise right now</b>' +
        '<div style="font-size:13.5px;color:var(--body);margin-top:6px;line-height:1.6">' +
        (R.total
          ? 'You are up to date. The next one comes back ' +
            esc(whenNext(R.nextAt)) + '.'
          : 'This fills itself in as you go. Whenever you get something ' +
            'wrong — a quiz, a query, an interview answer — it is kept here ' +
            'and put back in front of you before you forget it.') +
        '</div></div>' + adderHTML();
  }

  function doneHTML() {
    return headerHTML() +
      '<div class="card" style="border-color:var(--ok);margin-bottom:12px">' +
        '<b style="font-size:16px">Done for now</b>' +
        '<div style="font-size:13.5px;color:var(--body);margin-top:6px;line-height:1.6">' +
        'That is everything due. ' +
        (R.nextAt ? 'The next one comes back ' + esc(whenNext(R.nextAt)) + '.'
                  : '') +
        ' Coming back tomorrow is worth more than doing twice as much today — ' +
        'the gap is what makes it stick.</div></div>' +
      '<div class="row" style="gap:8px;flex-wrap:wrap">' +
      '<button class="btn ghost" data-rvreload>Check again</button>' +
      adderHTML() + '</div>';
  }

  R.html = function () {
    if (R.busy && !R.items.length) {
      return '<div class="card"><div style="color:var(--dim)">Loading…</div></div>';
    }
    if (R.err && !R.items.length) {
      return headerHTML() +
        '<div class="card" style="color:#e05a5a">' + esc(R.err) + '</div>';
    }
    if (!R.items.length) return emptyHTML();
    if (R.done) return doneHTML();

    var c = card();
    if (!c) return doneHTML();
    var res = R.result || {};
    var item = res.item || {};

    return headerHTML() +
      '<div class="card" style="margin-bottom:12px;border-color:var(--accent)">' +
        '<div class="row" style="gap:8px;align-items:baseline;flex-wrap:wrap">' +
          '<span class="pill" style="background:var(--accent);color:#1a1205;' +
          'font-weight:800">' + (R.i + 1) + ' OF ' + R.items.length + '</span>' +
          (c.topic ? '<span style="font-size:12.5px;color:var(--muted)">' +
            esc(c.topic) + '</span>' : '') +
          '<span style="margin-left:auto">' + strengthBar(c.strength || 0) +
          '</span>' +
        '</div>' +
        '<div style="font-size:17px;font-weight:650;line-height:1.5;margin-top:10px">' +
          esc(c.prompt) + '</div>' +
        (c.seen ? '<div style="font-size:11.5px;color:var(--dim);margin-top:8px">' +
          'seen ' + c.seen + ' time' + (c.seen === 1 ? '' : 's') +
          ' · right ' + (c.right || 0) + ' · missed ' + (c.wrong || 0) +
          '</div>' : '') +
      '</div>' +

      (!R.shown
        ? /* Attempt first. There is no "show me" button, and that is the
             entire point of the screen. */
          '<div class="card" style="margin-bottom:12px">' +
            '<div class="eyebrow" style="margin:0 0 6px">Your answer</div>' +
            '<textarea id="rvAttempt" class="pj-note" style="min-height:110px;' +
            'width:100%" placeholder="Write it out, even roughly. Getting it ' +
            'wrong on purpose here is worth more than reading it again.">' +
            esc(R.attempt) + '</textarea>' +
            '<div style="font-size:11.5px;color:var(--dim);margin-top:8px">' +
            esc(R.note) + '</div>' +
          '</div>' +
          (R.err ? '<div class="card" style="color:#e05a5a;font-size:13px;' +
            'margin-bottom:10px">' + esc(R.err) + '</div>' : '') +
          '<div class="row" style="gap:8px;flex-wrap:wrap">' +
            '<button class="btn" data-rvv="got" style="flex:1">I had it</button>' +
            '<button class="btn ghost" data-rvv="almost" style="flex:1">Almost</button>' +
            '<button class="btn ghost" data-rvv="missed" style="flex:1">Missed it</button>' +
          '</div>'

        : /* Only now. */
          '<div class="card" style="margin-bottom:12px;border-left:3px solid var(--ok)">' +
            '<div class="eyebrow" style="margin:0 0 4px">The answer</div>' +
            '<div style="font-size:14.5px;color:var(--body);line-height:1.7">' +
              esc(item.expect || "—") + '</div>' +
          '</div>' +
          (R.attempt
            ? '<div class="card" style="margin-bottom:12px">' +
              '<div class="eyebrow" style="margin:0 0 4px">What you wrote</div>' +
              '<div style="font-size:13px;color:var(--muted);line-height:1.6">' +
              esc(R.attempt) + '</div></div>'
            : '') +
          '<div class="card" style="margin-bottom:12px">' +
            '<div style="font-size:13.5px;color:var(--body)">' +
            (res.graded
              ? (res.verdict === "got"
                  ? '<b style="color:var(--ok)">Right.</b> '
                  : '<b style="color:var(--warn)">Not quite.</b> ') +
                'Marked against the answer, not on how it felt.'
              : 'Noted.') +
            ' Back ' + (res.next_in_days === 1 ? 'tomorrow'
                        : 'in ' + (res.next_in_days || 1) + ' days') + '.' +
            '</div></div>' +
          '<div class="row" style="gap:8px">' +
            '<button class="btn ghost" data-rvdrop>I know this — stop asking</button>' +
            '<button class="btn" data-rvnext style="flex:1">Next →</button>' +
          '</div>');
  };

  /* One delegated handler, so index.html knows about exactly one function. */
  R.click = function (e) {
    var el = e.target.closest("[data-rvv]");
    if (el) { R.mark(el.dataset.rvv); return true; }
    if (e.target.closest("[data-rvnext]")) { R.next(); return true; }
    if (e.target.closest("[data-rvdrop]")) { R.drop(); return true; }
    if (e.target.closest("[data-rvreload]")) { R.load(); return true; }
    if (e.target.closest("[data-rvadd]")) { R.adding = true; R.err = ""; repaint(); return true; }
    if (e.target.closest("[data-rvcancel]")) { R.adding = false; R.err = ""; repaint(); return true; }
    if (e.target.closest("[data-rvsave]")) { R.add(); return true; }
    return false;
  };

  /* Keeps the typed attempt across a repaint. */
  R.input = function (e) {
    if (e.target && e.target.id === "rvAttempt") {
      R.attempt = e.target.value;
      return true;
    }
    if (e.target && e.target.id === "rvNewQ") { R.aQ = e.target.value; return true; }
    if (e.target && e.target.id === "rvNewA") { R.aA = e.target.value; return true; }
    if (e.target && e.target.id === "rvNewT") { R.aT = e.target.value; return true; }
    return false;
  };

  global.renderRevise = function () {
    var main = document.querySelector("#main");
    if (main) main.innerHTML = R.html();
    // Once, not on every repaint.
    if (!R.loaded && !R.busy) R.load();
  };
})(window);
