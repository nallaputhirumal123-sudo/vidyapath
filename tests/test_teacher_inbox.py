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
sc=main.School(name='IB%d'%st); db.add(sc); db.commit(); db.refresh(sc)
hc=main._gen_head_code(db)
db.add(main.TeacherCode(code=hc,school=sc.name,school_id=sc.id,is_head=True,active=True)); db.commit()
adm=TestClient(main.app); em='ib%d@example.com'%st
adm.post('/api/auth/signup',json={'name':'Admin','email':em,'password':'IbPass123!'})
u=db.query(main.User).filter(main.User.email==em).first(); u.dob=dt.date(1985,1,1); db.commit()
adm.post('/api/class/join',json={'code':hc})
A=adm.post('/api/teacher/class',json={'name':'9-P %d'%st}).json()['id']
B=adm.post('/api/teacher/class',json={'name':'9-Q %d'%st}).json()['id']
adm.post('/api/teacher/class/%d/roster'%A,json={'names':'Asha K'})
adm.post('/api/teacher/class/%d/roster'%B,json={'names':'Bala M'})
def staff(tag, pairs):
    made=adm.post('/api/head/staff',json={'name':'T'+tag,'email':'i%s%d@s.in'%(tag,st),'role':'teacher'}).json()
    for cid,sub in pairs:
        adm.post('/api/head/assign',json={'class_id':cid,'subject':sub,'user_id':made['user_id']})
    c=TestClient(main.app); c.post('/api/auth/login',json={'email':'i%s%d@s.in'%(tag,st),'password':made['temporary_password']})
    return c
phys=staff('p',[(A,'Physics'),(B,'Physics')])
math=staff('m',[(A,'Mathematics')])
PA=phys.post('/api/teacher/class/%d/assignment'%A,json={'subject':'Physics','title':'Rays','body':'x','due_date':''}).json()['id']
PB=phys.post('/api/teacher/class/%d/assignment'%B,json={'subject':'Physics','title':'Optics','body':'x','due_date':''}).json()['id']
MA=math.post('/api/teacher/class/%d/assignment'%A,json={'subject':'Mathematics','title':'Algebra','body':'x','due_date':''}).json()['id']
main._CODE_TRIES.clear(); main._CODE_FAILS.clear()
def kid(cid):
    code=db.get(main.Klass,cid).join_code
    c=TestClient(main.app)
    free=c.post('/api/craxlearn/code',json={'code':code}).json()['names']
    c.post('/api/craxlearn/claim',json={'code':code,'roster_id':free[0]['id']}); return c
k1=kid(A); k2=kid(B)
k1.post('/api/assignment/%d/message'%PA,json={'body':'Stuck on Q3'})
k2.post('/api/assignment/%d/message'%PB,json={'body':'Which lens?'})
k1.post('/api/assignment/%d/message'%MA,json={'body':'Algebra help'})

print("\nthe teacher's inbox across their classes")
d=phys.get('/api/teacher/messages').json()
subs={t['subject'] for t in d['threads']}
ck('gathers both classes in one view', len(d['threads'])==2, str(len(d['threads'])))
ck('only their own subject', subs=={'Physics'}, str(subs))
ck('with the student name', all(t['student'] for t in d['threads']), str([t['student'] for t in d['threads']]))
ck('and the class it came from', {t['class_name'][:3] for t in d['threads']}=={'9-P','9-Q'}, str([t['class_name'] for t in d['threads']]))
ck('all waiting for a reply', d['waiting']==2, str(d['waiting']))

print("\nanother teacher sees only theirs")
dm=math.get('/api/teacher/messages').json()
ck('the Maths teacher sees one', len(dm['threads'])==1, str(len(dm['threads'])))
ck('and it is Maths', dm['threads'][0]['subject']=='Mathematics', dm['threads'][0]['subject'])

print("\nanswering takes it off the waiting list")
_sid = db.query(main.RosterName).filter(main.RosterName.class_id==A).first().claimed_by
_r = phys.post('/api/assignment/%d/message'%PA,
               json={'body':'Look at figure 3.', 'student_id': _sid})
ck('the teacher reply is accepted', _r.status_code==200, _r.text[:60])
d2=phys.get('/api/teacher/messages').json()
ck('one fewer waiting', d2['waiting']==1, str(d2['waiting']))
ck('the answered thread is still listed', len(d2['threads'])==2, str(len(d2['threads'])))
ck('and the waiting one is first', d2['threads'][0]['waiting'] is True, str(d2['threads'][0]['waiting']))

print("\nthe admin sees the school")
da=adm.get('/api/teacher/messages').json()
ck('every thread at the school', len(da['threads'])==3, str(len(da['threads'])))
print(f"\nPASSED {P}   FAILED {F}")
sys.exit(1 if F else 0)
