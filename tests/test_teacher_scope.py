import os, sys, time, datetime as dt
sys.path.insert(0, r"C:\Users\nalla\vidyapath")
os.environ.setdefault("JWT_SECRET","t"*40)
os.environ["DATABASE_URL"]="sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"   # local test database; refused on a deployment
os.environ["JOBS_ENABLED"]="0"; os.environ["COOKIE_SECURE"]="0"
import main
from fastapi.testclient import TestClient
main.Base.metadata.create_all(bind=main.engine); main.send_email=lambda *a,**k: None
st=int(time.time()); db=main.SessionLocal(); P=F=0
def ck(n,ok,d=""):
    global P,F
    if ok: P+=1; print("  PASS ",n,("("+d+")") if d else "")
    else:  F+=1; print("  FAIL ",n,d)
def acct(t):
    c=TestClient(main.app); em=f"tp{t}{st}@example.com"
    c.post("/api/auth/signup",json={"name":"P"+t,"email":em,"password":"TeachPass1!"})
    u=db.query(main.User).filter(main.User.email==em).first(); u.dob=dt.date(1990,1,1); db.commit()
    return c,u
sc=main.School(name=f"TS{st}"); db.add(sc); db.commit(); db.refresh(sc)
hc=f"HEAD-T{str(st)[-4:]}"
db.add(main.TeacherCode(code=hc,school=sc.name,school_id=sc.id,is_head=True,active=True)); db.commit()
adm,_=acct("adm"); adm.post("/api/class/join",json={"code":hc})
CID=adm.post("/api/teacher/class",json={"name":f"9-B {st}"}).json()["id"]
adm.post(f"/api/teacher/class/{CID}/roster",json={"names":"Anu R, 3101\nBala S, 3102"})
# a real subject teacher, claiming a slot
slot=adm.post(f"/api/teacher/class/{CID}/subject",json={"subject":"Maths"}) if False else None
tc=main.SubjectSlot(class_id=CID,subject="Maths",code=main._gen_slot_code(db),teacher_id=0,status="open")
db.add(tc); db.commit(); db.refresh(tc)
tch,tu=acct("tch"); tch.post("/api/class/join",json={"code":tc.code})

print("\nwho may set work")
a={"subject":"Maths","title":"Ch 3","body":"do it","due_date":""}
r=tch.post(f"/api/teacher/class/{CID}/assignment",json=a)
ck("the subject teacher can set work", r.status_code==200, r.text[:70])
# The admin may set work too. This once refused them — work being the
# teacher's judgement about their own class — but an admin who cannot cover a
# class on the morning a teacher is off keeps a second system for the days
# that matter, and they already see every assignment and mark, so the
# restriction bought no privacy. It only removed a capability.
r=adm.post(f"/api/teacher/class/{CID}/assignment",json=a)
ck("the school admin can too", r.status_code==200, f"got {r.status_code}")

print("\nwho may address what")
def post(cl,aud,title,**kw):
    b={"title":title,"body":"x","urgent":False,"starts_on":"","ends_on":"","audience":aud}; b.update(kw)
    return cl.post("/api/office/notice",json=b)
ck("a teacher can post to their own class",
   post(tch,"class","Maths test Friday",class_id=CID).status_code==200)
r=post(tch,"all","Whole school notice")
ck("a teacher cannot post to everyone", r.status_code==403, f"got {r.status_code}")
r=post(tch,"teachers","All staff")
ck("nor to all teachers", r.status_code==403, f"got {r.status_code}")
r=post(tch,"students","All students")
ck("nor to all students", r.status_code==403, f"got {r.status_code}")
ck("the school admin still can", post(adm,"all","Closure").status_code==200)

# A child who has not signed in has no account, and a notice is addressed to
# accounts — so the search shows only the ones who have. One claims a name here.
main._CODE_TRIES.clear()
main._CODE_FAILS.clear()
kid = TestClient(main.app)
_code = db.get(main.Klass, CID).join_code
_free = kid.post("/api/craxlearn/code", json={"code": _code}).json()["names"]
kid.post("/api/craxlearn/claim",
         json={"code": _code, "roster_id": _free[0]["id"]})

print("\nwho a teacher can look up")
r=tch.get("/api/head/people")
pp=r.json()["people"]
ck("a teacher sees their own class's children", any(p["kind"]=="student" for p in pp), str(len(pp)))
ck("and no staff list", all(p["kind"]!="teacher" for p in pp),
   "addressing colleagues is the admin's school-wide notice")
ck("the admin still sees staff too", any(p["kind"]=="teacher" for p in adm.get("/api/head/people").json()["people"]))

print("\nthe roll number")
rid=[x["id"] for x in adm.get(f"/api/teacher/class/{CID}/roster").json()["roster"]][0]
r=adm.patch(f"/api/teacher/roster/{rid}",json={"name":"Anu Reddy","student_code":"3199"})
ck("name and roll number save together", r.status_code==200 and r.json()["student_code"]=="3199", r.text[:70])
r=adm.patch(f"/api/teacher/roster/{rid}",json={"name":"Anu Reddy","student_code":"3102"})
ck("a duplicate roll number is refused", r.status_code==409, f"got {r.status_code}")
print(f"\nPASSED {P}   FAILED {F}")
sys.exit(1 if F else 0)
