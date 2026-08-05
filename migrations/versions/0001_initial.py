"""Initial schema.

Frozen Postgres DDL for the 38 tables as they stood when this project moved
off boot-time schema reconciliation. Generated from the SQLAlchemy models
once, then FROZEN — it is never regenerated.

Why frozen literal SQL rather than Base.metadata.create_all(op.get_bind()):
create_all builds whatever the models happen to say on the day it runs, so
this revision would quietly change meaning every time a model changed, and
migration history would stop being reproducible. A migration must mean the
same thing in a year as it does today. These statements are what the schema
WAS at this revision, and they stay that way.

Later revisions are written explicitly. Nothing reconciles a schema at boot
any more: main.py verifies the database is at head and refuses to start
otherwise.

Revision ID: 0001_initial
Revises:
"""
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

# Sorted by foreign-key dependency at generation time.
STATEMENTS = [
    'CREATE TABLE ask_cache (\n\tid SERIAL NOT NULL, \n\tqkey VARCHAR(500) NOT NULL, \n\tscope VARCHAR(40), \n\tsubject VARCHAR(60), \n\tlevel VARCHAR(60), \n\tquestion TEXT, \n\tlesson TEXT, \n\thits INTEGER, \n\tcreated_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id)\n)',
    'CREATE UNIQUE INDEX ix_ask_cache_qkey ON ask_cache (qkey)',
    'CREATE INDEX ix_ask_cache_scope ON ask_cache (scope)',
    'CREATE TABLE jobs (\n\tid SERIAL NOT NULL, \n\tsource VARCHAR(40) NOT NULL, \n\texternal_id VARCHAR(200) NOT NULL, \n\ttitle VARCHAR(300), \n\tcompany VARCHAR(200), \n\tcountry VARCHAR(80), \n\tlocation VARCHAR(200), \n\tremote BOOLEAN, \n\tcategory VARCHAR(30), \n\tjob_type VARCHAR(20), \n\tsalary VARCHAR(120), \n\tmin_years INTEGER, \n\tdescription TEXT, \n\tengagement VARCHAR(10), \n\tvisa VARCHAR(20), \n\turl TEXT, \n\ttext TEXT, \n\tskills TEXT, \n\treq_skills TEXT, \n\tposted_at TIMESTAMP WITH TIME ZONE, \n\tfirst_seen TIMESTAMP WITH TIME ZONE, \n\tlast_seen TIMESTAMP WITH TIME ZONE, \n\tis_open BOOLEAN, \n\tclosed_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_job_src UNIQUE (source, external_id)\n)',
    'CREATE INDEX ix_jobs_category ON jobs (category)',
    'CREATE INDEX ix_jobs_company ON jobs (company)',
    'CREATE INDEX ix_jobs_country ON jobs (country)',
    'CREATE INDEX ix_jobs_engagement ON jobs (engagement)',
    'CREATE INDEX ix_jobs_first_seen ON jobs (first_seen)',
    'CREATE INDEX ix_jobs_is_open ON jobs (is_open)',
    'CREATE INDEX ix_jobs_job_type ON jobs (job_type)',
    'CREATE INDEX ix_jobs_last_seen ON jobs (last_seen)',
    'CREATE INDEX ix_jobs_source ON jobs (source)',
    'CREATE INDEX ix_jobs_visa ON jobs (visa)',
    'CREATE TABLE school_notices (\n\tid SERIAL NOT NULL, \n\tschool_id INTEGER, \n\tauthor_id INTEGER, \n\ttitle VARCHAR(240) NOT NULL, \n\tbody TEXT, \n\tfile_data TEXT, \n\tfile_name VARCHAR(160), \n\tmime VARCHAR(80), \n\tsize INTEGER, \n\taudience VARCHAR(16), \n\taudience_ids TEXT, \n\tclass_id INTEGER, \n\turgent BOOLEAN, \n\tstarts_on VARCHAR(20), \n\tends_on VARCHAR(20), \n\tcreated_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id)\n)',
    'CREATE INDEX ix_school_notices_class_id ON school_notices (class_id)',
    'CREATE INDEX ix_school_notices_created_at ON school_notices (created_at)',
    'CREATE INDEX ix_school_notices_school_id ON school_notices (school_id)',
    'CREATE TABLE schools (\n\tid SERIAL NOT NULL, \n\tname VARCHAR(200) NOT NULL, \n\tcity VARCHAR(120), \n\tcountry VARCHAR(120), \n\tproduct VARCHAR(16), \n\tcreated_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id)\n)',
    'CREATE TABLE sys_counters (\n\tk VARCHAR(60) NOT NULL, \n\tv INTEGER, \n\tPRIMARY KEY (k)\n)',
    'CREATE TABLE teacher_codes (\n\tid SERIAL NOT NULL, \n\tcode VARCHAR(40) NOT NULL, \n\tschool VARCHAR(160), \n\tschool_id INTEGER, \n\tis_head BOOLEAN, \n\tactive BOOLEAN NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id)\n)',
    'CREATE UNIQUE INDEX ix_teacher_codes_code ON teacher_codes (code)',
    'CREATE TABLE teacher_requests (\n\tid SERIAL NOT NULL, \n\tschool_id INTEGER, \n\tclass_id INTEGER, \n\tteacher_id INTEGER NOT NULL, \n\tmessage TEXT, \n\tstatus VARCHAR(12), \n\tcreated_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id)\n)',
    'CREATE INDEX ix_teacher_requests_school_id ON teacher_requests (school_id)',
    'CREATE TABLE tracks (\n\tid SERIAL NOT NULL, \n\tslug VARCHAR(60) NOT NULL, \n\ticon VARCHAR(16), \n\tname VARCHAR(160) NOT NULL, \n\taudience VARCHAR(20), \n\tlevel VARCHAR(80), \n\tcolor VARCHAR(20), \n\tweeks INTEGER, \n\tlang VARCHAR(40), \n\t"desc" TEXT, \n\toutcomes TEXT, \n\tquiz TEXT, \n\tposition INTEGER, \n\tpublished BOOLEAN NOT NULL, \n\tPRIMARY KEY (id)\n)',
    'CREATE UNIQUE INDEX ix_tracks_slug ON tracks (slug)',
    'CREATE TABLE users (\n\tid SERIAL NOT NULL, \n\temail VARCHAR(255) NOT NULL, \n\tname VARCHAR(120) NOT NULL, \n\tpassword_hash VARCHAR(255) NOT NULL, \n\tis_admin BOOLEAN NOT NULL, \n\tis_active BOOLEAN NOT NULL, \n\tcollege VARCHAR(160), \n\tcity VARCHAR(120), \n\tdegree VARCHAR(120), \n\tpath VARCHAR(40), \n\tcreated_at TIMESTAMP WITH TIME ZONE, \n\tlast_seen TIMESTAMP WITH TIME ZONE, \n\tsession_token VARCHAR(400), \n\tsession_seen_at TIMESTAMP WITH TIME ZONE, \n\tplan VARCHAR(20), \n\tplan_provider VARCHAR(20), \n\topen_to_work BOOLEAN, \n\tdob DATE, \n\tkind VARCHAR(16), \n\temployer_status VARCHAR(12), \n\temployer_company VARCHAR(200), \n\temployer_site VARCHAR(300), \n\topen_to_work_at TIMESTAMP WITH TIME ZONE, \n\tplan_ref VARCHAR(120), \n\tplan_expires TIMESTAMP WITH TIME ZONE, \n\tplan_started TIMESTAMP WITH TIME ZONE, \n\tplan_cancelled_at TIMESTAMP WITH TIME ZONE, \n\ttotp_secret VARCHAR(64), \n\ttotp_enabled BOOLEAN NOT NULL, \n\ttotp_backup TEXT, \n\temail_verified BOOLEAN NOT NULL, \n\tverified_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id)\n)',
    'CREATE UNIQUE INDEX ix_users_email ON users (email)',
    'CREATE INDEX ix_users_plan ON users (plan)',
    'CREATE TABLE attendance (\n\tid SERIAL NOT NULL, \n\tschool_id INTEGER, \n\tclass_id INTEGER, \n\tuser_id INTEGER NOT NULL, \n\tday VARCHAR(20) NOT NULL, \n\tpresent BOOLEAN, \n\tnote VARCHAR(200), \n\tmarked_by INTEGER, \n\tcreated_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_att_day UNIQUE (user_id, day), \n\tFOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE\n)',
    'CREATE INDEX ix_attendance_class_id ON attendance (class_id)',
    'CREATE INDEX ix_attendance_day ON attendance (day)',
    'CREATE INDEX ix_attendance_school_id ON attendance (school_id)',
    'CREATE INDEX ix_attendance_user_id ON attendance (user_id)',
    'CREATE TABLE classes (\n\tid SERIAL NOT NULL, \n\tname VARCHAR(160) NOT NULL, \n\tjoin_code VARCHAR(16) NOT NULL, \n\tteacher_id INTEGER NOT NULL, \n\tschool VARCHAR(160), \n\tschool_id INTEGER, \n\tschedule TEXT, \n\tarchived_at TIMESTAMP WITH TIME ZONE, \n\tcreated_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(teacher_id) REFERENCES users (id) ON DELETE CASCADE\n)',
    'CREATE UNIQUE INDEX ix_classes_join_code ON classes (join_code)',
    'CREATE INDEX ix_classes_teacher_id ON classes (teacher_id)',
    'CREATE TABLE employer_jobs (\n\tid SERIAL NOT NULL, \n\towner_id INTEGER, \n\ttitle VARCHAR(200), \n\tcompany VARCHAR(200), \n\tlocation VARCHAR(200), \n\tengagement VARCHAR(20), \n\tjd TEXT, \n\tis_open BOOLEAN, \n\tcreated_at TIMESTAMP WITH TIME ZONE, \n\tupdated_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(owner_id) REFERENCES users (id)\n)',
    'CREATE INDEX ix_employer_jobs_owner_id ON employer_jobs (owner_id)',
    'CREATE TABLE fee_items (\n\tid SERIAL NOT NULL, \n\tschool_id INTEGER, \n\tuser_id INTEGER NOT NULL, \n\ttitle VARCHAR(240) NOT NULL, \n\tnote TEXT, \n\tamount INTEGER, \n\tpaid INTEGER, \n\tcurrency VARCHAR(8), \n\tdue_on VARCHAR(20), \n\tkind VARCHAR(12), \n\tmarked_by INTEGER, \n\tcreated_at TIMESTAMP WITH TIME ZONE, \n\tpaid_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE\n)',
    'CREATE INDEX ix_fee_items_created_at ON fee_items (created_at)',
    'CREATE INDEX ix_fee_items_school_id ON fee_items (school_id)',
    'CREATE INDEX ix_fee_items_user_id ON fee_items (user_id)',
    'CREATE TABLE job_alerts (\n\tid SERIAL NOT NULL, \n\tuser_id INTEGER, \n\tkind VARCHAR(24), \n\ticon VARCHAR(8), \n\ttext TEXT, \n\turl TEXT, \n\tseen BOOLEAN NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(user_id) REFERENCES users (id)\n)',
    'CREATE INDEX ix_job_alerts_created_at ON job_alerts (created_at)',
    'CREATE INDEX ix_job_alerts_kind ON job_alerts (kind)',
    'CREATE INDEX ix_job_alerts_user_id ON job_alerts (user_id)',
    'CREATE TABLE job_tracks (\n\tid SERIAL NOT NULL, \n\tuser_id INTEGER, \n\tjob_id INTEGER, \n\tstatus VARCHAR(20), \n\ttitle VARCHAR(300), \n\tcompany VARCHAR(200), \n\tlocation VARCHAR(200), \n\turl TEXT, \n\tscore INTEGER, \n\tnote TEXT, \n\tapplied_at TIMESTAMP WITH TIME ZONE, \n\tcreated_at TIMESTAMP WITH TIME ZONE, \n\tupdated_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(user_id) REFERENCES users (id)\n)',
    'CREATE INDEX ix_job_tracks_job_id ON job_tracks (job_id)',
    'CREATE INDEX ix_job_tracks_status ON job_tracks (status)',
    'CREATE INDEX ix_job_tracks_user_id ON job_tracks (user_id)',
    'CREATE TABLE learn_records (\n\tid SERIAL NOT NULL, \n\tuser_id INTEGER, \n\tscope VARCHAR(40), \n\tschool_id INTEGER, \n\tkind VARCHAR(12), \n\ttext VARCHAR(220), \n\tsubject VARCHAR(60), \n\tlevel VARCHAR(60), \n\tcreated_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE\n)',
    'CREATE INDEX ix_learn_records_created_at ON learn_records (created_at)',
    'CREATE INDEX ix_learn_records_school_id ON learn_records (school_id)',
    'CREATE INDEX ix_learn_records_scope ON learn_records (scope)',
    'CREATE INDEX ix_learn_records_user_id ON learn_records (user_id)',
    'CREATE TABLE lessons (\n\tid SERIAL NOT NULL, \n\tslug VARCHAR(60) NOT NULL, \n\ttrack_id INTEGER NOT NULL, \n\ttitle VARCHAR(240) NOT NULL, \n\tmins INTEGER, \n\tlang VARCHAR(10), \n\tcontent TEXT, \n\tvideos TEXT, \n\trefs TEXT, \n\tlab TEXT, \n\texercises TEXT, \n\tworksheet TEXT, \n\tposition INTEGER, \n\tpublished BOOLEAN NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(track_id) REFERENCES tracks (id) ON DELETE CASCADE\n)',
    'CREATE UNIQUE INDEX ix_lessons_slug ON lessons (slug)',
    'CREATE TABLE notes (\n\tid SERIAL NOT NULL, \n\tuser_id INTEGER NOT NULL, \n\tk VARCHAR(120) NOT NULL, \n\tv TEXT, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_user_key UNIQUE (user_id, k), \n\tFOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE\n)',
    'CREATE INDEX ix_notes_user_id ON notes (user_id)',
    'CREATE TABLE password_resets (\n\tid SERIAL NOT NULL, \n\tuser_id INTEGER, \n\ttoken_hash VARCHAR(64), \n\texpires_at TIMESTAMP WITH TIME ZONE, \n\tused_at TIMESTAMP WITH TIME ZONE, \n\tpurpose VARCHAR(20), \n\tcreated_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(user_id) REFERENCES users (id)\n)',
    'CREATE INDEX ix_password_resets_purpose ON password_resets (purpose)',
    'CREATE UNIQUE INDEX ix_password_resets_token_hash ON password_resets (token_hash)',
    'CREATE INDEX ix_password_resets_user_id ON password_resets (user_id)',
    'CREATE TABLE progress (\n\tid SERIAL NOT NULL, \n\tuser_id INTEGER NOT NULL, \n\tlesson_slug VARCHAR(60) NOT NULL, \n\tcompleted BOOLEAN NOT NULL, \n\tattempts INTEGER, \n\tcode TEXT, \n\tcompleted_at TIMESTAMP WITH TIME ZONE, \n\tupdated_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_user_lesson UNIQUE (user_id, lesson_slug), \n\tFOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE\n)',
    'CREATE INDEX ix_progress_lesson_slug ON progress (lesson_slug)',
    'CREATE INDEX ix_progress_user_id ON progress (user_id)',
    'CREATE TABLE quiz_results (\n\tid SERIAL NOT NULL, \n\tuser_id INTEGER NOT NULL, \n\ttrack_slug VARCHAR(60) NOT NULL, \n\tscore INTEGER, \n\ttotal INTEGER, \n\tpassed BOOLEAN, \n\tcreated_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE\n)',
    'CREATE INDEX ix_quiz_results_track_slug ON quiz_results (track_slug)',
    'CREATE INDEX ix_quiz_results_user_id ON quiz_results (user_id)',
    'CREATE TABLE remote_links (\n\tid SERIAL NOT NULL, \n\tcode VARCHAR(12), \n\tuser_id INTEGER, \n\tschool_id INTEGER, \n\tlabel VARCHAR(80), \n\tcreated_at TIMESTAMP WITH TIME ZONE, \n\texpires_at TIMESTAMP WITH TIME ZONE, \n\tboard_seen TIMESTAMP WITH TIME ZONE, \n\tphone_seen TIMESTAMP WITH TIME ZONE, \n\tclosed_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(user_id) REFERENCES users (id)\n)',
    'CREATE UNIQUE INDEX ix_remote_links_code ON remote_links (code)',
    'CREATE INDEX ix_remote_links_expires_at ON remote_links (expires_at)',
    'CREATE INDEX ix_remote_links_school_id ON remote_links (school_id)',
    'CREATE INDEX ix_remote_links_user_id ON remote_links (user_id)',
    'CREATE TABLE skill_unlocks (\n\tid SERIAL NOT NULL, \n\tuser_id INTEGER, \n\tlabel VARCHAR(60), \n\ttokens VARCHAR(120), \n\ttimes INTEGER, \n\tcreated_at TIMESTAMP WITH TIME ZONE, \n\tlast_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(user_id) REFERENCES users (id)\n)',
    'CREATE INDEX ix_skill_unlocks_label ON skill_unlocks (label)',
    'CREATE INDEX ix_skill_unlocks_user_id ON skill_unlocks (user_id)',
    'CREATE TABLE teacher_access (\n\tid SERIAL NOT NULL, \n\tuser_id INTEGER NOT NULL, \n\tschool VARCHAR(160), \n\tschool_id INTEGER, \n\trole VARCHAR(12), \n\tcreated_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE\n)',
    'CREATE UNIQUE INDEX ix_teacher_access_user_id ON teacher_access (user_id)',
    'CREATE TABLE assignments (\n\tid SERIAL NOT NULL, \n\tclass_id INTEGER NOT NULL, \n\tteacher_id INTEGER, \n\tsubject VARCHAR(80), \n\ttitle VARCHAR(240) NOT NULL, \n\tkind VARCHAR(12), \n\tlesson_slug VARCHAR(60), \n\tbody TEXT, \n\tpdf_data TEXT, \n\tpdf_name VARCHAR(160), \n\tdue_date VARCHAR(20), \n\tclosed_at TIMESTAMP WITH TIME ZONE, \n\tclosed_by INTEGER, \n\tboard_topic VARCHAR(200), \n\tcreated_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(class_id) REFERENCES classes (id) ON DELETE CASCADE\n)',
    'CREATE INDEX ix_assignments_class_id ON assignments (class_id)',
    'CREATE TABLE class_members (\n\tid SERIAL NOT NULL, \n\tclass_id INTEGER NOT NULL, \n\tuser_id INTEGER NOT NULL, \n\tjoined_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_class_user UNIQUE (class_id, user_id), \n\tFOREIGN KEY(class_id) REFERENCES classes (id) ON DELETE CASCADE, \n\tFOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE\n)',
    'CREATE INDEX ix_class_members_class_id ON class_members (class_id)',
    'CREATE INDEX ix_class_members_user_id ON class_members (user_id)',
    'CREATE TABLE class_posts (\n\tid SERIAL NOT NULL, \n\tclass_id INTEGER NOT NULL, \n\tuser_id INTEGER NOT NULL, \n\tparent_id INTEGER, \n\tsubject VARCHAR(80), \n\tbody TEXT NOT NULL, \n\tfrom_staff BOOLEAN, \n\tcreated_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(class_id) REFERENCES classes (id) ON DELETE CASCADE, \n\tFOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE\n)',
    'CREATE INDEX ix_class_posts_class_id ON class_posts (class_id)',
    'CREATE INDEX ix_class_posts_created_at ON class_posts (created_at)',
    'CREATE INDEX ix_class_posts_parent_id ON class_posts (parent_id)',
    'CREATE INDEX ix_class_posts_user_id ON class_posts (user_id)',
    'CREATE TABLE classroom_teachers (\n\tid SERIAL NOT NULL, \n\tclass_id INTEGER NOT NULL, \n\tteacher_id INTEGER NOT NULL, \n\tsubject VARCHAR(80), \n\tcreated_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_class_teacher UNIQUE (class_id, teacher_id), \n\tFOREIGN KEY(class_id) REFERENCES classes (id) ON DELETE CASCADE, \n\tFOREIGN KEY(teacher_id) REFERENCES users (id) ON DELETE CASCADE\n)',
    'CREATE INDEX ix_classroom_teachers_class_id ON classroom_teachers (class_id)',
    'CREATE INDEX ix_classroom_teachers_teacher_id ON classroom_teachers (teacher_id)',
    'CREATE TABLE job_invites (\n\tid SERIAL NOT NULL, \n\temployer_job_id INTEGER, \n\tuser_id INTEGER, \n\tscore INTEGER, \n\tstate VARCHAR(12), \n\tcreated_at TIMESTAMP WITH TIME ZONE, \n\tanswered_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_invite_once UNIQUE (employer_job_id, user_id), \n\tFOREIGN KEY(employer_job_id) REFERENCES employer_jobs (id), \n\tFOREIGN KEY(user_id) REFERENCES users (id)\n)',
    'CREATE INDEX ix_job_invites_created_at ON job_invites (created_at)',
    'CREATE INDEX ix_job_invites_employer_job_id ON job_invites (employer_job_id)',
    'CREATE INDEX ix_job_invites_state ON job_invites (state)',
    'CREATE INDEX ix_job_invites_user_id ON job_invites (user_id)',
    'CREATE TABLE materials (\n\tid SERIAL NOT NULL, \n\tclass_id INTEGER NOT NULL, \n\tteacher_id INTEGER, \n\tsubject VARCHAR(80), \n\ttitle VARCHAR(240) NOT NULL, \n\tnote TEXT, \n\turl TEXT, \n\tfile_data TEXT, \n\tfile_name VARCHAR(160), \n\tmime VARCHAR(80), \n\tsize INTEGER, \n\tbody TEXT, \n\tfigures TEXT, \n\tcreated_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(class_id) REFERENCES classes (id) ON DELETE CASCADE\n)',
    'CREATE INDEX ix_materials_class_id ON materials (class_id)',
    'CREATE INDEX ix_materials_created_at ON materials (created_at)',
    'CREATE TABLE remote_cmds (\n\tid SERIAL NOT NULL, \n\tlink_id INTEGER, \n\tkind VARCHAR(24), \n\tpayload TEXT, \n\tcreated_at TIMESTAMP WITH TIME ZONE, \n\ttaken_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(link_id) REFERENCES remote_links (id)\n)',
    'CREATE INDEX ix_remote_cmds_created_at ON remote_cmds (created_at)',
    'CREATE INDEX ix_remote_cmds_link_id ON remote_cmds (link_id)',
    'CREATE TABLE roster_names (\n\tid SERIAL NOT NULL, \n\tclass_id INTEGER NOT NULL, \n\tname VARCHAR(80) NOT NULL, \n\tstudent_code VARCHAR(40), \n\tclaimed_by INTEGER, \n\tclaimed_at TIMESTAMP WITH TIME ZONE, \n\tremoved_at TIMESTAMP WITH TIME ZONE, \n\tcreated_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(class_id) REFERENCES classes (id) ON DELETE CASCADE\n)',
    'CREATE INDEX ix_roster_names_claimed_by ON roster_names (claimed_by)',
    'CREATE INDEX ix_roster_names_class_id ON roster_names (class_id)',
    'CREATE INDEX ix_roster_names_student_code ON roster_names (student_code)',
    'CREATE TABLE schedule_items (\n\tid SERIAL NOT NULL, \n\tclass_id INTEGER NOT NULL, \n\tday VARCHAR(40), \n\ttext TEXT, \n\tposition INTEGER, \n\tcreated_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(class_id) REFERENCES classes (id) ON DELETE CASCADE\n)',
    'CREATE INDEX ix_schedule_items_class_id ON schedule_items (class_id)',
    'CREATE TABLE subject_slots (\n\tid SERIAL NOT NULL, \n\tclass_id INTEGER NOT NULL, \n\tsubject VARCHAR(80) NOT NULL, \n\tcode VARCHAR(16) NOT NULL, \n\tteacher_id INTEGER, \n\tstatus VARCHAR(12), \n\tcreated_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(class_id) REFERENCES classes (id) ON DELETE CASCADE\n)',
    'CREATE INDEX ix_subject_slots_class_id ON subject_slots (class_id)',
    'CREATE UNIQUE INDEX ix_subject_slots_code ON subject_slots (code)',
    'CREATE INDEX ix_subject_slots_teacher_id ON subject_slots (teacher_id)',
    'CREATE TABLE assignment_messages (\n\tid SERIAL NOT NULL, \n\tassignment_id INTEGER NOT NULL, \n\tstudent_id INTEGER NOT NULL, \n\tsender_id INTEGER NOT NULL, \n\tfrom_teacher BOOLEAN, \n\tbody TEXT, \n\tcreated_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(assignment_id) REFERENCES assignments (id) ON DELETE CASCADE\n)',
    'CREATE INDEX ix_assignment_messages_assignment_id ON assignment_messages (assignment_id)',
    'CREATE INDEX ix_assignment_messages_student_id ON assignment_messages (student_id)',
    'CREATE TABLE invite_files (\n\tid SERIAL NOT NULL, \n\tinvite_id INTEGER, \n\tfrom_employer BOOLEAN, \n\tfilename VARCHAR(200), \n\tkind VARCHAR(8), \n\tsize INTEGER, \n\tdata TEXT, \n\tcreated_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(invite_id) REFERENCES job_invites (id)\n)',
    'CREATE INDEX ix_invite_files_created_at ON invite_files (created_at)',
    'CREATE INDEX ix_invite_files_invite_id ON invite_files (invite_id)',
    'CREATE TABLE invite_messages (\n\tid SERIAL NOT NULL, \n\tinvite_id INTEGER, \n\tfrom_employer BOOLEAN, \n\tbody TEXT, \n\tkind VARCHAR(12), \n\tseen BOOLEAN NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(invite_id) REFERENCES job_invites (id)\n)',
    'CREATE INDEX ix_invite_messages_created_at ON invite_messages (created_at)',
    'CREATE INDEX ix_invite_messages_invite_id ON invite_messages (invite_id)',
    'CREATE TABLE submissions (\n\tid SERIAL NOT NULL, \n\tassignment_id INTEGER NOT NULL, \n\tuser_id INTEGER NOT NULL, \n\tresponse TEXT, \n\tfeedback TEXT, \n\treviewed_at TIMESTAMP WITH TIME ZONE, \n\treviewed_by INTEGER, \n\tcreated_at TIMESTAMP WITH TIME ZONE, \n\tupdated_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_sub_user UNIQUE (assignment_id, user_id), \n\tFOREIGN KEY(assignment_id) REFERENCES assignments (id) ON DELETE CASCADE, \n\tFOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE\n)',
    'CREATE INDEX ix_submissions_assignment_id ON submissions (assignment_id)',
    'CREATE INDEX ix_submissions_user_id ON submissions (user_id)',
]

DROPS = [
    'DROP TABLE IF EXISTS "submissions" CASCADE',
    'DROP TABLE IF EXISTS "invite_messages" CASCADE',
    'DROP TABLE IF EXISTS "invite_files" CASCADE',
    'DROP TABLE IF EXISTS "assignment_messages" CASCADE',
    'DROP TABLE IF EXISTS "subject_slots" CASCADE',
    'DROP TABLE IF EXISTS "schedule_items" CASCADE',
    'DROP TABLE IF EXISTS "roster_names" CASCADE',
    'DROP TABLE IF EXISTS "remote_cmds" CASCADE',
    'DROP TABLE IF EXISTS "materials" CASCADE',
    'DROP TABLE IF EXISTS "job_invites" CASCADE',
    'DROP TABLE IF EXISTS "classroom_teachers" CASCADE',
    'DROP TABLE IF EXISTS "class_posts" CASCADE',
    'DROP TABLE IF EXISTS "class_members" CASCADE',
    'DROP TABLE IF EXISTS "assignments" CASCADE',
    'DROP TABLE IF EXISTS "teacher_access" CASCADE',
    'DROP TABLE IF EXISTS "skill_unlocks" CASCADE',
    'DROP TABLE IF EXISTS "remote_links" CASCADE',
    'DROP TABLE IF EXISTS "quiz_results" CASCADE',
    'DROP TABLE IF EXISTS "progress" CASCADE',
    'DROP TABLE IF EXISTS "password_resets" CASCADE',
    'DROP TABLE IF EXISTS "notes" CASCADE',
    'DROP TABLE IF EXISTS "lessons" CASCADE',
    'DROP TABLE IF EXISTS "learn_records" CASCADE',
    'DROP TABLE IF EXISTS "job_tracks" CASCADE',
    'DROP TABLE IF EXISTS "job_alerts" CASCADE',
    'DROP TABLE IF EXISTS "fee_items" CASCADE',
    'DROP TABLE IF EXISTS "employer_jobs" CASCADE',
    'DROP TABLE IF EXISTS "classes" CASCADE',
    'DROP TABLE IF EXISTS "attendance" CASCADE',
    'DROP TABLE IF EXISTS "users" CASCADE',
    'DROP TABLE IF EXISTS "tracks" CASCADE',
    'DROP TABLE IF EXISTS "teacher_requests" CASCADE',
    'DROP TABLE IF EXISTS "teacher_codes" CASCADE',
    'DROP TABLE IF EXISTS "sys_counters" CASCADE',
    'DROP TABLE IF EXISTS "schools" CASCADE',
    'DROP TABLE IF EXISTS "school_notices" CASCADE',
    'DROP TABLE IF EXISTS "jobs" CASCADE',
    'DROP TABLE IF EXISTS "ask_cache" CASCADE',
]


def upgrade():
    for sql in STATEMENTS:
        op.execute(sql)


def downgrade():
    for sql in DROPS:
        op.execute(sql)
