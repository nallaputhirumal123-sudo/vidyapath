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

  /* The program inside the frame. It never sees the parent: it is handed a
     port, and everything it can do is answer on it. */
  function HARNESS(lang) {
    return [
      "<!doctype html><meta charset='utf-8'><body><script>",
      "var PORT=null, PY=null;",
      "onmessage=function(e){ if(e.data==='port'){ PORT=e.ports[0];",
      "  PORT.onmessage=function(m){ run(m.data); }; PORT.postMessage({ready:1}); } };",
      "function say(o){ if(PORT) PORT.postMessage(o); }",
      lang === "py" ? PY_RUN : JS_RUN,
      "<\/script></body>"
    ].join("");
  }

  /* A short wait before answering, because a lesson may print from a
     setTimeout or a promise. The old in-page runner waited 400ms for the
     same reason; without it, anything asynchronous prints into a result
     that has already been sent and the box looks empty. */
  var JS_RUN = [
    "function run(code){",
    "  var out=[];",
    "  var log=function(){ out.push([].slice.call(arguments).map(function(v){",
    "    if(typeof v==='string') return v;",
    "    try{ return JSON.stringify(v); }catch(e){ return String(v); }",
    "  }).join(' ')); };",
    "  try{ new Function('console','\"use strict\";\\n'+code)",
    "        ({log:log,error:log,warn:log,info:log}); }",
    "  catch(e){ out.push(String(e)); }",
    "  setTimeout(function(){",
    "    say({out: out.join('\\n') || '(nothing printed)'});",
    "  }, 400);",
    "}"
  ].join("\n");

  var PY_RUN = [
    "async function boot(){",
    "  if(PY) return PY;",
    "  await new Promise(function(res,rej){",
    "    var s=document.createElement('script');",
    "    s.src='https://cdn.jsdelivr.net/pyodide/v0.26.2/full/pyodide.js';",
    "    s.onload=res; s.onerror=rej; document.head.appendChild(s); });",
    "  PY=await loadPyodide({indexURL:'https://cdn.jsdelivr.net/pyodide/v0.26.2/full/'});",
    "  return PY;",
    "}",
    "async function run(code){",
    "  var py;",
    "  try{ py=await boot(); }",
    "  catch(e){ return say({out:'Python could not start here. It is "
    + "downloaded from a public CDN — this device may be offline or the "
    + "network may be blocking it.'}); }",
    "  py.runPython('import sys, io\\n_b = io.StringIO()\\nsys.stdout = _b\\nsys.stderr = _b');",
    "  try{ py.runPython(code); }",
    "  catch(e){ py.runPython('import traceback; traceback.print_exc()'); }",
    "  say({out: py.runPython('sys.stdout = sys.__stdout__\\nsys.stderr = "
    + "sys.__stderr__\\n_b.getvalue()') || '(nothing printed)'});",
    "}"
  ].join("\n");

  function build(lang) {
    var f = document.createElement("iframe");
    /* allow-scripts and nothing else. Adding allow-same-origin here would
       hand the frame this origin back and undo the entire file. */
    f.setAttribute("sandbox", "allow-scripts");
    f.style.cssText = "position:absolute;width:0;height:0;border:0;left:-9999px";
    f.srcdoc = HARNESS(lang);
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
