"""The packet engine: order, prefixes and state.

Networking is taught with boxes and arrows, and what people get wrong is never
the diagram — it is the order. Which rule matched first. Whether the longest
prefix or the first listed route wins. Why the reply came back when only an
outbound rule was written. Those are sequence questions and a picture cannot
answer them, so this computes them.

No model is involved, which is the point on a teaching site: a model asked why
a packet was dropped gives a fluent and plausible reason, and this gives the
actual one.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import net                                         # noqa: E402

PASS = FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {name}" + (f"  ({detail})" if detail else ""))
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


# ---- addresses --------------------------------------------------------
check("an address round-trips",
      net.int_to_ip(net.ip_to_int("192.168.1.50")) == "192.168.1.50")
check("the broadcast address is the top of the range",
      net.int_to_ip(0xFFFFFFFF) == "255.255.255.255")
for bad in ("999.1.1.1", "10.0.0", "not an ip", "", "10.0.0.256"):
    try:
        net.ip_to_int(bad)
        check(f"{bad!r} is refused", False, "accepted")
    except net.BadAddress:
        check(f"{bad!r} is refused", True)

# ---- subnetting -------------------------------------------------------
check("inside a /24", net.in_network("192.168.1.50", "192.168.1.0/24"))
check("outside a /24", not net.in_network("192.168.2.50", "192.168.1.0/24"))
check("a /16 is wider", net.in_network("192.168.2.50", "192.168.0.0/16"))
check("a /32 is one address", net.in_network("10.0.0.5", "10.0.0.5/32"))
check("and only that one", not net.in_network("10.0.0.6", "10.0.0.5/32"))
check("a /0 holds everything", net.in_network("8.8.8.8", "0.0.0.0/0"))
check("the boundary is included", net.in_network("10.0.0.0", "10.0.0.0/24"))
check("and the last address too",
      net.in_network("10.0.0.255", "10.0.0.0/24"))
check("but not the next one", not net.in_network("10.0.1.0", "10.0.0.0/24"))

# ---- routing: longest prefix, not first listed ------------------------
ROUTES = [
    {"network": "0.0.0.0/0", "via": "10.0.0.1", "dev": "eth0"},
    {"network": "192.168.1.0/24", "via": "", "dev": "eth1"},
    {"network": "192.168.0.0/16", "via": "10.0.0.9", "dev": "eth2"},
]
best, others = net.route_for("192.168.1.50", ROUTES)
check("the /24 wins, though it is listed second",
      best["network"] == "192.168.1.0/24", best["network"])
check("and the routes it beat are reported", len(others) == 2,
      str([o["network"] for o in others]))
best2, _ = net.route_for("192.168.9.9", ROUTES)
check("with no /24 match the /16 takes it",
      best2["network"] == "192.168.0.0/16", best2["network"])
best3, _ = net.route_for("8.8.8.8", ROUTES)
check("and anything else goes to the default",
      best3["network"] == "0.0.0.0/0", best3["network"])
none, rejected = net.route_for("8.8.8.8", [
    {"network": "192.168.1.0/24", "via": "", "dev": "eth1"}])
check("no route at all is reported as none", none is None)
check("and the misses are still listed", len(rejected) == 1)

# ---- firewall: first match wins, which makes rules dead ---------------
RULES = [
    {"action": "accept", "proto": "tcp", "dst": "10.0.0.5", "port": 443},
    {"action": "drop", "proto": "tcp", "src": "203.0.113.0/24"},
    {"action": "accept", "proto": "tcp", "port": 22},
]
verdict, trace, by = net.evaluate(
    RULES, {"src": "203.0.113.7", "dst": "10.0.0.5",
            "proto": "tcp", "dport": 443})
check("a blocked subnet still gets in when a rule above allows it",
      verdict == "ACCEPT" and by["n"] == 1,
      "the drop rule below is never reached — the dead-rule lesson")

verdict2, trace2, by2 = net.evaluate(
    RULES, {"src": "203.0.113.7", "dst": "10.0.0.9",
            "proto": "tcp", "dport": 80})
check("the same source is dropped when nothing above matches",
      verdict2 == "DROP" and by2["n"] == 2, f"{verdict2} by {by2['n']}")
check("and every rule considered says why it did not match",
      all(t.get("why") for t in trace2), str(trace2[:1]))

verdict3, trace3, _ = net.evaluate(
    RULES, {"src": "10.1.1.1", "dst": "10.0.0.9",
            "proto": "udp", "dport": 53})
check("nothing matching means the default policy drops it",
      verdict3 == "DROP" and trace3[-1]["rule"] == "policy")

# The single most common confusion about stateful firewalls.
verdict4, trace4, _ = net.evaluate(
    RULES, {"src": "10.0.0.5", "dst": "203.0.113.7",
            "proto": "tcp", "dport": 51234}, established=True)
check("a reply is accepted without consulting the rules at all",
      verdict4 == "ACCEPT" and trace4[0]["rule"] == "conntrack",
      "why outbound-only rules still allow replies")

check("an empty rule list drops by policy",
      net.evaluate([], {"src": "1.1.1.1", "dst": "2.2.2.2",
                        "proto": "tcp", "dport": 80})[0] == "DROP")

# ---- it must never raise on bad input --------------------------------
for junk in ([{"action": "accept", "src": "not-an-ip"}],
             [{"action": "weird"}], [{}], [{"port": "abc"}]):
    try:
        net.evaluate(junk, {"src": "1.1.1.1", "dst": "2.2.2.2",
                            "proto": "tcp", "dport": 80})
        check(f"survives {str(junk)[:30]}", True)
    except Exception as e:
        check(f"survives {str(junk)[:30]}", False, f"{type(e).__name__}: {e}")

print(f"\nPASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
