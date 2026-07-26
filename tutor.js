/* ==========================================================================
   Craxle TUTOR — an on-screen guide who explains what to do.

   Self-contained. No API key, no internet, no cost. Uses the browser's
   built-in speech synthesis, so it works offline and responds instantly.

   Usage:  load this file with a script tag, then:

           Tutor.init();                       creates the character
           Tutor.say("text");                  speak + show a bubble
           Tutor.onLesson(lessonObj, trackObj) guidance for a lesson
           Tutor.onExercisePass(n);
           Tutor.onExerciseFail(n, attempts);
           Tutor.readAloud(element);           reads lesson notes out loud

   NOTE: never put a literal closing script tag in this file, even inside a
   comment. It truncates the file when embedded directly into a page.
   ========================================================================== */

(function (global) {
"use strict";

/* ---------------------------------------------------------------- state */
var el = {};                 // dom references
var speaking = false;
var muted   = false;
var minimised = false;
var queue = [];
var currentUtterance = null;
var blinkTimer = null;
var mouthTimer = null;

try { muted = localStorage.getItem("vp_tutor_muted") === "1"; } catch (e) {}
try { minimised = localStorage.getItem("vp_tutor_min") === "1"; } catch (e) {}

/* ------------------------------------------------------------- messages */
/* Guidance keyed by track id, then by lesson id. Falls back sensibly. */
var LESSON_TIPS = {
  /* Stage 1 */
  "sc1": "This is your very first lesson. Read the notes slowly, then try the exercises. Do not worry about remembering everything.",
  "sc2": "A variable is just a box with a label on it. If that idea makes sense, the rest of this lesson is easy.",
  "sc3": "The tricky part here is that input always gives you text, never a number. Watch out for that in the exercises.",
  "sc4": "Two things trip everyone up here. The colon at the end of the if line, and using two equals signs to compare.",
  "sc5": "Loops save you from writing the same line a thousand times. Remember that range starts counting at zero.",
  "sc6": "Lists hold many values in one box. The first item is at position zero, not one.",
  "sc7": "A function is an instruction you invent yourself. The key idea is the difference between print and return.",
  "sc8": "Now you put everything together. Write the steps in plain English on paper first, before you write any code.",
  "sc9": "No code in this lesson. Just read carefully and answer in your own words. This is the lesson that explains what AI really is.",

  /* Stage 2 */
  "t1":  "Text works just like a list. Each letter has a position, starting at zero.",
  "t2":  "This lesson is about cleaning messy text. The strip and lower trick will save you many hours later.",
  "t3":  "Formatting makes your work look finished. Small detail, big difference in how people judge it.",
  "d1":  "Dictionaries give every value a label. This is the most useful structure in all of Python.",
  "d2":  "Comprehensions are a shortcut for a loop you have already written many times. Do not force them everywhere.",

  /* Stage 3A - SQL */
  "q1":  "Now you are talking to a database. Remember, SQL uses one equals sign to compare, not two like Python.",
  "q2":  "Sorting and counting. The important idea is that where runs before the counting happens.",
  "q3":  "Group by sorts rows into piles, then summarises each pile. Hold that picture and this lesson is simple.",
  "q4":  "Joins connect two tables. Take it one row at a time and it makes sense.",
  "q5":  "This lesson has the most expensive mistake in the whole course. Never forget the where on an update.",

  /* Stage 3B - Data */
  "da1": "Always look at data before you analyse it. Thirty seconds of checking prevents very embarrassing mistakes.",
  "da2": "Cleaning is eighty percent of a real data job. This is not boring, it is the actual work.",
  "da3": "Grouping in Python. You already did this in SQL, so the thinking should feel familiar.",
  "da4": "Charts can lie without a single false number. Learn what not to do here.",

  /* Stage 4 - ML */
  "m1":  "Now we get to machine learning. The big idea is that the computer works out the rule instead of you writing it.",
  "m2":  "You are going to build the learning loop by hand. Once you do this, it stops being magic forever.",
  "m3":  "This lesson is about not fooling yourself. A model scoring ninety nine percent is usually a warning sign.",
  "m4":  "Neural networks are simpler than the hype suggests. A neuron is just multiply, add, and one small function.",

  /* Stage 5 - AI */
  "a1":  "A language model does exactly one thing. It predicts the next word. Everything else comes from that.",
  "a2":  "Writing prompts that work with real users. Being specific is the whole skill.",
  "a3":  "This is the most requested AI skill in job listings right now. Take your time with it.",
  "a4":  "Agents can take actions, which makes guardrails essential. Also cost control, which is most of the real job."
};

var TRACK_TIPS = {
  "s-start":  "Welcome. This track assumes you have never written code before. Go slowly and do every exercise.",
  "s-think":  "Now your programs learn to make decisions and repeat work. This is where it gets powerful.",
  "s-build":  "Time to build real things and find out what AI actually is.",
  "p2-text":  "Handling text properly. Most real programming is text work.",
  "p2-data":  "Structuring real data. Dictionaries are the tool you will use most.",
  "s3-sql":   "Databases. This one skill can get you a job on its own.",
  "s3-data":  "Turning messy data into something true and useful.",
  "s4-ml":    "Machine learning, built from the ground up.",
  "s5-ai":    "The final stage. Building real AI applications."
};

var ENCOURAGE = [
  "Take your time. Nobody gets this instantly.",
  "Try writing it wrong first. That is genuinely how people learn.",
  "Stuck is normal. Every programmer is stuck most of the day.",
  "Read the error message. The last line usually tells you the problem.",
  "Have another look at the worked example above. The pattern is the same."
];

var CELEBRATE = [
  "Correct. Well done.",
  "That is right. Keep going.",
  "Got it. On to the next one.",
  "Nicely done.",
  "Correct. You are making good progress."
];

var pick = function (arr) { return arr[Math.floor(Math.random() * arr.length)]; };

/* ------------------------------------------------------------------ svg */
/* A friendly, simple guide. Deliberately stylised rather than realistic. */
/* Axle. Stays SVG rather than a PNG on purpose: the mouth and eyelids are
 * animated by id while speaking, which a flat image cannot do, and vector
 * stays sharp from the 40px bubble up to a retina display. */
function avatarSVG() {
  return '' +
  '<svg viewBox="0 0 120 120" width="100%" height="100%" aria-hidden="true">' +
    '<defs>' +
      '<linearGradient id="vpSkin" x1="0" y1="0" x2="0" y2="1">' +
        '<stop offset="0%" stop-color="#f3d0ab"/><stop offset="100%" stop-color="#dfae83"/>' +
      '</linearGradient>' +
      '<linearGradient id="vpShirt" x1="0" y1="0" x2="1" y2="1">' +
        '<stop offset="0%" stop-color="#ffa947"/><stop offset="100%" stop-color="#dd6f18"/>' +
      '</linearGradient>' +
      '<linearGradient id="vpRing" x1="0" y1="0" x2="1" y2="1">' +
        '<stop offset="0%" stop-color="#2a3446"/><stop offset="100%" stop-color="#151d29"/>' +
      '</linearGradient>' +
      '<clipPath id="vpClip"><circle cx="60" cy="60" r="56"/></clipPath>' +
    '</defs>' +
    /* badge backdrop, so the head reads as an avatar at any size */
    '<circle cx="60" cy="60" r="56" fill="url(#vpRing)"/>' +
    '<g clip-path="url(#vpClip)">' +
      /* shoulders */
      '<path d="M14 120 Q14 90 60 90 Q106 90 106 120 Z" fill="url(#vpShirt)"/>' +
      '<path d="M50 91 L60 104 L70 91 Q60 96 50 91 Z" fill="#fff" opacity=".9"/>' +
      /* neck */
      '<path d="M52 74 h16 v14 q-8 5 -16 0 Z" fill="#d5a179"/>' +
      /* head */
      '<ellipse cx="60" cy="54" rx="28" ry="31" fill="url(#vpSkin)"/>' +
      /* ears */
      '<ellipse cx="32" cy="57" rx="4.5" ry="7.5" fill="#dfae83"/>' +
      '<ellipse cx="88" cy="57" rx="4.5" ry="7.5" fill="#dfae83"/>' +
      /* hair — a cleaner silhouette than the old zig-zag fringe */
      '<path d="M31 52 Q29 22 60 21 Q91 22 89 52 Q86 38 76 33 '
        + 'Q66 41 50 36 Q37 37 34 52 Z" fill="#241a13"/>' +
      /* headset: reads instantly as "guide", and gives Axle a silhouette */
      '<path d="M31 56 Q31 27 60 27 Q89 27 89 56" stroke="#2f3b4f" '
        + 'stroke-width="4.5" fill="none" stroke-linecap="round"/>' +
      '<rect x="25.5" y="50" width="9" height="15" rx="4.5" fill="#3b4a63"/>' +
      '<rect x="85.5" y="50" width="9" height="15" rx="4.5" fill="#3b4a63"/>' +
      '<path d="M30 65 Q30 78 45 79" stroke="#3b4a63" stroke-width="3" '
        + 'fill="none" stroke-linecap="round"/>' +
      '<circle cx="47" cy="79" r="3.4" fill="#ffa947"/>' +
      /* eyes — ids kept: the blink animation targets them */
      '<g id="vpEyes">' +
        '<ellipse cx="49" cy="54" rx="5.6" ry="6.2" fill="#fff"/>' +
        '<ellipse cx="71" cy="54" rx="5.6" ry="6.2" fill="#fff"/>' +
        '<circle cx="49.5" cy="55" r="3.1" fill="#22303f"/>' +
        '<circle cx="71.5" cy="55" r="3.1" fill="#22303f"/>' +
        '<circle cx="50.7" cy="53.5" r="1.15" fill="#fff"/>' +
        '<circle cx="72.7" cy="53.5" r="1.15" fill="#fff"/>' +
      '</g>' +
      '<g id="vpLids" style="opacity:0">' +
        '<ellipse cx="49" cy="54" rx="6.1" ry="6.6" fill="#ecc49c"/>' +
        '<ellipse cx="71" cy="54" rx="6.1" ry="6.6" fill="#ecc49c"/>' +
      '</g>' +
      /* brows */
      '<path d="M43 45 Q49 41.5 55 45" stroke="#241a13" stroke-width="2.4" '
        + 'fill="none" stroke-linecap="round"/>' +
      '<path d="M65 45 Q71 41.5 77 45" stroke="#241a13" stroke-width="2.4" '
        + 'fill="none" stroke-linecap="round"/>' +
      /* nose */
      '<path d="M60 58 L57.8 65 Q60 66.4 62.2 65" stroke="#c79067" '
        + 'stroke-width="1.8" fill="none" stroke-linecap="round"/>' +
      /* cheeks */
      '<ellipse cx="42" cy="64" rx="4.5" ry="2.8" fill="#e8956b" opacity=".28"/>' +
      '<ellipse cx="78" cy="64" rx="4.5" ry="2.8" fill="#e8956b" opacity=".28"/>' +
      /* mouth — id kept: resized on every syllable while speaking */
      '<ellipse id="vpMouth" cx="60" cy="73" rx="7.5" ry="2.4" fill="#8f3f3f"/>' +
    '</g>' +
    '<circle cx="60" cy="60" r="55" fill="none" stroke="#ffa947" '
      + 'stroke-width="2" opacity=".55"/>' +
  '</svg>';
}

/* ----------------------------------------------------------------- styles */
var CSS = '' +
'#vpTutor{position:fixed;right:20px;bottom:20px;z-index:9999;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;display:flex;align-items:flex-end;gap:12px;pointer-events:none}' +
'#vpTutor *{box-sizing:border-box}' +
'#vpBubble{pointer-events:auto;max-width:330px;background:#fff;color:#1a1a19;border:1px solid #d8d6d1;border-radius:16px 16px 4px 16px;padding:15px 17px;font-size:14.5px;line-height:1.6;box-shadow:0 10px 34px rgba(0,0,0,.18);opacity:0;transform:translateY(8px) scale(.97);transition:.22s;transform-origin:bottom right}' +
'#vpBubble.on{opacity:1;transform:translateY(0) scale(1)}' +
'#vpBubble .vpName{font-size:10.5px;text-transform:uppercase;letter-spacing:1px;color:#c2410c;font-weight:800;margin-bottom:5px}' +
'#vpBubble .vpActs{display:flex;gap:7px;margin-top:12px;flex-wrap:wrap}' +
'#vpBubble button{font-family:inherit;font-size:12.5px;padding:6px 12px;border-radius:7px;border:1px solid #d8d6d1;background:#faf9f7;color:#1a1a19;cursor:pointer}' +
'#vpBubble button:hover{border-color:#c2410c;color:#c2410c}' +
'#vpBubble button.pri{background:#c2410c;color:#fff;border-color:#c2410c}' +
'#vpBubble button.pri:hover{filter:brightness(1.1);color:#fff}' +
'#vpAvatarWrap{pointer-events:auto;position:relative;width:96px;height:96px;flex-shrink:0;cursor:pointer;filter:drop-shadow(0 6px 18px rgba(0,0,0,.22));transition:transform .18s}' +
'#vpAvatarWrap:hover{transform:translateY(-3px)}' +
'#vpAvatar{width:96px;height:96px;border-radius:50%;overflow:hidden;background:linear-gradient(160deg,#fff4e6,#ffe2c2);border:3px solid #fff}' +
'#vpTutor.speaking #vpAvatar{box-shadow:0 0 0 4px rgba(255,153,51,.35)}' +
'#vpBadge{position:absolute;top:-3px;right:-3px;width:24px;height:24px;border-radius:50%;background:#c2410c;color:#fff;font-size:12px;display:flex;align-items:center;justify-content:center;border:2px solid #fff;font-weight:700}' +
'#vpMini{pointer-events:auto;position:fixed;right:20px;bottom:20px;z-index:9999;width:56px;height:56px;border-radius:50%;background:#c2410c;color:#fff;border:none;cursor:pointer;font-size:22px;box-shadow:0 6px 20px rgba(0,0,0,.25);display:none;align-items:center;justify-content:center}' +
'#vpMini.on{display:flex}' +
'@media(max-width:640px){#vpBubble{max-width:230px;font-size:13.5px}#vpAvatarWrap,#vpAvatar{width:72px;height:72px}}' +
'@media print{#vpTutor,#vpMini{display:none!important}}';

/* -------------------------------------------------------------- speaking */
/* Voice choice. Browsers do not tag voices by gender, so we match on the
 * names the major platforms actually ship — and fall back to pitch, which
 * still reads clearly as one or the other when no named voice exists. */
var VOICE_NAMES = {
  female: /(female|woman|zira|susan|samantha|karen|moira|tessa|fiona|veena|heera|aria|jenny|neerja|kalpana|swara|sonia|hazel|catherine|linda|eva|joanna)/i,
  male: /(male|man|david|mark|guy|alex|daniel|fred|thomas|rishi|prabhat|ravi|george|james|brian|matthew|oliver|william|hemant)/i
};
var voicePref = "female";
try {
  voicePref = global.localStorage.getItem("vp_voice") || "female";
} catch (e) {}

function pickVoice() {
  var voices = (global.speechSynthesis && global.speechSynthesis.getVoices()) || [];
  if (!voices.length) return null;
  var want = VOICE_NAMES[voicePref] || VOICE_NAMES.female;
  var other = voicePref === "female" ? VOICE_NAMES.male : VOICE_NAMES.female;
  // Indian English first, then any English, and never a voice whose name
  // clearly belongs to the other choice.
  var tiers = [
    function (v) { return want.test(v.name) && /en[-_]IN/i.test(v.lang); },
    function (v) { return want.test(v.name) && /^en/i.test(v.lang); },
    function (v) { return want.test(v.name); },
    function (v) { return /en[-_]IN/i.test(v.lang) && !other.test(v.name); },
    function (v) { return /^en/i.test(v.lang) && !other.test(v.name); },
    function (v) { return /^en/i.test(v.lang); }
  ];
  for (var i = 0; i < tiers.length; i++) {
    var hit = voices.filter(tiers[i])[0];
    if (hit) return hit;
  }
  return voices[0];
}

function setVoice(pref) {
  voicePref = (pref === "male") ? "male" : "female";
  try { global.localStorage.setItem("vp_voice", voicePref); } catch (e) {}
  var b = document.getElementById("vpVoice");
  if (b) b.textContent = voicePref === "male" ? "🗣 Male voice" : "🗣 Female voice";
}

function speak(text) {
  if (muted || !global.speechSynthesis) return;
  try {
    global.speechSynthesis.cancel();
    var u = new SpeechSynthesisUtterance(text);
    u.rate = 0.95;
    // Nudge pitch as well: on devices with only one English voice this is
    // the only thing that distinguishes the two choices.
    u.pitch = voicePref === "male" ? 0.85 : 1.15;

    var preferred = pickVoice();
    if (preferred) u.voice = preferred;

    u.onstart = function () { setSpeaking(true); };
    u.onend   = function () { setSpeaking(false); };
    u.onerror = function () { setSpeaking(false); };

    currentUtterance = u;
    global.speechSynthesis.speak(u);
  } catch (e) { setSpeaking(false); }
}

function stopSpeaking() {
  try { if (global.speechSynthesis) global.speechSynthesis.cancel(); } catch (e) {}
  setSpeaking(false);
}

function setSpeaking(on) {
  speaking = on;
  if (!el.root) return;
  el.root.classList.toggle("speaking", on);
  clearInterval(mouthTimer);
  var mouth = el.root.querySelector("#vpMouth");
  if (!mouth) return;
  if (on) {
    mouthTimer = setInterval(function () {
      var r = 1.6 + Math.random() * 4.5;
      mouth.setAttribute("ry", r.toFixed(1));
      mouth.setAttribute("rx", (7 + Math.random() * 2).toFixed(1));
    }, 110);
  } else {
    mouth.setAttribute("ry", "2.4");
    mouth.setAttribute("rx", "8");
  }
}

function startBlinking() {
  clearInterval(blinkTimer);
  blinkTimer = setInterval(function () {
    var lids = el.root && el.root.querySelector("#vpLids");
    if (!lids) return;
    lids.style.transition = "opacity .09s";
    lids.style.opacity = "1";
    setTimeout(function () { lids.style.opacity = "0"; }, 130);
  }, 3800 + Math.random() * 2500);
}

/* --------------------------------------------------------------- bubble */
function showBubble(text, actions) {
  if (!el.bubble) return;
  var html = '<div class="vpName">Axle &middot; your guide</div>' +
             '<div class="vpText"></div>';
  el.bubble.innerHTML = html;
  el.bubble.querySelector(".vpText").textContent = text;

  var acts = document.createElement("div");
  acts.className = "vpActs";

  (actions || []).forEach(function (a) {
    var b = document.createElement("button");
    b.textContent = a.label;
    if (a.primary) b.className = "pri";
    b.onclick = a.onClick;
    acts.appendChild(b);
  });

  var mute = document.createElement("button");
  mute.textContent = muted ? "Turn voice on" : "Turn voice off";
  mute.onclick = function () {
    muted = !muted;
    try { localStorage.setItem("vp_tutor_muted", muted ? "1" : "0"); } catch (e) {}
    if (muted) stopSpeaking();
    mute.textContent = muted ? "Turn voice on" : "Turn voice off";
  };
  acts.appendChild(mute);

  /* Male / female voice, next to the mute control. Speaks a sample on
     change so the choice is audible immediately rather than next time. */
  var voice = document.createElement("button");
  voice.id = "vpVoice";
  voice.textContent = voicePref === "male" ? "🗣 Male voice" : "🗣 Female voice";
  voice.onclick = function () {
    setVoice(voicePref === "male" ? "female" : "male");
    if (!muted) speak(voicePref === "male"
      ? "Male voice selected." : "Female voice selected.");
  };
  acts.appendChild(voice);

  var hide = document.createElement("button");
  hide.textContent = "Hide";
  hide.onclick = function () { API.minimise(); };
  acts.appendChild(hide);

  el.bubble.appendChild(acts);
  el.bubble.classList.add("on");
}

function hideBubble() { if (el.bubble) el.bubble.classList.remove("on"); }

/* ------------------------------------------------------------------ api */
var API = {

  init: function () {
    if (el.root) return;

    var style = document.createElement("style");
    style.textContent = CSS;
    document.head.appendChild(style);

    var root = document.createElement("div");
    root.id = "vpTutor";
    root.innerHTML =
      '<div id="vpBubble"></div>' +
      '<div id="vpAvatarWrap" title="Ask Axle">' +
        '<div id="vpAvatar">' + avatarSVG() + '</div>' +
        '<div id="vpBadge">?</div>' +
      '</div>';
    document.body.appendChild(root);

    var mini = document.createElement("button");
    mini.id = "vpMini";
    mini.textContent = "?";
    mini.title = "Show Axle";
    mini.onclick = function () { API.restore(); };
    document.body.appendChild(mini);

    el.root   = root;
    el.bubble = root.querySelector("#vpBubble");
    el.mini   = mini;

    root.querySelector("#vpAvatarWrap").onclick = function () {
      if (speaking) { stopSpeaking(); return; }
      if (el.bubble.classList.contains("on")) hideBubble();
      else API.say(pick(ENCOURAGE));
    };

    startBlinking();

    /* voices load asynchronously in some browsers */
    if (global.speechSynthesis && global.speechSynthesis.onvoiceschanged !== undefined) {
      global.speechSynthesis.onvoiceschanged = function () {};
    }

    if (minimised) API.minimise();
  },

  say: function (text, actions) {
    if (minimised) return;
    showBubble(text, actions);
    speak(text);
  },

  /* Guidance when a lesson opens */
  onLesson: function (lesson, track) {
    if (!lesson) return;
    var tip = LESSON_TIPS[lesson.id]
           || (track && TRACK_TIPS[track.id])
           || "Read the notes first, then try the exercises below.";

    var nEx = (lesson.exercises || []).length;
    var extra = nEx ? " There are " + nEx + " exercises after the notes." : "";

    API.say(tip + extra, [
      { label: "Read the notes aloud", primary: true, onClick: function () {
          var notes = document.querySelector(".lesson, .notes");
          API.readAloud(notes);
      }},
      { label: "How do I do this?", onClick: function () {
          API.say("Read the worked examples in the notes. Every exercise below follows the same pattern as one of them. Type the code yourself instead of copying, then press Run.");
      }}
    ]);
  },

  onTrack: function (track) {
    if (!track) return;
    API.say(TRACK_TIPS[track.id] || ("This track has " + track.lessons.length + " lessons. Start with the first one."));
  },

  onExercisePass: function (n) {
    API.say(pick(CELEBRATE) + (n ? " That was exercise " + n + "." : ""));
  },

  onExerciseFail: function (n, attempts) {
    if (attempts >= 4) {
      API.say("You have tried this a few times now. Open the hint, and if it still does not work, look at the solution, then close it and type it again from memory. That is not cheating, it is how people learn.");
    } else if (attempts >= 2) {
      API.say("Not yet. Compare your output with what the question asked for. Often it is one small difference. The hint button is there if you want it.");
    } else {
      API.say(pick(ENCOURAGE));
    }
  },

  onError: function (message) {
    API.say("An error is normal. Read the last line of the red text, it usually names the problem and the line number. Fix that one line and run it again.");
  },

  /* Read a block of lesson notes out loud, cleaned of code */
  readAloud: function (element) {
    if (!element) { API.say("There is nothing to read on this page."); return; }
    if (muted) {
      API.say("Voice is currently off. Turn it on first using the button below.");
      return;
    }

    var clone = element.cloneNode(true);
    /* code blocks read terribly aloud, so drop them */
    clone.querySelectorAll("pre").forEach(function (p) { p.remove(); });

    var text = (clone.textContent || "")
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, 4000);          /* keep it to a sensible length */

    if (!text) { API.say("There is nothing to read here."); return; }

    showBubble("Reading the notes aloud. Tap me to stop.", [
      { label: "Stop reading", primary: true, onClick: function () {
          stopSpeaking();
          API.say("Stopped.");
      }}
    ]);
    speak(text);
  },

  minimise: function () {
    minimised = true;
    try { localStorage.setItem("vp_tutor_min", "1"); } catch (e) {}
    stopSpeaking();
    if (el.root) el.root.style.display = "none";
    if (el.mini) el.mini.classList.add("on");
  },

  restore: function () {
    minimised = false;
    try { localStorage.setItem("vp_tutor_min", "0"); } catch (e) {}
    if (el.root) el.root.style.display = "flex";
    if (el.mini) el.mini.classList.remove("on");
    API.say("I am here if you get stuck. Tap me any time.");
  },

  stop: stopSpeaking,
  isMuted: function () { return muted; }
};

global.Tutor = API;

})(window);
