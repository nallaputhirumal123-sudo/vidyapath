/* Composed drawings, on a canvas.
 *
 * The eight fixed sketch kinds answer eight questions and everything else not
 * at all — which is precisely why "only some questions get a picture". This
 * draws from primitives instead, so a cell, a gearbox, a food web and a
 * distillation rig are all reachable with the same vocabulary.
 *
 * Canvas rather than SVG, deliberately. Path data still uses SVG path syntax
 * because Path2D parses it natively and it is the most compact way to
 * describe a curve — but it is parsed as geometry, never inserted as markup,
 * and nothing here is executed.
 *
 * Everything arrives in a fixed 1000x600 space and is scaled to fit. A model
 * that has one canvas size to think about places things far more consistently
 * than one that has to ask how wide the page is.
 */
(function () {
  "use strict";

  var VW = 1000, VH = 600;

  var INK = {
    chalk: "#eafff2", amber: "#ffb020", blue: "#7fb8ff", green: "#8fe3b0",
    rose: "#d98fb0", violet: "#c9a0ff", grey: "#8fa3b0", dim: "#5c6b7a",
    red: "#e0714a", none: "transparent"
  };
  function ink(v) { return INK[v] || (v && v.charAt(0) === "#" ? v : INK.chalk); }

  /* ---- the symbol library -------------------------------------------
   * Each draws into a 60x40 box centred on the origin, so they can be
   * placed, scaled and rotated uniformly. Drawn to the conventions a student
   * will meet in a textbook — a resistor built out of rectangles is not a
   * resistor to anyone who has seen a real schematic. */
  var SYM = {};
  function leads(c, w) { // the wire stubs either side
    c.beginPath(); c.moveTo(-30, 0); c.lineTo(-w, 0);
    c.moveTo(w, 0); c.lineTo(30, 0); c.stroke();
  }

  SYM.resistor = function (c) { leads(c, 18); c.strokeRect(-18, -8, 36, 16); };
  SYM.inductor = function (c) {
    leads(c, 18);
    c.beginPath();
    for (var i = 0; i < 4; i++) c.arc(-13.5 + i * 9, 0, 4.5, Math.PI, 0);
    c.stroke();
  };
  SYM.capacitor = function (c) {
    leads(c, 5);
    c.beginPath(); c.moveTo(-5, -13); c.lineTo(-5, 13);
    c.moveTo(5, -13); c.lineTo(5, 13); c.stroke();
  };
  SYM.cell = function (c) {
    leads(c, 5);
    c.beginPath(); c.moveTo(-5, -14); c.lineTo(-5, 14); c.stroke();
    c.lineWidth = c.lineWidth * 2.4;
    c.beginPath(); c.moveTo(5, -7); c.lineTo(5, 7); c.stroke();
  };
  SYM.battery = function (c) {
    leads(c, 14);
    for (var i = 0; i < 2; i++) {
      var x = -14 + i * 18;
      c.beginPath(); c.moveTo(x, -14); c.lineTo(x, 14); c.stroke();
      c.beginPath(); c.moveTo(x + 8, -7); c.lineTo(x + 8, 7); c.stroke();
    }
  };
  SYM.lamp = function (c) {
    leads(c, 14);
    c.beginPath(); c.arc(0, 0, 14, 0, 7); c.stroke();
    c.beginPath(); c.moveTo(-10, -10); c.lineTo(10, 10);
    c.moveTo(10, -10); c.lineTo(-10, 10); c.stroke();
  };
  SYM.switch = function (c) {
    leads(c, 15);
    c.beginPath(); c.arc(-15, 0, 3, 0, 7); c.fill();
    c.beginPath(); c.arc(15, 0, 3, 0, 7); c.fill();
    c.beginPath(); c.moveTo(-15, 0); c.lineTo(11, -13); c.stroke();
  };
  SYM.fuse = function (c) {
    leads(c, 18); c.strokeRect(-18, -8, 36, 16);
    c.beginPath(); c.moveTo(-18, 0); c.lineTo(18, 0); c.stroke();
  };
  SYM.diode = function (c) {
    leads(c, 10);
    c.beginPath(); c.moveTo(-10, -11); c.lineTo(10, 0); c.lineTo(-10, 11);
    c.closePath(); c.fill();
    c.beginPath(); c.moveTo(10, -11); c.lineTo(10, 11); c.stroke();
  };
  SYM.led = function (c) {
    SYM.diode(c);
    [[14, -14], [19, -9]].forEach(function (p) {
      c.beginPath(); c.moveTo(p[0], p[1]); c.lineTo(p[0] + 9, p[1] - 9);
      c.stroke();
    });
  };
  SYM.transistor = function (c) {
    c.beginPath(); c.arc(0, 0, 16, 0, 7); c.stroke();
    c.beginPath(); c.moveTo(-30, 0); c.lineTo(-7, 0);
    c.moveTo(-7, -11); c.lineTo(-7, 11); c.stroke();
    c.beginPath(); c.moveTo(-7, -6); c.lineTo(12, -14); c.lineTo(12, -26);
    c.moveTo(-7, 6); c.lineTo(12, 14); c.lineTo(12, 26); c.stroke();
  };
  function meter(letter) {
    return function (c) {
      leads(c, 14);
      c.beginPath(); c.arc(0, 0, 14, 0, 7); c.stroke();
      c.font = "bold 15px system-ui, sans-serif";
      c.textAlign = "center";
      c.fillText(letter, 0, 5);
      c.textAlign = "left";
    };
  }
  SYM.ammeter = meter("A");
  SYM.voltmeter = meter("V");
  SYM.motor = meter("M");
  SYM.speaker = function (c) {
    leads(c, 12);
    c.strokeRect(-12, -10, 10, 20);
    c.beginPath(); c.moveTo(-2, -10); c.lineTo(12, -20);
    c.lineTo(12, 20); c.lineTo(-2, 10); c.stroke();
  };
  SYM.ground = function (c) {
    c.beginPath(); c.moveTo(0, -20); c.lineTo(0, 0); c.stroke();
    for (var i = 0; i < 3; i++) {
      var w = 18 - i * 6;
      c.beginPath(); c.moveTo(-w, i * 6); c.lineTo(w, i * 6); c.stroke();
    }
  };

  function gate(shape, invert) {
    return function (c) {
      c.beginPath();
      if (shape === "and") {
        c.moveTo(-16, -18); c.lineTo(0, -18);
        c.arc(0, 0, 18, -Math.PI / 2, Math.PI / 2);
        c.lineTo(-16, 18); c.closePath();
      } else if (shape === "or" || shape === "xor") {
        c.moveTo(-16, -18);
        c.quadraticCurveTo(6, -16, 20, 0);
        c.quadraticCurveTo(6, 16, -16, 18);
        c.quadraticCurveTo(-6, 0, -16, -18);
      } else {                                   // not
        c.moveTo(-14, -16); c.lineTo(16, 0); c.lineTo(-14, 16); c.closePath();
      }
      c.stroke();
      if (shape === "xor") {
        c.beginPath(); c.moveTo(-22, -18);
        c.quadraticCurveTo(-12, 0, -22, 18); c.stroke();
      }
      if (invert) { c.beginPath(); c.arc(24, 0, 5, 0, 7); c.stroke(); }
      c.beginPath();
      c.moveTo(-30, -9); c.lineTo(-16, -9);
      c.moveTo(-30, 9); c.lineTo(-16, 9);
      c.moveTo(invert ? 29 : 20, 0); c.lineTo(34, 0);
      c.stroke();
    };
  }
  SYM.and_gate = gate("and"); SYM.nand_gate = gate("and", 1);
  SYM.or_gate = gate("or"); SYM.nor_gate = gate("or", 1);
  SYM.xor_gate = gate("xor"); SYM.not_gate = gate("not", 1);

  SYM.spring = function (c) {
    c.beginPath(); c.moveTo(-30, 0); c.lineTo(-20, 0);
    for (var i = 0; i < 6; i++) {
      c.lineTo(-17 + i * 6, i % 2 ? 10 : -10);
    }
    c.lineTo(20, 0); c.lineTo(30, 0); c.stroke();
  };
  SYM.damper = function (c) {
    c.beginPath(); c.moveTo(-30, 0); c.lineTo(-10, 0); c.stroke();
    c.strokeRect(-10, -11, 16, 22);
    c.beginPath(); c.moveTo(2, 0); c.lineTo(30, 0); c.stroke();
    c.beginPath(); c.moveTo(2, -9); c.lineTo(2, 9); c.stroke();
  };
  SYM.mass = function (c) { c.strokeRect(-18, -14, 36, 28); c.fill(); };
  SYM.pulley = function (c) {
    c.beginPath(); c.arc(0, 0, 16, 0, 7); c.stroke();
    c.beginPath(); c.arc(0, 0, 3, 0, 7); c.fill();
  };
  SYM.wheel = function (c) {
    c.beginPath(); c.arc(0, 0, 18, 0, 7); c.stroke();
    for (var i = 0; i < 6; i++) {
      var a = i * Math.PI / 3;
      c.beginPath(); c.moveTo(0, 0);
      c.lineTo(Math.cos(a) * 18, Math.sin(a) * 18); c.stroke();
    }
  };
  SYM.pivot = function (c) {
    c.beginPath(); c.moveTo(0, -4); c.lineTo(-13, 16); c.lineTo(13, 16);
    c.closePath(); c.stroke();
    c.beginPath(); c.arc(0, -4, 3.5, 0, 7); c.fill();
  };

  SYM.beaker = function (c) {
    c.beginPath(); c.moveTo(-16, -20); c.lineTo(-16, 18);
    c.quadraticCurveTo(-16, 22, -11, 22); c.lineTo(11, 22);
    c.quadraticCurveTo(16, 22, 16, 18); c.lineTo(16, -20); c.stroke();
    c.beginPath(); c.moveTo(-16, 4); c.lineTo(16, 4); c.stroke();
  };
  SYM.flask = function (c) {
    c.beginPath(); c.moveTo(-6, -22); c.lineTo(-6, -4);
    c.lineTo(-19, 20); c.lineTo(19, 20); c.lineTo(6, -4);
    c.lineTo(6, -22); c.closePath(); c.stroke();
  };
  SYM.test_tube = function (c) {
    c.beginPath(); c.moveTo(-8, -22); c.lineTo(-8, 12);
    c.arc(0, 12, 8, Math.PI, 0, true); c.lineTo(8, -22); c.stroke();
  };
  SYM.burette = function (c) {
    c.beginPath(); c.moveTo(-6, -24); c.lineTo(-6, 14); c.lineTo(0, 24);
    c.lineTo(6, 14); c.lineTo(6, -24); c.stroke();
    for (var i = 0; i < 4; i++) {
      c.beginPath(); c.moveTo(-6, -16 + i * 8); c.lineTo(-1, -16 + i * 8);
      c.stroke();
    }
  };
  SYM.funnel = function (c) {
    c.beginPath(); c.moveTo(-18, -18); c.lineTo(18, -18); c.lineTo(4, 6);
    c.lineTo(4, 22); c.moveTo(-4, 22); c.lineTo(-4, 6); c.closePath();
    c.stroke();
  };
  SYM.condenser = function (c) {
    c.strokeRect(-24, -9, 48, 18);
    c.beginPath(); c.moveTo(-30, 0); c.lineTo(-24, 0);
    c.moveTo(24, 0); c.lineTo(30, 0); c.stroke();
    c.beginPath(); c.moveTo(-14, -9); c.lineTo(-14, -17);
    c.moveTo(14, 9); c.lineTo(14, 17); c.stroke();
  };
  SYM.bunsen = function (c) {
    c.beginPath(); c.moveTo(-4, 20); c.lineTo(-4, -6); c.lineTo(4, -6);
    c.lineTo(4, 20); c.stroke();
    c.beginPath(); c.moveTo(-14, 22); c.lineTo(14, 22); c.stroke();
    c.beginPath(); c.moveTo(0, -8);
    c.quadraticCurveTo(-8, -18, 0, -26);
    c.quadraticCurveTo(8, -18, 0, -8); c.stroke();
  };
  SYM.thermometer = function (c) {
    c.beginPath(); c.moveTo(-4, -24); c.lineTo(-4, 10);
    c.arc(0, 14, 6, Math.PI, 0, true); c.lineTo(4, -24);
    c.arc(0, -24, 4, 0, Math.PI, true); c.stroke();
    c.beginPath(); c.arc(0, 14, 4, 0, 7); c.fill();
  };
  SYM.balance = function (c) {
    c.beginPath(); c.moveTo(-24, -10); c.lineTo(24, -10); c.stroke();
    c.beginPath(); c.moveTo(0, -10); c.lineTo(0, 14); c.stroke();
    c.beginPath(); c.moveTo(-14, 20); c.lineTo(14, 20); c.stroke();
    [-24, 24].forEach(function (x) {
      c.beginPath(); c.moveTo(x, -10); c.lineTo(x - 6, 2);
      c.lineTo(x + 6, 2); c.closePath(); c.stroke();
    });
  };

  /* ---- drawing one element ------------------------------------------ */
  function shape(c, e, t) {
    c.save();
    c.globalAlpha = e._alpha === undefined ? e.opacity : e._alpha;
    c.strokeStyle = ink(e.stroke);
    c.fillStyle = ink(e.fill);
    c.lineWidth = e.w;
    c.setLineDash(e.dash ? [7, 5] : []);

    var dx = (e._dx || 0), dy = (e._dy || 0);
    if (e.rotate || e._rot || e._scale) {
      var ax = e.cx !== undefined ? e.cx : (e.x !== undefined ? e.x : 0);
      var ay = e.cy !== undefined ? e.cy : (e.y !== undefined ? e.y : 0);
      c.translate(ax + dx, ay + dy);
      c.rotate(((e.rotate || 0) + (e._rot || 0)) * Math.PI / 180);
      if (e._scale) c.scale(e._scale, e._scale);
      c.translate(-ax, -ay);
    } else if (dx || dy) {
      c.translate(dx, dy);
    }

    var filled = e.fill !== "transparent";
    if (e.type === "circle") {
      c.beginPath(); c.arc(e.cx, e.cy, e.r, 0, 7);
      if (filled) c.fill();
      c.stroke();
    } else if (e.type === "ellipse") {
      c.beginPath(); c.ellipse(e.cx, e.cy, e.rx, e.ry, 0, 0, 7);
      if (filled) c.fill();
      c.stroke();
    } else if (e.type === "rect") {
      c.beginPath();
      if (c.roundRect) c.roundRect(e.x, e.y, e.rw, e.rh, e.radius || 0);
      else c.rect(e.x, e.y, e.rw, e.rh);
      if (filled) c.fill();
      c.stroke();
    } else if (e.type === "polygon") {
      c.beginPath();
      e.points.forEach(function (p, i) {
        if (i) c.lineTo(p[0], p[1]); else c.moveTo(p[0], p[1]);
      });
      if (e.closed) c.closePath();
      if (filled) c.fill();
      c.stroke();
    } else if (e.type === "path") {
      // Path2D parses SVG path syntax as geometry. The string was validated
      // server-side to path characters only; nothing here is executed.
      try {
        var p2 = new Path2D(e.d);
        if (filled) c.fill(p2);
        if (e._dashLen !== undefined) {
          c.setLineDash([e._dashLen, 100000]);
        }
        c.stroke(p2);
      } catch (err) { /* an unparseable path draws nothing, not a crash */ }
    } else if (e.type === "line" || e.type === "arrow") {
      var x2 = e.x2, y2 = e.y2;
      if (e._grow !== undefined) {
        x2 = e.x1 + (e.x2 - e.x1) * e._grow;
        y2 = e.y1 + (e.y2 - e.y1) * e._grow;
      }
      c.beginPath(); c.moveTo(e.x1, e.y1); c.lineTo(x2, y2); c.stroke();
      if (e.type === "arrow") {
        head(c, e.x1, e.y1, x2, y2);
        if (e.double) head(c, x2, y2, e.x1, e.y1);
        if (e.label) {
          text(c, e.label, (e.x1 + x2) / 2, (e.y1 + y2) / 2 - 9, 13,
               "middle", true, ink(e.stroke));
        }
      }
    } else if (e.type === "label") {
      text(c, e.text, e.x, e.y, e.size, e.anchor, e.plate, ink(e.stroke));
    } else if (e.type === "symbol") {
      var fn = SYM[e.name];
      if (fn) {
        c.save();
        c.translate(e.x, e.y);
        c.scale(e.scale, e.scale);
        c.lineJoin = "round";
        fn(c);
        c.restore();
        if (e.label) {
          text(c, e.label, e.x, e.y - 26 * e.scale, 12, "middle", true,
               ink(e.stroke));
        }
      }
    }
    c.restore();
  }

  function head(c, x1, y1, x2, y2) {
    var a = Math.atan2(y2 - y1, x2 - x1), h = 11;
    c.beginPath();
    c.moveTo(x2, y2);
    c.lineTo(x2 - h * Math.cos(a - 0.4), y2 - h * Math.sin(a - 0.4));
    c.lineTo(x2 - h * Math.cos(a + 0.4), y2 - h * Math.sin(a + 0.4));
    c.closePath();
    c.fillStyle = c.strokeStyle;
    c.fill();
  }

  function text(c, s, x, y, size, anchor, plate, col) {
    c.font = "600 " + (size || 15) + "px system-ui, -apple-system, sans-serif";
    var w = c.measureText(s).width;
    var ox = anchor === "end" ? -w : anchor === "middle" ? -w / 2 : 0;
    if (plate) {
      c.fillStyle = "rgba(8,11,15,.74)";
      c.beginPath();
      var pad = 6, hgt = size + 8;
      if (c.roundRect) c.roundRect(x + ox - pad, y - size + 2, w + pad * 2, hgt, 6);
      else c.rect(x + ox - pad, y - size + 2, w + pad * 2, hgt);
      c.fill();
    }
    c.fillStyle = col || INK.chalk;
    c.fillText(s, x + ox, y + 4);
  }

  /* ---- animation ----------------------------------------------------- */
  function apply(el, anims, now) {
    el._alpha = undefined; el._dx = el._dy = 0;
    el._rot = 0; el._scale = 0; el._grow = undefined; el._dashLen = undefined;
    anims.forEach(function (a) {
      if (a.target !== el.id) return;
      var t = now - a.delay;
      if (t < 0) {
        // Not started: hold the element in its pre-animation state so a
        // "draw" does not flash the finished shape before tracing it.
        if (a.type === "draw") { el._grow = 0; el._dashLen = 0; }
        if (a.type === "fade") el._alpha = 0;
        return;
      }
      var p = a.loop ? (t % a.duration) / a.duration
                     : Math.min(1, t / a.duration);
      var e = p * p * (3 - 2 * p);            // ease in and out
      if (a.type === "draw") { el._grow = e; el._dashLen = e * 4000; }
      else if (a.type === "fade") el._alpha = el.opacity * e;
      else if (a.type === "pulse") {
        el._scale = 1 + 0.06 * Math.sin(t / a.duration * Math.PI * 2);
      } else if (a.type === "rotate") el._rot = (a.to || 180) * e;
      else if (a.type === "scale") el._scale = 1 + ((a.to || 1.4) - 1) * e;
      else if (a.type === "move" && a.to) {
        var base = el.cx !== undefined ? { x: el.cx, y: el.cy }
                                       : { x: el.x || 0, y: el.y || 0 };
        el._dx = (a.to.x - base.x) * e;
        el._dy = (a.to.y - base.y) * e;
      }
    });
  }

  /* ---- mounting ------------------------------------------------------ */
  window.Draw = {
    symbols: Object.keys(SYM),

    /* Returns a disposer. `reveal` limits which ids are shown, so narration
       can bring a drawing up a piece at a time. */
    mount: function (host, spec) {
      if (!host || !spec || !spec.elements) return function () {};
      var cv = document.createElement("canvas");
      cv.style.cssText = "width:100%;display:block";
      host.innerHTML = "";
      host.appendChild(cv);

      var start = performance.now(), live = true, raf = 0;
      var shown = null;
      var anims = spec.animations || [];
      var moving = anims.length > 0;

      function frame(now) {
        if (!live) return;
        var W = host.clientWidth || 640;
        var scale = W / VW, H = VH * scale;
        var dpr = Math.min(window.devicePixelRatio || 1, 2);
        if (cv.width !== Math.round(W * dpr)) {
          cv.width = Math.round(W * dpr);
          cv.height = Math.round(H * dpr);
          cv.style.height = H + "px";
        }
        var c = cv.getContext("2d");
        c.setTransform(dpr * scale, 0, 0, dpr * scale, 0, 0);
        c.clearRect(0, 0, VW, VH);
        c.textBaseline = "alphabetic";
        c.lineCap = "round";

        var t = now - start;
        spec.elements.forEach(function (el) {
          if (shown && shown.indexOf(el.id) < 0) return;
          if (moving) apply(el, anims, t);
          shape(c, el, t);
        });

        // Once every animation has finished and none loop, stop asking for
        // frames — a still picture should not hold a phone's GPU awake.
        var done = !anims.some(function (a) {
          return a.loop || t < a.delay + a.duration;
        });
        if (done) { moving = false; return; }
        raf = requestAnimationFrame(frame);
      }
      raf = requestAnimationFrame(frame);

      var ro = new ResizeObserver(function () {
        if (!moving) { moving = true; start = performance.now() - 1e6;
                       raf = requestAnimationFrame(frame); }
      });
      ro.observe(host);

      return {
        dispose: function () {
          live = false; cancelAnimationFrame(raf); ro.disconnect();
          if (cv.parentNode) cv.remove();
        },
        reveal: function (ids) {
          shown = ids && ids.length ? ids : null;
          moving = true; raf = requestAnimationFrame(frame);
        }
      };
    }
  };
})();
