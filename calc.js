/* Arithmetic, worked on the board itself.
 *
 * The calculator posted every sum to the server, and the server asks who is
 * asking — so on a board that nobody has signed in to, which is the normal
 * state of a board, pressing = returned 401 and the answer line stayed
 * empty. The board's own code says what was intended two hundred lines
 * away:
 *
 *     var OPEN_TOOLS = ["write", "calc", "formula"];  // needs no server
 *
 * That is the fifth thing on this board to need a person it does not have.
 * The others were the simulations, the course list, the source search and
 * the scanner; each time the fix was to stop asking. Here it is better than
 * that: arithmetic does not need a network at all. A calculator that works
 * in a power cut is a better calculator.
 *
 * **No eval, and no Function.** The expression is typed by whoever is
 * standing at the board, in a room full of teenagers who have just been
 * taught what a sandbox is. This parses to a tree and walks it against an
 * allowlist — numbers, the operators, and the functions below — exactly as
 * maths.py does on the server, and the two keep the same names so an answer
 * does not change depending on which one worked it out.
 *
 * **Degrees, because a school board is a school board.** sin(30) is 0.5 in
 * every Class 10 textbook in the country, and a calculator that answers
 * -0.988 is right in a way that helps nobody. Radians are available by
 * name — sin(pi/6) still works, because pi is a constant and the conversion
 * only applies to the number handed to a trigonometric function.
 */
(function (global) {
  "use strict";

  var CONSTS = { pi: Math.PI, e: Math.E };

  /* Degrees in, degrees out. asin/acos/atan return degrees for the same
     reason: a teacher who types asin(0.5) is expecting 30. */
  var D = Math.PI / 180;
  var FUNCS = {
    sqrt: Math.sqrt, abs: Math.abs, exp: Math.exp,
    sin: function (x) { return Math.sin(x * D); },
    cos: function (x) { return Math.cos(x * D); },
    tan: function (x) { return Math.tan(x * D); },
    asin: function (x) { return Math.asin(x) / D; },
    acos: function (x) { return Math.acos(x) / D; },
    atan: function (x) { return Math.atan(x) / D; },
    sinh: Math.sinh, cosh: Math.cosh, tanh: Math.tanh,
    log: Math.log, ln: Math.log, log10: Math.log10,
    floor: Math.floor, ceil: Math.ceil, round: Math.round,
    min: Math.min, max: Math.max
  };

  var MAX_POW = 64;          /* 2^1e9 is not a maths error, it is a hang */

  function Fail(msg) { this.message = msg; }
  Fail.prototype.toString = function () { return this.message; };

  /* ---- reading the expression ---------------------------------------- */
  function tokens(src) {
    var out = [], i = 0, s = String(src);
    while (i < s.length) {
      var c = s[i];
      if (c === " " || c === "\t" || c === ",") { i++; continue; }
      if (c >= "0" && c <= "9" || c === ".") {
        var j = i;
        while (j < s.length && (s[j] >= "0" && s[j] <= "9" || s[j] === ".")) j++;
        var num = s.slice(i, j);
        if ((num.match(/\./g) || []).length > 1) {
          throw new Fail(num + " has two decimal points in it");
        }
        out.push({ t: "num", v: parseFloat(num) });
        i = j;
        continue;
      }
      if (/[A-Za-z]/.test(c)) {
        var k = i;
        while (k < s.length && /[A-Za-z0-9_]/.test(s[k])) k++;
        out.push({ t: "name", v: s.slice(i, k).toLowerCase() });
        i = k;
        continue;
      }
      if ("+-*/^%()".indexOf(c) >= 0) { out.push({ t: c }); i++; continue; }
      /* The keypad writes these, and they mean what they look like. */
      if (c === "×") { out.push({ t: "*" }); i++; continue; }
      if (c === "÷") { out.push({ t: "/" }); i++; continue; }
      if (c === "−") { out.push({ t: "-" }); i++; continue; }
      if (c === "√") { out.push({ t: "name", v: "sqrt" }); i++; continue; }
      if (c === "π") { out.push({ t: "name", v: "pi" }); i++; continue; }
      throw new Fail("I cannot read “" + c + "” in that");
    }
    return out;
  }

  /* ---- one pass, lowest precedence first ------------------------------ */
  function parse(ts) {
    var at = 0;
    function peek() { return ts[at]; }
    function take(t) {
      var got = ts[at];
      if (!got || (t && got.t !== t)) return null;
      at++;
      return got;
    }

    function expr() { return addsub(); }

    function addsub() {
      var left = muldiv();
      for (;;) {
        var op = peek();
        if (!op || (op.t !== "+" && op.t !== "-")) return left;
        at++;
        var right = muldiv();
        left = op.t === "+" ? left + right : left - right;
      }
    }

    function muldiv() {
      var left = unary();
      for (;;) {
        var op = peek();
        if (!op || (op.t !== "*" && op.t !== "/" && op.t !== "%")) return left;
        at++;
        var right = unary();
        if ((op.t === "/" || op.t === "%") && right === 0) {
          throw new Fail("that divides by zero");
        }
        left = op.t === "*" ? left * right
             : op.t === "/" ? left / right
             : left % right;
      }
    }

    function unary() {
      if (take("-")) return -unary();
      if (take("+")) return unary();
      return power();
    }

    /* Right-associative, so 2^3^2 is 512 the way it is on paper. */
    function power() {
      var base = atom();
      if (!peek() || peek().t !== "^") return base;
      at++;
      var exp = unary();
      if (Math.abs(exp) > MAX_POW) {
        throw new Fail("that power is too large to work out here");
      }
      return Math.pow(base, exp);
    }

    function atom() {
      if (take("(")) {
        var v = expr();
        if (!take(")")) throw new Fail("a bracket is not closed");
        return v;
      }
      var n = take("num");
      if (n) return n.v;
      var name = take("name");
      if (name) {
        if (Object.prototype.hasOwnProperty.call(CONSTS, name.v)) {
          return CONSTS[name.v];
        }
        if (!Object.prototype.hasOwnProperty.call(FUNCS, name.v)) {
          /* The commonest case by far, and worth saying properly: a letter
             on its own is an unknown, and this works numbers rather than
             algebra. */
          throw new Fail("“" + name.v + "” has no value here — "
                       + "this works out numbers, so give it one");
        }
        if (!take("(")) throw new Fail(name.v + " needs a number in brackets "
                                     + "after it, like " + name.v + "(30)");
        var args = [expr()];
        while (peek() && peek().t === "num") args.push(expr());
        if (!take(")")) throw new Fail("a bracket is not closed");
        var f = FUNCS[name.v];
        var out = args.length > 1 ? f.apply(null, args) : f(args[0]);
        if (typeof out !== "number" || !isFinite(out)) {
          throw new Fail(name.v + " has no answer for that");
        }
        return out;
      }
      throw new Fail("that expression is not finished");
    }

    var value = expr();
    if (at < ts.length) throw new Fail("I could not read the end of that");
    return value;
  }

  /* ---- what a screen calls -------------------------------------------- */
  global.Calc = {
    /* Returns { ok:true, value, text } or { ok:false, why }. Never throws:
       a calculator that throws at its caller is a blank answer line. */
    run: function (src) {
      var text = String(src == null ? "" : src).trim();
      /* A trailing = is how anybody writes a sum they want the answer to. */
      text = text.replace(/=\s*$/, "").trim();
      if (!text) return { ok: false, why: "" };
      if (text.length > 500) {
        return { ok: false, why: "that is longer than this will work out" };
      }
      try {
        var v = parse(tokens(text));
        if (typeof v !== "number" || !isFinite(v)) {
          return { ok: false, why: "that has no numeric answer" };
        }
        return { ok: true, value: v, text: global.Calc.show(v) };
      } catch (e) {
        return { ok: false, why: (e && e.message) || "that cannot be worked out" };
      }
    },

    /* Rounded for reading, not for storing. A board is read from the back of
       the room, and 0.30000000000000004 is a distraction rather than a
       precision. */
    show: function (v) {
      if (Math.abs(v) >= 1e12 || (v !== 0 && Math.abs(v) < 1e-9)) {
        return v.toExponential(6).replace(/e([+-])/, "e$1");
      }
      var r = Math.round(v * 1e10) / 1e10;
      return String(r);
    }
  };
})(window);
