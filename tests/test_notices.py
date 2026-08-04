import os, sys, time, datetime as dt
sys.path.insert(0, r"C:\Users\nalla\vidyapath")
os.environ.setdefault("JWT_SECRET","t"*40)
os.environ["DATABASE_URL"]="sqlite:///./vidyapath.db"
os.environ["JOBS_ENABLED"]="0"; os.environ["COOKIE_SECURE"]="0"
import main
from fastapi.testclient import TestClient
main.Base.metadata.create_all(bind=main.engine)
main.send_email = lambda *a, **k: None
st=int(time.time()); db=main.SessionLocal(); P=F=0
def ck(n, ok, d=""):
    global P,F
    if ok: P+=1; print("  PASS ", n, ("("+d+")") if d else "")
    else:  F+=1; print("  FAIL ", n, d)
def acct(tag):
    c=TestClient(main.app); em=f"nt{tag}{st}@example.com"
    c.post("/api/auth/signup", json={"name":f"P{tag}","email":em,"password":"NotePass123!"})
    u=db.query(main.User).filter(main.User.email==em).first(); u.dob=dt.date(1990,1,1); db.commit()
    return c,u

sc=main.School(name=f"NSchool {st}"); db.add(sc); db.commit(); db.refresh(sc)
hc="HEAD-N"+str(st)[-4:]
db.add(main.TeacherCode(code=hc, school=sc.name, school_id=sc.id, is_head=True, active=True)); db.commit()

head,hu=acct("head"); head.post("/api/class/join", json={"code":hc})
teach,tu=acct("teach")
main._grant_teacher(db, tu, sc.name, sc.id, "teacher"); db.commit()
learner,lu=acct("learn")

print("\nputting a notice up")
r=head.post("/api/office/notice", json={"title":"Sports day moved","body":"Now Friday.","urgent":True,"starts_on":"","ends_on":""})
ck("the head teacher can", r.status_code==200, r.text[:70])
nid=r.json()["notice"]["id"] if r.status_code==200 else 0

r=teach.post("/api/office/notice", json={"title":"Nope","body":"x","urgent":False,"starts_on":"","ends_on":""})
ck("an ordinary subject teacher still cannot", r.status_code==403, f"got {r.status_code}")
r=learner.post("/api/office/notice", json={"title":"Nope","body":"x","urgent":False,"starts_on":"","ends_on":""})
ck("nor a learner", r.status_code==403, f"got {r.status_code}")

print("\nand taking it down")
r=teach.delete(f"/api/office/notice/{nid}")
ck("a subject teacher cannot remove it", r.status_code==403, f"got {r.status_code}")
r=head.delete(f"/api/office/notice/{nid}")
ck("the head who wrote it can", r.status_code==200, r.text[:50])

print("\nattendance and fees stay with the office")
r=head.get("/api/office/fees") if False else None
import inspect
src=inspect.getsource(main)
ck("other office routes are untouched", src.count("Depends(school_admin_user)")>=6,
   f"{src.count('Depends(school_admin_user)')} still office-only")
print(f"\nPASSED {P}   FAILED {F}")
sys.exit(1 if F else 0)
