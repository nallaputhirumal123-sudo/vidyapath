/* Marking something on the board and doing something with it.
 *
 * A teacher standing at a smart board has a pen and no keyboard. They read a
 * line out, somebody asks what one word of it means, and the only ways to
 * answer were to retype the phrase into the follow-up box or to abandon the
 * lesson and ask a new one. Both cost the room its attention.
 *
 * So: mark a line, a formula, a chemical equation or a block of code, and get
 * Copy and Ask Axle where the mark is. Hold the pen down on the board with
 * nothing marked and get Copy and Paste, because a hold is what a pen has
 * instead of a right-click.
 *
 * Three decisions worth stating.
 *
 * **The toolbar follows the mark, not the cursor.** It is placed against the
 * selection's own rectangle and clamped to the viewport, because a board is
 * two metres wide and a menu that opens where the pointer happens to be can
 * open past the edge of the room's reach.
 *
 * **Paste is only offered where paste means something.** Reading the clipboard
 * needs permission the browser may refuse, and offering it over a paragraph
 * that cannot receive text is a button that does nothing. It appears for
 * editable targets only.
 *
 * **The answer opens in a window, not over the lesson.** What is on the board
 * is what the class is looking at. An explanation of one phrase is a side
 * question, so it arrives beside the work, movable and resizable and closable,
 * and the lesson underneath is never replaced.
 *
 * Nothing here calls a model. It collects text and hands it to a callback.
 */
(function (global) {
  "use strict";

  var HOLD_MS = 550;      /* a deliberate hold, not a slow tap */
  var HOLD_SLOP = 10;     /* a pen resting on a board drifts a little */
  var MAX_ASK = 500;      /* what /api/ask accepts */

  var bar = null, win = null, cfg = null;
  var holdTimer = null, holdFrom = null;

  function css() {
    if (document.getElementById("mk-css")) return;
    var s = document.createElement("style");
    s.id = "mk-css";
    s.textContent = [
      ".mk-bar{position:fixed;z-index:9500;display:flex;gap:4px;padding:5px;",
      "border-radius:11px;background:#14181c;border:1px solid #2c3238;",
      "box-shadow:0 8px 26px rgba(0,0,0,.45)}",
      ".mk-bar button{font:600 13.5px/1 inherit;color:#e8eef2;cursor:pointer;",
      "background:transparent;border:0;border-radius:8px;padding:9px 12px;",
      "white-space:nowrap}",
      ".mk-bar button:hover{background:rgba(255,176,32,.16);color:#ffb020}",
      ".mk-win{position:fixed;z-index:9600;width:min(430px,92vw);",
      "height:min(340px,70vh);min-width:250px;min-height:150px;resize:both;",
      "overflow:hidden;display:flex;flex-direction:column;border-radius:13px;",
      "background:#14181c;border:1px solid #2c3238;",
      "box-shadow:0 14px 44px rgba(0,0,0,.5)}",
      ".mk-hd{display:flex;align-items:center;gap:8px;padding:10px 12px;",
      "border-bottom:1px solid #2c3238;cursor:move;flex:0 0 auto;",
      "touch-action:none}",
      ".mk-hd b{font-size:13.5px;color:#e8eef2;overflow:hidden;",
      "text-overflow:ellipsis;white-space:nowrap}",
      ".mk-hd button{margin-left:auto;background:transparent;border:0;",
      "color:#8fa3b0;font-size:19px;line-height:1;cursor:pointer;padding:0 3px}",
      ".mk-hd button:hover{color:#e8eef2}",
      ".mk-bd{padding:12px 14px;overflow:auto;flex:1 1 auto;",
      "font-size:14px;line-height:1.6;color:#d7e2e8}",
      ".mk-bd ul{margin:6px 0 0;padding-left:19px}",
      ".mk-bd li{margin:0 0 6px}",
      ".mk-q{font-size:12px;color:#8fa3b0;border-left:2px solid #3a444c;",
      "padding-left:9px;margin-bottom:10px;white-space:pre-wrap}",
      ".mk-bd pre{background:#0e1215;padding:9px 11px;border-radius:7px;",
      "overflow:auto;font-size:12.5px}"
    ].join("");
    document.head.appendChild(s);
  }

  function esc(t) {
    return String(t == null ? "" : t).replace(/&/g, "&amp;")
      .replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function hideBar() {
    if (bar) { bar.remove(); bar = null; }
  }

  /* Against the mark itself and inside the viewport. A board is wide enough
     that an unclamped menu opens somewhere nobody can reach. */
  function place(el, rect) {
    el.style.visibility = "hidden";
    document.body.appendChild(el);
    var w = el.offsetWidth, h = el.offsetHeight, pad = 8;
    var x = rect.left + rect.width / 2 - w / 2;
    var y = rect.top - h - pad;
    if (y < pad) y = rect.bottom + pad;                  /* no room above */
    if (y + h > innerHeight - pad) y = innerHeight - h - pad;
    x = Math.max(pad, Math.min(x, innerWidth - w - pad));
    el.style.left = Math.round(x) + "px";
    el.style.top = Math.round(y) + "px";
    el.style.visibility = "";
  }

  function showBar(rect, items) {
    hideBar();
    css();
    bar = document.createElement("div");
    bar.className = "mk-bar";
    items.forEach(function (it) {
      var b = document.createElement("button");
      b.textContent = it.label;
      b.onclick = function (e) {
        e.preventDefault();
        e.stopPropagation();
        hideBar();
        it.run();
      };
      bar.appendChild(b);
    });
    /* Keep the selection alive: a mousedown on the toolbar would otherwise
       collapse it before the button's own click could read it. */
    bar.addEventListener("mousedown", function (e) { e.preventDefault(); });
    bar.addEventListener("pointerdown", function (e) { e.stopPropagation(); });
    place(bar, rect);
  }

  function marked() {
    var sel = global.getSelection && global.getSelection();
    if (!sel || sel.isCollapsed || !sel.rangeCount) return null;
    var text = String(sel).trim();
    if (!text) return null;
    var range = sel.getRangeAt(0);
    var scope = cfg.scope && document.querySelector(cfg.scope);
    if (scope && !scope.contains(range.commonAncestorContainer)) return null;
    var rect = range.getBoundingClientRect();
    if (!rect || (!rect.width && !rect.height)) return null;
    return { text: text, rect: rect };
  }

  function copy(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text)
        .then(function () { say("Copied."); })
        .catch(function () { fallbackCopy(text); });
    }
    fallbackCopy(text);
    return Promise.resolve();
  }

  /* Clipboard permission can be refused, and a board in a school is exactly
     where it will be. A hidden textarea still works there. */
  function fallbackCopy(text) {
    try {
      var t = document.createElement("textarea");
      t.value = text;
      t.style.cssText = "position:fixed;left:-9999px;top:0";
      document.body.appendChild(t);
      t.select();
      document.execCommand("copy");
      t.remove();
      say("Copied.");
    } catch (e) { say("This browser would not let me copy that."); }
  }

  function editable(el) {
    if (!el) return null;
    var e = el.closest && el.closest("input,textarea,[contenteditable=true]");
    return e || null;
  }

  function paste(target) {
    if (!navigator.clipboard || !navigator.clipboard.readText) {
      say("This browser will not let a page read the clipboard. "
        + "Press Ctrl+V or long-press the box itself.");
      return;
    }
    navigator.clipboard.readText().then(function (text) {
      if (!text) { say("There is nothing on the clipboard."); return; }
      if (target.isContentEditable) { target.textContent += text; }
      else {
        var at = target.selectionStart == null
          ? target.value.length : target.selectionStart;
        var end = target.selectionEnd == null ? at : target.selectionEnd;
        target.value = target.value.slice(0, at) + text + target.value.slice(end);
        target.selectionStart = target.selectionEnd = at + text.length;
      }
      target.dispatchEvent(new Event("input", { bubbles: true }));
      target.focus();
    }).catch(function () {
      say("The browser would not give the page the clipboard. Press Ctrl+V.");
    });
  }

  function say(m) {
    if (cfg && typeof cfg.toast === "function") cfg.toast(m);
  }

  /* ---- the answer window ---- */

  function closeWin() {
    if (win) { win.remove(); win = null; }
  }

  function openWin(question) {
    css();
    closeWin();
    win = document.createElement("div");
    win.className = "mk-win";
    win.innerHTML =
      '<div class="mk-hd"><b>Axle</b><button type="button" '
      + 'aria-label="Close">&times;</button></div>'
      + '<div class="mk-bd"><div class="mk-q">' + esc(question) + "</div>"
      + '<div class="mk-out">Thinking…</div></div>';
    document.body.appendChild(win);

    var r = win.getBoundingClientRect();
    win.style.left = Math.round((innerWidth - r.width) / 2) + "px";
    win.style.top = Math.round(Math.max(12, (innerHeight - r.height) / 3)) + "px";

    win.querySelector(".mk-hd button").onclick = closeWin;
    drag(win.querySelector(".mk-hd"), win);
    return win.querySelector(".mk-out");
  }

  /* Pointer events, so a pen drags the window as readily as a mouse. */
  function drag(handle, box) {
    handle.addEventListener("pointerdown", function (e) {
      if (e.target.tagName === "BUTTON") return;
      var sx = e.clientX, sy = e.clientY;
      var r = box.getBoundingClientRect(), ox = r.left, oy = r.top;
      handle.setPointerCapture(e.pointerId);
      function move(ev) {
        var x = ox + ev.clientX - sx, y = oy + ev.clientY - sy;
        x = Math.max(0, Math.min(x, innerWidth - box.offsetWidth));
        y = Math.max(0, Math.min(y, innerHeight - box.offsetHeight));
        box.style.left = Math.round(x) + "px";
        box.style.top = Math.round(y) + "px";
      }
      function up() {
        handle.removeEventListener("pointermove", move);
        handle.removeEventListener("pointerup", up);
      }
      handle.addEventListener("pointermove", move);
      handle.addEventListener("pointerup", up);
      e.preventDefault();
    });
  }

  function render(out, lesson) {
    if (!lesson || !lesson.steps || !lesson.steps.length) {
      out.textContent = "Nothing came back for that.";
      return;
    }
    var h = "";
    if (lesson.title) h += "<b>" + esc(lesson.title) + "</b>";
    lesson.steps.forEach(function (st) {
      var lines = String(st.t || "").split("\n")
        .map(function (x) { return x.trim(); })
        .filter(Boolean);
      if (lines.length > 1) {
        h += "<ul>" + lines.map(function (x) {
          return "<li>" + esc(x) + "</li>";
        }).join("") + "</ul>";
      } else if (lines.length) {
        h += "<p>" + esc(lines[0]) + "</p>";
      }
      if (st.code) h += "<pre>" + esc(st.code) + "</pre>";
    });
    if (lesson.takeaway) h += "<p><b>In short:</b> " + esc(lesson.takeaway) + "</p>";
    out.innerHTML = h;
  }

  function ask(text) {
    var q = text.length > MAX_ASK ? text.slice(0, MAX_ASK) : text;
    var out = openWin(q);
    Promise.resolve(cfg.onAsk(q)).then(function (lesson) {
      if (out.isConnected) render(out, lesson);
    }).catch(function (err) {
      if (out.isConnected) {
        out.textContent = (err && err.message)
          || "That did not come back. Try again.";
      }
    });
  }

  /* ---- wiring ---- */

  function offer() {
    var m = marked();
    if (!m) { hideBar(); return; }
    showBar(m.rect, [
      { label: "Copy", run: function () { copy(m.text); } },
      { label: "Ask Axle", run: function () { ask(m.text); } }
    ]);
  }

  function init(options) {
    cfg = options || {};
    css();

    document.addEventListener("mouseup", function () { setTimeout(offer, 0); });
    document.addEventListener("keyup", function (e) {
      if (e.shiftKey || e.key === "Escape") setTimeout(offer, 0);
    });

    /* A hold is what a pen has instead of a right-click. */
    document.addEventListener("pointerdown", function (e) {
      if (win && win.contains(e.target)) return;
      hideBar();
      holdFrom = { x: e.clientX, y: e.clientY, target: e.target };
      clearTimeout(holdTimer);
      holdTimer = setTimeout(function () {
        if (!holdFrom) return;
        if (marked()) { offer(); return; }   /* a hold over a mark keeps it */
        var box = editable(holdFrom.target);
        var items = [];
        if (box) items.push({
          label: "Paste", run: function () { paste(box); }
        });
        var near = (holdFrom.target.innerText || "").trim();
        if (near) items.push({
          label: "Copy", run: function () { copy(near.slice(0, 4000)); }
        });
        if (!items.length) return;
        showBar({ left: holdFrom.x, top: holdFrom.y, width: 0, height: 0,
                  bottom: holdFrom.y }, items);
      }, HOLD_MS);
    }, true);

    document.addEventListener("pointermove", function (e) {
      if (!holdFrom) return;
      if (Math.abs(e.clientX - holdFrom.x) > HOLD_SLOP
        || Math.abs(e.clientY - holdFrom.y) > HOLD_SLOP) {
        clearTimeout(holdTimer);
        holdFrom = null;
      }
    }, true);

    ["pointerup", "pointercancel"].forEach(function (n) {
      document.addEventListener(n, function () {
        clearTimeout(holdTimer);
        holdFrom = null;
      }, true);
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { hideBar(); closeWin(); }
    });

    /* Scrolling moves the board under a toolbar pinned to the viewport. */
    global.addEventListener("scroll", hideBar, true);
    global.addEventListener("resize", hideBar);
  }

  global.Marker = { init: init, close: closeWin, hide: hideBar, ask: ask };
})(window);
