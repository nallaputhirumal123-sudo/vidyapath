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
      lens: { focal: 50, object: 150 },
      spring: { k: 200, mass: 0.5, x: 0.1 },
      collision: { m1: 2, u1: 3, m2: 1, u2: 0, elastic: true },
      gas: { p1: 100, v1: 1, t1: 300, p2: 200, t2: 300 },
      calorimetry: { mass_a: 0.1, temp_a: 80, mass_b: 0.1, temp_b: 20 },
      wave: { freq: 170, speed: 343, length: 1 },
      punnett: { a: "Aa", b: "Aa" },
      population: { n0: 100, rate: 0.1, steps: 12, capacity: 1000 },
      ph: { conc: 0.01, kind: "acid" }
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
      (LB.tab === "mix" ? mixHtml()
        : LB.tab === "any" ? anyHtml() : simHtml(LB.tab)) +
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

  /* Anything the five benches cannot compute.
   *
   * Kept visibly apart from them. The computed benches carry numbers that
   * came out of a balanced equation or a closed-form formula and can be
   * relied on; this one carries a written answer. Both are useful and they
   * are not the same, so this panel never borrows the numeric styling. */
  function anyHtml() {
    var h = '<div class="lbrow">' +
      '<div class="lbf" style="flex:1 1 100%"><label>What is the ' +
      'experiment?</label>' +
      '<input id="lbAnyQ" style="width:100%" maxlength="300" ' +
      'placeholder="e.g. a beam loaded at its centre, or bacteria in a ' +
      'nutrient broth" value="' + esc(LB.anyQ || "") + '"></div>' +
      '<div class="lbf"><label>Subject (optional)</label>' +
      '<input id="lbAnyS" maxlength="40" placeholder="biology" value="' +
      esc(LB.anyS || "") + '"></div>' +
      '<button class="btn" id="lbAnyGo"' + (LB.anyBusy ? " disabled" : "") +
      ">" + (LB.anyBusy ? "Working it out…" : "What would happen?") +
      "</button></div>";

    if (LB.anyOut) {
      h += '<div class="lbexp"><b>⚠ Explained, not simulated</b><p>' +
        esc(LB.anyOut) + "</p><em>The five benches beside this one compute " +
        "their numbers from a balanced equation or a formula. This one is a " +
        "written answer — good for understanding what would happen, and not " +
        "a measurement.</em></div>";
    } else if (!LB.anyBusy) {
      h += '<div class="lbno">Describe anything you would set up and ' +
        "observe — any subject. You get what would happen and why, and it " +
        "is labelled as an explanation rather than a computed result.</div>";
    }
    return h;
  }

  async function askAny() {
    var q = (document.getElementById("lbAnyQ") || {}).value || "";
    q = q.trim();
    if (!q) return;
    LB.anyQ = q;
    LB.anyS = ((document.getElementById("lbAnyS") || {}).value || "").trim();
    LB.anyBusy = true; LB.anyOut = ""; paint();
    try {
      var r = await api.post("/api/lab/explain",
        { what: q, subject: LB.anyS });
      LB.anyOut = r.text;
      if (typeof recordAsk === "function") recordAsk(q, "lab");
    } catch (e) {
      LB.anyOut = e.message || "Could not work that out.";
    }
    LB.anyBusy = false;
    paint();
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
           ["object", "Object distance (mm)", 1, 5000]],
    spring: [["k", "Stiffness k (N/m)", 1, 10000],
             ["mass", "Mass (kg)", 0.01, 100],
             ["x", "Pulled back (m)", 0, 2]],
    collision: [["m1", "Mass 1 (kg)", 0.01, 1000],
                ["u1", "Speed 1 (m/s)", -100, 100],
                ["m2", "Mass 2 (kg)", 0.01, 1000],
                ["u2", "Speed 2 (m/s)", -100, 100]],
    gas: [["p1", "Pressure before (kPa)", 1, 10000],
          ["v1", "Volume before (L)", 0.01, 1000],
          ["t1", "Temp before (K)", 1, 3000],
          ["p2", "Pressure after (kPa)", 0, 10000],
          ["t2", "Temp after (K)", 0, 3000]],
    calorimetry: [["mass_a", "Hot water (kg)", 0.001, 100],
                  ["temp_a", "Its temp (C)", -20, 150],
                  ["mass_b", "Cold water (kg)", 0.001, 100],
                  ["temp_b", "Its temp (C)", -20, 150]],
    wave: [["freq", "Frequency (Hz)", 0.1, 100000],
           ["speed", "Speed (m/s)", 0.1, 400000],
           ["length", "String length (m)", 0, 50]],
    population: [["n0", "Starting number", 1, 1000000],
                 ["rate", "Growth rate per step", -0.9, 2],
                 ["steps", "Steps", 1, 40],
                 ["capacity", "Carrying capacity", 0, 1000000]],
    ph: [["conc", "Concentration (mol/L)", 0.0000001, 12]]
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
    } else if (kind === "punnett") {
      h += '<div class="lbf"><label>Parent 1</label>' +
        '<input maxlength="2" data-lbtext2="a" value="' + esc(v.a) + '"></div>' +
        '<div class="lbf"><label>Parent 2</label>' +
        '<input maxlength="2" data-lbtext2="b" value="' + esc(v.b) + '"></div>' +
        '<div class="lbf" style="min-width:200px"><label>&nbsp;</label>' +
        '<span style="font-size:11.5px;color:var(--muted)">Capital is ' +
        'dominant — Aa, aa, AA</span></div>';
    } else {
      (FIELDS[kind] || []).forEach(function (f) {
        h += '<div class="lbf"><label>' + esc(f[1]) + "</label>" +
          '<input type="number" step="any" min="' + f[2] + '" max="' + f[3] +
          '" data-lbnum2="' + f[0] + '" value="' + v[f[0]] + '"></div>';
      });
    }
    if (kind === "collision") {
      h += '<div class="lbf"><label>Collision</label>' +
        '<select data-lbpick="elastic">' +
        '<option value="e"' + (v.elastic ? " selected" : "") +
        ">Elastic (bounces)</option>" +
        '<option value="i"' + (v.elastic ? "" : " selected") +
        ">Inelastic (they stick)</option></select></div>";
    }
    if (kind === "ph") {
      h += '<div class="lbf"><label>Which</label>' +
        '<select data-lbpick="kind">' +
        '<option value="acid"' + (v.kind === "acid" ? " selected" : "") +
        ">Strong acid</option>" +
        '<option value="base"' + (v.kind === "base" ? " selected" : "") +
        ">Strong base</option></select></div>";
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
    } else if (kind === "spring") {
      h += '<div class="lbnum">' +
        cell("Force at that stretch", o.force_n + " N", "") +
        cell("Energy stored", o.energy_j + " J", "") +
        cell("Period", o.period_s + " s", "one full swing") +
        cell("Fastest it moves", o.max_speed_ms + " m/s", "at the middle") +
        "</div>";
    } else if (kind === "collision") {
      h += '<div class="lbnum">' +
        cell("Mass 1 after", o.v1 + " m/s", "") +
        cell("Mass 2 after", o.v2 + " m/s", "") +
        cell("Momentum", o.p_before + " → " + o.p_after,
             "conserved, always") +
        cell("Kinetic energy", o.ke_before + " → " + o.ke_after + " J",
             o.ke_lost_j > 0.001 ? o.ke_lost_j + " J lost to heat and sound"
                                 : "none lost") +
        "</div>";
    } else if (kind === "gas") {
      h += '<div class="lbnum">' +
        cell("Amount of gas", o.moles + " mol", o.molecules + " molecules") +
        (o.v2_l !== undefined ? cell("Volume after", o.v2_l + " L", "") : "") +
        (o.p2_kpa !== undefined ? cell("Pressure after", o.p2_kpa + " kPa", "") : "") +
        (o.t2_k !== undefined ? cell("Temperature after", o.t2_k + " K", "") : "") +
        "</div>";
    } else if (kind === "calorimetry") {
      h += '<div class="lbnum">' +
        cell("Settles at", o.final_c + " °C", "") +
        cell("Heat that moved", o.heat_moved_kj + " kJ",
             o.heat_moved_j + " joules") + "</div>";
    } else if (kind === "wave") {
      h += '<div class="lbnum">' +
        cell("Wavelength", o.wavelength_m + " m", "") +
        cell("Speed", o.speed_ms + " m/s", "") +
        cell("Period", o.period_s + " s", "") +
        (o.fundamental_hz ? cell("Fundamental", o.fundamental_hz + " Hz",
          "harmonics: " + o.harmonics_hz.join(", ")) : "") + "</div>";
    } else if (kind === "punnett") {
      h += '<div class="lbgrid" style="max-width:280px"><table><tbody>' +
        "<tr><td>" + esc(o.grid[0]) + "</td><td>" + esc(o.grid[1]) +
        "</td></tr><tr><td>" + esc(o.grid[2]) + "</td><td>" +
        esc(o.grid[3]) + "</td></tr></tbody></table></div>" +
        '<div class="lbnum">' +
        cell("Genotypes", esc(o.genotype_ratio), "") +
        cell("Phenotypes", esc(o.phenotype_ratio),
             o.pct_dominant + "% show the dominant trait") + "</div>";
    } else if (kind === "population") {
      var last = o.exponential[o.exponential.length - 1];
      h += '<div class="lbnum">' +
        cell("After " + o.steps + " steps", String(last), "unchecked") +
        (o.logistic ? cell("With a ceiling",
          String(o.logistic[o.logistic.length - 1]),
          "capacity " + o.capacity) : "") +
        (o.doubling_time ? cell("Doubles every", o.doubling_time + " steps", "")
                         : "") + "</div>" +
        popPlot(o);
    } else if (kind === "ph") {
      h += '<div class="lbnum">' +
        cell("pH", String(o.ph), o.verdict) +
        cell("pOH", String(o.poh), "") +
        cell("H+ concentration", o.h_conc + " mol/L", "") + "</div>";
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

  /* Growth is the one bench whose answer is a shape rather than a number, so
     it borrows the sketch renderer rather than printing forty figures. */
  function popPlot(o) {
    if (!window.Sketch) return "";
    setTimeout(function () {
      var el = document.getElementById("lbPop");
      if (!el) return;
      var series = [{ name: "unchecked",
                      points: o.exponential.map(function (v, i) { return [i, v]; }) }];
      if (o.logistic) {
        series.push({ name: "with a ceiling", dashed: true,
                      points: o.logistic.map(function (v, i) { return [i, v]; }) });
      }
      Sketch.mount(el, { kind: "plot", height: 260, x: "steps",
                         y: "population", series: series });
    }, 0);
    return '<div id="lbPop" style="margin-bottom:12px"></div>';
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
    document.querySelectorAll("[data-lbtext2]").forEach(function (el) {
      el.oninput = function () { LB.sim[LB.tab][el.dataset.lbtext2] = el.value; };
    });
    document.querySelectorAll("[data-lbpick]").forEach(function (el) {
      el.onchange = function () {
        var key = el.dataset.lbpick;
        LB.sim[LB.tab][key] = key === "elastic" ? el.value === "e" : el.value;
      };
    });

    var go = document.getElementById("lbGo");
    if (go) go.onclick = mix;
    var rn = document.getElementById("lbRun");
    if (rn) rn.onclick = run;
    var ask = document.getElementById("lbAsk");
    if (ask) ask.onclick = explain;
    var anyGo = document.getElementById("lbAnyGo");
    if (anyGo) anyGo.onclick = askAny;
    var anyQ = document.getElementById("lbAnyQ");
    if (anyQ) {
      anyQ.onkeydown = function (e) {
        if (e.key === "Enter") { e.preventDefault(); askAny(); }
      };
    }
  }

  window.renderLab = load;
})();
