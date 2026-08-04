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
sc=main.School(name='BA%d'%st); db.add(sc); db.commit(); db.refresh(sc)
hc=main._gen_head_code(db)
db.add(main.TeacherCode(code=hc,school=sc.name,school_id=sc.id,is_head=True,active=True)); db.commit()
adm=TestClient(main.app); em='ba%d@example.com'%st
adm.post('/api/auth/signup',json={'name':'Admin','email':em,'password':'BaPass123!'})
u=db.query(main.User).filter(main.User.email==em).first(); u.dob=dt.date(1985,1,1); db.commit()
adm.post('/api/class/join',json={'code':hc})
A=adm.post('/api/teacher/class',json={'name':'9-A %d'%st}).json()['id']
B=adm.post('/api/teacher/class',json={'name':'9-B %d'%st}).json()['id']
made=adm.post('/api/head/staff',json={'name':'Latha','email':'lb%d@s.in'%st,'role':'teacher'}).json()
adm.post('/api/head/assign',json={'class_id':A,'subject':'Physics','user_id':made['user_id']})
adm.post('/api/head/assign',json={'class_id':B,'subject':'Physics','user_id':made['user_id']})
adm.post('/api/head/assign',json={'class_id':B,'subject':'Chemistry','user_id':made['user_id']})
t=TestClient(main.app); t.post('/api/auth/login',json={'email':'lb%d@s.in'%st,'password':made['temporary_password']})

print("\nwhich subject the board can work out on its own")
sa=[x for x in t.get('/api/class/%d/subjects'%A).json()['subjects'] if x['teacher_id']==made['user_id']]
ck('one subject in 9-A, so it can decide', len(sa)==1 and sa[0]['subject']=='Physics', str([x['subject'] for x in sa]))
sb=[x for x in t.get('/api/class/%d/subjects'%B).json()['subjects'] if x['teacher_id']==made['user_id']]
ck('two in 9-B, so it must ask', len(sb)==2, str(sorted(x['subject'] for x in sb)))

print("\nremembering the class")
r=t.post('/api/note',json={'key':'boardclass','value':str(A)})
ck('the choice is stored per teacher', r.status_code==200, r.text[:40])
prog=t.get('/api/progress').json()
ck('and comes back with their progress', prog['notes'].get('boardclass')==str(A), str(prog['notes'].get('boardclass')))

print("\nfiling straight there")
lesson={'title':'Refraction','takeaway':'x','steps':[{'t':'Light bends.','where':'','code':''}]}
r=t.post('/api/craxlearn/board/save',json={'class_id':A,'topic':'refraction','title':'Refraction',
    'subject':sa[0]['subject'],'note':'','lesson':lesson})
ck('the lesson lands in that class', r.status_code==200, r.text[:60])
mats=t.get('/api/class/%d/materials'%A).json()['materials']
ck('under the subject it was worked out to be', any(m.get('subject')=='Physics' for m in mats), str([m.get('subject') for m in mats]))
ck('and the other class got nothing', len(t.get('/api/class/%d/materials'%B).json()['materials'])==0)
print(f"\nPASSED {P}   FAILED {F}")
sys.exit(1 if F else 0)
