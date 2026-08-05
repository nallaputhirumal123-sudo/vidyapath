import os, sys, time, datetime as dt
sys.path.insert(0, r"C:\Users\nalla\vidyapath")
os.environ.setdefault("JWT_SECRET","t"*40); os.environ["DATABASE_URL"]="sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"   # local test database; refused on a deployment
os.environ["JOBS_ENABLED"]="0"; os.environ["COOKIE_SECURE"]="0"
import main
from fastapi.testclient import TestClient

def _pw(uid, pw='TeachPass123!'):
    """A password for a staff account, for suites that only need a session.

    Staff are not given one when they are created any more — a teacher signs
    in with the subject code the office hands them. These suites are about
    what a teacher may SEE once signed in, not about how they got there, so
    they set one directly rather than being rewritten around codes.
    """
    _d = main.SessionLocal()
    _u = _d.get(main.User, uid)
    _u.password_hash = main.hash_pw(pw)
    _d.commit(); _d.close()
    return pw

main.Base.metadata.create_all(bind=main.engine); main.send_email=lambda *a,**k: None
st=int(time.time()); db=main.SessionLocal(); P=F=0
def ck(n,ok,d=""):
    global P,F
    if ok: P+=1; print("  PASS ",n,("("+d+")") if d else "")
    else:  F+=1; print("  FAIL ",n,d)
sc=main.School(name='DS%d'%st); db.add(sc); db.commit(); db.refresh(sc)
hc=main._gen_head_code(db)
db.add(main.TeacherCode(code=hc,school=sc.name,school_id=sc.id,is_head=True,active=True)); db.commit()
adm=TestClient(main.app); em='ds%d@example.com'%st
adm.post('/api/auth/signup',json={'name':'Admin','email':em,'password':'DsPass123!'})
u=db.query(main.User).filter(main.User.email==em).first(); u.dob=dt.date(1985,1,1); db.commit()
adm.post('/api/class/join',json={'code':hc})
CID=adm.post('/api/teacher/class',json={'name':'9-D %d'%st}).json()['id']
adm.post('/api/teacher/class/%d/roster'%CID,json={'names':'Ana P\nBimal Q'})
made=adm.post('/api/head/staff',json={'name':'Sir R','email':'dt%d@s.in'%st,'role':'teacher'}).json()
adm.post('/api/head/assign',json={'class_id':CID,'subject':'Physics','user_id':made['user_id']})
tch=TestClient(main.app); tch.post('/api/auth/login',json={'email':'dt%d@s.in'%st,'password':_pw(made['user_id'])})
main._CODE_TRIES.clear(); main._CODE_FAILS.clear()
code=db.get(main.Klass,CID).join_code
kids=[]
for _ in range(2):
    c=TestClient(main.app)
# Roster names no longer disappear when claimed, so "the first name on
# the list" is the same child every time and every client after the
# first lands in one account — which single-session sign-in then signs
# out. Take the first name nobody has taken instead.
    free=[n for n in c.post('/api/craxlearn/code',json={'code':code}).json()['names'] if not n.get('taken')]
    if not free: break
    c.post('/api/craxlearn/claim',json={'code':code,'roster_id':free[0]['id']}); kids.append(c)

print("\na question in one subject")
r=kids[0].post('/api/class/%d/discussion'%CID,json={'body':'Why does light bend?','subject':'Physics'})
ck('a student can ask against a subject', r.status_code==200, r.text[:50])
qid=r.json()['id']
kids[1].post('/api/class/%d/discussion'%CID,json={'body':'Fractions confuse me','subject':'Mathematics'})

print("\nthe loop: students and teacher, all in one thread")
r=kids[1].post('/api/class/%d/discussion'%CID,json={'body':'I think it slows down.','parent_id':qid})
ck('another student can answer', r.status_code==200, r.text[:50])
r=tch.post('/api/class/%d/discussion'%CID,json={'body':'Right - and the angle changes.','parent_id':qid})
ck('and the teacher joins the same thread', r.status_code==200, r.text[:50])

print("\nthe subject holds the whole thread together")
d=kids[0].get('/api/class/%d/discussion?subject=Physics'%CID).json()
ck('asking for Physics returns only Physics', len(d['threads'])==1, str(len(d['threads'])))
t0=d['threads'][0]
ck('with both answers under the question', len(t0['replies'])==2, str(len(t0['replies'])))
ck('a reply inherits the subject', all(
   (db.get(main.ClassPost,r_['id']).subject or '')=='Physics' for r_ in t0['replies']),
   'otherwise the answer falls out of the page it was typed on')
ck('the student answer is not marked as staff', any(not r_['from_staff'] for r_ in t0['replies']))
ck('the teacher answer is', any(r_['from_staff'] for r_ in t0['replies']),
   'a class should know which answer came from the teacher')
d2=kids[0].get('/api/class/%d/discussion?subject=Mathematics'%CID).json()
ck('and Maths is its own conversation', len(d2['threads'])==1 and 'Fractions' in d2['threads'][0]['body'])
d3=kids[0].get('/api/class/%d/discussion'%CID).json()
ck('no subject asked for still returns everything', len(d3['threads'])==2, str(len(d3['threads'])))
print(f"\nPASSED {P}   FAILED {F}")
sys.exit(1 if F else 0)
