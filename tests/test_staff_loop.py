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
sc=main.School(name='LP%d'%st); db.add(sc); db.commit(); db.refresh(sc)
hc=main._gen_head_code(db)
db.add(main.TeacherCode(code=hc,school=sc.name,school_id=sc.id,is_head=True,active=True)); db.commit()
def acct(t):
    c=TestClient(main.app); em='lp%s%d@example.com'%(t,st)
    c.post('/api/auth/signup',json={'name':'P'+t,'email':em,'password':'LpPass123!'})
    u=db.query(main.User).filter(main.User.email==em).first(); u.dob=dt.date(1990,1,1); db.commit()
    return c,u
adm,_=acct('adm'); adm.post('/api/class/join',json={'code':hc})
A=adm.post('/api/teacher/class',json={'name':'7-A %d'%st}).json()['id']
B=adm.post('/api/teacher/class',json={'name':'7-B %d'%st}).json()['id']
adm.post('/api/teacher/class/%d/roster'%A,json={'names':'Ann A\nBen B\nCal C'})
adm.post('/api/teacher/class/%d/roster'%B,json={'names':'Dev D'})
# one teacher, two classes -- the whole point
made=adm.post('/api/head/staff',json={'name':'Latha','email':'lt%d@s.in'%st,'role':'teacher'}).json()
for cid,subj in [(A,'Physics'),(B,'Physics')]:
    adm.post('/api/head/assign',json={'class_id':cid,'subject':subj,'user_id':made['user_id']})
print("\none teacher across two classes")
ck('holds the subject in 7-A', main._my_subjects(db,A,db.get(main.User,made['user_id']))=={'Physics'})
ck('and in 7-B too', main._my_subjects(db,B,db.get(main.User,made['user_id']))=={'Physics'},
   'the same person, not a second account')
tch=TestClient(main.app); tch.post('/api/auth/login',json={'email':'lt%d@s.in'%st,'password':made['temporary_password']})
# every child in A signs in
main._CODE_TRIES.clear(); main._CODE_FAILS.clear()
kidsA=[]
codeA=db.get(main.Klass,A).join_code
for _ in range(3):
    c=TestClient(main.app)
    free=c.post('/api/craxlearn/code',json={'code':codeA}).json()['names']
    if not free: break
    c.post('/api/craxlearn/claim',json={'code':codeA,'roster_id':free[0]['id']}); kidsA.append(c)
codeB=db.get(main.Klass,B).join_code
kb=TestClient(main.app)
freeB=kb.post('/api/craxlearn/code',json={'code':codeB}).json()['names']
kb.post('/api/craxlearn/claim',json={'code':codeB,'roster_id':freeB[0]['id']})
print("\nan update to one class reaches that whole class")
r=tch.post('/api/office/notice',json={'title':'Physics test Friday','body':'ch 4','urgent':False,
    'starts_on':'','ends_on':'','audience':'class','class_id':A})
ck('the teacher can post to 7-A', r.status_code==200, r.text[:60])
seen=[('Physics test Friday' in [n['title'] for n in k.get('/api/my/notices').json()['notices']]) for k in kidsA]
ck('every child in 7-A sees it', all(seen) and len(seen)==3, f'{sum(seen)}/{len(seen)}')
ck('a child in 7-B does not',
   'Physics test Friday' not in [n['title'] for n in kb.get('/api/my/notices').json()['notices']],
   'targeted means targeted')
print(f"\nPASSED {P}   FAILED {F}")
sys.exit(1 if F else 0)
