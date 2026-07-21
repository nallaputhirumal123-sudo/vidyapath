/* ==========================================================================
   VidyaPath PRESENTER — Vidya, full-body, gesturing, speaking.

   Extends tutor.js. Load AFTER it. Adds:
     Presenter.open()        full presenter panel with a talking figure
     Presenter.tour()        spoken guided tour of the whole course
     Presenter.explain(txt)  say anything, with matching gestures

   Still no API key, no internet, no cost. Browser speech only.
   NOTE: never put a literal closing script tag in this file, even in a
   comment — it truncates the file when embedded directly into a page.
   ========================================================================== */

(function (global) {
"use strict";

var el = {};
var speaking = false;
var gestureTimer = null;
var blinkTimer = null;
var mouthTimer = null;
var breathTimer = null;
var queue = [];
var queueIndex = 0;
var stopped = false;

function muted() {
  return global.Tutor ? global.Tutor.isMuted() : false;
}

/* ---------------------------------------------------------------- figure */
/* Full body, waist up. Arms are separate groups so they can gesture. */
function figureSVG() {
  return '' +
  '<svg id="vpFig" viewBox="0 0 260 300" width="100%" height="100%">' +
    '<defs>' +
      '<linearGradient id="pSkin" x1="0" y1="0" x2="0" y2="1">' +
        '<stop offset="0%" stop-color="#f2cea6"/><stop offset="100%" stop-color="#e2b489"/>' +
      '</linearGradient>' +
      '<linearGradient id="pKurta" x1="0" y1="0" x2="1" y2="1">' +
        '<stop offset="0%" stop-color="#ffa842"/><stop offset="100%" stop-color="#e0761a"/>' +
      '</linearGradient>' +
      '<radialGradient id="pGlow" cx="50%" cy="45%" r="55%">' +
        '<stop offset="0%" stop-color="#ffb347" stop-opacity=".22"/>' +
        '<stop offset="100%" stop-color="#ffb347" stop-opacity="0"/>' +
      '</radialGradient>' +
    '</defs>' +

    '<ellipse cx="130" cy="150" rx="125" ry="140" fill="url(#pGlow)"/>' +

    /* ---- left arm (viewer left) ---- */
    '<g id="pArmL" style="transform-origin:88px 190px">' +
      '<path d="M88 190 Q62 218 58 250" stroke="url(#pKurta)" stroke-width="21" ' +
            'fill="none" stroke-linecap="round"/>' +
      '<circle cx="58" cy="252" r="11" fill="url(#pSkin)"/>' +
    '</g>' +

    /* ---- right arm — the gesturing one ---- */
    '<g id="pArmR" style="transform-origin:172px 190px">' +
      '<path d="M172 190 Q198 218 202 250" stroke="url(#pKurta)" stroke-width="21" ' +
            'fill="none" stroke-linecap="round"/>' +
      '<circle cx="202" cy="252" r="11" fill="url(#pSkin)"/>' +
    '</g>' +

    /* ---- torso ---- */
    '<g id="pBody">' +
      '<path d="M78 300 Q78 186 130 186 Q182 186 182 300 Z" fill="url(#pKurta)"/>' +
      '<path d="M130 186 L130 300" stroke="#c96612" stroke-width="1.6" opacity=".5"/>' +
      '<path d="M112 188 Q130 206 148 188" fill="none" stroke="#fff7ec" ' +
            'stroke-width="3" opacity=".8"/>' +
      /* dupatta over one shoulder */
      '<path d="M150 190 Q186 214 178 300" fill="none" stroke="#7cc2ff" ' +
            'stroke-width="13" opacity=".82" stroke-linecap="round"/>' +
    '</g>' +

    /* ---- neck ---- */
    '<rect x="119" y="158" width="22" height="34" rx="10" fill="#e2b489"/>' +

    /* ---- head ---- */
    '<g id="pHead" style="transform-origin:130px 118px">' +
      '<ellipse cx="130" cy="118" rx="45" ry="50" fill="url(#pSkin)"/>' +

      /* hair back + bun */
      '<path d="M85 116 Q85 62 130 62 Q175 62 175 116 Q175 96 158 88 ' +
            'Q142 100 118 94 Q98 94 92 112 Z" fill="#2a1a12"/>' +
      '<circle cx="130" cy="66" r="15" fill="#2a1a12"/>' +

      /* ears */
      '<ellipse cx="85" cy="122" rx="7" ry="12" fill="#e2b489"/>' +
      '<ellipse cx="175" cy="122" rx="7" ry="12" fill="#e2b489"/>' +

      /* eyes */
      '<g id="pEyes">' +
        '<ellipse cx="112" cy="117" rx="8" ry="9" fill="#fff"/>' +
        '<ellipse cx="148" cy="117" rx="8" ry="9" fill="#fff"/>' +
        '<circle cx="112.8" cy="118.5" r="4.6" fill="#2a1a12"/>' +
        '<circle cx="148.8" cy="118.5" r="4.6" fill="#2a1a12"/>' +
        '<circle cx="114.4" cy="116.4" r="1.6" fill="#fff"/>' +
        '<circle cx="150.4" cy="116.4" r="1.6" fill="#fff"/>' +
      '</g>' +
      '<g id="pLids" style="opacity:0">' +
        '<ellipse cx="112" cy="117" rx="8.6" ry="9.6" fill="#eac49b"/>' +
        '<ellipse cx="148" cy="117" rx="8.6" ry="9.6" fill="#eac49b"/>' +
      '</g>' +

      /* brows — move with expression */
      '<g id="pBrows">' +
        '<path d="M102 102 Q112 97 122 102" stroke="#2a1a12" stroke-width="3.2" ' +
              'fill="none" stroke-linecap="round"/>' +
        '<path d="M138 102 Q148 97 158 102" stroke="#2a1a12" stroke-width="3.2" ' +
              'fill="none" stroke-linecap="round"/>' +
      '</g>' +

      /* nose */
      '<path d="M130 122 L126 134 Q130 136.5 134 134" stroke="#cf9d76" ' +
            'stroke-width="2.4" fill="none" stroke-linecap="round"/>' +

      /* mouth — animates while speaking */
      '<ellipse id="pMouth" cx="130" cy="146" rx="12" ry="3.4" fill="#a03f45"/>' +
      '<path id="pSmile" d="M118 144 Q130 152 142 144" stroke="#a03f45" ' +
            'stroke-width="2.6" fill="none" stroke-linecap="round" style="opacity:0"/>' +

      /* bindi */
      '<circle cx="130" cy="94" r="3.4" fill="#c2410c"/>' +
    '</g>' +
  '</svg>';
}

/* ----------------------------------------------------------------- style */
var CSS = '' +
'#vpPresenter{position:fixed;inset:0;z-index:10000;background:rgba(6,10,16,.72);' +
  'backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);display:none;' +
  'align-items:center;justify-content:center;padding:20px;' +
  'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}' +
'#vpPresenter.on{display:flex}' +
'#vpPanel{background:var(--panel,#131923);color:var(--text,#e8eef6);' +
  'border:1px solid var(--line,#252e3d);border-radius:22px;width:100%;max-width:860px;' +
  'max-height:92vh;overflow:hidden;display:grid;grid-template-columns:280px 1fr;' +
  'box-shadow:0 30px 90px rgba(0,0,0,.5)}' +
'#vpStage{background:linear-gradient(170deg,rgba(255,168,66,.13),transparent 65%);' +
  'display:flex;align-items:flex-end;justify-content:center;padding:14px 8px 0;' +
  'border-right:1px solid var(--line,#252e3d);position:relative;min-height:300px}' +
'#vpStage svg{max-height:330px;width:100%}' +
'#vpLive{position:absolute;top:12px;left:12px;font-size:10px;font-weight:800;' +
  'letter-spacing:1px;padding:4px 10px;border-radius:99px;background:rgba(0,0,0,.35);' +
  'color:#9aa7b8;border:1px solid rgba(255,255,255,.12)}' +
'#vpPresenter.speaking #vpLive{color:#3fb950;border-color:rgba(63,185,80,.4)}' +
'#vpSide{padding:26px 28px;overflow-y:auto;display:flex;flex-direction:column}' +
'#vpSide h3{font-size:19px;font-weight:750;letter-spacing:-.3px;margin-bottom:3px}' +
'#vpSide .who{font-size:11px;text-transform:uppercase;letter-spacing:1.2px;' +
  'color:var(--accent,#ff9933);font-weight:800;margin-bottom:10px}' +
'#vpText{font-size:15.5px;line-height:1.72;color:var(--body,#ccd6e2);flex:1;' +
  'min-height:110px;margin-bottom:14px}' +
'#vpProg{height:4px;background:rgba(255,255,255,.09);border-radius:99px;' +
  'overflow:hidden;margin-bottom:16px}' +
'#vpProg i{display:block;height:100%;background:linear-gradient(90deg,#ffb347,#f08a1d);' +
  'transition:width .4s}' +
'#vpBtns{display:flex;gap:8px;flex-wrap:wrap}' +
'#vpBtns button{font-family:inherit;font-size:13.5px;padding:9px 16px;border-radius:9px;' +
  'border:1px solid var(--line,#252e3d);background:transparent;' +
  'color:var(--text,#e8eef6);cursor:pointer}' +
'#vpBtns button:hover{border-color:var(--accent,#ff9933);color:var(--accent,#ff9933)}' +
'#vpBtns button.pri{background:linear-gradient(135deg,#ffb347,#f08a1d);' +
  'color:#10151c;border-color:transparent;font-weight:650}' +
'#vpBtns button.pri:hover{color:#10151c;filter:brightness(1.08)}' +
'#pArmR,#pArmL,#pHead{transition:transform .5s cubic-bezier(.34,1.4,.64,1)}' +
'#pBody{transition:transform 2.4s ease-in-out}' +
'@media(max-width:720px){' +
  '#vpPanel{grid-template-columns:1fr;max-height:94vh}' +
  '#vpStage{min-height:190px;border-right:none;' +
    'border-bottom:1px solid var(--line,#252e3d)}' +
  '#vpStage svg{max-height:190px}' +
  '#vpSide{padding:20px}}' +
'@media print{#vpPresenter{display:none!important}}';

/* ------------------------------------------------------------- animation */
var GESTURES = {
  rest:    { armR:"rotate(0deg)",                 armL:"rotate(0deg)",  head:"rotate(0deg)" },
  point:   { armR:"rotate(-58deg) translateY(-8px)", armL:"rotate(0deg)",  head:"rotate(-3deg)" },
  open:    { armR:"rotate(-34deg)",               armL:"rotate(30deg)", head:"rotate(0deg)" },
  count:   { armR:"rotate(-46deg) translateX(-6px)", armL:"rotate(0deg)",  head:"rotate(2deg)" },
  think:   { armR:"rotate(-72deg) translateX(-26px)", armL:"rotate(0deg)", head:"rotate(6deg)" },
  welcome: { armR:"rotate(-40deg)",               armL:"rotate(38deg)", head:"rotate(-2deg)" },
};

function setGesture(name) {
  var g = GESTURES[name] || GESTURES.rest;
  var r = document.getElementById("pArmR");
  var l = document.getElementById("pArmL");
  var h = document.getElementById("pHead");
  if (r) r.style.transform = g.armR;
  if (l) l.style.transform = g.armL;
  if (h) h.style.transform = g.head;
}

/* Pick a gesture that matches what is being said. */
function gestureFor(text) {
  var t = (text || "").toLowerCase();
  if (/welcome|hello|hi |namaste|glad/.test(t))            return "welcome";
  if (/first|second|third|one|two|three|stage|step/.test(t)) return "count";
  if (/notice|look|here|this|see |above|below/.test(t))    return "point";
  if (/think|remember|understand|why|question|imagine/.test(t)) return "think";
  return "open";
}

function startIdle() {
  clearInterval(blinkTimer);
  blinkTimer = setInterval(function () {
    var lids = document.getElementById("pLids");
    if (!lids) return;
    lids.style.transition = "opacity .09s";
    lids.style.opacity = "1";
    setTimeout(function () { lids.style.opacity = "0"; }, 120);
  }, 3600 + Math.random() * 2400);

  clearInterval(breathTimer);
  var up = false;
  breathTimer = setInterval(function () {
    var b = document.getElementById("pBody");
    if (!b) return;
    up = !up;
    b.style.transform = up ? "translateY(-2.5px)" : "translateY(0)";
  }, 2400);
}

function setSpeaking(on) {
  speaking = on;
  if (el.root) el.root.classList.toggle("speaking", on);
  if (el.live) el.live.textContent = on ? "● SPEAKING" : "○ READY";

  clearInterval(mouthTimer);
  var mouth = document.getElementById("pMouth");
  var smile = document.getElementById("pSmile");
  if (!mouth) return;

  if (on) {
    if (smile) smile.style.opacity = "0";
    mouth.style.opacity = "1";
    mouthTimer = setInterval(function () {
      mouth.setAttribute("ry", (2 + Math.random() * 6).toFixed(1));
      mouth.setAttribute("rx", (10 + Math.random() * 4).toFixed(1));
    }, 105);
  } else {
    mouth.setAttribute("ry", "3.4");
    mouth.setAttribute("rx", "12");
    mouth.style.opacity = "0";
    if (smile) smile.style.opacity = "1";
    setGesture("rest");
  }
}

/* --------------------------------------------------------------- speech */
function speak(text, onDone) {
  setGesture(gestureFor(text));

  if (muted() || !global.speechSynthesis) {
    // Voice off: still show the line, pace it by length so it stays readable
    setSpeaking(true);
    var wait = Math.min(9000, 1400 + text.length * 42);
    setTimeout(function () { setSpeaking(false); if (onDone) onDone(); }, wait);
    return;
  }

  try {
    global.speechSynthesis.cancel();
    var u = new SpeechSynthesisUtterance(text);
    u.rate = 0.95;
    u.pitch = 1.05;

    var voices = global.speechSynthesis.getVoices() || [];
    var pick = voices.filter(function (v) {
      return /en[-_]IN/i.test(v.lang) || /India/i.test(v.name);
    })[0] || voices.filter(function (v) { return /^en/i.test(v.lang); })[0];
    if (pick) u.voice = pick;

    u.onstart = function () { setSpeaking(true); };
    u.onend   = function () { setSpeaking(false); if (onDone) onDone(); };
    u.onerror = function () { setSpeaking(false); if (onDone) onDone(); };

    global.speechSynthesis.speak(u);

    // Re-gesture mid-sentence so long lines do not freeze
    clearInterval(gestureTimer);
    gestureTimer = setInterval(function () {
      if (speaking) setGesture(gestureFor(text));
      else clearInterval(gestureTimer);
    }, 3400);
  } catch (e) {
    setSpeaking(false);
    if (onDone) onDone();
  }
}

function stopAll() {
  stopped = true;
  clearInterval(gestureTimer);
  try { if (global.speechSynthesis) global.speechSynthesis.cancel(); } catch (e) {}
  setSpeaking(false);
}

/* ------------------------------------------------------------- the tour */
function buildTour() {
  var tracks = (global.TRACKS && global.TRACKS.length) ? global.TRACKS : [];
  var lessons = 0, exercises = 0;
  tracks.forEach(function (t) {
    lessons += t.lessons.length;
    t.lessons.forEach(function (l) { exercises += (l.exercises || []).length; });
  });

  var lines = [
    "Hello, and welcome to VidyaPath. I am Vidya, and I will walk you through what this course is and how to use it.",
    "This course takes you from never having written a single line of code, all the way to building real artificial intelligence systems. Nothing is assumed at any point.",
  ];

  if (lessons) {
    lines.push("Right now there are " + lessons + " lessons and " + exercises +
      " coding exercises waiting for you. Every single exercise has been tested, so if your answer is marked correct, it genuinely is correct.");
  }

  lines = lines.concat([
    "The course is organised into six stages, and you should go through them in order.",
    "Stage one is for absolute beginners. It explains what a computer actually does, then teaches variables, decisions, loops and lists. It even explains what artificial intelligence really is, honestly, without the hype.",
    "Stage two makes you fluent in Python. Handling text properly, structuring real data, writing code the way working programmers actually write it.",
    "Stage three is databases and SQL. This is the most valuable stage for getting a job quickly. Every query you write runs against a real database, right here in your browser.",
    "Stage four is data analysis. Taking messy real data, cleaning it honestly, and reporting what you found without misleading anybody.",
    "Stage five is the mathematics, then machine learning and artificial intelligence. You will build the learning loop by hand, so it stops feeling like magic and starts feeling like something you understand.",
    "Stage six covers other languages and career preparation. Your portfolio, your resume, and what interviews actually test.",
    "Now, how to actually use this. Read the notes first. Then close them, and try to explain the idea out loud to yourself. If you cannot, read them again.",
    "Then do the exercises. Type them out yourself. Do not copy and paste, and do not open the solution until you have genuinely tried. Being stuck for ten minutes teaches you more than reading for an hour.",
    "You will get errors. Everybody does, every day, at every level of experience. An error is just the computer telling you which line it did not understand. Read the last line, fix it, and run again.",
    "Every lesson also has a printable worksheet. Answer those questions on paper, in your own words. Writing an explanation is the fastest way to find out whether you truly understood something.",
    "Two hours a day, six days a week, will take you through the whole course in about nine months. One hour a day still works. It just takes longer.",
    "Finish all the lessons in a stage and you earn a certificate for it. You earn it by passing real graded work, not by watching videos.",
    "And I am always here. Tap me any time and I will explain what to do, or read a lesson out loud for you.",
    "That is everything. Start with stage one, lesson one, and go slowly. Good luck.",
  ]);

  return lines;
}

/* ------------------------------------------------------------------ api */
var API = {

  init: function () {
    if (el.root) return;

    var style = document.createElement("style");
    style.textContent = CSS;
    document.head.appendChild(style);

    var root = document.createElement("div");
    root.id = "vpPresenter";
    root.innerHTML =
      '<div id="vpPanel">' +
        '<div id="vpStage"><div id="vpLive">○ READY</div>' + figureSVG() + '</div>' +
        '<div id="vpSide">' +
          '<div class="who">Vidya &middot; your guide</div>' +
          '<h3 id="vpTitle">Course introduction</h3>' +
          '<div id="vpProg"><i style="width:0%"></i></div>' +
          '<div id="vpText"></div>' +
          '<div id="vpBtns">' +
            '<button class="pri" id="vpNext">Next</button>' +
            '<button id="vpRepeat">Say again</button>' +
            '<button id="vpSkip">Skip tour</button>' +
            '<button id="vpClose">Close</button>' +
          '</div>' +
        '</div>' +
      '</div>';
    document.body.appendChild(root);

    el.root  = root;
    el.text  = root.querySelector("#vpText");
    el.title = root.querySelector("#vpTitle");
    el.prog  = root.querySelector("#vpProg i");
    el.live  = root.querySelector("#vpLive");

    root.querySelector("#vpNext").onclick   = function () { stopAll(); stopped = false; step(1); };
    root.querySelector("#vpRepeat").onclick = function () { stopAll(); stopped = false; step(0); };
    root.querySelector("#vpSkip").onclick   = function () { API.close(); };
    root.querySelector("#vpClose").onclick  = function () { API.close(); };
    root.addEventListener("click", function (e) { if (e.target === root) API.close(); });

    startIdle();
    setSpeaking(false);
  },

  tour: function () {
    API.init();
    queue = buildTour();
    queueIndex = -1;
    stopped = false;
    el.title.textContent = "Course introduction";
    el.root.classList.add("on");
    step(1);
  },

  explain: function (text, title) {
    API.init();
    queue = Array.isArray(text) ? text : [text];
    queueIndex = -1;
    stopped = false;
    el.title.textContent = title || "Vidya explains";
    el.root.classList.add("on");
    step(1);
  },

  open: function () { API.tour(); },

  close: function () {
    stopAll();
    if (el.root) el.root.classList.remove("on");
  },
};

function step(delta) {
  queueIndex += delta;
  if (queueIndex < 0) queueIndex = 0;

  if (queueIndex >= queue.length) {
    el.text.textContent = "That is the end of the tour. Close this and start with Stage 1.";
    el.prog.style.width = "100%";
    setGesture("welcome");
    return;
  }

  var line = queue[queueIndex];
  el.text.textContent = line;
  el.prog.style.width = Math.round((queueIndex + 1) / queue.length * 100) + "%";

  speak(line, function () {
    // auto-advance unless the user interrupted
    if (!stopped && queueIndex < queue.length - 1) {
      setTimeout(function () { if (!stopped) step(1); }, 380);
    }
  });
}

global.Presenter = API;

})(window);
