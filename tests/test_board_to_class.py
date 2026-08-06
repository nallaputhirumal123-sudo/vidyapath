import os, sys, time, datetime as dt
sys.path.insert(0, r"C:\Users\nalla\vidyapath")
os.environ.setdefault("JWT_SECRET","t"*40); os.environ["DATABASE_URL"]="sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"   # local test database; refused on a deployment
os.environ["JOBS_ENABLED"]="0"; os.environ["COOKIE_SECURE"]="0"
import main
from fastapi.testclient import TestClient
from _school import teacher_on, make_staff   # noqa: E402
main.Base.metadata.create_all(bind=main.engine); main.send_email=lambda *a,**k: None
st=int(time.time()); db=main.SessionLocal(); P=F=0
def ck(n,ok,d=""):
    global P,F
    if ok: P+=1; print("  PASS ",n,("("+d+")") if d else "")
    else:  F+=1; print("  FAIL ",n,d)
sc=main.School(name='BD%d'%st); db.add(sc); db.commit(); db.refresh(sc)
hc=main._gen_head_code(db)
db.add(main.TeacherCode(code=hc,school=sc.name,school_id=sc.id,is_head=True,active=True)); db.commit()
adm=TestClient(main.app); em='bd%d@example.com'%st
adm.post('/api/auth/signup',json={'name':'Admin','email':em,'password':'BdPass123!'})
u=db.query(main.User).filter(main.User.email==em).first(); u.dob=dt.date(1990,1,1); db.commit()
adm.post('/api/class/join',json={'code':hc})
CID=adm.post('/api/teacher/class',json={'name':'6-B %d'%st}).json()['id']
adm.post('/api/teacher/class/%d/roster'%CID,json={'names':'Nita S'})
# The office creates the class and the subject; the TEACHER of that subject is
# who files a lesson into it. The school admin used to do both, which is why
# the two dashboards looked the same.
tch,_uid,_code,_sid = teacher_on(main, adm, CID, 'Science', 'Board Teacher')
main._CODE_TRIES.clear(); main._CODE_FAILS.clear()
code=db.get(main.Klass,CID).join_code
kid=TestClient(main.app)
free=kid.post('/api/craxlearn/code',json={'code':code}).json()['names']
kid.post('/api/craxlearn/claim',json={'code':code,'roster_id':free[0]['id']})

lesson={'title':'Refraction of light','takeaway':'Light bends at a boundary.',
        'steps':[{'t':'Light slows in glass.\nIt bends towards the normal.','where':'','code':'',
                  'sketch':{'kind':'plot','caption':'Angle in against angle out','series':[{'label':'glass','points':[[0,0],[10,6],[20,13],[30,19]]}]}},
                 {'t':'The angle depends on the two materials.','where':'','code':''}]}
print("\nfiling what was taught")
r=tch.post('/api/craxlearn/board/save',json={'class_id':CID,'topic':'refraction',
    'title':'Refraction of light','subject':'Science','note':'What we did Tuesday','lesson':lesson})
ck('a taught lesson files into the class', r.status_code==200, r.text[:70])
mats=adm.get('/api/class/%d/materials'%CID).json()['materials']
ck('it appears in study material', len(mats)==1, str(len(mats)))
m=mats[0]
ck('under the subject it was taught as', m.get('subject')=='Science', str(m.get('subject')))
ck('carrying the words', 'Light slows in glass' in (m.get('body') or ''), (m.get('body') or '')[:40])
ck('and its figures', len(m.get('figures') or [])>=1, str(len(m.get('figures') or [])))
print("\nthe class can read it")
kmats=kid.get('/api/class/%d/materials'%CID).json()['materials']
ck('a child in the class sees it', len(kmats)==1)
ck('it is not homework', len(adm.get('/api/teacher/class/%d'%CID).json().get('assignments',[]))==0,
   'nobody hands a lesson in')
print("\nnot for other classes")
OTHER=adm.post('/api/teacher/class',json={'name':'6-C %d'%st}).json()['id']
ck('another class does not get it', len(adm.get('/api/class/%d/materials'%OTHER).json()['materials'])==0)
r=kid.post('/api/craxlearn/board/save',json={'class_id':CID,'topic':'x','title':'x','subject':'y','note':'','lesson':lesson})
ck('a learner cannot file into their own class', r.status_code in (403,404), f'got {r.status_code}')
print(f"\nPASSED {P}   FAILED {F}")
sys.exit(1 if F else 0)
