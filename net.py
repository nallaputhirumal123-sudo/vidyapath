"""What actually happens to a packet, step by step.

Networking is taught with diagrams of boxes and arrows, and the thing people
get wrong is never the diagram — it is the order. Which rule matched first.
Whether the router had an ARP entry yet. Why the reply came back when the
outbound rule was the only one written. Those are sequence questions, and a
picture of a network cannot answer them.

So this runs the packet. Given hosts, routes and firewall rules it walks the
decision one hop at a time and says what happened at each: the ARP lookup, the
longest-prefix match and why that route won over the default, the first
firewall rule that matched, the NAT translation, the state entry that lets the
reply back in.

No model call. Every answer here comes from the rules the user set, computed
the way a router computes them, so it is free, instant, identical for
everybody, and — the part that matters on a teaching site — incapable of
inventing a firewall decision. A model asked why a packet was dropped will
produce a fluent and plausible reason. This produces the actual one.

Addresses are handled as integers throughout, because that is what a prefix
match is: mask both sides and compare. Doing it on strings is where the
off-by-one errors live.
"""
import re

MAX_RULES = 24
MAX_ROUTES = 16
MAX_HOSTS = 12

_IP = re.compile(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$")
_CIDR = re.compile(r"^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/(\d{1,2})$")


class BadAddress(Exception):
    """Not an address. Said plainly rather than guessed at."""


def ip_to_int(text):
    m = _IP.match(str(text or "").strip())
    if not m:
        raise BadAddress(f"{text!r} is not an IPv4 address")
    parts = [int(g) for g in m.groups()]
    if any(p > 255 for p in parts):
        raise BadAddress(f"{text} has an octet above 255")
    return (parts[0] << 24) | (parts[1] << 16) | (parts[2] << 8) | parts[3]


def int_to_ip(n):
    n = int(n) & 0xFFFFFFFF
    return f"{(n >> 24) & 255}.{(n >> 16) & 255}.{(n >> 8) & 255}.{n & 255}"


def parse_cidr(text):
    """A network as (network integer, prefix length)."""
    m = _CIDR.match(str(text or "").strip())
    if not m:
        raise BadAddress(f"{text!r} is not a network like 10.0.0.0/24")
    bits = int(m.group(2))
    if bits > 32:
        raise BadAddress(f"/{bits} is not a valid prefix length")
    mask = (0xFFFFFFFF << (32 - bits)) & 0xFFFFFFFF if bits else 0
    return ip_to_int(m.group(1)) & mask, bits


def in_network(addr, cidr):
    """Is this address inside that network?

    The whole of subnetting is this one line: mask both and compare. Every
    other way of asking it is a way of getting it wrong.
    """
    net, bits = parse_cidr(cidr)
    mask = (0xFFFFFFFF << (32 - bits)) & 0xFFFFFFFF if bits else 0
    return (ip_to_int(addr) & mask) == net


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------
def route_for(dst, routes):
    """The route a router would choose, and every route it rejected.

    Longest prefix wins — that is the entire algorithm, and it is the thing
    people expect to be "first match" or "most specific by some other measure".
    Returning the losers as well is the point: seeing that 0.0.0.0/0 matched
    too, and lost to /24, is what makes the rule stick.
    """
    dst_i = ip_to_int(dst)
    matched, rejected = [], []
    for r in routes[:MAX_ROUTES]:
        try:
            net, bits = parse_cidr(r.get("network", ""))
        except BadAddress:
            continue
        mask = (0xFFFFFFFF << (32 - bits)) & 0xFFFFFFFF if bits else 0
        entry = {"network": r.get("network"), "via": r.get("via", ""),
                 "dev": r.get("dev", ""), "bits": bits}
        (matched if (dst_i & mask) == net else rejected).append(entry)
    if not matched:
        return None, rejected
    best = max(matched, key=lambda e: e["bits"])
    others = [e for e in matched if e is not best] + rejected
    return best, others


# ---------------------------------------------------------------------------
# Firewall
# ---------------------------------------------------------------------------
def _rule_matches(rule, pkt):
    """Does this rule match, and which field decided it did not?"""
    for field, key in (("src", "src"), ("dst", "dst")):
        want = str(rule.get(field) or "any").strip().lower()
        if want in ("any", "*", ""):
            continue
        try:
            ok = (in_network(pkt[key], want) if "/" in want
                  else ip_to_int(pkt[key]) == ip_to_int(want))
        except BadAddress:
            ok = False
        if not ok:
            return False, f"{field} {pkt[key]} is not {want}"

    want_proto = str(rule.get("proto") or "any").strip().lower()
    if want_proto not in ("any", "*", "") and want_proto != pkt["proto"]:
        return False, f"protocol is {pkt['proto']}, not {want_proto}"

    want_port = rule.get("port")
    if want_port not in (None, "", "any"):
        try:
            if int(want_port) != int(pkt["dport"]):
                return False, f"destination port is {pkt['dport']}, " \
                              f"not {want_port}"
        except (TypeError, ValueError):
            return False, "port is not a number"
    return True, ""


def evaluate(rules, pkt, established=False):
    """Walk the rule list in order and stop at the first match.

    In order and first match wins, which is the thing that catches people out:
    a permissive rule above a restrictive one makes the restrictive one dead,
    and the list still reads as though it does something. Every rule that was
    considered and why it did not match is reported, because that is the
    lesson.

    A packet belonging to an established connection is accepted before the
    rules are read at all — which is why a firewall with only outbound rules
    still lets replies back in, and is the single most common confusion about
    stateful firewalls.
    """
    trace = []
    if established:
        trace.append({"n": 0, "rule": "conntrack",
                      "result": "ACCEPT",
                      "why": "this packet belongs to a connection already "
                             "established, so the rules are never consulted"})
        return "ACCEPT", trace, {"n": 0, "rule": "conntrack"}

    for i, rule in enumerate(rules[:MAX_RULES], 1):
        ok, why = _rule_matches(rule, pkt)
        action = str(rule.get("action") or "accept").strip().upper()
        if action not in ("ACCEPT", "DROP", "REJECT"):
            action = "ACCEPT"
        shown = _describe(rule)
        if ok:
            trace.append({"n": i, "rule": shown, "result": action,
                          "why": "matched"})
            return action, trace, {"n": i, "rule": shown}
        trace.append({"n": i, "rule": shown, "result": "skipped", "why": why})

    trace.append({"n": len(rules[:MAX_RULES]) + 1, "rule": "policy",
                  "result": "DROP",
                  "why": "no rule matched, and the default policy is DROP"})
    return "DROP", trace, {"n": 0, "rule": "default policy"}


def _describe(rule):
    """A rule as an engineer would read it back."""
    bits = [str(rule.get("action") or "accept").lower()]
    if str(rule.get("proto") or "any").lower() not in ("any", "*", ""):
        bits.append(str(rule["proto"]).lower())
    src = str(rule.get("src") or "any")
    dst = str(rule.get("dst") or "any")
    bits.append(f"from {src}")
    bits.append(f"to {dst}")
    if rule.get("port") not in (None, "", "any"):
        bits.append(f"port {rule['port']}")
    return " ".join(bits)
