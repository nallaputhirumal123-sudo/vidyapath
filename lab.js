/* The bench.
 *
 * Everything on this page is computed on the server from a table of real
 * reactions and closed-form physics — no model call, so it is free, instant,
 * and gives the same answer to everyone forever.
 *
 * The one interface decision worth stating: when a pair is not in the table,
 * this says so. It would be easy to hand the question to the tutor and print
 * a fluent paragraph, and that is exactly the thing a chemistry lab must not
 * do. A made-up reaction is not a wrong answer like a wrong date is a wrong
 * answer — somebody goes and mixes it.
 */
(function () {
  "use strict";

  var LB = {
    tab: "mix",
    shelf: null,
    a: "HCl", b: "NaOH", ga: 36.46, gb: 40,
    out: null,
    sim: {
      projectile: { speed: 20, angle: 45, height: 0 },
      circuit: { r: [100, 220, 330], volts: 12, series: true },
      pendulum: { length: 1, angle: 10 },
      lens: { focal: 50, object: 150 }
    },
    simOut: {}
  };
  window.LB = LB;

  var esc = window.esc || function (s) {
    return String(s).replace(/[&<>]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c];
    });
  };
  var $ = function (s) { return document.querySelector(s); };

  var CSS = [
    ".lbwrap{max-width:820px}",
    ".lbtabs{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:16px}",
    ".lbtab{font-size:12.5px;padding:7px 13px;border-radius:999px;",
    "  cursor:pointer;border:1px solid var(--line,#2a2a2a);",
    "  background:transparent;color:inherit}",
    ".lbtab.on{border-color:var(--accent,#ffb020);color:var(--accent,#ffb020)}",
    ".lbrow{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end;",
    "  margin-bottom:12px}",
    ".lbf{display:flex;flex-direction:column;gap:4px;min-width:120px}",
    ".lbf label{font-size:11px;letter-spacing:.4px;text-transform:uppercase;",
    "  color:var(--dim,#666);font-weight:700}",
    ".lbf select,.lbf input{font-size:13px;padding:8px 10px;border-radius:9px;",
    "  border:1px solid var(--line,#2a2a2a);background:var(--panel2,#0f0f0f);",
    "  color:var(--text,#eee)}",
    ".lbf input{width:110px}",
    ".lbeq{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:15px;",
    "  font-weight:700;padding:12px 14px;border-radius:10px;",
    "  background:var(--panel2,#0f0f0f);border:1px solid var(--line,#2a2a2a);",
    "  margin-bottom:12px;overflow-x:auto;white-space:nowrap}",
    ".lbsee{border:1px solid #3fae6a;background:rgba(63,174,106,.10);",
    "  border-radius:11px;padding:12px 14px;font-size:14px;line-height:1.6;",
    "  margin-bottom:11px}",
    ".lbhaz{border:1px solid #d9534f;background:rgba(217,83,79,.10);",
    "  border-radius:11px;padding:11px 13px;font-size:13px;line-height:1.6;",
    "  margin-bottom:11px}",
    ".lbnum{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));",
    "  gap:9px;margin-bottom:12px}",
    ".lbcell{border:1px solid var(--line,#2a2a2a);border-radius:10px;",
    "  padding:10px 12px}",
    ".lbcell b{display:block;font-size:18px;font-weight:800;line-height:1.2}",
    ".lbcell span{font-size:11px;color:var(--dim,#666);letter-spacing:.3px;",
    "  text-transform:uppercase;font-weight:700}",
    ".lbcell em{display:block;font-style:normal;font-size:11.5px;",
    "  color:var(--muted,#8a8a8a);margin-top:2px}",
    ".lbwhy{font-size:13px;line-height:1.75;color:var(--body,#ccc);",
    "  border-left:2px solid var(--accent,#ffb020);padding-left:12px;",
    "  margin-bottom:12px}",
    ".lbexp{border:1px solid var(--accent,#ffb020);border-radius:11px;",
    "  padding:13px 15px;margin-bottom:11px;",
    "  background:rgba(255,176,32,.07)}",
    ".lbexp b{display:block;font-size:13px;color:var(--accent,#ffb020);",
    "  margin-bottom:6px}",
    ".lbexp p{margin:0 0 8px;font-size:13.5px;line-height:1.7}",
    ".lbexp em{font-style:normal;font-size:11.5px;color:var(--muted,#8a8a8a);",
    "  line-height:1.55;display:block}",
    ".lbno{border:1px dashed var(--line,#2a2a2a);border-radius:11px;",
    "  padding:14px;font-size:13px;line-height:1.65;",
    "  color:var(--muted,#8a8a8a)}",
    ".lbplot{width:100%;height:auto;display:block;border-radius:10px;",
    "  border:1px solid var(--line,#2a2a2a);background:var(--panel2,#0f0f0f)}",
    ".lbgrid{overflow-x:auto;border:1px solid var(--line,#2a2a2a);",
    "  border-radius:10px;margin-bottom:12px}",
    ".lbgrid table{border-collapse:collapse;width:100%;font-size:12.5px;",
    "  font-family:ui-monospace,Menlo,Consolas,monospace}",
    ".lbgrid th{text-align:left;padding:7px 11px;font-weight:700;",
    "  background:var(--panel2,#0f0f0f);border-bottom:1px solid var(--line,#2a2a2a)}",
    ".lbgrid td{padding:6px 11px;border-bottom:1px solid var(--line,#1e1e1e)}"
  ].join("");

  function styles() {
    if (document.getElementById("lab-css")) return;
    var s = document.createElement("style");
    s.id = "lab-css";
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  async function load() {
    styles();
    if (!LB.shelf) {
      try { LB.shelf = await api.get("/api/lab"); }
      catch (e) { LB.shelf = { experiments: [], reagents: [], pairs: [] }; }
    }
    paint();
  }

  /* ------------------------------------------------------------------ */
  function paint() {
    var host = $("#main");
    if (!host) return;
    var exps = (LB.shelf && LB.shelf.experiments) || [];
    host.innerHTML = '<div class="lbwrap">' +
      '<h2 style="margin:0 0 4px">🧪 The lab</h2>' +
      '<p style="font-size:13px;color:var(--muted);margin:0 0 16px;' +
      'max-width:60ch">Practise, not watch. Every number here is worked out ' +
      'from the real balanced equation or the real formula — never guessed ' +
      'at — so you can change something and find out what actually happens. ' +
      'Free and unlimited: none of it costs a thing to run.</p>' +
      '<div class="lbtabs">' + exps.map(function (e) {
        return '<button class="lbtab' + (LB.tab === e.id ? " on" : "") +
          '" data-lbtab="' + e.id + '">' + esc(e.name) + "</button>";
      }).join("") + "</div>" +
      '<p style="font-size:12.5px;color:var(--muted);margin:-6px 0 14px">' +
      esc((exps.filter(function (e) { return e.id === LB.tab; })[0] || {}).ask
        || "") + "</p>" +
      (LB.tab === "mix" ? mixHtml() : simHtml(LB.tab)) +
      "</div>";
    wire();
  }

  /* ---- chemistry ---------------------------------------------------- */
  function mixHtml() {
    var rs = (LB.shelf && LB.shelf.reagents) || [];
    /* A text box with the shelf behind it, rather than a dropdown.
     *
     * The dropdown said, wrongly, that these seventeen are the only things
     * chemistry contains. Now you can type anything: if the pair has a
     * verified reaction behind it you get the real arithmetic, and if it does
     * not you get an explanation that is clearly labelled as an explanation.
     * Refusing to answer was a bad response to a good instinct. */
    function sel(id, val) {
      return '<input list="lbShelf" data-lbsel="' + id + '" value="' +
        esc(val) + '" placeholder="type or pick — e.g. HCl" ' +
        'autocomplete="off" spellcheck="false">';
    }
    var datalist = '<datalist id="lbShelf">' + rs.map(function (r) {
      return '<option value="' + esc(r.sym) + '">' + esc(r.name) + "</option>";
    }).join("") + "</datalist>";
    var h = datalist + '<div class="lbrow">' +
      '<div class="lbf"><label>First</label>' + sel("a", LB.a) + "</div>" +
      '<div class="lbf"><label>grams</label>' +
        '<input type="number" step="0.01" min="0" data-lbnum="ga" value="' +
        LB.ga + '"></div>' +
      '<div class="lbf"><label>Second</label>' + sel("b", LB.b) + "</div>" +
      '<div class="lbf"><label>grams</label>' +
        '<input type="number" step="0.01" min="0" data-lbnum="gb" value="' +
        LB.gb + '"></div>' +
      '<button class="btn" id="lbGo">Mix them</button></div>';

    var o = LB.out;
    if (!o) {
      return h + '<div class="lbno">Pick two things and how much of each. ' +
        "You will get the balanced equation, which reagent runs out first, " +
        "what is left in the flask and what you would actually see.</div>";
    }
    if (!o.ok) {
      if (o.known === false) {
        // Not on the shelf. Offer the explanation, and never let it look like
        // a simulated result: a number computed from a balanced equation and
        // a paragraph written by a model are different kinds of thing, and on
        // a chemistry bench they must not share a style.
        return h +
          (LB.explain
            ? '<div class="lbexp"><b>⚠ Explained, not simulated</b>' +
              '<p>' + esc(LB.explain) + "</p>" +
              '<em>This one has no verified reaction behind it, so this is an ' +
              "explanation rather than a computed result. Treat the numbers " +
              "in it with more suspicion than the ones on the bench.</em></div>"
            : '<div class="lbno">' + esc(o.error) + "</div>") +
          '<div class="scbar" style="margin-top:10px">' +
          '<button class="btn ghost sm" id="lbAsk"' +
          (LB.explainBusy ? " disabled" : "") + ">" +
          (LB.explainBusy ? "Working it out…"
            : LB.explain ? "Explain again" : "Explain what would happen") +
          "</button></div>";
      }
      return h + '<div class="lbno">' + esc(o.error) + "</div>";
    }

    h += '<div class="lbeq">' + esc(o.equation) + "</div>";
    h += '<div class="lbsee">👁 ' + esc(o.see) + "</div>";
    if (o.hazard) h += '<div class="lbhaz">⚠ ' + esc(o.hazard) + "</div>";

    h += '<div class="lbnum">' +
      cell("Runs out first", esc(o.limiting_name),
           "everything else is in excess") +
      cell("Reaction runs", o.runs_mol + " mol", "of the equation as written") +
      (o.gas_ml ? cell("Gas made", (o.gas_ml / 1000).toFixed(2) + " L",
                       "at room temperature") : "") +
      (o.temp_rise_c !== null && o.temp_rise_c !== undefined
        ? cell("Warms by", "+" + o.temp_rise_c + " °C", esc(o.temp_note))
        : "") +
      "</div>";

    h += '<div class="lbgrid"><table><thead><tr><th>In the flask at the end</th>' +
      "<th>grams</th></tr></thead><tbody>";
    Object.keys(o.products).forEach(function (k) {
      h += "<tr><td>" + esc(k) + " (made)</td><td>" + o.products[k] +
        "</td></tr>";
    });
    Object.keys(o.left_over).forEach(function (k) {
      if (o.left_over[k] > 0.001) {
        h += "<tr><td>" + esc(k) + " (left over)</td><td>" + o.left_over[k] +
          "</td></tr>";
      }
    });
    h += "</tbody></table></div>";
    h += '<div class="lbwhy">' + esc(o.why) + "</div>";
    return h;
  }

  function cell(label, big, note) {
    return '<div class="lbcell"><span>' + label + "</span><b>" + big + "</b>" +
      (note ? "<em>" + note + "</em>" : "") + "</div>";
  }

  /* ---- physics ------------------------------------------------------ */
  var FIELDS = {
    projectile: [["speed", "Speed (m/s)", 1, 200], ["angle", "Angle (°)", 0, 90],
                 ["height", "Launch height (m)", 0, 200]],
    pendulum: [["length", "Length (m)", 0.05, 50], ["angle", "Swing (°)", 1, 90]],
    lens: [["focal", "Focal length (mm)", -500, 500],
           ["object", "Object distance (mm)", 1, 5000]]
  };

  function simHtml(kind) {
    var v = LB.sim[kind] || {};
    var h = '<div class="lbrow">';
    if (kind === "circuit") {
      h += '<div class="lbf"><label>Resistors (ohms, comma separated)</label>' +
        '<input style="width:200px" data-lbtext="r" value="' +
        esc(v.r.join(", ")) + '"></div>' +
        '<div class="lbf"><label>Volts</label>' +
        '<input type="number" step="0.1" data-lbnum2="volts" value="' +
        v.volts + '"></div>' +
        '<div class="lbf"><label>Wiring</label><select data-lbwire="1">' +
        '<option value="s"' + (v.series ? " selected" : "") + ">Series</option>" +
        '<option value="p"' + (v.series ? "" : " selected") + ">Parallel</option>" +
        "</select></div>";
    } else {
      (FIELDS[kind] || []).forEach(function (f) {
        h += '<div class="lbf"><label>' + esc(f[1]) + "</label>" +
          '<input type="number" step="any" min="' + f[2] + '" max="' + f[3] +
          '" data-lbnum2="' + f[0] + '" value="' + v[f[0]] + '"></div>';
      });
    }
    h += '<button class="btn" id="lbRun">Run it</button></div>';

    var o = LB.simOut[kind];
    if (!o) return h + '<div class="lbno">Set the numbers and run it.</div>';
    if (!o.ok) return h + '<div class="lbno">' + esc(o.error) + "</div>";

    if (kind === "projectile") {
      h += '<div class="lbnum">' +
        cell("Range", o.range_m + " m", "") +
        cell("Highest point", o.peak_m + " m", "") +
        cell("Time in the air", o.flight_s + " s", "") +
        cell("Speed on landing", o.impact_ms + " m/s", "") + "</div>" +
        plot(o.path);
    } else if (kind === "circuit") {
      h += '<div class="lbnum">' +
        cell("Total resistance", o.total_r + " Ω", "") +
        cell("Current drawn", o.current_a + " A", "") +
        cell("Power", o.power_w + " W", "") + "</div>" +
        '<div class="lbgrid"><table><thead><tr><th>Resistor</th><th>Volts</th>' +
        "<th>Amps</th><th>Watts</th></tr></thead><tbody>" +
        o.per_resistor.map(function (x) {
          return "<tr><td>" + x.r + " Ω</td><td>" + x.v + "</td><td>" + x.i +
            "</td><td>" + x.w + "</td></tr>";
        }).join("") + "</tbody></table></div>";
    } else if (kind === "pendulum") {
      h += '<div class="lbnum">' +
        cell("Textbook period", o.period_small_s + " s", "small-angle formula") +
        cell("Real period", o.period_real_s + " s", "exact series") +
        cell("The formula is out by", o.error_pct + " %", "") + "</div>";
    } else if (kind === "lens") {
      h += '<div class="lbnum">' +
        (o.at_focus
          ? cell("No image", "—", "rays leave parallel")
          : cell("Image forms at", o.image_mm + " mm",
                 o.real ? "real — catch it on a screen"
                        : "virtual — only appears to be there") +
            cell("Magnification", o.magnification + "×",
                 o.inverted ? "upside down" : "upright")) + "</div>";
    }
    return h + '<div class="lbwhy">' + esc(o.why) + "</div>";
  }

  /* The trajectory, drawn from the points the server returned. No library —
     it is a polyline through 25 coordinates. */
  function plot(path) {
    if (!path || !path.length) return "";
    var xs = path.map(function (p) { return p[0]; });
    var ys = path.map(function (p) { return p[1]; });
    var mx = Math.max.apply(null, xs) || 1, my = Math.max.apply(null, ys) || 1;
    var W = 640, H = 240, pad = 26;
    var pts = path.map(function (p) {
      return (pad + (p[0] / mx) * (W - pad * 2)).toFixed(1) + "," +
        (H - pad - (p[1] / my) * (H - pad * 2)).toFixed(1);
    }).join(" ");
    return '<svg class="lbplot" viewBox="0 0 ' + W + " " + H +
      '" role="img" aria-label="Trajectory: peak ' + my.toFixed(1) +
      ' metres, range ' + mx.toFixed(1) + ' metres">' +
      '<line x1="' + pad + '" y1="' + (H - pad) + '" x2="' + (W - pad) +
      '" y2="' + (H - pad) + '" stroke="rgba(234,255,242,.3)"/>' +
      '<polyline points="' + pts + '" fill="none" stroke="#ffb020" ' +
      'stroke-width="2.2"/>' +
      '<text x="' + (W - pad) + '" y="' + (H - 8) +
      '" text-anchor="end" font-size="11" fill="#8fa3b0">' +
      mx.toFixed(1) + " m</text>" +
      '<text x="6" y="' + (pad + 4) + '" font-size="11" fill="#8fa3b0">' +
      my.toFixed(1) + " m</text></svg>";
  }

  /* ------------------------------------------------------------------ */
  async function mix() {
    LB.out = { ok: true, pending: true };
    LB.explain = "";
    try {
      LB.out = await api.post("/api/lab/mix",
        { a: LB.a, b: LB.b, grams_a: LB.ga, grams_b: LB.gb });
    } catch (e) {
      LB.out = { ok: false, error: e.message || "Could not run that." };
    }
    paint();
  }

  async function explain() {
    LB.explainBusy = true; LB.explain = ""; paint();
    try {
      var r = await api.post("/api/lab/explain", { a: LB.a, b: LB.b });
      LB.explain = r.text;
    } catch (e) {
      LB.explain = e.message || "Could not work that out.";
    }
    LB.explainBusy = false;
    paint();
  }

  async function run() {
    var kind = LB.tab;
    var v = LB.sim[kind];
    var values = kind === "circuit"
      ? { resistances: v.r, volts: v.volts, series: v.series }
      : v;
    try {
      LB.simOut[kind] = await api.post("/api/lab/sim",
        { kind: kind, values: values });
    } catch (e) {
      LB.simOut[kind] = { ok: false, error: e.message || "Could not run." };
    }
    paint();
  }

  function wire() {
    document.querySelectorAll("[data-lbtab]").forEach(function (el) {
      el.onclick = function () { LB.tab = el.dataset.lbtab; paint(); };
    });
    document.querySelectorAll("[data-lbsel]").forEach(function (el) {
      el.onchange = function () { LB[el.dataset.lbsel] = el.value; };
    });
    document.querySelectorAll("[data-lbnum]").forEach(function (el) {
      el.oninput = function () { LB[el.dataset.lbnum] = parseFloat(el.value) || 0; };
    });
    document.querySelectorAll("[data-lbnum2]").forEach(function (el) {
      el.oninput = function () {
        LB.sim[LB.tab][el.dataset.lbnum2] = parseFloat(el.value) || 0;
      };
    });
    var rt = document.querySelector("[data-lbtext=r]");
    if (rt) {
      rt.oninput = function () {
        LB.sim.circuit.r = rt.value.split(",")
          .map(function (x) { return parseFloat(x); })
          .filter(function (x) { return !isNaN(x) && x > 0; });
      };
    }
    var w = document.querySelector("[data-lbwire]");
    if (w) w.onchange = function () { LB.sim.circuit.series = w.value === "s"; };

    var go = document.getElementById("lbGo");
    if (go) go.onclick = mix;
    var rn = document.getElementById("lbRun");
    if (rn) rn.onclick = run;
    var ask = document.getElementById("lbAsk");
    if (ask) ask.onclick = explain;
  }

  window.renderLab = load;
})();
