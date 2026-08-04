import os, sys, time, datetime as dt
sys.path.insert(0, r"C:\Users\nalla\vidyapath")
os.environ.setdefault("JWT_SECRET","t"*40); os.environ["DATABASE_URL"]="sqlite:///./vidyapath.db"
os.environ["JOBS_ENABLED"]="0"; os.environ["COOKIE_SECURE"]="0"
import main
from fastapi.testclient import TestClient
main.Base.metadata.create_all(bind=main.engine); main.send_email=lambda *a,**k: None
st=int(time.time()); db=main.SessionLocal(); P=F=0
def ck(n,ok,d=""):
    global P,F
    if ok: P+=1; print("  PASS ",n,("("+d+")") if d else "")
    else:  F+=1; print("  FAIL ",n,d)
sc=main.School(name='RT%d'%st); db.add(sc); db.commit(); db.refresh(sc)
hc=main._gen_head_code(db)
db.add(main.TeacherCode(code=hc,school=sc.name,school_id=sc.id,is_head=True,active=True)); db.commit()
def acct(t,age=1990):
    c=TestClient(main.app); em='rt%s%d@example.com'%(t,st)
    c.post('/api/auth/signup',json={'name':'P'+t,'email':em,'password':'RtPass123!'})
    u=db.query(main.User).filter(main.User.email==em).first(); u.dob=dt.date(age,1,1); db.commit()
    return c,u
adm,_=acct('adm'); r=adm.post('/api/class/join',json={'code':hc})
print("\nwhat the server says each code makes you")
ck('a school admin code says school admin', r.json().get('role')=='school admin', r.json().get('role'))
CID=adm.post('/api/teacher/class',json={'name':'5-Z %d'%st}).json()['id']
class_code=db.get(main.Klass,CID).join_code
slot=main.SubjectSlot(class_id=CID,subject='Maths',code=main._gen_slot_code(db),teacher_id=0,status='open')
db.add(slot); db.commit(); db.refresh(slot)
tch,_=acct('tch'); r=tch.post('/api/class/join',json={'code':slot.code})
ck('a subject code says teacher', r.json().get('role')=='teacher', r.json().get('role'))
stu,_=acct('stu'); r=stu.post('/api/class/join',json={'code':class_code})
ck('a class code says student', r.json().get('role')=='student', r.json().get('role'))
ck('and names the class they joined', r.json().get('class')=='5-Z %d'%st, str(r.json().get('class')))
print("\nand the page each role should land on")
import io, re
idx=io.open(r'C:\Users\nalla\vidyapath\index.html',encoding='utf-8').read()
ck('the client routes on the returned role', 'asStudent ? "class" : "teacher"' in idx,
   'it used to send everybody to the teacher dashboard')
ck('it does not hard-code teacher any more',
   'await boot();\n    S.view={page:"teacher"};' not in idx)
print(f"\nPASSED {P}   FAILED {F}")
sys.exit(1 if F else 0)
