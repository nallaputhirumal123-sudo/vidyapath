import os, sys, time, datetime as dt
sys.path.insert(0, r"C:\Users\nalla\vidyapath")
os.environ.setdefault("JWT_SECRET","t"*40); os.environ["DATABASE_URL"]="sqlite:///./vidyapath.db"
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

print("\na claimed subject code")
# The admin assigned this slot to a teacher and then entered its code
# themselves. Being refused there is a door locked from the inside: they can
# already open that class, its register and its marks.
slot2 = main.SubjectSlot(class_id=CID, subject='Physics',
                         code=main._gen_slot_code(db), teacher_id=0,
                         status='open')
db.add(slot2); db.commit(); db.refresh(slot2)
other, ou = acct('oth')
r = other.post('/api/class/join', json={'code': slot2.code})
ck('a free subject can be claimed', r.status_code == 200, r.text[:60])
r = adm.post('/api/class/join', json={'code': slot2.code})
ck('the school admin is not locked out of it', r.status_code == 200,
   f'got {r.status_code} {r.text[:60]}')
third, _ = acct('thr')
r = third.post('/api/class/join', json={'code': slot2.code})
ck('but a stranger still is', r.status_code == 400, f'got {r.status_code}')
ck('and is told who holds it', 'Physics is already taught by' in r.text,
   r.json().get('detail', '')[:70])

# There is ONE email sign-in, and it is on the tab called Sign in.
#
# The Join with code tab carried its own copy of the email and password
# boxes for staff, so the same two fields appeared on two tabs and the one
# actually labelled "Sign in" read as the wrong door. This tab takes a code:
# a class code for a pupil, and the ten digits the office was issued for
# whoever becomes the school administrator.
import io as _io                                            # noqa: E402
import os as _os                                            # noqa: E402
_idx = _io.open(_os.path.join(_os.path.dirname(_os.path.dirname(
    _os.path.abspath(__file__))), "index.html"), encoding="utf-8").read()
ck("the join tab has no email box", 'id="jn_email"' not in _idx,
   "two tabs asking for the same two things is one tab too many")
ck("nor a password box", 'id="jn_pw"' not in _idx)
ck("and nothing is left reading them", "jn_staff" not in _idx,
   "a handler for fields that no longer exist is the next dead branch")
ck("the sign-in form still has both", 'id="li_email"' in _idx
   and 'id="li_pw"' in _idx, "this is the one that signs people in")
ck("and the join tab points staff at it",
   "use the Sign in tab instead" in _idx,
   "a teacher with a password needs telling where it goes")

print(f"\nPASSED {P}   FAILED {F}")
sys.exit(1 if F else 0)
