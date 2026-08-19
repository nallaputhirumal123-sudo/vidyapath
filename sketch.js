/* Flat drawings, on a canvas.
 *
 * Canvas rather than SVG for two reasons. The board's SVG diagrams were taken
 * out because six labels and an edge list produced a picture that said less
 * than the sentence beside it, and reintroducing the same technology under a
 * new name would invite the same result. And drawing imperatively means the
 * layout is decided here, in code that can measure text before it places it —
 * which is what stops labels landing on each other, the problem that has
 * dogged every diagram in this product.
 *
 * Everything is drawn from validated numbers and short labels. No markup
 * reaches this file, so there is nothing to escape.
 *
 * Redrawn on resize and on theme change, because a chart with dark axes on a
 * dark background is not a chart.
 */
(function () {
  "use strict";

  var PAL = ["#ffb020", "#7fb8ff", "#8fe3b0", "#d98fb0", "#c9a0ff"];

  function ink() {
    // Read the page's own colours so a sketch belongs to the board it is on.
    var cs = getComputedStyle(document.documentElement);
    var t = (cs.getPropertyValue("--text") || "#eaeaea").trim();
    var m = (cs.getPropertyValue("--muted") || "#8a8a8a").trim();
    var l = (cs.getPropertyValue("--line") || "#2a2a2a").trim();
    return { text: t, muted: m, line: l };
  }

  function hex(n, fallback) {
    if (n === undefined || n === null) return fallback;
    return "#" + ("000000" + n.toString(16)).slice(-6);
  }

  /* ---- helpers ------------------------------------------------------ */
  function arrow(c, x1, y1, x2, y2, col, w) {
    c.strokeStyle = col;
    c.fillStyle = col;
    c.lineWidth = w || 2;
    c.beginPath();
    c.moveTo(x1, y1);
    c.lineTo(x2, y2);
    c.stroke();
    var a = Math.atan2(y2 - y1, x2 - x1), h = 9;
    c.beginPath();
    c.moveTo(x2, y2);
    c.lineTo(x2 - h * Math.cos(a - 0.4), y2 - h * Math.sin(a - 0.4));
    c.lineTo(x2 - h * Math.cos(a + 0.4), y2 - h * Math.sin(a + 0.4));
    c.closePath();
    c.fill();
  }

  /* Where labels have already been put on this canvas.
   *
   * Canvas draws immediately, so a label cannot be moved once it is down —
   * the only way to stop two overlapping is to check before drawing. Every
   * chip records its box here and the next one is nudged clear of them.
   * Reset per render, which is what makes it work on resize too. */
  var placed = [];

  function freeSpot(x, y, w, h) {
    for (var pass = 0; pass < 24; pass++) {
      var clash = false;
      for (var i = 0; i < placed.length; i++) {
        var p = placed[i];
        if (Math.abs(x - p.x) < (w + p.w) / 2 + 2 &&
            Math.abs(y - p.y) < (h + p.h) / 2 + 2) { clash = true; break; }
      }
      if (!clash) break;
      // Alternate above and below the wanted spot, widening each time, so a
      // label ends up as near where it belongs as it can get.
      y += (pass % 2 ? 1 : -1) * (h + 3) * Math.ceil((pass + 1) / 2);
    }
    placed.push({ x: x, y: y, w: w, h: h });
    return y;
  }

  /* Text with a plate behind it. Cheap, and it means a label crossing a line
     or a filled shape stays readable without any layout cleverness. */
  function chip(c, text, x, y, col, align) {
    c.font = "600 12px system-ui, -apple-system, sans-serif";
    var w = c.measureText(text).width;
    var ox = align === "right" ? -w - 10 : align === "center" ? -w / 2 - 5 : 0;
    y = freeSpot(x + ox + w / 2, y, w + 10, 18);
    c.fillStyle = "rgba(10,12,16,.72)";
    c.beginPath();
    var r = 5, x0 = x + ox - 5, y0 = y - 11, ww = w + 10, hh = 18;
    c.moveTo(x0 + r, y0);
    c.arcTo(x0 + ww, y0, x0 + ww, y0 + hh, r);
    c.arcTo(x0 + ww, y0 + hh, x0, y0 + hh, r);
    c.arcTo(x0, y0 + hh, x0, y0, r);
    c.arcTo(x0, y0, x0 + ww, y0, r);
    c.fill();
    c.fillStyle = col;
    c.fillText(text, x + ox, y + 3);
    return w;
  }

  function plain(c, text, x, y, col, size, align, keep) {
    c.font = (size || 11) + "px system-ui, -apple-system, sans-serif";
    // Axis numbers and gridline values opt out: they are laid out on a grid
    // already and nudging one off its tick makes it a lie.
    if (!keep) {
      var w = c.measureText(text).width;
      var cx = align === "center" ? x : align === "right" ? x - w / 2 : x + w / 2;
      y = freeSpot(cx, y, w, (size || 11) + 4);
    }
    c.fillStyle = col;
    c.textAlign = align || "left";
    c.fillText(text, x, y);
    c.textAlign = "left";
  }

  /* ---- the drawings -------------------------------------------------- */
  var DRAW = {};

  DRAW.plot = function (c, s, W, H) {
    var I = ink(), L = 54, R = 16, T = 18, B = 40;
    var all = [];
    s.series.forEach(function (x) { all = all.concat(x.points); });
    var xs = all.map(function (p) { return p[0]; });
    var ys = all.map(function (p) { return p[1]; });
    var x0 = Math.min.apply(null, xs), x1 = Math.max.apply(null, xs);
    var y0 = Math.min.apply(null, ys), y1 = Math.max.apply(null, ys);
    if (x1 === x0) x1 = x0 + 1;
    if (y1 === y0) y1 = y0 + 1;
    // A little air, and include zero when it is nearly in range — a bar of
    // values from 98 to 102 drawn without zero exaggerates by twenty times.
    var pad = (y1 - y0) * 0.12;
    y0 -= pad; y1 += pad;
    if (y0 > 0 && y0 < (y1 - y0) * 0.35) y0 = 0;

    var px = function (v) { return L + (v - x0) / (x1 - x0) * (W - L - R); };
    var py = function (v) { return H - B - (v - y0) / (y1 - y0) * (H - T - B); };

    // Gridlines and their values, which is the entire point of a plot.
    c.strokeStyle = I.line;
    c.lineWidth = 1;
    for (var g = 0; g <= 4; g++) {
      var gy = H - B - g / 4 * (H - T - B);
      c.beginPath(); c.moveTo(L, gy); c.lineTo(W - R, gy); c.stroke();
      plain(c, (y0 + g / 4 * (y1 - y0)).toFixed(
        Math.abs(y1 - y0) < 10 ? 1 : 0), L - 7, gy + 4, I.muted, 11, "right", 1);
    }
    for (var gx = 0; gx <= 4; gx++) {
      var vx = x0 + gx / 4 * (x1 - x0);
      plain(c, (Math.abs(x1 - x0) < 10 ? vx.toFixed(1) : vx.toFixed(0)),
            px(vx), H - B + 16, I.muted, 11, "center", 1);
    }
    c.strokeStyle = I.muted;
    c.beginPath(); c.moveTo(L, T); c.lineTo(L, H - B); c.lineTo(W - R, H - B);
    c.stroke();
    if (s.x) plain(c, s.x, (L + W - R) / 2, H - 8, I.muted, 11.5, "center");
    if (s.y) {
      c.save(); c.translate(13, (T + H - B) / 2); c.rotate(-Math.PI / 2);
      plain(c, s.y, 0, 0, I.muted, 11.5, "center"); c.restore();
    }

    s.series.forEach(function (ser, i) {
      var col = hex(ser.color, PAL[i % PAL.length]);
      c.strokeStyle = col; c.lineWidth = 2.2;
      c.setLineDash(ser.dashed ? [6, 5] : []);
      c.beginPath();
      ser.points.forEach(function (p, k) {
        var X = px(p[0]), Y = py(p[1]);
        if (k) c.lineTo(X, Y); else c.moveTo(X, Y);
      });
      c.stroke();
      c.setLineDash([]);
      if (ser.name) {
        var last = ser.points[ser.points.length - 1];
        chip(c, ser.name, Math.min(px(last[0]) + 6, W - R - 4),
             py(last[1]), col, px(last[0]) > W - 90 ? "right" : "left");
      }
    });

    (s.marks || []).forEach(function (m) {
      var X = px(m.x), Y = py(m.y);
      c.fillStyle = I.text;
      c.beginPath(); c.arc(X, Y, 3.5, 0, 7); c.fill();
      chip(c, m.label, X, Y - 12, I.text, "center");
    });
  };

  DRAW.bar = function (c, s, W, H) {
    var I = ink(), L = 54, R = 16, T = 18, B = 46;
    var vals = s.bars.map(function (b) { return b.value; });
    var top = Math.max.apply(null, vals), bot = Math.min.apply(null, vals);
    if (bot > 0) bot = 0;
    if (top === bot) top = bot + 1;
    var py = function (v) { return H - B - (v - bot) / (top - bot) * (H - T - B); };
    var gap = (W - L - R) / s.bars.length;

    c.strokeStyle = I.line;
    for (var g = 0; g <= 4; g++) {
      var gy = H - B - g / 4 * (H - T - B);
      c.beginPath(); c.moveTo(L, gy); c.lineTo(W - R, gy); c.stroke();
      plain(c, (bot + g / 4 * (top - bot)).toFixed(0), L - 7, gy + 4,
            I.muted, 11, "right", 1);
    }
    if (s.y) {
      c.save(); c.translate(13, (T + H - B) / 2); c.rotate(-Math.PI / 2);
      plain(c, s.y, 0, 0, I.muted, 11.5, "center"); c.restore();
    }
    s.bars.forEach(function (b, i) {
      var x = L + i * gap + gap * 0.18, w = gap * 0.64;
      var y = py(b.value), zero = py(0);
      c.fillStyle = hex(b.color, PAL[i % PAL.length]);
      c.fillRect(x, Math.min(y, zero), w, Math.abs(zero - y));
      plain(c, String(b.value), x + w / 2, y - 6, I.text, 11.5, "center");
      plain(c, b.name, x + w / 2, H - B + 16, I.muted, 11, "center");
    });
  };

  /* A table.
   *
   * The board could not draw one at all, so every lesson whose real shape is
   * a table — active against passive, the alkali metals down a column,
   * reactants against products — arrived as prose describing a table. That is
   * the hardest form to read and the easiest to write, which is exactly the
   * wrong way round.
   *
   * Column widths come from the content, not from an equal split: a column of
   * one-word labels beside a column of sentences should not get half the
   * board each. Measured from the actual text, then scaled to fit.
   */
  DRAW.table = function (c, s, W, H) {
    var I = ink(), L = 8, R = 8, T = 6;
    var cols = s.columns, rows = s.rows;
    var n = cols.length;

    c.font = "12px system-ui, -apple-system, sans-serif";
    var want = cols.map(function (h, i) {
      var w = c.measureText(h).width;
      rows.forEach(function (r) {
        w = Math.max(w, c.measureText(r[i] || "").width);
      });
      return w + 22;
    });
    var total = want.reduce(function (a, b) { return a + b; }, 0);
    var avail = W - L - R;
    var widths = want.map(function (w) { return w / total * avail; });
    // Nothing narrower than will hold its own heading's first word, or the
    // heading is what gets clipped — and a table whose headings are cut off
    // is a grid of numbers with no meaning attached.
    var min = Math.min(64, avail / n);
    var short = 0;
    widths = widths.map(function (w) {
      if (w < min) { short += min - w; return min; }
      return w;
    });
    if (short > 0) {
      var slack = widths.reduce(function (a, w) {
        return a + Math.max(0, w - min); }, 0);
      if (slack > short) {
        widths = widths.map(function (w) {
          return w > min ? w - (w - min) / slack * short : w; });
      }
    }

    var rowH = Math.min(30, Math.max(20, (H - T - 34) / Math.max(1, rows.length)));
    var headH = rowH + 4;

    // The heading band, so the first row reads as headings rather than data.
    c.fillStyle = I.line;
    c.globalAlpha = 0.55;
    c.fillRect(L, T, avail, headH);
    c.globalAlpha = 1;

    var x = L;
    cols.forEach(function (h, i) {
      c.font = "600 12px system-ui, -apple-system, sans-serif";
      plain(c, clipTo(c, h, widths[i] - 16), x + 8, T + headH / 2 + 4,
            I.text, 12, "left", 1);
      x += widths[i];
    });

    c.strokeStyle = I.line;
    c.lineWidth = 1;
    var y = T + headH;
    rows.forEach(function (r, k) {
      // A faint band on every other row. Ruled lines between every row make
      // a dense grid; alternating shade tracks across a wide table better.
      if (k % 2) {
        c.fillStyle = I.line;
        c.globalAlpha = 0.22;
        c.fillRect(L, y, avail, rowH);
        c.globalAlpha = 1;
      }
      var cx = L;
      r.forEach(function (cell, i) {
        c.font = "12px system-ui, -apple-system, sans-serif";
        if (cell) {
          plain(c, clipTo(c, cell, widths[i] - 16), cx + 8, y + rowH / 2 + 4,
                I.text, 12, "left", 1);
        }
        cx += widths[i];
      });
      y += rowH;
    });

    // The frame and the column rules, drawn last so no fill covers them.
    c.strokeStyle = I.line;
    c.strokeRect(L, T, avail, y - T);
    c.beginPath();
    c.moveTo(L, T + headH); c.lineTo(L + avail, T + headH);
    var rx = L;
    for (var i = 0; i < n - 1; i++) {
      rx += widths[i];
      c.moveTo(rx, T); c.lineTo(rx, y);
    }
    c.stroke();
  };

  /* Text that fits its column, with an ellipsis when it does not. Clipped
     rather than wrapped: a wrapped cell changes the row height, and a table
     whose rows are different heights is harder to read across than one with
     a truncated cell in it. */
  function clipTo(c, text, max) {
    if (max <= 8) return "";
    if (c.measureText(text).width <= max) return text;
    var s = text;
    while (s.length > 1 && c.measureText(s + "…").width > max) {
      s = s.slice(0, -1);
    }
    return s + "…";
  }

  /* A share as a percentage, at the precision it deserves.
   *
   * Rounding everything to a whole number put "0%" beside carbon dioxide in
   * a pie of dry air, which is both wrong and the single most interesting
   * number on that chart. Anything under one per cent says so rather than
   * claiming a false zero. */
  function pctOf(frac) {
    var p = frac * 100;
    if (p >= 10) return Math.round(p) + "%";
    if (p >= 1) return p.toFixed(1) + "%";
    return "<1%";
  }

  /* A pie.
   *
   * The share of a whole, which is the one thing a bar chart genuinely does
   * not say: the composition of air, where a rupee of tax goes, the split of
   * a population. Percentages are computed here from the values rather than
   * taken as given — asked for both, a model will sooner or later send values
   * that do not add to its own percentages, and then the drawing argues with
   * the label on it.
   */
  DRAW.pie = function (c, s, W, H) {
    var I = ink();
    var total = s.slices.reduce(function (a, x) { return a + x.value; }, 0);
    if (!(total > 0)) return;

    // The legend takes the right-hand third; the pie centres in what is left.
    var legendW = Math.min(200, Math.max(120, W * 0.34));
    var cx = (W - legendW) / 2;
    var cy = H / 2;
    var r = Math.max(30, Math.min((W - legendW) / 2 - 14, H / 2 - 18));

    var a0 = -Math.PI / 2;   // start at twelve o'clock, as a pie is read
    s.slices.forEach(function (sl, i) {
      var frac = sl.value / total;
      var a1 = a0 + frac * Math.PI * 2;
      var col = hex(sl.color, PAL[i % PAL.length]);
      c.fillStyle = col;
      c.beginPath();
      c.moveTo(cx, cy);
      c.arc(cx, cy, r, a0, a1);
      c.closePath();
      c.fill();
      // A hairline between slices, so two similar colours still separate.
      c.strokeStyle = I.line;
      c.lineWidth = 1.5;
      c.stroke();

      // The percentage rides on the slice when there is room for it, and
      // goes to the legend when there is not. A number half off its own
      // slice is worse than a number in a list.
      if (frac > 0.07) {
        var mid = (a0 + a1) / 2;
        plain(c, pctOf(frac), cx + Math.cos(mid) * r * 0.62,
              cy + Math.sin(mid) * r * 0.62 + 4, "#101418", 12, "center", 1);
      }
      a0 = a1;
    });

    var ly = cy - (s.slices.length * 20) / 2 + 10;
    s.slices.forEach(function (sl, i) {
      var col = hex(sl.color, PAL[i % PAL.length]);
      var lx = W - legendW + 6;
      c.fillStyle = col;
      c.fillRect(lx, ly - 9, 11, 11);
      c.font = "11.5px system-ui, -apple-system, sans-serif";
      plain(c, clipTo(c, sl.name, legendW - 62), lx + 17, ly, I.text,
            11.5, "left", 1);
      plain(c, pctOf(sl.value / total), W - 8, ly, I.muted, 11.5, "right", 1);
      ly += 20;
    });

    if (s.unit) {
      plain(c, "of " + s.unit, cx, H - 4, I.muted, 11, "center", 1);
    }
  };

  DRAW.timeline = function (c, s, W, H) {
    // Wide margins. The line used to run to within 30px of each edge, so
    // the first and last events — the two that matter most on a timeline —
    // were the two whose labels got cut off.
    var I = ink(), L = 78, R = 78;
    var y = H / 2;
    c.strokeStyle = I.muted; c.lineWidth = 2;
    c.beginPath(); c.moveTo(L, y); c.lineTo(W - R, y); c.stroke();
    var step = (W - L - R) / Math.max(1, s.events.length - 1);
    s.events.forEach(function (e, i) {
      var x = L + i * step, up = i % 2 === 0;
      var col = PAL[i % PAL.length];
      c.strokeStyle = col; c.lineWidth = 1.5;
      c.beginPath(); c.moveTo(x, y); c.lineTo(x, up ? y - 34 : y + 34); c.stroke();
      c.fillStyle = col;
      c.beginPath(); c.arc(x, y, 5, 0, 7); c.fill();
      // Alternating above and below, so eight events fit without touching.
      chip(c, e.name, x, up ? y - 42 : y + 50, I.text, "center");
      if (e.at) plain(c, e.at, x, up ? y - 60 : y + 68, col, 11.5, "center");
      if (e.note) {
        plain(c, e.note, x, up ? y - 76 : y + 84, I.muted, 10.5, "center");
      }
    });
  };

  DRAW.tree = function (c, s, W, H) {
    var I = ink();
    var byDepth = {};
    s.nodes.forEach(function (n, i) {
      (byDepth[n.depth] = byDepth[n.depth] || []).push(i);
    });
    var depths = Object.keys(byDepth).length;
    var pos = [];
    Object.keys(byDepth).forEach(function (d) {
      var row = byDepth[d];
      row.forEach(function (idx, k) {
        pos[idx] = {
          x: (W / (row.length + 1)) * (k + 1),
          y: 30 + (+d) * ((H - 60) / Math.max(1, depths - 1))
        };
      });
    });
    c.strokeStyle = I.line; c.lineWidth = 1.6;
    s.edges.forEach(function (e) {
      var a = pos[e[0]], b = pos[e[1]];
      if (!a || !b) return;
      c.beginPath();
      c.moveTo(a.x, a.y + 10);
      c.bezierCurveTo(a.x, (a.y + b.y) / 2, b.x, (a.y + b.y) / 2, b.x, b.y - 10);
      c.stroke();
      if (e[2]) {
        plain(c, e[2], (a.x + b.x) / 2, (a.y + b.y) / 2 + 4, I.muted, 10,
              "center");
      }
    });
    s.nodes.forEach(function (n, i) {
      var p = pos[i];
      if (p) chip(c, n.name, p.x, p.y, I.text, "center");
    });
  };

  DRAW.forces = function (c, s, W, H) {
    var I = ink(), cx = W / 2, cy = H / 2;
    if (s.surface) {
      c.strokeStyle = I.muted; c.lineWidth = 2;
      c.beginPath(); c.moveTo(cx - 130, cy + 40); c.lineTo(cx + 130, cy + 40);
      c.stroke();
      for (var h = -125; h < 130; h += 14) {
        c.beginPath(); c.moveTo(cx + h, cy + 40);
        c.lineTo(cx + h - 8, cy + 50); c.stroke();
      }
      plain(c, s.surface, cx + 132, cy + 54, I.muted, 11, "right");
    }
    c.fillStyle = "rgba(127,184,255,.28)";
    c.strokeStyle = "#7fb8ff"; c.lineWidth = 2;
    if (s.body === "ball") {
      c.beginPath(); c.arc(cx, cy, 26, 0, 7); c.fill(); c.stroke();
    } else {
      c.fillRect(cx - 30, cy - 22, 60, 62);
      c.strokeRect(cx - 30, cy - 22, 60, 62);
    }
    var V = { up: [0, -1], down: [0, 1], left: [-1, 0], right: [1, 0],
              ne: [0.71, -0.71], nw: [-0.71, -0.71],
              se: [0.71, 0.71], sw: [-0.71, 0.71] };
    s.arrows.forEach(function (a, i) {
      // size is optional. Without the fallback an arrow with none became
      // NaN long, the endpoints were NaN, and canvas silently drew nothing —
      // a free-body diagram with a block, a floor, and no forces on it.
      var v = V[a.dir] || V.down;
      var mag = (typeof a.size === "number" && isFinite(a.size)) ? a.size : 0.8;
      // The arrow has to fit, and so does the label past its tip. Sized off
      // the canvas rather than fixed: at 55+55 the vertical ones ran off the
      // top and bottom of a 230px box and "W = 49 N" was sliced in half.
      var room = Math.min((H / 2) - 34, (W / 2) - 60);
      var len = Math.max(34, room * (0.55 + mag * 0.45));
      var ex = cx + v[0] * len, ey = cy + v[1] * len;
      var col = PAL[i % PAL.length];
      arrow(c, cx, cy, ex, ey, col, 2.4);
      var lx = ex + v[0] * 14, ly = ey + v[1] * 16;
      chip(c, a.label, Math.max(58, Math.min(W - 58, lx)),
           Math.max(16, Math.min(H - 8, ly)), col,
           v[0] < -0.3 ? "right" : v[0] > 0.3 ? "left" : "center");
    });
  };

  DRAW.circuit = function (c, s, W, H) {
    var I = ink();
    var L = 46, R = W - 46, T = 44, B = H - 44;
    c.strokeStyle = I.text; c.lineWidth = 2;
    c.strokeRect(L, T, R - L, B - T);

    var n = s.parts.length;
    // Series: spread around the loop. Parallel: the branches stack.
    var spots = [];
    if (s.layout === "parallel" && n > 1) {
      spots.push({ x: L, y: (T + B) / 2, rot: 1 });        // the source
      for (var k = 1; k < n; k++) {
        var y = T + (B - T) * (k / n);
        c.beginPath(); c.moveTo(L + 40, y); c.lineTo(R - 40, y); c.stroke();
        spots.push({ x: (L + R) / 2, y: y, rot: 0 });
      }
    } else {
      var per = (R - L) / Math.max(1, n);
      s.parts.forEach(function (_, i) {
        spots.push({ x: L + per * (i + 0.5), y: T, rot: 0 });
      });
    }
    s.parts.forEach(function (p, i) {
      var sp = spots[i] || { x: (L + R) / 2, y: T, rot: 0 };
      part(c, p, sp.x, sp.y, sp.rot, I);
    });
  };

  function part(c, p, x, y, vert, I) {
    var col = I.text;
    c.strokeStyle = col; c.fillStyle = col; c.lineWidth = 2;
    // Clear the wire behind the symbol.
    c.save();
    c.globalCompositeOperation = "destination-out";
    if (vert) c.fillRect(x - 5, y - 24, 10, 48);
    else c.fillRect(x - 24, y - 5, 48, 10);
    c.restore();
    c.strokeStyle = col; c.fillStyle = col;

    if (p.type === "battery") {
      var d = vert ? 1 : 0;
      c.lineWidth = 2.5;
      c.beginPath();
      if (d) { c.moveTo(x - 11, y - 7); c.lineTo(x + 11, y - 7); }
      else { c.moveTo(x - 7, y - 11); c.lineTo(x - 7, y + 11); }
      c.stroke();
      c.lineWidth = 5;
      c.beginPath();
      if (d) { c.moveTo(x - 6, y + 6); c.lineTo(x + 6, y + 6); }
      else { c.moveTo(x + 6, y - 6); c.lineTo(x + 6, y + 6); }
      c.stroke();
    } else if (p.type === "resistor") {
      c.lineWidth = 2;
      c.strokeRect(x - 20, y - 8, 40, 16);
    } else if (p.type === "lamp") {
      c.beginPath(); c.arc(x, y, 13, 0, 7); c.stroke();
      c.beginPath(); c.moveTo(x - 9, y - 9); c.lineTo(x + 9, y + 9);
      c.moveTo(x + 9, y - 9); c.lineTo(x - 9, y + 9); c.stroke();
    } else if (p.type === "switch") {
      c.beginPath(); c.arc(x - 14, y, 3, 0, 7); c.fill();
      c.beginPath(); c.arc(x + 14, y, 3, 0, 7); c.fill();
      c.beginPath(); c.moveTo(x - 14, y); c.lineTo(x + 10, y - 12); c.stroke();
    } else if (p.type === "capacitor") {
      c.lineWidth = 2.5;
      c.beginPath(); c.moveTo(x - 5, y - 12); c.lineTo(x - 5, y + 12);
      c.moveTo(x + 5, y - 12); c.lineTo(x + 5, y + 12); c.stroke();
    } else if (p.type === "diode") {
      c.beginPath(); c.moveTo(x - 10, y - 10); c.lineTo(x + 8, y);
      c.lineTo(x - 10, y + 10); c.closePath(); c.fill();
      c.beginPath(); c.moveTo(x + 8, y - 10); c.lineTo(x + 8, y + 10);
      c.stroke();
    } else {
      // ammeter, voltmeter, motor — a lettered circle, as on every schematic.
      c.beginPath(); c.arc(x, y, 13, 0, 7); c.stroke();
      plain(c, p.type[0].toUpperCase(), x, y + 5, col, 14, "center");
    }
    if (p.label) chip(c, p.label, x, y - 26, I.text, "center");
  }

  DRAW.venn = function (c, s, W, H) {
    var I = ink(), r = Math.min(W, H) * 0.28, cy = H / 2 + 6;
    var ax = W / 2 - r * 0.68, bx = W / 2 + r * 0.68;
    c.globalAlpha = 0.3;
    c.fillStyle = PAL[1];
    c.beginPath(); c.arc(ax, cy, r, 0, 7); c.fill();
    c.fillStyle = PAL[2];
    c.beginPath(); c.arc(bx, cy, r, 0, 7); c.fill();
    c.globalAlpha = 1;
    c.strokeStyle = I.muted; c.lineWidth = 1.5;
    c.beginPath(); c.arc(ax, cy, r, 0, 7); c.stroke();
    c.beginPath(); c.arc(bx, cy, r, 0, 7); c.stroke();
    chip(c, s.a, ax - r * 0.35, cy - r - 10, PAL[1], "center");
    chip(c, s.b, bx + r * 0.35, cy - r - 10, PAL[2], "center");
    // Pushed out to the far side of each circle and staggered, because
    // centred in their own lobe the three ran into one another and read as a
    // single sentence.
    if (s.only_a) plain(c, s.only_a, ax - r * 0.50, cy - 8, I.text, 11.5, "center");
    if (s.only_b) plain(c, s.only_b, bx + r * 0.50, cy - 8, I.text, 11.5, "center");
    if (s.both) plain(c, s.both, W / 2, cy + r * 0.62, I.text, 11.5, "center");
  };

  /* Optics, traced rather than described: the two standard rays are drawn and
     the image lands where they cross, which is the proof the formula is only
     shorthand for. */
  DRAW.ray = function (c, s, W, H) {
    var I = ink(), cx = W / 2, cy = H / 2;
    var k = (W * 0.4) / Math.max(s.u || 4, (s.f || 2) * 2);
    var f = s.f * k, u = s.u * k;
    var h = ((typeof s.height === "number" && isFinite(s.height))
      ? s.height : 1) * 26;
    c.strokeStyle = I.line; c.lineWidth = 1;
    c.beginPath(); c.moveTo(20, cy); c.lineTo(W - 20, cy); c.stroke();
    // The lens.
    c.strokeStyle = "#7fb8ff"; c.lineWidth = 2.5;
    c.beginPath(); c.moveTo(cx, cy - 62); c.lineTo(cx, cy + 62); c.stroke();
    [-1, 1].forEach(function (sgn) {
      c.beginPath();
      if (s.lens === "converging") {
        c.moveTo(cx - 7, cy + sgn * 54); c.lineTo(cx, cy + sgn * 62);
        c.lineTo(cx + 7, cy + sgn * 54);
      } else {
        c.moveTo(cx - 7, cy + sgn * 62); c.lineTo(cx, cy + sgn * 54);
        c.lineTo(cx + 7, cy + sgn * 62);
      }
      c.stroke();
    });
    [-1, 1].forEach(function (sgn) {
      c.fillStyle = I.muted;
      c.beginPath(); c.arc(cx + sgn * f, cy, 3, 0, 7); c.fill();
      plain(c, "F", cx + sgn * f, cy + 16, I.muted, 11, "center");
    });
    // The object.
    arrow(c, cx - u, cy, cx - u, cy - h, PAL[0], 2.2);
    plain(c, "object", cx - u, cy + 16, PAL[0], 11, "center");

    var fm = s.lens === "converging" ? s.f : -s.f;
    var v = (Math.abs(s.u - fm) < 1e-6) ? null : 1 / (1 / fm - 1 / s.u);
    c.strokeStyle = "rgba(255,230,161,.85)"; c.lineWidth = 1.4;
    // Parallel in, through the focus out.
    c.beginPath(); c.moveTo(cx - u, cy - h); c.lineTo(cx, cy - h); c.stroke();
    // Through the centre, undeviated.
    c.beginPath(); c.moveTo(cx - u, cy - h);
    c.lineTo(cx + (v ? v * k : W), cy + (v ? (h * (v / s.u)) : -h));
    c.stroke();
    if (v) {
      var vi = v * k, hi = -h * (v / s.u);
      c.beginPath(); c.moveTo(cx, cy - h); c.lineTo(cx + vi, cy + hi); c.stroke();
      arrow(c, cx + vi, cy, cx + vi, cy + hi, PAL[2], 2.2);
      chip(c, (v > 0 ? "real, " : "virtual, ") +
              (hi > 0 ? "inverted" : "upright"),
           cx + vi, cy + hi + (hi > 0 ? 24 : -18), PAL[2], "center");
    } else {
      chip(c, "object at F — no image forms", cx, cy - 80, I.text, "center");
    }
  };

  /* ---- mounting ------------------------------------------------------ */
  window.Sketch = {
    kinds: Object.keys(DRAW),

    /* Draw into an element. Returns a disposer, so a page can tear its
       drawings down before replacing the DOM they live in. */
    mount: function (el, spec) {
      if (!el || !spec || !DRAW[spec.kind]) return function () {};
      var cv = document.createElement("canvas");
      cv.style.cssText = "width:100%;display:block";
      el.innerHTML = "";
      el.appendChild(cv);

      var H = spec.height || 300;
      function render() {
        var W = el.clientWidth || 480;
        var dpr = Math.min(window.devicePixelRatio || 1, 2);
        cv.width = W * dpr;
        cv.height = H * dpr;
        cv.style.height = H + "px";
        var c = cv.getContext("2d");
        c.setTransform(dpr, 0, 0, dpr, 0, 0);
        c.clearRect(0, 0, W, H);
        c.textBaseline = "alphabetic";
        placed = [];
        try {
          DRAW[spec.kind](c, spec, W, H);
        } catch (e) {
          plain(c, "This drawing could not be built.", 12, 22,
                ink().muted, 12);
        }
      }
      render();

      var ro = new ResizeObserver(render);
      ro.observe(el);
      // The page has a light/dark toggle, and axes drawn for one are
      // invisible in the other.
      var mo = new MutationObserver(render);
      mo.observe(document.documentElement,
                 { attributes: true, attributeFilter: ["data-theme"] });

      return function () {
        ro.disconnect();
        mo.disconnect();
        if (cv.parentNode) cv.remove();
      };
    }
  };
})();
