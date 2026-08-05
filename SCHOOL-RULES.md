# How a school is set up, and who may do what

The rule, written once so it stops being re-decided. Everything below is
either **built** — with the route that does it — or **missing**, with what is
in the way. Nothing here is aspirational; the "built" lines were checked
against the code, not remembered.

---

## 1. The chain of authority

    platform admin  →  school + admin code (10 digits)
        school admin →  teachers, classes, subjects, students
            teacher  →  their assigned subjects, in their assigned classes
                student →  their own class, its subjects, its discussions

Each level is created by the one above it. Nobody creates themselves, and no
level can grant itself the one above. A school admin cannot make themselves a
platform admin; a teacher cannot make themselves a school admin; a pupil
cannot become either.

**A class-code pupil account can never hold staff access.** It has no password
anybody holds and no address that receives — right for signing in to a lesson,
wrong for an account with a school's records behind it. Enforced in
`_grant_teacher`, which every role-granting route passes through.

---

## 2. The platform admin (you)

| Rule | State |
|---|---|
| Create a school by name | **Built** — `POST /api/admin/school` |
| Get that school's admin code back | **Built** — returned by the same call as `head_code` |
| Issue more admin codes for a school | **Built** — `POST /api/admin/school/{sid}/head-code` |
| **Several admins per school, each with a code** | **MISSING** — see gap 1 |

The admin code is **ten digits, nothing else**. Not `HEAD-ABCD`: every
character is on a numeric keypad, and the code does not announce in itself
what it unlocks.

---

## 3. The school admin

Redeems the 10-digit code once, on the same sign-in form a teacher uses.
`POST /api/class/join` — the code decides the role, not the tab you are on.

| Rule | State |
|---|---|
| Create teacher profiles (name + email → one-time password) | **Built** — `POST /api/head/staff` |
| Correct a teacher's email, or reissue their password | **Built** — `PATCH /api/head/staff/{uid}` |
| Create a class; it gets a code automatically | **Built** — `POST /api/teacher/class` |
| Create subjects in a class; each gets a teacher code | **Built** — `POST /api/head/class/{cid}/slot` |
| Assign a saved teacher to a subject in a class | **Built** — `POST /api/head/assign` |
| Add students to a class register | **Built** — `POST /api/teacher/class/{cid}/roster` |
| Rotate any code that has leaked | **Built** — `/rotate` on class and slot |
| Attendance, fees, notices | **Built** — school-admin only |

---

## 4. The codes, and what each one opens

There are exactly three, and they are all anchored to one class.

| Code | Shape | Held by | Opens |
|---|---|---|---|
| Admin code | 10 digits | one per school today | the school |
| Class code | `VP-XXXXXX` | every student in the class | that class's register |
| Subject code | `T-XXXX` | the teacher of that subject | that subject, in that class |

**One class, one student code.** Every child in the class uses the same one and
then taps their own name. The subject codes hang off the same class, which is
what links a teacher, a subject and a register together without anybody typing
a second identifier.

A claimed name **stays on the register**. Hiding it meant a child who signed
out could never get back in — the register row is the credential.

---

## 5. The board

| Rule | State |
|---|---|
| Board saves the lesson into the class **and subject** it is signed in to | **Built** — `POST /api/craxlearn/board/save`, `/board/assign` |
| Students sign in on the board with the class code, then tap their name | **Built** — `POST /api/craxlearn/code` → `/claim` |
| **Admin opens a classroom on the board with the class code** | **MISSING** — see gap 2 |
| **Teacher joins that classroom with their subject code** | **MISSING** — see gap 3 |

Today a teacher reaches the board by signing in with email and password and
then choosing the class. That works, and it is not what this rule says.

---

## 6. The teacher

Static: created once by the admin, then selected. A teacher is never created
by typing their name into a class.

| Rule | State |
|---|---|
| Holds several subjects, across several classes | **Built** |
| Sees only the classes they are assigned to | **Built** — `GET /api/teacher/classes` |
| Opens any of their pre-assigned classrooms by selecting it | **Built** |
| Posts assignments, study material and updates in their subject | **Built** |
| Cannot create classes or subjects | **Built** — those are admin-only |

---

## 7. The subject discussion

| Rule | State |
|---|---|
| Every subject has its own thread, per class | **Built** — `/api/class/{cid}/discussion?subject=` |
| Students of that class can post and reply | **Built** |
| **Only the teacher assigned to that subject sees and replies** | **Built** — `_discussion_scope` |

---

## 8. What is recalled, and by what

Everything a teacher posts is filed under **class + subject**, so a student
opening a subject sees that subject's notes, work, updates and discussion, and
nothing from another teacher's subject. Built.

---

# The four gaps

### Gap 1 — a school can only have one admin code at a time

`admin_new_head_code` deactivates every previous head code for that school
before issuing a new one:

    for old in ...is_head == True: old.active = False

So issuing a second admin their code **cancels the first admin's**. The
comment says it is so a former head cannot re-register, which is a real
concern — but it is aimed at revocation and it costs multi-admin.

**Fix:** issue codes without cancelling, and revoke one explicitly.

### Gap 2 — the board has no "open this classroom" mode for an admin

On the board the class code means *student sign-in*: it returns the register
and the child taps a name. There is no path where an admin types the class
code and the board opens that classroom ready for a teacher.

**Fix:** a mode where the class code opens the room and then waits for a
subject code, without signing anybody in as a pupil.

### Gap 3 — the board does not accept a subject code

`POST /api/craxlearn/code` looks up class codes only. A `T-XXXX` typed there
is "no class has that code". Teachers currently sign in with email and
password instead.

**Fix:** accept a subject code at the board and open that subject, in that
class, for the teacher who holds it.

### Gap 4 — CLOSED

`_discussion_scope` now answers, per class: the head and office see
everything, a child sees every subject their class is taught, a teacher sees
the subjects they hold. Reading, replying and deleting all use it. A message
with no subject is addressed to the class and stays visible to everyone who
teaches there.

Two things this got wrong first, both worth keeping written down. Restricting
subject-less messages stopped teachers posting to their own class at all —
the check fired on an empty string, which is in nobody's subject list. And
reusing the read helper to decide who may DELETE handed every pupil the power
to remove their classmates' messages, because for a child that helper
correctly answers "every subject". Reading and moderating are two questions
and they need two helpers. tests/test_subject_walls.py (22).

---

## Order to build them

~~4~~ done. Then 1, then 2 and 3 together.

Gap 4 is a privacy rule and the smallest change. Gap 1 unblocks a real school
with more than one office account. Gaps 2 and 3 are one piece of work — the
board's sign-in — and should not be split.
