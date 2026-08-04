import os, sys, time, datetime as dt
sys.path.insert(0, r"C:\Users\nalla\vidyapath")
os.environ.setdefault("JWT_SECRET","t"*40)
os.environ["DATABASE_URL"]="sqlite:///./vidyapath.db"
os.environ["JOBS_ENABLED"]="0"; os.environ["COOKIE_SECURE"]="0"
import main
from fastapi.testclient import TestClient
main.Base.metadata.create_all(bind=main.engine)
main.send_email = lambda *a, **k: None
st = int(time.time()); db = main.SessionLocal()
P=F=0
def ck(n, ok, d=""):
    global P,F
    if ok: P+=1; print("  PASS ", n, ("("+d+")") if d else "")
    else:  F+=1; print("  FAIL ", n, d)

def acct(tag, admin=False):
    c = TestClient(main.app); em=f"hd{tag}{st}@example.com"
    c.post("/api/auth/signup", json={"name":f"P{tag}","email":em,"password":"HeadPass123!"})
    u = db.query(main.User).filter(main.User.email==em).first()
    u.dob = dt.date(1990,1,1)
    if admin: u.is_admin=True
    db.commit(); return c, u

# an admin mints a school + head code, as the admin panel does
adm, au = acct("adm", admin=True)
sc = main.School(name=f"Test School {st}")
db.add(sc); db.commit(); db.refresh(sc)
hc = "HEAD-"+str(st)[-5:]
db.add(main.TeacherCode(code=hc, school=sc.name, school_id=sc.id, is_head=True, active=True))
db.commit()

print("\na head teacher who already has an account")
head, hu = acct("head")
r = head.post("/api/class/join", json={"code": hc})
ck("can redeem a HEAD- code by signing in", r.status_code==200, r.text[:80])
ck("and is recognised as the school admin",
   "school admin" in r.text.lower(), r.text[:60])
t = main.teacher_row(hu, db)
ck("the teacher row says head", t is not None and t.role=="head", t.role if t else "none")

print("\nand can then build the school")
r = head.post("/api/teacher/class", json={"name": f"8-C {st}"})
ck("create a class", r.status_code==200, r.text[:60])
cid = r.json()["id"]
r = head.post(f"/api/teacher/class/{cid}/subject", json={"subject":"Physics"}) \
    if False else head.post(f"/api/teacher/class/{cid}/roster", json={"names":"Nila R\nArun K"})
ck("create student places on the register", r.status_code==200, r.text[:60])
r = head.get(f"/api/teacher/class/{cid}/roster")
ck("both students are there", r.json()["total"]==2, str(r.json()["total"]))
print(f"\nPASSED {P}   FAILED {F}")
sys.exit(1 if F else 0)
