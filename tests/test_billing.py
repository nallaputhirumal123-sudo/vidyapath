"""Stripe checkout and webhook, without touching Stripe.

Payments are the one path where a silent mistake costs real money, and it is
also the path that cannot be exercised against the live gateway from a test.
So the outbound call is intercepted and inspected, and the webhook is driven
with a correctly signed payload.
"""
import os, sys, time, json, hmac, hashlib
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main as m
from fastapi.testclient import TestClient

P, F = [], []
def ck(n, c, d=""):
    (P if c else F).append(n + (f" — {d}" if d else ""))


# ---------- intercept the call to Stripe ----------
SENT = {}


class _Resp:
    status_code = 200
    text = ""
    def json(self):
        return {"url": "https://checkout.stripe.com/c/pay/test_123"}


class _FakeClient:
    def __init__(self, *a, **k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    async def post(self, url, headers=None, data=None, json=None):
        SENT.clear()
        SENT.update({"url": url, "headers": headers or {}, "data": data or {}})
        return _Resp()


m.httpx.AsyncClient = _FakeClient
m.STRIPE_SECRET_KEY = "sk_test_fake"
m.STRIPE_ENABLED = True
m.STRIPE_WEBHOOK_SECRET = "whsec_test_fake"
m.STRIPE_PRICES = {}          # no dashboard Price IDs — the inline path

A = TestClient(m.app)
E = f"bill{int(time.time())}@example.com"
A.post("/api/auth/signup", json={"name": "Billing Test", "email": E,
                                 "password": "BillPass123!"})
db = m.SessionLocal()
UID = db.query(m.User).filter(m.User.email == E).first().id
db.close()

# ---------- monthly checkout ----------
r = A.post("/api/billing/checkout", json={"plan": "pro", "period": "month"})
ck("monthly checkout starts", r.status_code == 200, f"{r.status_code} {r.text[:150]}")
ck("returns the hosted Stripe url", r.json().get("url", "").startswith("https://checkout.stripe.com"))
d = SENT["data"]
ck("calls the checkout sessions endpoint",
   SENT["url"] == "https://api.stripe.com/v1/checkout/sessions", SENT["url"])
ck("uses the secret key as a bearer token",
   SENT["headers"].get("Authorization") == "Bearer sk_test_fake")
ck("mode is subscription, not one-off", d.get("mode") == "subscription", str(d.get("mode")))
ck("charges $15.99", d.get("line_items[0][price_data][unit_amount]") == "1599",
   str(d.get("line_items[0][price_data][unit_amount]")))
ck("currency is usd", d.get("line_items[0][price_data][currency]") == "usd")
ck("recurs monthly", d.get("line_items[0][price_data][recurring][interval]") == "month",
   str(d.get("line_items[0][price_data][recurring][interval]")))
ck("no dangling dashboard price id", "line_items[0][price]" not in d)
ck("user identified for the webhook", d.get("metadata[user_id]") == str(UID))
ck("period on the session", d.get("metadata[period]") == "month")
ck("period on the subscription too",
   d.get("subscription_data[metadata][period]") == "month",
   str(d.get("subscription_data[metadata][period]")))
ck("returns to the site after paying",
   d.get("success_url", "").endswith("/?upgraded=1"), str(d.get("success_url")))

# ---------- every term on sale ----------
EXPECT = {"month": ("1599", "month", "1"), "quarter": ("4299", "month", "3"),
          "half": ("7699", "month", "6"), "year": ("13499", "year", "1")}
for per, (amt, interval, count) in EXPECT.items():
    r = A.post("/api/billing/checkout", json={"plan": "pro", "period": per})
    ck(f"{per} checkout starts", r.status_code == 200, str(r.status_code))
    d = SENT["data"]
    ck(f"{per} charges the right amount",
       d.get("line_items[0][price_data][unit_amount]") == amt,
       str(d.get("line_items[0][price_data][unit_amount]")))
    # Stripe has no 3- or 6-month interval: it is a monthly interval with a
    # count, and getting this wrong bills someone monthly at the 6-month price.
    ck(f"{per} recurs on the right interval",
       d.get("line_items[0][price_data][recurring][interval]") == interval
       and d.get("line_items[0][price_data][recurring][interval_count]") == count,
       f"{d.get('line_items[0][price_data][recurring][interval]')} x"
       f"{d.get('line_items[0][price_data][recurring][interval_count]')}")
    ck(f"{per} period recorded on the subscription",
       d.get("subscription_data[metadata][period]") == per)

# ---------- a dashboard Price ID, if one is ever set, takes over ----------
m.STRIPE_PRICES = {("pro", "month"): "price_dash_123"}
A.post("/api/billing/checkout", json={"plan": "pro", "period": "month"})
ck("configured Price ID wins over the inline amount",
   SENT["data"].get("line_items[0][price]") == "price_dash_123"
   and "line_items[0][price_data][unit_amount]" not in SENT["data"],
   str(SENT["data"].get("line_items[0][price]")))
m.STRIPE_PRICES = {}

# ---------- bad input ----------
ck("unknown plan refused",
   A.post("/api/billing/checkout", json={"plan": "gold", "period": "month"}).status_code == 400)
ck("unknown period refused",
   A.post("/api/billing/checkout", json={"plan": "pro", "period": "decade"}).status_code == 400)


# ---------- webhook ----------
def signed(payload, secret="whsec_test_fake", ts=None):
    raw = json.dumps(payload).encode()
    t = str(int(ts or time.time()))
    sig = hmac.new(secret.encode(), f"{t}.".encode() + raw, hashlib.sha256).hexdigest()
    return raw, {"stripe-signature": f"t={t},v1={sig}",
                 "content-type": "application/json"}


def plan_row():
    s = m.SessionLocal()
    u = s.query(m.User).filter(m.User.email == E).first()
    out = (u.plan, u.plan_expires, u.plan_started, u.plan_provider)
    s.close()
    return out


ev = {"type": "checkout.session.completed",
      "data": {"object": {"id": "cs_1", "subscription": "sub_half_1",
                          "metadata": {"user_id": str(UID), "plan": "pro",
                                       "period": "half"}}}}
raw, hdr = signed(ev)
r = A.post("/api/billing/webhook/stripe", content=raw, headers=hdr)
ck("signed webhook accepted", r.status_code == 200, f"{r.status_code} {r.text[:120]}")
plan, exp, started, prov = plan_row()
ck("plan activated", plan == "pro", str(plan))
ck("provider recorded as stripe", prov == "stripe", str(prov))
days = (m._aware(exp) - m._aware(started)).days
ck("a 6-MONTH subscriber gets 6 months, not one", 150 < days < 200, f"{days} days")

# an unsigned copy of the same event must not extend anything
r = A.post("/api/billing/webhook/stripe", json=ev)
ck("unsigned webhook refused", r.status_code >= 400, str(r.status_code))

# nor a correctly signed one from the wrong secret
raw, hdr = signed(ev, secret="whsec_attacker")
r = A.post("/api/billing/webhook/stripe", content=raw, headers=hdr)
ck("wrong signing secret refused", r.status_code >= 400, str(r.status_code))

# nor an old one replayed
raw, hdr = signed(ev, ts=time.time() - 3600)
r = A.post("/api/billing/webhook/stripe", content=raw, headers=hdr)
ck("replayed old webhook refused", r.status_code >= 400, str(r.status_code))

# a renewal invoice carries no metadata — the period must survive anyway
ev2 = {"type": "invoice.payment_succeeded",
       "data": {"object": {"id": "in_1", "subscription": "sub_half_1",
                           "metadata": {}}}}
raw, hdr = signed(ev2)
r = A.post("/api/billing/webhook/stripe", content=raw, headers=hdr)
ck("renewal accepted", r.status_code == 200, str(r.status_code))
plan, exp, started, _ = plan_row()
days = (m._aware(exp) - m._aware(started)).days
ck("renewal keeps the 6-month term without metadata", 150 < days < 200, f"{days} days")

# cancellation lapses access rather than cutting it instantly
ev3 = {"type": "customer.subscription.deleted",
       "data": {"object": {"id": "sub_half_1"}}}
raw, hdr = signed(ev3)
r = A.post("/api/billing/webhook/stripe", content=raw, headers=hdr)
ck("cancellation webhook accepted", r.status_code == 200, str(r.status_code))

print("\n".join("PASS " + x for x in P))
print("\n".join("FAIL " + x for x in F))
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
