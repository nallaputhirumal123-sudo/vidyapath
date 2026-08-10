/* Draw on the board itself, over whatever is on it.
 *
 * Every drawing surface here has been a canvas the lesson owns — a sketch, a
 * 3D scene, a diagram. But a teacher does not want to draw in a box. They want
 * to ring the term that matters, underline the second line of a proof, cross
 * out the wrong step, put an arrow from the equation to the number it produced.
 * That is annotation over the page, not drawing inside a figure, and none of it
 * was possible.
 *
 * So this is a sheet of glass over everything. It is not part of any lesson and
 * never changes one: the marks sit above the page and come off, and what is
 * underneath is untouched.
 *
 * Decisions worth stating.
 *
 * **Off means gone.** With the pen down the glass takes every pointer event, so
 * nothing underneath can be clicked; that is the whole point while marking up
 * and intolerable the rest of the time. Off sets pointer-events to none, so the
 * layer is inert and the page behaves exactly as if it were not there.
 *
 * **Strokes are kept, not just pixels.** They are replayed on resize and on
 * device-pixel changes, and undo removes the last one. A canvas holding only
 * pixels cannot do either, and a board being dragged to another screen changes
 * both.
 *
 * **The palm is not a pen.** Boards are touched by a hand resting on them. Once
 * a stylus has been seen, touch stops drawing for a few seconds — the standard
 * bargain, and much better than a stray blob across a proof mid-lesson.
 *
 * **Page space, because a lesson is longer than a screen.** This started in
 * viewport space, on the reasoning that a classroom board annotates what is
 * visible. It does — but a lesson scrolls, and a ring drawn round the third
 * paragraph stayed where it was while the paragraph moved, so it ended up
 * round a different one. Worse, scrolling was locked outright while the pen
 * was on, so the answer to "how do I mark the next part" was: turn the pen
 * off, scroll, turn it on, and find your earlier marks in the wrong places.
 *
 * Strokes are stored in document coordinates and drawn at an offset. The
 * canvas is still fixed to the viewport — it only ever needs to cover what
 * is on screen — and the offset is the page's own scroll.
 */
(function (global) {
  "use strict";

  var PEN_MEMORY_MS = 2500;   /* how long a stylus suppresses touch */
  var ERASE_R = 22;           /* eraser radius in CSS pixels */

  var on = false, tool = "pen", colour = "#ff3b30";
  var cv = null, ctx = null, bar = null;
  var strokes = [], live = null, lastPen = 0, drawing = false;
  var cfg = {};

  /* Where the page has been scrolled to. One place, because every reader of
     it — capture, erase, redraw — has to agree, and a stroke laid down
     against one number and erased against another is a mark that cannot be
     rubbed out. */
  function sx() { return global.scrollX || global.pageXOffset || 0; }
  function sy() { return global.scrollY || global.pageYOffset || 0; }

  var TOOLS = {
    pen: { width: 3.2, alpha: 1, cap: "round" },
    /* Wide and translucent, and multiplied so text underneath survives. */
    marker: { width: 19, alpha: 0.34, cap: "round" }
  };

  var COLOURS = ["#ff3b30", "#ffb020", "#34c759", "#3b9cff", "#ffffff"];

  function css() {
    if (document.getElementById("ink-css")) return;
    var s = document.createElement("style");
    s.id = "ink-css";
    s.textContent = [
      "#ink-cv{position:fixed;inset:0;z-index:9700;pointer-events:none;",
      "touch-action:none}",
      "#ink-cv.on{pointer-events:auto;cursor:crosshair}",
      "#ink-bar{position:fixed;z-index:9750;left:50%;transform:translateX(-50%);",
      "bottom:18px;display:none;gap:5px;padding:7px;border-radius:13px;",
      "background:#14181c;border:1px solid #2c3238;align-items:center;",
      /* One row that scrolls, never a block that wraps. Wrapped, it grew
         tall enough on a phone to cover the very thing being marked up —
         and a board is wide enough that it never needs to wrap at all. */
      "box-shadow:0 10px 30px rgba(0,0,0,.5);max-width:96vw;",
      "flex-wrap:nowrap;overflow-x:auto}",
      "#ink-bar.on{display:flex}",
      "#ink-bar button{font:600 13px/1 inherit;color:#e8eef2;cursor:pointer;",
      "background:transparent;border:1px solid transparent;border-radius:9px;",
      "padding:9px 11px;white-space:nowrap}",
      "#ink-bar button:hover{background:rgba(255,255,255,.08)}",
      "#ink-bar button.sel{border-color:#ffb020;color:#ffb020;",
      "background:rgba(255,176,32,.14)}",
      "#ink-bar .sw{width:24px;height:24px;border-radius:50%;padding:0;",
      "border:2px solid transparent}",
      "#ink-bar .sw.sel{border-color:#e8eef2}",
      "#ink-bar .sep{width:1px;height:24px;background:#2c3238;margin:0 3px}"
    ].join("");
    document.head.appendChild(s);
  }

  function sizeCanvas() {
    if (!cv) return;
    var r = Math.min(global.devicePixelRatio || 1, 2);
    cv.width = Math.round(innerWidth * r);
    cv.height = Math.round(innerHeight * r);
    cv.style.width = innerWidth + "px";
    cv.style.height = innerHeight + "px";
    ctx = cv.getContext("2d");
    ctx.setTransform(r, 0, 0, r, 0, 0);
    redraw();
  }

  function strokePath(s) {
    var t = TOOLS[s.tool] || TOOLS.pen;
    ctx.save();
    ctx.globalAlpha = t.alpha;
    ctx.globalCompositeOperation = s.tool === "marker" ? "multiply" : "source-over";
    ctx.strokeStyle = s.colour;
    ctx.lineCap = t.cap;
    ctx.lineJoin = "round";
    var pts = s.pts;
    if (pts.length === 1) {
      /* A single tap is a dot, not nothing. */
      ctx.fillStyle = s.colour;
      ctx.beginPath();
      ctx.arc(pts[0].x, pts[0].y, (t.width * (pts[0].p || 1)) / 2, 0, 6.29);
      ctx.fill();
      ctx.restore();
      return;
    }
    for (var i = 1; i < pts.length; i++) {
      var a = pts[i - 1], b = pts[i];
      ctx.lineWidth = t.width * ((a.p + b.p) / 2 || 1);
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();
    }
    ctx.restore();
  }

  function redraw() {
    if (!ctx) return;
    /* Cleared in viewport space and drawn in page space. The clear has to
       come before the translate, or scrolling leaves a band of old marks
       along the edge the page came from. */
    ctx.clearRect(0, 0, innerWidth, innerHeight);
    ctx.save();
    ctx.translate(-sx(), -sy());
    strokes.forEach(strokePath);
    if (live) strokePath(live);
    ctx.restore();
  }

  /* A pen reports pressure; a finger and a mouse report 0 or a flat 0.5, and
     scaling a line by zero makes it vanish. */
  function pressure(e) {
    if (e.pointerType === "pen" && e.pressure > 0) {
      return 0.45 + e.pressure * 0.9;
    }
    return 1;
  }

  function ignore(e) {
    if (e.pointerType === "pen") { lastPen = Date.now(); return false; }
    /* A hand resting on the board while the other holds the stylus. */
    return e.pointerType === "touch" && (Date.now() - lastPen) < PEN_MEMORY_MS;
  }

  function erase(x, y) {
    var before = strokes.length;
    strokes = strokes.filter(function (s) {
      return !s.pts.some(function (p) {
        return Math.abs(p.x - x) < ERASE_R && Math.abs(p.y - y) < ERASE_R;
      });
    });
    if (strokes.length !== before) redraw();
  }

  function down(e) {
    if (!on || ignore(e)) return;
    e.preventDefault();
    drawing = true;
    try { cv.setPointerCapture(e.pointerId); } catch (err) {}
    if (tool === "eraser") { erase(e.clientX + sx(), e.clientY + sy()); return; }
    live = { tool: tool, colour: colour,
             pts: [{ x: e.clientX + sx(), y: e.clientY + sy(),
                     p: pressure(e) }] };
    redraw();
  }

  function move(e) {
    if (!on || !drawing) return;
    e.preventDefault();
    if (tool === "eraser") { erase(e.clientX + sx(), e.clientY + sy()); return; }
    if (!live) return;
    /* Coalesced events are the difference between a smooth arc and a polygon
       on a board sampling far faster than it paints.
       The empty check is not defensive padding: getCoalescedEvents returns an
       empty list for any event the browser did not generate itself, and
       without the fallback every such point is dropped and the stroke
       collapses to the single dot placed on pointerdown. */
    var evs = e.getCoalescedEvents ? e.getCoalescedEvents() : null;
    if (!evs || !evs.length) evs = [e];
    for (var i = 0; i < evs.length; i++) {
      live.pts.push({ x: evs[i].clientX + sx(), y: evs[i].clientY + sy(),
                      p: pressure(evs[i]) });
    }
    redraw();
  }

  function up() {
    if (!drawing) return;
    drawing = false;
    if (live && live.pts.length) strokes.push(live);
    live = null;
    redraw();
  }

  function button(label, title, fn, mark) {
    var b = document.createElement("button");
    b.textContent = label;
    b.title = title || label;
    b.type = "button";
    b.onclick = fn;
    if (mark) b.dataset.mark = mark;
    return b;
  }

  function paintBar() {
    if (!bar) return;
    bar.querySelectorAll("[data-mark]").forEach(function (b) {
      b.classList.toggle("sel", b.dataset.mark === tool);
    });
    bar.querySelectorAll(".sw").forEach(function (b) {
      b.classList.toggle("sel", b.dataset.colour === colour);
    });
  }

  function buildBar() {
    bar = document.createElement("div");
    bar.id = "ink-bar";
    bar.appendChild(button("✏️ Pen", "Draw", function () {
      tool = "pen"; paintBar();
    }, "pen"));
    bar.appendChild(button("🖍 Highlight", "Highlight", function () {
      tool = "marker"; paintBar();
    }, "marker"));
    bar.appendChild(button("🧽 Erase", "Rub out a stroke", function () {
      tool = "eraser"; paintBar();
    }, "eraser"));

    var sep = document.createElement("div"); sep.className = "sep";
    bar.appendChild(sep);

    COLOURS.forEach(function (c) {
      var b = document.createElement("button");
      b.className = "sw";
      b.type = "button";
      b.style.background = c;
      b.dataset.colour = c;
      b.title = "Colour";
      b.onclick = function () {
        colour = c;
        if (tool === "eraser") tool = "pen";
        paintBar();
      };
      bar.appendChild(b);
    });

    var sep2 = document.createElement("div"); sep2.className = "sep";
    bar.appendChild(sep2);

    bar.appendChild(button("↶ Undo", "Undo the last stroke", function () {
      strokes.pop(); redraw();
    }));
    bar.appendChild(button("Clear", "Take all the marks off", function () {
      if (!strokes.length) return;
      strokes = []; redraw();
      if (cfg.toast) cfg.toast("Marks cleared.");
    }));
    bar.appendChild(button("✓ Done", "Stop drawing and use the page", function () {
      set(false);
    }));
    document.body.appendChild(bar);
  }

  function set(want) {
    on = !!want;
    cv.classList.toggle("on", on);
    bar.classList.toggle("on", on);
    if (on) paintBar();
    /* The page is NOT frozen any more.
       It used to be: overflow went hidden the moment the pen came on, so a
       lesson longer than a screen could only be marked one screenful at a
       time — turn the pen off, scroll, turn it on. Now the marks travel with
       the document, so scrolling to the next part and carrying on is the
       obvious thing and it works. A wheel or trackpad scroll passes through
       the glass because nothing here calls preventDefault on it; on touch
       the glass still takes the gesture, which is what makes drawing with a
       finger possible at all. */
    document.documentElement.style.overflow = "";
    if (cfg.onToggle) cfg.onToggle(on);
    /* Marking up and selecting text are different intentions, and the glass
       swallows the events the selection toolbar listens for anyway. */
    if (on && global.Marker && global.Marker.hide) global.Marker.hide();
  }

  function init(options) {
    cfg = options || {};
    if (cv) return;
    css();
    cv = document.createElement("canvas");
    cv.id = "ink-cv";
    document.body.appendChild(cv);
    buildBar();
    sizeCanvas();

    cv.addEventListener("pointerdown", down);
    cv.addEventListener("pointermove", move);
    cv.addEventListener("pointerup", up);
    cv.addEventListener("pointercancel", up);
    cv.addEventListener("pointerleave", up);

    global.addEventListener("resize", sizeCanvas);
    /* The marks are anchored to the document, so every scroll moves them on
       screen. Passive, and one repaint per frame — a scroll fires far faster
       than the board paints, and redrawing per event is how a lesson with
       forty marks on it starts to stutter under a finger. */
    var pending = false;
    global.addEventListener("scroll", function () {
      if (!ctx || pending) return;
      pending = true;
      global.requestAnimationFrame(function () { pending = false; redraw(); });
    }, { passive: true });
    document.addEventListener("keydown", function (e) {
      if (!on) return;
      if (e.key === "Escape") set(false);
      /* Ctrl+Z is what a hand reaches for, and there is nothing else on the
         board it could mean while the pen is down. */
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
        e.preventDefault(); strokes.pop(); redraw();
      }
    });
  }

  global.Ink = {
    init: init,
    toggle: function () { set(!on); },
    on: function () { set(true); },
    off: function () { set(false); },
    isOn: function () { return on; },
    clear: function () { strokes = []; redraw(); },
    count: function () { return strokes.length; }
  };
})(window);
