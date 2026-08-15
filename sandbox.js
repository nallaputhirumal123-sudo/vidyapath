/* Run a learner's code where it cannot reach the learner's account.
 *
 * Both code labs used to execute in the page itself — JavaScript through
 * `new Function(code)()`, Python through Pyodide loaded into the same
 * window. That is the whole application's origin: the session cookie, every
 * API route, the DOM, and whatever is on screen belonging to somebody else.
 *
 * What that allowed, concretely, in an exercise box a child is invited to
 * type into:
 *
 *   fetch("/api/teacher/class/12/roster", {credentials: "include"})
 *
 * The cookie is httponly, so the token cannot be READ by script — and it
 * does not need to be. `credentials: "include"` sends it anyway, so the code
 * acts as whoever is signed in. On a personal laptop that is the learner's
 * own account and the blast radius is themselves. On the machine wired to
 * the classroom board, signed in as the teacher for the period, it is the
 * teacher: their register, their marks, their subject's discussion, and
 * anything they can POST. A pupil at the board during a lesson is exactly
 * the person standing in front of that box.
 *
 * It could also read the page (other children's names and marks are in the
 * DOM), rewrite it (replace the sign-in form and keep what is typed), and
 * post any of it to a server elsewhere.
 *
 * So the code runs in an iframe with `sandbox="allow-scripts"` and NOT
 * `allow-same-origin`. Those two together are the whole fix, and leaving the
 * second one in would undo it completely — it is worth saying plainly,
 * because "allow-same-origin allow-scripts" is a common pairing and it is
 * the same as no sandbox at all.
 *
 * What the iframe gets: a unique opaque origin. No cookies, no localStorage,
 * no access to the parent document, and a fetch to /api/... that is
 * cross-origin, uncredentialed and refused. What it keeps: printing, loops,
 * maths, and Pyodide from the CDN — everything a lesson actually asks for.
 *
 * Results come back over a MessageChannel port rather than window messages.
 * An opaque origin cannot be named in postMessage's targetOrigin, so "*"
 * would be the only option and any frame could then answer for it; a port
 * handed over once is only held by the frame we created.
 */
(function (global) {
  "use strict";

  var FRAMES = {};                 /* one per language, kept warm */
  var LIMIT_MS = { js: 5000, py: 60000 };   /* Pyodide's first run downloads */

  /* The runner lives at /sandbox-frame.html now, not in a srcdoc string.
   *
   * Built from srcdoc, the frame's document URL is "about:srcdoc" — and
   * Pyodide throws when it is loaded there, because it resolves its own
   * asset paths against the document and there is nothing to resolve
   * against. The name `loadPyodide` was defined with no value, the call
   * three lines later said "not a function", and the lab reported that the
   * Python runtime could not be downloaded. The network was never the
   * problem.
   *
   * A real URL fixes it and gives up nothing: the frame still carries
   * sandbox="allow-scripts" WITHOUT allow-same-origin, so it still has an
   * opaque origin — no cookies, no storage, no parent, every request to
   * this site cross-origin and uncredentialed.
   */
  /* The ?v= is the frame's own content hash, written by tools/stamp_assets.
     Without it the URL never changes, so a browser that has loaded the
     runner once keeps using that copy — and a fix to the runner ships,
     deploys, and reaches nobody. On a page that says "Python could not
     start", a stale runner is indefinitely convincing: every new attempt
     fails in the identical way. */
  var FRAME_SRC = "/sandbox-frame.html?v=2f42fd8491";

  function build(lang) {
    var f = document.createElement("iframe");
    /* allow-scripts and nothing else. Adding allow-same-origin here would
       hand the frame this origin back and undo the entire file. */
    f.setAttribute("sandbox", "allow-scripts");
    f.style.cssText = "position:absolute;width:0;height:0;border:0;left:-9999px";
    f.src = FRAME_SRC + "&lang=" + (lang === "py" ? "py" : "js");
    document.body.appendChild(f);

    var chan = new MessageChannel();
    var rec = { frame: f, port: chan.port1, ready: null, waiting: null };
    rec.ready = new Promise(function (res) {
      chan.port1.onmessage = function (e) {
        if (e.data && e.data.ready) return res(true);
        if (rec.waiting) { rec.waiting(e.data && e.data.out); rec.waiting = null; }
      };
    });
    f.onload = function () { f.contentWindow.postMessage("port", "*", [chan.port2]); };
    return rec;
  }

  function drop(lang) {
    var rec = FRAMES[lang];
    if (!rec) return;
    try { rec.frame.remove(); } catch (e) {}
    delete FRAMES[lang];
  }

  /* One run. Resolves with whatever the code printed — never rejects, since
     a lab that throws at the caller is a lab that shows a blank box. */
  global.Sandbox = {
    run: function (lang, code) {
      lang = lang === "py" ? "py" : "js";
      if (!FRAMES[lang]) FRAMES[lang] = build(lang);
      var rec = FRAMES[lang];
      return rec.ready.then(function () {
        return new Promise(function (res) {
          var done = false;
          var finish = function (out) {
            if (done) return;
            done = true;
            res(out == null ? "(nothing printed)" : out);
          };
          rec.waiting = finish;
          /* An endless loop cannot be interrupted from outside a frame, so
             the frame is thrown away instead. The next run builds a fresh
             one, which also throws away anything the last program left
             behind — a variable, a monkey-patched print, a half-finished
             import. */
          setTimeout(function () {
            if (done) return;
            drop(lang);
            finish("That took too long and was stopped. An endless loop is "
                 + "the usual reason — check any while.");
          }, LIMIT_MS[lang]);
          rec.port.postMessage(code);
        });
      });
    },
    /* For a page that wants Python ready before the learner presses Run. */
    warm: function (lang) {
      lang = lang === "py" ? "py" : "js";
      if (!FRAMES[lang]) FRAMES[lang] = build(lang);
      return FRAMES[lang].ready;
    }
  };
})(window);
