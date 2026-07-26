"""Cashfree checkout and webhook, without touching Cashfree.

Payments are the one path where a silent mistake costs real money, and the one
that cannot be exercised against the live gateway from a test. So the outbound
call is intercepted and inspected, and the webhook is driven with correctly
signed, unsigned, wrongly-signed and replayed payloads.
"""
import os, sys, time, json, hmac, hashlib, base64
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"
os.environ["CASHFREE_APP_ID"] = "test_app"
os.environ["CASHFREE_SECRET"] = "test_secret"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main as m
from fastapi.testclient import TestClient

P, F = [], []
def ck(n, c, d=""):
    (P if c else F).append(n + (f" — {d}" if d else ""))

SENT = {}


class _Resp:
    status_code = 200
    text = ""
    def json(self):
        return {"payment_session_id": "session_test_abc",
                "order_id": "craxle_test_1"}


class _FakeClient:
    def __init__(self, *a, **k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    async def post(self, url, headers=None, data=None, json=None):
        SENT.clear()
        SENT.update({"url": url, "headers": headers or {}, "json": json or {}})
        return _Resp()


m.httpx.AsyncClient = _FakeClient

A = TestClient(m.app)
E = f"bill{int(time.time())}@example.com"
A.post("/api/auth/signup", json={"name": "Billing Test", "email": E,
                                 "password": "BillPass123!"})
db = m.SessionLocal()
UID = db.query(m.User).filter(m.User.email == E).first().id
db.close()

# ---------- prices are quoted in rupees ----------
b = A.get("/api/billing/plans").json()
ck("gateway is cashfree", b["gateway"] == "cashfree", str(b["gateway"]))
ck("currency is INR", b["currency"] == "INR", str(b["currency"]))
ck("stripe is not offered", "stripe" not in b.get("available", {}),
   str(b.get("available")))
pro = [p for p in b["plans"] if p["id"] == "pro"][0]
ck("four terms on sale", len(pro["periods"]) == 4, str(len(pro["periods"])))
ck("discount ladder is 0/10/20/30",
   [t["save_pct"] for t in pro["periods"]] == [0, 10, 20, 30],
   str([t["save_pct"] for t in pro["periods"]]))

# ---------- every term creates the right order ----------
EXPECT = {"month": 1407.0, "quarter": 3799.0, "half": 6759.0, "year": 11819.0}
for per, rupees in EXPECT.items():
    r = A.post("/api/billing/checkout", json={"plan": "pro", "period": per})
    ck(f"{per} checkout starts", r.status_code == 200, f"{r.status_code} {r.text[:120]}")
    j = SENT["json"]
    ck(f"{per} hits the orders endpoint",
       SENT["url"].endswith("/pg/orders"), SENT["url"])
    # Cashfree takes RUPEES, not paise. Sending the stored minor units would
    # charge a hundred times the price.
    ck(f"{per} charges the right rupee amount",
       j.get("order_amount") == rupees, str(j.get("order_amount")))
    ck(f"{per} is in INR", j.get("order_currency") == "INR")
    ck(f"{per} carries the term in order_tags",
       (j.get("order_tags") or {}).get("period") == per,
       str((j.get("order_tags") or {}).get("period")))
    ck(f"{per} identifies the user", (j.get("order_tags") or {}).get("user_id") == str(UID))
ck("sends the pinned API version",
   SENT["headers"].get("x-api-version") == "2023-08-01",
   str(SENT["headers"].get("x-api-version")))
ck("authenticates with the app id and secret",
   SENT["headers"].get("x-client-id") == "test_app"
   and SENT["headers"].get("x-client-secret") == "test_secret")
ck("returns a payment session, not a raw url",
   A.post("/api/billing/checkout", json={"plan": "pro", "period": "month"}
          ).json().get("payment_session_id") == "session_test_abc")

# ---------- bad input ----------
ck("unknown plan refused",
   A.post("/api/billing/checkout", json={"plan": "gold", "period": "month"}).status_code == 400)
ck("unknown period refused",
   A.post("/api/billing/checkout", json={"plan": "pro", "period": "decade"}).status_code == 400)


# ---------- webhook ----------
def signed(payload, secret="test_secret", ts=None):
    raw = json.dumps(payload)
    t = str(int(ts or time.time()))
    sig = base64.b64encode(hmac.new(secret.encode(), (t + raw).encode(),
                                    hashlib.sha256).digest()).decode()
    return raw.encode(), {"x-webhook-signature": sig, "x-webhook-timestamp": t,
                          "content-type": "application/json"}


def plan_row():
    s = m.SessionLocal()
    u = s.query(m.User).filter(m.User.email == E).first()
    out = (u.plan, u.plan_expires, u.plan_started, u.plan_provider)
    s.close()
    return out


ev = {"type": "PAYMENT_SUCCESS_WEBHOOK",
      "data": {"order": {"order_id": "craxle_half_1",
                         "order_tags": {"user_id": str(UID), "plan": "pro",
                                        "period": "half"}},
               "payment": {"payment_status": "SUCCESS"}}}
raw, hdr = signed(ev)
r = A.post("/api/billing/webhook/cashfree", content=raw, headers=hdr)
ck("signed webhook accepted", r.status_code == 200, f"{r.status_code} {r.text[:120]}")
plan, exp, started, prov = plan_row()
ck("plan activated", plan == "pro", str(plan))
ck("provider recorded as cashfree", prov == "cashfree", str(prov))
days = (m._aware(exp) - m._aware(started)).days
ck("a 6-MONTH order grants 6 months", 150 < days < 200, f"{days} days")

r = A.post("/api/billing/webhook/cashfree", json=ev)
ck("unsigned webhook refused", r.status_code >= 400, str(r.status_code))
raw, hdr = signed(ev, secret="attacker_secret")
ck("wrong signing secret refused",
   A.post("/api/billing/webhook/cashfree", content=raw, headers=hdr).status_code >= 400)
raw, hdr = signed(ev, ts=time.time() - 3600)
ck("replayed old webhook refused",
   A.post("/api/billing/webhook/cashfree", content=raw, headers=hdr).status_code >= 400)

# a payment for an unknown term must not silently grant a year
ev2 = {"type": "PAYMENT_SUCCESS_WEBHOOK",
       "data": {"order": {"order_id": "craxle_junk_1",
                          "order_tags": {"user_id": str(UID), "plan": "pro",
                                         "period": "decade"}},
                "payment": {"payment_status": "SUCCESS"}}}
raw, hdr = signed(ev2)
r = A.post("/api/billing/webhook/cashfree", content=raw, headers=hdr)
ck("unknown term falls back to a month", r.status_code == 200)
plan, exp, started, _ = plan_row()
ck("unknown term grants a month, not more",
   (m._aware(exp) - m._aware(started)).days < 40,
   f"{(m._aware(exp) - m._aware(started)).days} days")

# ---------- the retired gateway is gone ----------
ck("stripe webhook removed",
   A.post("/api/billing/webhook/stripe", json={}).status_code == 404)
ck("razorpay webhook removed",
   A.post("/api/billing/webhook/razorpay", json={}).status_code == 404)

print("\n".join("PASS " + x for x in P))
print("\n".join("FAIL " + x for x in F))
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
