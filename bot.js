/* Axle, in the corner of every page.
 *
 * This replaces the scripted mascot that used to sit here. That thing had a
 * list of written tips and picked one — which is fine until somebody asks it
 * something, because it could not answer. A help button that cannot take a
 * question is decoration, and people learn within a day to stop pressing it.
 *
 * This one takes a question by typing or by talking, on any subject, from
 * anywhere on the site. Replies are short on purpose: this is the corner of
 * the screen, not the board. Anything that wants a diagram, runnable code or
 * a worked derivation gets handed to Ask Axle, which is built for it.
 *
 * Cost: every reply goes through /api/ask/talk, which is cached on the
 * question. The first person to ask what a foreign key is pays for it and
 * everyone after them does not.
 */
(function () {
  "use strict";

  var B = {
    open: false,
    turns: [],        // {who: "you"|"ax", text}
    busy: false,
    unread: false
  };
  window.Bot = B;

  function esc(s) {
    return String(s).replace(/[&<>]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c];
    });
  }

  var CSS = [
    "#botFab{position:fixed;right:20px;bottom:20px;z-index:8500;width:56px;",
    "  height:56px;border-radius:50%;border:none;cursor:pointer;font-size:23px;",
    "  display:flex;align-items:center;justify-content:center;color:#fff;",
    "  background:linear-gradient(150deg,#ff9933,#c2410c);",
    "  box-shadow:0 8px 24px rgba(0,0,0,.32);transition:transform .15s ease}",
    "#botFab:hover{transform:scale(1.06)}",
    "#botFab .dot{position:absolute;top:0;right:0;width:13px;height:13px;",
    "  border-radius:50%;background:#3fae6a;border:2px solid var(--bg,#0b0b0b)}",
    "#botPanel{position:fixed;right:20px;bottom:88px;z-index:8500;",
    "  width:min(380px,calc(100vw - 40px));max-height:min(72vh,560px);",
    "  display:flex;flex-direction:column;border-radius:18px;overflow:hidden;",
    "  background:var(--panel,#151515);border:1px solid var(--line,#2a2a2a);",
    "  box-shadow:0 18px 60px rgba(0,0,0,.5)}",
    "@media(max-width:520px){#botPanel{right:10px;left:10px;bottom:84px;",
    "  width:auto;max-height:70vh}}",
    "#botHead{display:flex;align-items:center;gap:9px;padding:13px 15px;",
    "  border-bottom:1px solid var(--line,#2a2a2a);font-size:14px;",
    "  font-weight:750}",
    "#botHead .sub{font-size:11px;font-weight:400;color:var(--muted,#8a8a8a)}",
    "#botLog{flex:1;overflow-y:auto;padding:14px 15px;min-height:120px}",
    ".botT{margin-bottom:12px;font-size:13.5px;line-height:1.65}",
    ".botT small{display:block;font-size:10px;letter-spacing:.6px;",
    "  text-transform:uppercase;color:var(--dim,#666);margin-bottom:3px}",
    ".botT.you{color:var(--muted,#8a8a8a)}",
    ".botT.ax{color:var(--text,#eee);white-space:pre-wrap}",
    ".botHint{font-size:12.5px;color:var(--muted,#8a8a8a);line-height:1.65}",
    ".botChip{font-size:11.5px;padding:5px 10px;border-radius:999px;",
    "  border:1px solid var(--line,#2a2a2a);background:transparent;",
    "  color:inherit;cursor:pointer;margin:0 5px 5px 0}",
    ".botChip:hover{border-color:var(--accent,#ffb020)}",
    "#botFoot{padding:11px 13px;border-top:1px solid var(--line,#2a2a2a)}",
    "#botRow{display:flex;gap:7px;align-items:center}",
    "#botIn{flex:1;min-width:0;font-size:13px;padding:9px 12px;",
    "  border-radius:10px;border:1px solid var(--line,#2a2a2a);",
    "  background:var(--panel2,#0f0f0f);color:var(--text,#eee)}",
    "#botIn:focus{outline:none;border-color:var(--accent,#ffb020)}",
    ".botIcon{width:36px;height:36px;flex:0 0 36px;border-radius:10px;",
    "  border:1px solid var(--line,#2a2a2a);background:transparent;",
    "  color:inherit;cursor:pointer;font-size:15px}",
    ".botIcon:hover{border-color:var(--accent,#ffb020)}",
    "@media print{#botFab,#botPanel{display:none!important}}"
  ].join("");

  // Things people actually arrive wanting, phrased as they would say them.
  var STARTERS = [
    "Explain this page to me",
    "What should I learn first?",
    "How do I use the SQL board?"
  ];

  function styles() {
    if (document.getElementById("bot-css")) return;
    var s = document.createElement("style");
    s.id = "bot-css";
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  function panel() {
    return document.getElementById("botPanel");
  }

  function draw() {
    var p = panel();
    if (!p) return;
    var log = B.turns.map(function (t) {
      return '<div class="botT ' + (t.who === "you" ? "you" : "ax") + '">' +
        "<small>" + (t.who === "you" ? "You" : "Axle") + "</small>" +
        esc(t.text) + "</div>";
    }).join("");
    // What it is hearing, as it hears it. Without this you cannot tell "it
    // did not hear me" from "it heard me wrong", and those need completely
    // different things from the person sitting there.
    if (B.listening && B.heard) {
      log += '<div class="botT you"><small>You</small><i>' + esc(B.heard) +
        "…</i></div>";
    }
    if (B.busy) log += '<div class="botHint">Thinking…</div>';
    // Every answer can be taken to the board, where it gets the room for
    // steps, code and a diagram that this corner does not have.
    if (B.turns.length && B.turns[B.turns.length - 1].who === "ax" && !B.busy) {
      log += '<button class="botChip" id="botBoard">⚡ Explain this on the ' +
        "smart board</button>";
    }
    if (!B.turns.length) {
      log = '<div class="botHint">Ask me anything — any subject, not just ' +
        "the ones with a track here. Short answers in this corner; press " +
        "the microphone to talk instead.</div><div style=\"margin-top:11px\">" +
        STARTERS.map(function (s) {
          return '<button class="botChip" data-botq="' + esc(s) + '">' +
            esc(s) + "</button>";
        }).join("") + "</div>";
    }
    var l = p.querySelector("#botLog");
    l.innerHTML = log;
    l.scrollTop = l.scrollHeight;
    wire();
  }

  /* ---- "explain that on the board" ---------------------------------
   *
   * Matched here rather than sent to a model to be classified. The phrasing
   * is a small, closed set — people say "on the board" or they do not — and
   * paying for a round trip to be told which is which would be paying to
   * learn something a regular expression already knows. It also makes the
   * handoff instant, which matters when it was asked out loud.
   */
  var BOARD_RE = /\b(?:(?:explain|show|teach|open|put|draw|do)\s+(?:me\s+|it\s+|this\s+|that\s+)?)?(?:on|in|to)\s+the\s+(?:smart\s*)?board\b/i;
  var STRIP = /\b(?:can you|could you|please|axle|explain|show me|show|teach me|teach|open|put|draw|do)\b/gi;

  function boardTopic(text, fallback) {
    // Everything that is not the instruction is the topic.
    var t = text.replace(BOARD_RE, " ").replace(STRIP, " ")
      .replace(/\b(?:it|this|that|them)\b/gi, " ")
      .replace(/[?.!,]+/g, " ").replace(/\s{2,}/g, " ").trim();
    return t.length >= 3 ? t : (fallback || "");
  }

  B.toBoard = function (topic) {
    topic = (topic || "").trim();
    if (!topic) return false;
    if (typeof sbTeach !== "function" || typeof S === "undefined") return false;
    if (B.open) toggle();
    if (typeof Voice !== "undefined" && Voice.on) Voice.stop();
    S.view = { page: "ask" };
    if (typeof render === "function") render();
    sbTeach(topic);
    return true;
  };

  /* The last thing worth explaining properly — used when somebody says "put
     that on the board", where "that" is the previous exchange, not the
     sentence containing the word "that". */
  function lastTopic() {
    for (var i = B.turns.length - 1; i >= 0; i--) {
      if (B.turns[i].who === "you" && !BOARD_RE.test(B.turns[i].text)) {
        return B.turns[i].text;
      }
    }
    return "";
  }

  async function send(text) {
    text = (text || "").trim();
    if (!text || B.busy) return;
    var box = document.getElementById("botIn");
    if (box) box.value = "";

    if (BOARD_RE.test(text)) {
      var topic = boardTopic(text, lastTopic());
      if (topic && B.toBoard(topic)) {
        B.turns.push({ who: "you", text: text });
        B.turns.push({ who: "ax",
          text: "Opening the board on " + topic + "." });
        draw();
        return "Opening the board on " + topic + ".";
      }
    }

    B.turns.push({ who: "you", text: text });
    B.busy = true;
    draw();
    var say = "";
    try {
      var r = await api.post("/api/ask/talk", {
        said: text,
        subject: (typeof ASK !== "undefined" && ASK.subject) || "General",
        level: (typeof ASK !== "undefined" && ASK.level) || "Intermediate",
        history: B.turns.slice(-5).map(function (t) {
          return (t.who === "you" ? "They said: " : "You said: ") + t.text;
        })
      });
      say = r.say;
    } catch (e) {
      say = e.message || "I could not answer that just now.";
    }
    B.turns.push({ who: "ax", text: say });
    B.busy = false;
    draw();
    return say;
  }
  B.send = send;

  function wire() {
    var p = panel();
    if (!p) return;
    p.querySelectorAll("[data-botq]").forEach(function (el) {
      el.onclick = function () { send(el.dataset.botq); };
    });
    var b = p.querySelector("#botBoard");
    if (b) b.onclick = function () { B.toBoard(lastTopic()); };
  }

  function build() {
    styles();
    if (panel()) return;
    var p = document.createElement("div");
    p.id = "botPanel";
    p.setAttribute("role", "dialog");
    p.setAttribute("aria-label", "Ask Axle");
    p.innerHTML =
      '<div id="botHead">⚡ Axle' +
        '<span class="sub">any subject</span>' +
        '<span style="flex:1"></span>' +
        '<button class="botIcon" id="botFull" title="Open the full board">⤢</button>' +
        '<button class="botIcon" id="botX" title="Close">✕</button>' +
      "</div>" +
      '<div id="botLog" aria-live="polite"></div>' +
      '<div id="botFoot"><div id="botRow">' +
        '<button class="botIcon" id="botMic" title="Talk instead">🎙</button>' +
        '<input id="botIn" placeholder="Ask anything…" maxlength="600">' +
        '<button class="botIcon" id="botGo" title="Send">→</button>' +
      "</div></div>";
    document.body.appendChild(p);

    p.querySelector("#botX").onclick = toggle;
    p.querySelector("#botGo").onclick = function () {
      send(document.getElementById("botIn").value);
    };
    p.querySelector("#botIn").onkeydown = function (e) {
      if (e.key === "Enter") { e.preventDefault(); send(e.target.value); }
    };
    p.querySelector("#botMic").onclick = B.talk;
    p.querySelector("#botFull").onclick = function () {
      toggle();
      if (typeof S !== "undefined") { S.view = { page: "ask" }; render(); }
    };
    draw();
  }

  /* ---- talking ------------------------------------------------------
   *
   * One conversation, two ways of putting things into it. Speech goes through
   * exactly the same send() as typing, so the transcript, the board handoff
   * and the history are identical whichever way you asked — and the reply
   * appears as text at the moment the voice starts saying it, rather than
   * afterwards, because watching the words arrive is how you follow along and
   * how you know it heard you right.
   */
  B.talk = function () {
    if (typeof Voice === "undefined") return;
    if (Voice.on) { Voice.stop(); B.listening = false; draw(); return; }
    if (!Voice.supported()) {
      B.turns.push({ who: "ax", text: "Talking needs Chrome, on desktop or " +
        "Android. Typing works everywhere." });
      return draw();
    }
    if (!B.open) toggle();
    Voice.start(function (said) {
      // send() pushes both turns and repaints, so the answer is on screen
      // before it is spoken. It also returns the text, which is what the
      // voice then reads — one string, one source of truth.
      return send(said);
    }, function (v) {
      B.listening = v.on && v.state === "listening";
      B.heard = v.heard;
      B.speaking = v.state === "speaking";
      var mic = document.getElementById("botMic");
      if (mic) {
        mic.textContent = !v.on ? "🎙"
          : v.state === "listening" ? "🔴"
          : v.state === "speaking" ? "🔊" : "…";
        mic.title = v.on ? "Stop talking" : "Talk instead";
      }
      draw();
    });
    draw();
  };

  function toggle() {
    B.open = !B.open;
    if (B.open) {
      build();
      var box = document.getElementById("botIn");
      if (box) box.focus();
    } else {
      var p = panel();
      if (p) p.remove();
    }
    var fab = document.getElementById("botFab");
    if (fab) fab.textContent = B.open ? "✕" : "⚡";
  }

  function mount() {
    styles();
    if (document.getElementById("botFab")) return;
    var f = document.createElement("button");
    f.id = "botFab";
    f.type = "button";
    f.textContent = "⚡";
    f.setAttribute("aria-label", "Ask Axle");
    f.onclick = toggle;
    document.body.appendChild(f);

    // The old mascot lived in this exact corner. Two round buttons on top of
    // one another is not a design decision anybody made.
    var old = document.getElementById("vpMini");
    if (old) old.style.display = "none";
    var oldRoot = document.getElementById("vpTutor");
    if (oldRoot) oldRoot.style.display = "none";
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();
