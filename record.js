/* Recording the lesson, from whichever screen the teacher is on.
 *
 * A teacher works a derivation across four spaces, a class asks for it again
 * next week, and nothing remembers it. A screenshot keeps the end of the
 * working and loses the order it was arrived at, which on a derivation is
 * the entire content of the lesson.
 *
 * **It lives here rather than inside a page, because it belongs on both.**
 * It was written into the board and only the board, so a teacher setting a
 * paper on craxle.com, walking a class through a solved question or turning
 * a molecule around had no way to record any of it. One file, loaded by
 * both, the same way mathtext.js is — two copies of this would be two
 * recorders that disagree about where the file went.
 *
 * The teacher chooses what is captured when the browser asks: this tab,
 * another window, or the whole screen. The last of those is what catches
 * everything else they use in a lesson, and it is theirs to pick rather
 * than ours to assume.
 *
 * **It is written to the machine's own disk, not to us.** A lesson is
 * hundreds of megabytes; the class shelf holds twelve and its own comment
 * says "a slide deck, not a film". Putting an hour of video into a database
 * row would be a decision about infrastructure wearing a feature's clothes.
 * So the file is chosen first, before anything starts, and the recording is
 * streamed into it as it goes: memory stays flat and a two-hour lesson is no
 * heavier than a two-minute one.
 *
 * Where a browser cannot write a file as it goes — Chrome on Android, which
 * is what a cheaper board runs — it is held in memory and downloaded at the
 * end, and that path stops itself at a quarter of an hour rather than
 * letting a tab die mid-lesson with nothing kept at all.
 *
 * **The room is told.** A screen recording on a wall-mounted display is a
 * camera pointed at a class, so it says so across the top of the screen for
 * as long as it runs, with the time it has been running. Nobody at a desk
 * can see a button change colour on a board eight feet away.
 */
(function (global) {
  "use strict";

  /* What each page lends it: somewhere to put a message, and a name for the
     file. Both have defaults, so a page that lends neither still records. */
  var HOST = {
    say: function (msg) {
      if (typeof global.toastLine === "function") return global.toastLine(msg);
      if (msg && typeof global.alert === "function") global.alert(msg);
    },
    label: function () { return ""; }
  };

  function el(id) { return document.getElementById(id); }
  function toastLine(msg) { HOST.say(msg); }

  /* The styles travel with it. A recorder whose notice is missing on one of
     the two screens is a recording that room does not know about. */
  var CSS = "/* A room can see that it is being recorded.\n *\n * A screen recording on a wall-mounted display is a camera pointed at a\n * class, and the one thing it must never be is quiet. The button turning\n * red is not enough \u2014 nobody sitting at a desk can see a 30-pixel button on\n * a board eight feet away \u2014 so the recording says so across the top of the\n * screen, in words, with the time it has been running, for as long as it\n * runs. Tapping it stops it, because the teacher who wants to stop is\n * looking at the thing that says it is recording. */\n#recPill{position:fixed;top:.5rem;left:50%;transform:translateX(-50%);\n  z-index:70;display:flex;align-items:center;gap:.5rem;\n  padding:.35rem .8rem;border-radius:999px;cursor:pointer;\n  background:#b3261e;color:#fff;font-weight:600;font-size:.95rem;\n  box-shadow:0 2px 10px rgba(0,0,0,.28);border:0}\n#recPill .dot{width:.6rem;height:.6rem;border-radius:50%;background:#fff;\n  animation:recblink 1.4s ease-in-out infinite}\n#recPill .rt{font-variant-numeric:tabular-nums}\n@keyframes recblink{0%,100%{opacity:1}50%{opacity:.25}}\n@media (prefers-reduced-motion:reduce){\n  #recPill .dot{animation:none}\n}\n#recBtn.on{color:#b3261e}";
  var STYLED = false;
  function styles() {
    if (STYLED) return;
    STYLED = true;
    var s = document.createElement("style");
    s.appendChild(document.createTextNode(CSS));
    document.head.appendChild(s);
  }

/* Recording the lesson, which is a screen recording and nothing more.
 *
 * A teacher works a derivation across four spaces, a class asks for it
 * again next week, and the board has no memory of it. A screenshot keeps
 * the end of the working and loses the order it was arrived at, which on a
 * derivation is the entire content of the lesson.
 *
 * **It is written to the board's own disk, not to us.** A lesson is
 * hundreds of megabytes; the class shelf holds twelve, and its own comment
 * says "a slide deck, not a film". Putting an hour of video into a database
 * row would be a decision about infrastructure disguised as a feature, and
 * a school that wants it shared already has somewhere it shares things. So
 * the file is asked for first, before anything starts, and the recording is
 * streamed into it as it goes — memory stays flat and a two-hour lesson is
 * no heavier on the board than a two-minute one.
 *
 * Where a browser cannot write a file as it goes — Chrome on Android, which
 * is what a cheaper board runs — it is held in memory and downloaded at the
 * end, and that path stops itself at a quarter of an hour rather than
 * letting a lesson end because the board ran out of memory.
 *
 * **The room is told.** A screen recording on a wall-mounted display is a
 * camera pointed at a class, so it says so across the top of the screen for
 * as long as it runs, with the time it has been running. Nobody sitting at
 * a desk can see a button change colour on a board eight feet away.
 */
var REC = { rec: null, view: null, mic: null, ctx: null, sink: null,
            chunks: null, bytes: 0, t0: 0, tick: null, queue: null,
            name: "", cap: 0 };
/* Fifteen minutes, and only where the whole recording has to be held in
   memory before it can be saved. At the bitrate below that is around 200 MB,
   which a board can hold; the half-hour that follows it is what makes a
   browser tab die mid-lesson with nothing kept. */
var REC_MEM_MS = 15 * 60 * 1000;
var REC_MAX_MS = 3 * 60 * 60 * 1000;

function recOn(){ return !!(REC.rec && REC.rec.state === "recording"); }

/* Modest on purpose. A board's screen is text and diagrams, which is the
   easiest thing in the world to compress, and 1.5 Mbit is legible at the
   back of a room. Tripling it triples the file for a picture nobody can
   tell apart at the distance it is watched from. */
function recPick(){
  var want = ["video/webm;codecs=vp9,opus", "video/webm;codecs=vp8,opus",
              "video/webm", "video/mp4"];
  for(var i = 0; i < want.length; i++){
    if(window.MediaRecorder && MediaRecorder.isTypeSupported(want[i]))
      return want[i];
  }
  return "";
}

/* The board's own sound and the teacher's voice are both the lesson.
   A video played on the board is half of what was taught; the sentence said
   over the top of it is the other half. Two tracks cannot go into one file,
   so where there are two they are mixed into one. */
function recMix(view, mic){
  var have = [];
  if(view && view.getAudioTracks().length) have.push(view);
  if(mic && mic.getAudioTracks().length) have.push(mic);
  if(!have.length) return { track: null, ctx: null };
  if(have.length === 1) return { track: have[0].getAudioTracks()[0], ctx: null };
  var AC = window.AudioContext || window.webkitAudioContext;
  if(!AC) return { track: have[0].getAudioTracks()[0], ctx: null };
  try{
    var ctx = new AC();
    var out = ctx.createMediaStreamDestination();
    have.forEach(function(s){ ctx.createMediaStreamSource(s).connect(out); });
    return { track: out.stream.getAudioTracks()[0], ctx: ctx };
  }catch(e){
    return { track: have[0].getAudioTracks()[0], ctx: null };
  }
}

function recFace(){
  var b = el("recBtn");
  if(b){
    b.classList.toggle("on", recOn());
    b.title = recOn() ? "Stop recording" : "Record the lesson";
  }
  var pill = el("recPill");
  if(!recOn()){
    if(pill) pill.remove();
    return;
  }
  if(!pill){
    pill = document.createElement("button");
    pill.id = "recPill";
    pill.type = "button";
    pill.innerHTML = '<span class="dot"></span><span>Recording</span>'
                   + '<span class="rt">0:00</span><span>· tap to stop</span>';
    pill.onclick = function(){ recStop(""); };
    document.body.appendChild(pill);
  }
  var ms = Date.now() - REC.t0;
  var s = Math.floor(ms / 1000);
  var t = Math.floor(s / 60) + ":" + ("0" + (s % 60)).slice(-2);
  if(s >= 3600) t = Math.floor(s / 3600) + ":" + ("0" + (Math.floor(s / 60) % 60)).slice(-2) + ":" + ("0" + (s % 60)).slice(-2);
  pill.querySelector(".rt").textContent = t;
  if(REC.cap && ms > REC.cap){
    recStop("Fifteen minutes is as much as this board can hold in one go. "
            + "It has been saved — start another to carry on.");
  }else if(ms > REC_MAX_MS){
    recStop("Three hours. It has been saved.");
  }
}

async function recStart(){
  if(!navigator.mediaDevices || !navigator.mediaDevices.getDisplayMedia
     || !window.MediaRecorder){
    toastLine("This board's browser cannot record the screen. The camera "
              + "button photographs what is on it.");
    return;
  }
  var type = recPick();
  if(!type){
    toastLine("This board's browser cannot record the screen.");
    return;
  }
  var ext = type.indexOf("mp4") >= 0 ? ".mp4" : ".webm";
  var subj = HOST.label().toLowerCase()
               .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  REC.name = "craxlearn-" + (subj ? subj + "-" : "")
    + new Date().toISOString().slice(0, 16).replace(/[:T]/g, "-") + ext;

  /* The file is chosen before the recording starts, so that stopping is one
     tap and finished rather than one tap and a dialog — a teacher stops
     recording because the lesson has ended and the room is leaving. */
  var sink = null;
  if(window.showSaveFilePicker){
    try{
      var acc = {};
      acc[type.split(";")[0]] = [ext];
      var handle = await window.showSaveFilePicker({
        suggestedName: REC.name,
        types: [{ description: "Lesson recording", accept: acc }] });
      sink = await handle.createWritable();
    }catch(e){
      if(e && e.name === "AbortError") return;   // changed their mind
      sink = null;                               // held in memory instead
    }
  }

  var view = null;
  try{
    view = await navigator.mediaDevices.getDisplayMedia({
      video: { displaySurface: "browser", frameRate: { ideal: 15, max: 30 } },
      audio: true });
  }catch(e){
    if(sink){ try{ await sink.abort(); }catch(_){} }
    return;                       /* cancelling the picker is not an error */
  }
  var mic = null;
  try{
    mic = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true } });
  }catch(e){
    mic = null;      /* no microphone, or a no — record the screen silently */
  }

  var mixed = recMix(view, mic);
  var out = new MediaStream();
  view.getVideoTracks().forEach(function(t){ out.addTrack(t); });
  if(mixed.track) out.addTrack(mixed.track);

  var rec;
  try{
    rec = new MediaRecorder(out, { mimeType: type,
                                   videoBitsPerSecond: 1500000,
                                   audioBitsPerSecond: 96000 });
  }catch(e){
    try{ rec = new MediaRecorder(out); }catch(e2){
      view.getTracks().forEach(function(t){ t.stop(); });
      if(mic) mic.getTracks().forEach(function(t){ t.stop(); });
      if(sink){ try{ await sink.abort(); }catch(_){} }
      toastLine("This board's browser cannot record the screen.");
      return;
    }
  }

  REC.rec = rec; REC.view = view; REC.mic = mic; REC.ctx = mixed.ctx;
  REC.sink = sink; REC.chunks = sink ? null : []; REC.bytes = 0;
  REC.t0 = Date.now(); REC.queue = Promise.resolve();
  REC.cap = sink ? 0 : REC_MEM_MS;
  REC.ending = false;

  rec.ondataavailable = function(e){
    if(!e.data || !e.data.size) return;
    REC.bytes += e.data.size;
    if(REC.sink){
      /* Written in order, one at a time. Two overlapping writes to the same
         file interleave their bytes and the recording will not play. */
      var blob = e.data;
      REC.queue = REC.queue.then(function(){
        return REC.sink.write(blob);
      }).catch(function(){});
    }else if(REC.chunks){
      REC.chunks.push(e.data);
    }
  };
  rec.onstop = function(){ recFinish(); };
  /* The browser's own "Stop sharing" is a real stop, and the recording has
     to be closed properly when it happens or the file is left unplayable. */
  view.getVideoTracks().forEach(function(t){
    t.addEventListener("ended", function(){ recStop(""); });
  });

  rec.start(4000);           /* a chunk every four seconds, to write as it goes */
  REC.tick = setInterval(recFace, 1000);
  recFace();
  toastLine(sink ? "Recording. It is being written to the file as it goes."
                 : "Recording. It will download when you stop.");
}

function recStop(msg){
  if(REC.tick){ clearInterval(REC.tick); REC.tick = null; }
  if(REC.rec && REC.rec.state !== "inactive"){
    REC.msg = msg || "";
    try{ REC.rec.stop(); }catch(e){ recFinish(); }
    return;
  }
  /* Nothing running. Only finish if there is something left to finish —
     otherwise a second stop lands on an already-finished recording and
     reports "Nothing was recorded" over the message that said where the
     file went. A teacher who stopped a good recording would read the last
     line and believe they had lost it. */
  if(REC.view || REC.sink || REC.chunks) recFinish();
}

async function recFinish(){
  /* Once per recording, whatever ends it.
     There are three ways in — the button, the notice, and the browser's own
     "Stop sharing" bar ending the track — and on a bad day two of them
     arrive together. */
  if(REC.ending) return;
  REC.ending = true;
  var sink = REC.sink, chunks = REC.chunks, name = REC.name;
  var msg = REC.msg || "";
  var type = (REC.rec && REC.rec.mimeType) || "video/webm";
  if(REC.view) REC.view.getTracks().forEach(function(t){ t.stop(); });
  if(REC.mic) REC.mic.getTracks().forEach(function(t){ t.stop(); });
  if(REC.ctx){ try{ REC.ctx.close(); }catch(e){} }
  var secs = Math.max(1, Math.round((Date.now() - REC.t0) / 1000));
  REC.rec = null; REC.view = null; REC.mic = null; REC.ctx = null;
  REC.sink = null; REC.chunks = null; REC.msg = "";
  if(REC.tick){ clearInterval(REC.tick); REC.tick = null; }
  recFace();

  var where = "";
  try{
    if(sink){
      await REC.queue;                 /* every chunk written before closing */
      await sink.close();
      where = "Saved to " + name + ".";
    }else if(chunks && chunks.length){
      var blob = new Blob(chunks, { type: type });
      var url = URL.createObjectURL(blob);
      var a = document.createElement("a");
      a.href = url; a.download = name;
      a.click();
      setTimeout(function(){ URL.revokeObjectURL(url); }, 30000);
      where = "Downloaded as " + name + ".";
    }else{
      where = "Nothing was recorded.";
    }
  }catch(e){
    where = "The recording could not be saved: " + (e.message || e);
  }
  var mins = Math.floor(secs / 60), rest = secs % 60;
  toastLine((msg ? msg + " " : "")
            + where + " " + (mins ? mins + " min " : "") + rest + " sec.");
}


  /* What a page calls.
     `attach` is how it lends its own toast and its own naming; `supported`
     is how a page decides whether to show the button at all, because an
     offer that fails when pressed is worse than no offer. */
  global.Recorder = {
    attach: function (opts) {
      if (opts && typeof opts.say === "function") HOST.say = opts.say;
      if (opts && typeof opts.label === "function") HOST.label = opts.label;
    },
    supported: function () {
      return !!(navigator.mediaDevices &&
                navigator.mediaDevices.getDisplayMedia &&
                global.MediaRecorder);
    },
    on: recOn,
    toggle: function () {
      styles();
      return recOn() ? recStop("") : recStart();
    },
    stop: function (msg) { return recStop(msg || ""); }
  };
})(window);
