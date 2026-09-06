/* The shortest route from your resume to this board.
 *
 * A job board tells you what exists. A course platform tells you what to
 * learn. Neither can tell you the thing that actually decides what somebody
 * does this evening: *which one skill stands between you and the most jobs
 * you already qualify for* — and then hand you the lesson for it.
 *
 * Both halves were already here and had never been joined. Postings carry
 * the skills they want, extracted at ingest from the same vocabulary a
 * resume is read with; the curriculum is sitting in tracks and lessons. This
 * is the join, and it is a set difference over stored columns — no model
 * call, nothing to bill, which is why it can run free on every visit.
 *
 * **The number that matters is "unlocks", not "demand".** How many postings
 * mention AWS is a statistic. How many postings you match on every single
 * requirement *except* AWS is a reason to start tonight. Ranking by mentions
 * puts the loudest skill on top and it is usually five skills away; ranking
 * by what it opens puts the nearest one on top. That is the whole idea.
 *
 * **Where it is honest about itself.** The curriculum covers a fraction of
 * what the board asks for, so most skills come back with no lesson. The page
 * says "no lesson yet" and still shows the jobs, because the count is true
 * whether or not we can teach it — and pretending otherwise would be the
 * one thing that makes the numbers untrustworthy.
 */
(function (global) {
  "use strict";

  var L = { data: null, busy: false, err: "", open: "" };
  global.Learn = L;

  function repaint() {
    if (typeof renderCareers === "function") renderCareers();
  }

  /* esc() escapes & < > and not quotes; job titles and company names come
     off crawled postings, so an attribute needs the stronger one. */
  function escAttr(v) { return esc(v).replace(/"/g, "&quot;"); }

  L.load = async function () {
    if (L.busy) return;
    L.busy = true; L.err = ""; repaint();
    try {
      L.data = await api.get("/api/career/next-skills?limit=10");
    } catch (e) {
      L.err = e.message || "Could not work that out.";
      L.data = null;
    }
    L.busy = false;
    repaint();
  };

  L.openTab = function () {
    if (!L.data && !L.busy) L.load();
  };

  function plural(n, one, many) { return n === 1 ? one : (many || one + "s"); }

  function lessonBtn(x) {
    /* data-nav="lesson" is the page's own navigation, so this reuses the
       existing click chain rather than inventing a second way to open a
       lesson. track.id and lesson.id are the slugs this API returns. */
    return '<button class="btn ghost sm" data-nav="lesson" data-track="' +
      escAttr(x.track) + '" data-id="' + escAttr(x.slug) + '" ' +
      'style="text-align:left;margin:0 6px 6px 0">' +
      esc(x.title) +
      (x.mins ? ' <span style="opacity:.65">· ' + x.mins + ' min</span>' : '') +
      '</button>';
  }

  function skillCard(s, i) {
    var lessons = s.lessons || [];
    var jobs = s.jobs || [];
    var openIt = L.open === s.skill;

    return '<div class="card" style="margin-bottom:12px' +
        (i === 0 ? ';border-color:var(--accent)' : '') + '">' +

      '<div class="row" style="gap:12px;align-items:baseline;flex-wrap:wrap">' +
        '<b style="font-size:17px;text-transform:capitalize">' + esc(s.skill) + '</b>' +
        (lessons.length
          ? '<span class="pill" style="background:var(--ok);color:#07240f;' +
            'font-weight:800">WE TEACH THIS</span>'
          : '<span class="pill" style="opacity:.6">no lesson yet</span>') +
        '<span style="margin-left:auto;font-size:22px;font-weight:800;' +
        'color:var(--accent)">' + s.unlocks +
        '<span style="font-size:12.5px;color:var(--muted);font-weight:600"> ' +
        plural(s.unlocks, 'job') + ' unlocked</span></span>' +
      '</div>' +

      '<div style="font-size:12.5px;color:var(--muted);margin-top:4px">' +
        'You match everything else these postings ask for.' +
        (s.nearly ? '  ·  ' + s.nearly + ' more ' + plural(s.nearly, 'is', 'are') +
          ' two skills away.' : '') +
        '  ·  ' + s.demand + ' ' + plural(s.demand, 'posting') + ' ask for it.' +
      '</div>' +

      (lessons.length
        ? '<div style="margin-top:10px">' +
          '<div class="eyebrow" style="margin:0 0 5px">Learn it here</div>' +
          lessons.slice(0, 3).map(lessonBtn).join("") +
          '</div>'
        : '<div style="margin-top:8px;font-size:12.5px;color:var(--dim)">' +
          'No lesson for this yet — the jobs are real either way.</div>') +

      (jobs.length
        ? '<div style="margin-top:10px">' +
          '<button class="btn ghost sm" data-lrjobs="' + escAttr(s.skill) + '">' +
          (openIt ? 'Hide the jobs' : 'Show the ' + plural(s.unlocks, 'job') +
            ' this opens →') + '</button>' +
          (openIt
            ? '<div style="margin-top:8px">' + jobs.map(function (j) {
                return '<div style="padding:7px 0;border-top:1px solid var(--line);' +
                  'font-size:13px;line-height:1.5">' +
                  '<b>' + esc(j.title) + '</b>' +
                  '<span style="color:var(--muted)"> · ' + esc(j.company) +
                  (j.location ? ' · ' + esc(j.location) : '') + '</span></div>';
              }).join("") +
              (s.unlocks > jobs.length
                ? '<div style="font-size:12px;color:var(--dim);margin-top:6px">' +
                  'and ' + (s.unlocks - jobs.length) + ' more.</div>' : '') +
              '</div>'
            : '') +
          '</div>'
        : '') +

      '</div>';
  }

  L.html = function () {
    if (L.busy && !L.data) {
      return '<div class="card"><div style="color:var(--dim);font-size:13.5px">' +
        'Reading your resume against every open posting…</div></div>';
    }
    if (L.err) {
      return '<div class="card" style="color:#e05a5a;font-size:13.5px">' +
        esc(L.err) + '</div>';
    }
    var d = L.data;
    if (!d) return '<div class="card"><div style="color:var(--dim)">Nothing yet.</div></div>';

    if (!d.ready) {
      return '<div class="card" style="border-color:var(--accent)">' +
        '<b style="font-size:16px">Add your resume first</b>' +
        '<div style="font-size:13.5px;color:var(--body);margin-top:6px;line-height:1.6">' +
        esc(d.message || "") + '</div>' +
        '<button class="btn" data-nav="resume" style="margin-top:10px">' +
        'Go to the resume builder →</button></div>';
    }

    var skills = d.skills || [];
    var top = skills[0];

    return '' +
      '<div class="card" style="margin-bottom:12px;border-color:var(--accent)">' +
        '<div class="eyebrow" style="margin:0 0 4px">What to learn next</div>' +
        '<b style="font-size:16px">The shortest route from your resume to this board</b>' +
        '<div style="font-size:13.5px;color:var(--body);margin-top:6px;line-height:1.6">' +
          (top
            ? 'Learn <b style="color:var(--accent);text-transform:capitalize">' +
              esc(top.skill) + '</b> and <b>' + top.unlocks + '</b> ' +
              plural(top.unlocks, 'posting') + ' open up that you already match ' +
              'on everything else.'
            : 'Your resume already covers every skill the postings on this ' +
              'board ask for.') +
        '</div>' +
        '<div class="row" style="gap:20px;margin-top:12px;flex-wrap:wrap">' +
          '<div><div style="font-size:24px;font-weight:800;color:var(--ok)">' +
            d.matched_now + '</div><div style="font-size:11.5px;color:var(--muted)">' +
            'you fully match today</div></div>' +
          '<div><div style="font-size:24px;font-weight:800">' + d.considered +
            '</div><div style="font-size:11.5px;color:var(--muted)">' +
            'open postings counted</div></div>' +
          '<div><div style="font-size:24px;font-weight:800">' + d.have_n +
            '</div><div style="font-size:11.5px;color:var(--muted)">' +
            'skills on your resume</div></div>' +
        '</div>' +
        '<div style="font-size:11.5px;color:var(--dim);margin-top:10px">' +
        'Ranked by what each skill <b>opens</b>, not by how often it is ' +
        'mentioned — the loudest skill on a board is usually five skills ' +
        'away. Uses no AI credits.</div>' +
      '</div>' +

      skills.map(skillCard).join("") +

      '<div style="font-size:11.5px;color:var(--dim);margin-top:4px;' +
      'padding:0 2px 8px">' + esc(d.basis || "") + '</div>';
  };

  /* Only the "show the jobs" toggle belongs to this tab. Lesson buttons
     carry data-nav and are deliberately left to the page's own click chain. */
  L.click = function (e) {
    var el = e.target.closest("[data-lrjobs]");
    if (el) {
      var s = el.dataset.lrjobs;
      L.open = (L.open === s) ? "" : s;
      repaint();
      return true;
    }
    return false;
  };
})(window);
