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
   "Sign in instead &rarr;" in _idx or "Sign in instead →" in _idx,
   "a teacher with a password needs telling where it goes")
# That check used to look for the sentence "use the Sign in tab instead".
# The sentence became a link, and the only remaining copy of those words in
# the file was inside the code comment explaining WHY it became a link — so
# the assertion went on passing while testing nothing a user can see. It
# looks for the link's own text now.

# The boxes went and the sign above them stayed.
#
# "or use email" is a divider between Google and the email fields. Removing
# the fields from this tab left the divider announcing them, so the code tab
# read: Continue with Google — or use email — YOUR CODE. Both the button and
# the rule are withdrawn here, because Google on the code tab lands you in an
# account rather than in the class.
ck("the code tab shows no or-use-email rule",
   'const gon = GOOGLE_ON && which !== "join";' in _idx,
   "a divider naming fields that are not there")
ck("and neither the Google button above it",
   'if(gb) gb.style.display = gon ? "flex" : "none";' in _idx)
ck("the other two tabs still get both",
   'if(go) go.style.display = gon ? "flex" : "none";' in _idx
   and "let GOOGLE_ON = false;" in _idx)
ck("and the config reply cannot switch them back on over the code tab",
   'const on = !$("#tabJoin") || !$("#tabJoin").classList.contains("on");'
   in _idx,
   "/api/auth/config settles after the tab is chosen, so it would have "
   "re-shown them on a deep link straight to the code tab")

# One code per subject, and it does both jobs.
#
# This went back and forth. The code opens the subject on a classroom board
# AND signs in the teacher who holds it. Refusing the second half was correct
# in isolation — a code chalked up and read by a room is not a credential —
# and in practice it left a teacher with a code, no password, and no way in,
# told to use an email nobody had issued her. The cost is answered by the
# code being rotatable; the loop was not answerable at all.
ck("the heading no longer calls them board codes only",
   "Subjects &amp; their\n        codes" in _idx)
ck("the line under it says the code does both",
   "and it signs its teacher in" in _idx)
ck("and points at the way to replace one that has been up too long",
   "the\n        old one stops working at once" in _idx,
   "rotation is the whole answer to a code a room can read")
ck("each row says both ways in",
   "signs in with this code, or as " in _idx,
   "the code is the one she will use; the address is the stronger one and "
   "the only one that survives the code being rotated while she is out")
ck("and an unclaimed subject says what to do about it",
   "put a teacher on this subject and the code signs them in" in _idx)

ck("and the pupils' code says whose it is",
   "for pupils, on the Join with code tab" in _idx,
   "a class code typed into the Teacher tab is the other half of the same "
   "confusion")

print(f"\nPASSED {P}   FAILED {F}")
sys.exit(1 if F else 0)
