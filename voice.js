/* Talking to Axle, rather than typing at it.
 *
 * A conversation loop: it listens, you stop talking, it answers out loud, and
 * then it listens again — until you end it. No press-to-talk between turns,
 * because having to find a button after every sentence is not a conversation,
 * it is dictation with extra steps.
 *
 * Recognition is the browser's SpeechRecognition, which in Chrome is Google's
 * recogniser. That matters for two reasons: it is genuinely good at
 * conversational English including Indian English, and it costs nothing per
 * minute — the audio never touches our servers, so a student who talks for an
 * hour costs exactly what one who talks for a minute does. A paid speech API
 * would be a per-second bill on the single most open-ended thing in the
 * product.
 *
 * The parts that are easy to get wrong, and what is done about them here:
 *
 *  - Barge-in. If you start talking while it is still speaking, it stops
 *    speaking. Somebody who interrupts has heard enough, and talking over
 *    them is what makes voice assistants feel deaf.
 *  - Chrome ends recognition on every pause. Restarting inside onend, rather
 *    than assuming continuous mode works, is what keeps a turn alive while
 *    somebody thinks mid-sentence.
 *  - The microphone must never be open while the voice is speaking, or it
 *    transcribes the answer and asks it back as a question. That loop is
 *    endless and it bills on every lap.
 */
(function () {
  "use strict";

  var SR = window.SpeechRecognition || window.webkitSpeechRecognition;

  var V = {
    on: false,          // the conversation is running
    state: "idle",      // idle | listening | thinking | speaking
    heard: "",          // live transcript of the current turn
    error: "",
    rec: null,
    quiet: 0,           // consecutive turns where nothing was said
    onChange: null,
    ask: null           // async (text) -> text to say back
  };
  window.Voice = V;

  V.supported = function () {
    return !!SR && !!window.speechSynthesis;
  };

  function tell() {
    if (typeof V.onChange === "function") V.onChange(V);
  }

  function set(state) {
    V.state = state;
    tell();
  }

  /* ---- speaking ---------------------------------------------------- *
   *
   * Sentence by sentence, and the caller is told after each one — so the
   * words can appear on screen as they are said rather than all at once
   * before the voice starts. Watching a paragraph land and then listening to
   * it being read is two separate experiences of the same answer; having the
   * line show up as you hear it is one.
   *
   * Chrome also truncates long utterances, so chunking is what makes a full
   * answer actually finish being spoken. Both reasons point the same way.
   */
  function sentences(text) {
    var out = [];
    String(text).replace(/\s+/g, " ").trim()
      .split(/(?<=[.!?:])\s+/).forEach(function (s) {
        while (s.length > 180) {              // long clause, break on a comma
          var cut = s.lastIndexOf(", ", 180);
          if (cut < 60) cut = 180;
          out.push(s.slice(0, cut));
          s = s.slice(cut).replace(/^,\s*/, "");
        }
        if (s.trim()) out.push(s.trim());
      });
    return out;
  }

  function sayOne(part) {
    return new Promise(function (resolve) {
      if (!window.speechSynthesis) return resolve();
      var u = new SpeechSynthesisUtterance(part);
      var v = (typeof askPickVoice === "function") ? askPickVoice() : null;
      if (v) u.voice = v;
      u.rate = 0.98;
      var done = false;
      var go = function () { if (!done) { done = true; setTimeout(resolve, 80); } };
      u.onend = go;
      u.onerror = go;
      // Never hang on an event Chrome forgot to fire.
      setTimeout(go, 2200 + part.length * 80);
      window.speechSynthesis.speak(u);
    });
  }

  async function say(text, onPart) {
    if (!text || !window.speechSynthesis) {
      if (onPart) onPart(text || "");
      return;
    }
    var parts = sentences(text), shown = "";
    for (var i = 0; i < parts.length; i++) {
      if (!V.on) return;
      shown = shown ? shown + " " + parts[i] : parts[i];
      if (onPart) onPart(shown);
      await sayOne(parts[i]);
    }
  }

  function hush() {
    if (window.speechSynthesis) window.speechSynthesis.cancel();
  }

  /* ---- listening --------------------------------------------------- */
  function listen() {
    if (!V.on) return;
    // Never with the voice still going, or it hears the answer and asks it
    // back. That loop does not terminate and it costs a request every lap.
    hush();
    V.heard = "";
    set("listening");

    var r = new SR();
    V.rec = r;
    r.lang = "en-IN";
    r.interimResults = true;
    r.continuous = false;
    r.maxAlternatives = 1;

    var finalText = "";
    r.onresult = function (ev) {
      var interim = "";
      for (var i = ev.resultIndex; i < ev.results.length; i++) {
        var t = ev.results[i][0].transcript;
        if (ev.results[i].isFinal) finalText += t;
        else interim += t;
      }
      V.heard = (finalText + " " + interim).trim();
      tell();
    };
    r.onerror = function (e) {
      var name = (e && e.error) || "";
      if (name === "not-allowed" || name === "service-not-allowed") {
        V.error = "The microphone is blocked. Allow it in your browser to talk.";
        return stop();
      }
      if (name === "no-speech") return;      // handled by onend
      if (name === "aborted") return;
      V.error = "The microphone had a problem. Try again.";
    };
    r.onend = function () {
      if (!V.on) return;
      var said = finalText.trim();
      if (!said) {
        // Nothing said. Two silences in a row means they have walked away or
        // finished; a conversation that keeps a microphone open forever is
        // worse than one that ends.
        V.quiet += 1;
        if (V.quiet >= 3) {
          V.error = "I stopped listening — say hello to start again.";
          return stop();
        }
        return listen();
      }
      V.quiet = 0;
      turn(said);
    };

    try {
      r.start();
    } catch (e) {
      // start() while the previous one is still winding down. Give it a beat.
      setTimeout(function () { if (V.on) listen(); }, 300);
    }
  }

  /* ---- hearing you over its own voice ------------------------------
   *
   * Barge-in only works if something is listening while Axle talks, and
   * SpeechRecognition cannot be that thing: it opens its own microphone and
   * would transcribe the answer being spoken as if you had said it.
   *
   * So a second, separate audio stream is opened with echo cancellation on,
   * and watched for energy. Echo cancellation is what makes this possible at
   * all — it subtracts the device's own output from what the microphone
   * picks up, so what is left is mostly you.
   *
   * It is left deliberately hard to trigger. The threshold floats above
   * whatever is leaking through while the voice is speaking, and the energy
   * has to stay up for a few frames running, because a single spike is a door
   * closing or a chair moving, and cutting the tutor off mid-sentence for a
   * chair is worse than not having barge-in at all.
   */
  var vad = { stream: null, ctx: null, node: null, buf: null, timer: null,
              floor: 0, hot: 0 };

  async function watchForSpeech() {
    if (vad.stream || !navigator.mediaDevices) return;
    try {
      vad.stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true,
                 autoGainControl: true }
      });
    } catch (e) {
      return;                 // no barge-in; tapping the orb still works
    }
    var AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    vad.ctx = new AC();
    var src = vad.ctx.createMediaStreamSource(vad.stream);
    vad.node = vad.ctx.createAnalyser();
    vad.node.fftSize = 1024;
    vad.buf = new Float32Array(vad.node.fftSize);
    src.connect(vad.node);

    vad.timer = setInterval(function () {
      if (!V.on || !vad.node) return;
      vad.node.getFloatTimeDomainData(vad.buf);
      var sum = 0;
      for (var i = 0; i < vad.buf.length; i++) sum += vad.buf[i] * vad.buf[i];
      var rms = Math.sqrt(sum / vad.buf.length);

      if (V.state !== "speaking") {
        // Between turns, learn what the room sounds like. Slow, so one loud
        // moment does not permanently deafen it.
        vad.floor = vad.floor ? vad.floor * 0.94 + rms * 0.06 : rms;
        vad.hot = 0;
        return;
      }
      // Speaking. Anything above the room plus a clear margin is a person.
      var trigger = Math.max(0.045, (vad.floor || 0.01) * 3.2);
      vad.hot = rms > trigger ? vad.hot + 1 : 0;
      if (vad.hot >= 4) {           // ~4 frames at 60ms — a fifth of a second
        vad.hot = 0;
        V.bargeIn();
      }
    }, 60);
  }

  function stopWatching() {
    if (vad.timer) clearInterval(vad.timer);
    if (vad.stream) vad.stream.getTracks().forEach(function (t) { t.stop(); });
    if (vad.ctx && vad.ctx.close) { try { vad.ctx.close(); } catch (e) {} }
    vad = { stream: null, ctx: null, node: null, buf: null, timer: null,
            floor: 0, hot: 0 };
  }

  /* ---- one exchange ------------------------------------------------ */
  async function turn(said) {
    set("thinking");
    var reply = "";
    try {
      reply = await V.ask(said);
    } catch (e) {
      reply = e && e.message ? e.message : "Something went wrong there.";
    }
    if (!V.on) return;
    set("speaking");
    // The caller gets each sentence as it is spoken, so its transcript grows
    // in step with the voice instead of appearing whole beforehand.
    await say(reply, function (sofar) {
      V.saying = sofar;
      tell();
    });
    V.saying = "";
    if (!V.on) return;
    listen();
  }

  /* ---- control ----------------------------------------------------- */
  V.start = function (askFn, onChange) {
    if (!V.supported()) {
      V.error = "This browser cannot do voice. Chrome on desktop or Android " +
        "works best.";
      V.onChange = onChange || V.onChange;
      tell();
      return false;
    }
    V.ask = askFn;
    V.onChange = onChange || V.onChange;
    V.on = true;
    V.error = "";
    V.quiet = 0;
    watchForSpeech();
    listen();
    return true;
  };

  function stop() {
    V.on = false;
    V.heard = "";
    if (V.rec) {
      try { V.rec.abort(); } catch (e) {}
      V.rec = null;
    }
    hush();
    stopWatching();
    set("idle");
  }
  V.stop = stop;

  /* Interrupting is allowed, and is the whole point. Somebody who starts
     talking over the answer has heard enough of it, and a tutor that will not
     be interrupted is a lecture. Called both by the voice detector above and
     by tapping the orb, so it works even where the microphone cannot be
     opened twice. */
  V.bargeIn = function () {
    if (V.on && V.state === "speaking") {
      hush();
      listen();
    }
  };

  // Leaving the page with the microphone live is not acceptable.
  window.addEventListener("pagehide", stop);
  window.addEventListener("hashchange", stop);
})();
