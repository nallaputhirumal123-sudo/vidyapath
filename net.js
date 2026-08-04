/* The packet walkthrough.
 *
 * Networking is taught with boxes and arrows, and what people get wrong is
 * never the diagram — it is the order. Which rule matched first. Whether the
 * longest prefix or the first listed route wins. Why the reply came back when
 * only an outbound rule was written.
 *
 * So this is not a diagram. You set the routes and the rules, send a packet,
 * and watch the decision happen one stage at a time. Change a rule, send it
 * again, see the drop become an allow. Every answer is computed on the server
 * from the rules on screen — no model call — so it is free, instant, and
 * cannot invent a firewall decision.
 *
 * The default network is chosen to demonstrate the dead-rule fault: a packet
 * from a subnet with an explicit drop rule is accepted anyway, because a
 * port-443 rule sits above it. That is the thing every real firewall
 * accumulates and no diagram shows.
 */
(function () {
  "use strict";

  var NW = { pre: null, packet: null, routes: [], rules: [],
             out: null, busy: false, established: false };
  window.NW = NW;

  var esc = window.esc || function (s) {
    return String(s).replace(/[&<>]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c];
    });
  };
  var $ = function (s) { return document.querySelector(s); };

  var CSS = [
    ".nwwrap{max-width:860px}",
    ".nwgrid{display:grid;grid-template-columns:1fr 1fr;gap:14px;",
    "  margin-bottom:14px}",
    "@media(max-width:760px){.nwgrid{grid-template-columns:1fr}}",
    ".nwbox{border:1px solid var(--line,#2a2a2a);border-radius:12px;",
    "  padding:12px 13px}",
    ".nwbox h4{margin:0 0 9px;font-size:12px;letter-spacing:.5px;",
    "  text-transform:uppercase;color:var(--dim,#666);font-weight:800}",
    ".nwrow{display:flex;gap:6px;align-items:center;margin-bottom:6px;",
    "  flex-wrap:wrap}",
    ".nwrow input,.nwrow select{font-size:16px;padding:6px 8px;",
    "  border-radius:8px;border:1px solid var(--line,#2a2a2a);",
    "  background:var(--panel2,#0f0f0f);color:var(--text,#eee);min-width:0}",
    ".nwrow input{flex:1 1 90px}",
    ".nwdel{border:0;background:transparent;color:var(--dim,#666);",
    "  cursor:pointer;font-size:16px;padding:0 4px}",
    ".nwdel:hover{color:#d9534f}",
    ".nwsend{display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end;",
    "  margin-bottom:14px}",
    ".nwverdict{font-size:15px;font-weight:800;padding:11px 14px;",
    "  border-radius:11px;margin-bottom:12px}",
    ".nwok{border:1px solid #3fae6a;background:rgba(63,174,106,.12)}",
    ".nwno{border:1px solid #d9534f;background:rgba(217,83,79,.12)}",
    ".nwstep{border-left:2px solid var(--accent,#ffb020);padding:0 0 0 13px;",
    "  margin-bottom:15px}",
    ".nwstep b{display:block;font-size:13.5px;margin-bottom:4px}",
    ".nwstep p{margin:0;font-size:13px;line-height:1.7;",
    "  color:var(--body,#ccc)}",
    ".nwbeat{font-size:12px;color:var(--muted,#8a8a8a);margin-top:5px}",
    ".nwrules{margin-top:9px;border:1px solid var(--line,#2a2a2a);",
    "  border-radius:9px;overflow:hidden}",
    ".nwrule{display:flex;gap:9px;padding:7px 11px;font-size:12.5px;",
    "  border-bottom:1px solid var(--line,#1e1e1e);align-items:baseline;",
    "  font-family:ui-monospace,Menlo,Consolas,monospace}",
    ".nwrule:last-child{border-bottom:none}",
    ".nwrule .n{color:var(--dim,#666);flex:0 0 20px}",
    ".nwrule .r{flex:1;min-width:0;word-break:break-word}",
    ".nwrule .v{font-weight:800;flex:0 0 auto}",
    ".nwrule.hit{background:rgba(255,176,32,.10)}",
    ".nwrule.hit .v{color:var(--accent,#ffb020)}",
    ".nwrule .why{color:var(--muted,#8a8a8a);font-size:11.5px}",
    ".nwadd{font-size:12.5px;padding:5px 11px;border-radius:8px;cursor:pointer;",
    "  border:1px dashed var(--line,#2a2a2a);background:transparent;",
    "  color:var(--muted,#8a8a8a);margin-top:4px}"
  ].join("");

  function styles() {
    if (document.getElementById("net-css")) return;
    var s = document.createElement("style");
    s.id = "net-css";
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  async function load() {
    styles();
    if (!NW.pre) {
      try {
        NW.pre = await api.get("/api/net");
        NW.routes = NW.pre.routes.slice();
        NW.rules = NW.pre.rules.slice();
        NW.packet = Object.assign({}, NW.pre.packet);
      } catch (e) {
        NW.pre = { routes: [], rules: [], packet: {} };
      }
    }
    paint();
  }

  /* Load one named lab instead of the starting network.
   *
   * The tutor picks the topology and the server hands over the whole thing
   * — routes, rules and the packet — already checked. Nothing is derived
   * here from the name, because a client that decided what "dmz" meant
   * would be a second opinion about a network the packet engine is the only
   * authority on.
   *
   * The board is replaced rather than added to. A lab whose point is that
   * rule order matters does not survive having the previous lab's rules
   * still sitting above it.
   */
  function open(preset) {
    if (!preset || !preset.rules || !preset.routes) return false;
    styles();
    NW.pre = { routes: preset.routes, rules: preset.rules,
               packet: preset.packet };
    NW.routes = preset.routes.slice();
    NW.rules = preset.rules.slice();
    NW.packet = Object.assign({}, preset.packet);
    NW.established = !!preset.established;
    NW.out = null;
    NW.lab = preset.title ? { title: preset.title, teaches: preset.teaches }
                          : null;
    paint();
    return true;
  }

  function routeRow(r, i) {
    return '<div class="nwrow">' +
      '<input data-nr="' + i + '" data-f="network" value="' + esc(r.network || "") +
        '" placeholder="10.0.0.0/24">' +
      '<input data-nr="' + i + '" data-f="via" value="' + esc(r.via || "") +
        '" placeholder="via (blank = direct)">' +
      '<button class="nwdel" data-nrdel="' + i + '" title="Remove">×</button>' +
      "</div>";
  }

  function ruleRow(r, i) {
    var acts = ["accept", "drop"].map(function (a) {
      return '<option value="' + a + '"' +
        (String(r.action).toLowerCase() === a ? " selected" : "") + ">" +
        a + "</option>";
    }).join("");
    return '<div class="nwrow">' +
      '<select data-nu="' + i + '" data-f="action">' + acts + "</select>" +
      '<input data-nu="' + i + '" data-f="src" value="' + esc(r.src || "any") +
        '" placeholder="from" style="flex:1 1 80px">' +
      '<input data-nu="' + i + '" data-f="dst" value="' + esc(r.dst || "any") +
        '" placeholder="to" style="flex:1 1 80px">' +
      '<input data-nu="' + i + '" data-f="port" value="' + esc(r.port || "any") +
        '" placeholder="port" style="flex:0 1 62px">' +
      '<button class="nwdel" data-nudel="' + i + '" title="Remove">×</button>' +
      "</div>";
  }

  function paint() {
    var host = $("#main");
    if (!host) return;
    var p = NW.packet || {};
    host.innerHTML = '<div class="nwwrap">' +
      '<h2 style="margin:0 0 4px">🌐 Packet walkthrough</h2>' +
      '<p style="font-size:13px;color:var(--muted);margin:0 0 16px;' +
      'max-width:62ch">Set the routes and the rules, send a packet, and watch ' +
      'the decision happen one stage at a time. Every answer is computed from ' +
      'the rules on this page — nothing is guessed, so it cannot invent a ' +
      'reason a packet was dropped. Free and unlimited: change a rule and ' +
      'send it again as often as you like.</p>' +

      // What this particular network is here to teach, when the tutor
      // handed one over. Without it a lab is a form full of addresses and
      // the point it was chosen to make is invisible.
      (NW.lab ? '<div class="nwbox" style="margin-bottom:14px">' +
          '<h4>' + esc(NW.lab.title) + "</h4>" +
          '<p style="font-size:13px;color:var(--muted);margin:0;' +
          'max-width:62ch">' + esc(NW.lab.teaches || "") + "</p></div>" : "") +

      '<div class="nwgrid">' +
        '<div class="nwbox"><h4>Routing table</h4>' +
          NW.routes.map(routeRow).join("") +
          '<button class="nwadd" data-nradd="1">+ add a route</button></div>' +
        '<div class="nwbox"><h4>Firewall rules — read in order</h4>' +
          NW.rules.map(ruleRow).join("") +
          '<button class="nwadd" data-nuadd="1">+ add a rule</button></div>' +
      "</div>" +

      '<div class="nwbox" style="margin-bottom:14px"><h4>The packet</h4>' +
        '<div class="nwsend">' +
          '<input id="nwSrc" value="' + esc(p.src || "") + '" placeholder="from" style="flex:1 1 120px">' +
          '<input id="nwDst" value="' + esc(p.dst || "") + '" placeholder="to" style="flex:1 1 120px">' +
          '<input id="nwPort" value="' + esc(p.dport || 443) + '" placeholder="port" style="flex:0 1 74px">' +
          '<label style="font-size:12.5px;display:flex;gap:5px;align-items:center">' +
            '<input type="checkbox" id="nwEst"' + (NW.established ? " checked" : "") +
            ' style="flex:0"> reply to an established connection</label>' +
          '<button class="btn" data-nwgo="1"' + (NW.busy ? " disabled" : "") + ">" +
            (NW.busy ? "…" : "Send it") + "</button>" +
        "</div></div>" +

      (NW.out ? outHTML(NW.out) : "") +
      "</div>";
    wire();
  }

  function outHTML(d) {
    var ok = d.verdict === "ACCEPT";
    var h = '<div class="nwverdict ' + (ok ? "nwok" : "nwno") + '">' +
      (ok ? "✓ Delivered" : "✕ " + esc(d.verdict)) + " — " +
      esc(d.packet.src) + " → " + esc(d.packet.dst) + ":" + esc(d.packet.dport) +
      "</div>";

    (d.steps || []).forEach(function (s) {
      h += '<div class="nwstep"><b>' + esc(s.stage) + "</b>" +
        "<p>" + esc(s.detail) + "</p>";
      if (s.beaten && s.beaten.length) {
        h += '<div class="nwbeat">Also matched, and lost: ' +
          s.beaten.map(esc).join(", ") + "</div>";
      }
      if (s.rules && s.rules.length) {
        h += '<div class="nwrules">' + s.rules.map(function (r) {
          var hit = r.result === "ACCEPT" || r.result === "DROP" ||
                    r.result === "REJECT";
          return '<div class="nwrule' + (hit ? " hit" : "") + '">' +
            '<span class="n">' + esc(r.n) + "</span>" +
            '<span class="r">' + esc(r.rule) +
              '<br><span class="why">' + esc(r.why) + "</span></span>" +
            '<span class="v">' + esc(r.result) + "</span></div>";
        }).join("") + "</div>";
      }
      h += "</div>";
    });
    return h;
  }

  async function send() {
    if (NW.busy) return;
    NW.packet = {
      src: ($("#nwSrc") || {}).value || "",
      dst: ($("#nwDst") || {}).value || "",
      proto: "tcp",
      dport: parseInt(($("#nwPort") || {}).value, 10) || 443
    };
    NW.established = !!(($("#nwEst") || {}).checked);
    NW.busy = true; paint();
    try {
      NW.out = await api.post("/api/net/trace", {
        src: NW.packet.src, dst: NW.packet.dst, proto: "tcp",
        dport: NW.packet.dport, established: NW.established,
        routes: NW.routes, rules: NW.rules
      });
    } catch (e) {
      NW.out = null;
      if (typeof toast === "function") toast(e.message || "That did not send.");
    }
    NW.busy = false; paint();
  }

  function wire() {
    document.querySelectorAll("[data-nr]").forEach(function (el) {
      el.oninput = function () {
        NW.routes[+el.dataset.nr][el.dataset.f] = el.value;
      };
    });
    document.querySelectorAll("[data-nu]").forEach(function (el) {
      el.oninput = el.onchange = function () {
        NW.rules[+el.dataset.nu][el.dataset.f] = el.value;
      };
    });
    var go = $("[data-nwgo]");
    if (go) go.onclick = send;
  }

  document.addEventListener("click", function (e) {
    var t = e.target;
    if (t.closest && t.closest("[data-nradd]")) {
      NW.routes.push({ network: "", via: "", dev: "eth0" }); paint();
    } else if (t.closest && t.closest("[data-nuadd]")) {
      NW.rules.push({ action: "accept", proto: "tcp", src: "any",
                      dst: "any", port: "any" }); paint();
    } else if (t.closest && t.closest("[data-nrdel]")) {
      NW.routes.splice(+t.closest("[data-nrdel]").dataset.nrdel, 1); paint();
    } else if (t.closest && t.closest("[data-nudel]")) {
      NW.rules.splice(+t.closest("[data-nudel]").dataset.nudel, 1); paint();
    }
  });

  window.NetBoard = { load: load, open: open };
  // Same shape as the lab, so the router calls it the same way.
  window.renderNet = load;
})();
