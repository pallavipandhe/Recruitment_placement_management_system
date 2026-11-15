PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS roles (
 role_id INTEGER PRIMARY KEY AUTOINCREMENT, role_code TEXT NOT NULL UNIQUE,
 role_name TEXT NOT NULL, is_active INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS users (
 user_id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE,
 password_hash TEXT NOT NULL, full_name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
 role_id INTEGER NOT NULL REFERENCES roles(role_id),
 status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','INACTIVE','LOCKED')),
 last_login_at TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS candidates (
 candidate_id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_code TEXT NOT NULL UNIQUE,
 full_name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, mobile TEXT NOT NULL UNIQUE,
 date_of_birth TEXT, gender TEXT, qualification TEXT NOT NULL, college TEXT,
 university TEXT, passing_year INTEGER NOT NULL,
 percentage REAL CHECK(percentage IS NULL OR percentage BETWEEN 0 AND 100),
 cgpa REAL, backlog_count INTEGER NOT NULL DEFAULT 0 CHECK(backlog_count >= 0),
 created_by INTEGER REFERENCES users(user_id),
 primary_technology TEXT, current_location TEXT, preferred_location TEXT,
 profile_status TEXT NOT NULL DEFAULT 'ACTIVE'
  CHECK(profile_status IN ('ACTIVE','INACTIVE','ON_HOLD','BLACKLISTED')),
 placement_status TEXT NOT NULL DEFAULT 'NOT_PLACED'
  CHECK(placement_status IN ('NOT_PLACED','PLACED')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS skills (
 skill_id INTEGER PRIMARY KEY AUTOINCREMENT, skill_name TEXT NOT NULL UNIQUE,
 category TEXT, is_active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS candidate_skills (
 candidate_skill_id INTEGER PRIMARY KEY AUTOINCREMENT,
 candidate_id INTEGER NOT NULL REFERENCES candidates(candidate_id),
 skill_id INTEGER NOT NULL REFERENCES skills(skill_id), proficiency_level TEXT,
 years_experience REAL NOT NULL DEFAULT 0, is_primary INTEGER NOT NULL DEFAULT 0,
 UNIQUE(candidate_id, skill_id)
);
CREATE TABLE IF NOT EXISTS companies (
 company_id INTEGER PRIMARY KEY AUTOINCREMENT, company_code TEXT NOT NULL UNIQUE,
 company_name TEXT NOT NULL, industry TEXT, website TEXT, location TEXT,
 company_type TEXT, hr_name TEXT, hr_email TEXT, hr_mobile TEXT,
 status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','INACTIVE')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS jobs (
 job_id INTEGER PRIMARY KEY AUTOINCREMENT, job_code TEXT NOT NULL UNIQUE,
 company_id INTEGER NOT NULL REFERENCES companies(company_id),
 job_title TEXT NOT NULL, employment_type TEXT NOT NULL DEFAULT 'FULL_TIME',
 location TEXT NOT NULL, openings INTEGER NOT NULL CHECK(openings > 0),
 min_package_lpa REAL, max_package_lpa REAL,
 min_percentage REAL CHECK(min_percentage IS NULL OR min_percentage BETWEEN 0 AND 100),
 min_passing_year INTEGER, max_passing_year INTEGER,
 max_backlogs INTEGER NOT NULL DEFAULT 0 CHECK(max_backlogs >= 0),
 experience_min_years REAL NOT NULL DEFAULT 0, qualification_rule TEXT,
 posted_date TEXT NOT NULL, application_deadline TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'OPEN' CHECK(status IN ('DRAFT','OPEN','CLOSED','CANCELLED')),
 created_by INTEGER REFERENCES users(user_id), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CHECK(min_package_lpa IS NULL OR max_package_lpa IS NULL OR min_package_lpa <= max_package_lpa),
 CHECK(application_deadline >= posted_date),
 CHECK(min_passing_year IS NULL OR max_passing_year IS NULL OR min_passing_year <= max_passing_year)
);
CREATE TABLE IF NOT EXISTS job_skills (
 job_skill_id INTEGER PRIMARY KEY AUTOINCREMENT,
 job_id INTEGER NOT NULL REFERENCES jobs(job_id),
 skill_id INTEGER NOT NULL REFERENCES skills(skill_id),
 minimum_level TEXT, mandatory_flag INTEGER NOT NULL DEFAULT 1,
 is_primary INTEGER NOT NULL DEFAULT 0,
 UNIQUE(job_id, skill_id)
);
CREATE TABLE IF NOT EXISTS applications (
 application_id INTEGER PRIMARY KEY AUTOINCREMENT, application_code TEXT NOT NULL UNIQUE,
 candidate_id INTEGER NOT NULL REFERENCES candidates(candidate_id),
 job_id INTEGER NOT NULL REFERENCES jobs(job_id),
 applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 eligibility_status TEXT NOT NULL DEFAULT 'PENDING'
  CHECK(eligibility_status IN ('PENDING','ELIGIBLE','NOT_ELIGIBLE')),
 eligibility_reason TEXT, application_status TEXT NOT NULL DEFAULT 'APPLIED',
 source TEXT, assigned_recruiter_id INTEGER REFERENCES users(user_id),
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(candidate_id, job_id)
);
CREATE TABLE IF NOT EXISTS application_history (
 history_id INTEGER PRIMARY KEY AUTOINCREMENT,
 application_id INTEGER NOT NULL REFERENCES applications(application_id),
 old_status TEXT, new_status TEXT NOT NULL, remarks TEXT,
 changed_by INTEGER REFERENCES users(user_id),
 changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS interview_rounds (
 interview_id INTEGER PRIMARY KEY AUTOINCREMENT,
 application_id INTEGER NOT NULL REFERENCES applications(application_id),
 round_number INTEGER NOT NULL CHECK(round_number > 0), round_type TEXT NOT NULL,
 scheduled_date TEXT NOT NULL, scheduled_time TEXT,
 mode TEXT NOT NULL CHECK(mode IN ('ONLINE','OFFLINE','TELEPHONIC')),
 interviewer_name TEXT, meeting_or_location TEXT,
 status TEXT NOT NULL DEFAULT 'SCHEDULED'
  CHECK(status IN ('SCHEDULED','COMPLETED','RESCHEDULED','CANCELLED','NO_SHOW')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(application_id, round_number)
);
CREATE TABLE IF NOT EXISTS interview_feedback (
 feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
 interview_id INTEGER NOT NULL UNIQUE REFERENCES interview_rounds(interview_id),
 technical_rating REAL CHECK(technical_rating IS NULL OR technical_rating BETWEEN 0 AND 5),
 communication_rating REAL CHECK(communication_rating IS NULL OR communication_rating BETWEEN 0 AND 5),
 problem_solving_rating REAL CHECK(problem_solving_rating IS NULL OR problem_solving_rating BETWEEN 0 AND 5),
 overall_rating REAL CHECK(overall_rating IS NULL OR overall_rating BETWEEN 0 AND 5),
 recommendation TEXT NOT NULL CHECK(recommendation IN ('NEXT_ROUND','SELECTED','REJECTED','ON_HOLD')),
 remarks TEXT, submitted_by INTEGER REFERENCES users(user_id),
 submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS offers (
 offer_id INTEGER PRIMARY KEY AUTOINCREMENT, offer_code TEXT NOT NULL UNIQUE,
 application_id INTEGER NOT NULL UNIQUE REFERENCES applications(application_id),
 designation TEXT NOT NULL, offered_package_lpa REAL NOT NULL CHECK(offered_package_lpa > 0),
 offer_date TEXT NOT NULL, expected_joining_date TEXT,
 offer_status TEXT NOT NULL DEFAULT 'OFFERED'
  CHECK(offer_status IN ('OFFERED','ACCEPTED','REJECTED','EXPIRED','WITHDRAWN')),
 remarks TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS placements (
 placement_id INTEGER PRIMARY KEY AUTOINCREMENT,
 candidate_id INTEGER NOT NULL REFERENCES candidates(candidate_id),
 company_id INTEGER NOT NULL REFERENCES companies(company_id),
 job_id INTEGER NOT NULL REFERENCES jobs(job_id),
 offer_id INTEGER NOT NULL UNIQUE REFERENCES offers(offer_id),
 designation TEXT NOT NULL, final_package_lpa REAL NOT NULL CHECK(final_package_lpa > 0),
 expected_joining_date TEXT, actual_joining_date TEXT,
 joining_status TEXT NOT NULL DEFAULT 'PENDING'
  CHECK(joining_status IN ('PENDING','JOINED','NOT_JOINED','DEFERRED','NO_SHOW')),
 placement_status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(placement_status IN ('ACTIVE','CANCELLED')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS activity_logs (
 log_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER REFERENCES users(user_id),
 module_name TEXT NOT NULL, action_name TEXT NOT NULL, record_id TEXT,
 description TEXT, logged_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS qualifications (
 qualification_id INTEGER PRIMARY KEY AUTOINCREMENT,
 qualification_name TEXT NOT NULL UNIQUE, is_active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS locations (
 location_id INTEGER PRIMARY KEY AUTOINCREMENT,
 location_name TEXT NOT NULL UNIQUE, is_active INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_candidates_technology ON candidates(primary_technology);
CREATE INDEX IF NOT EXISTS idx_candidates_passing_year ON candidates(passing_year);
CREATE INDEX IF NOT EXISTS idx_candidates_placement_status ON candidates(placement_status);
CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(company_name);
CREATE INDEX IF NOT EXISTS idx_companies_status ON companies(status);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_deadline ON jobs(application_deadline);
CREATE INDEX IF NOT EXISTS idx_jobs_location ON jobs(location);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(application_status);
CREATE INDEX IF NOT EXISTS idx_applications_recruiter ON applications(assigned_recruiter_id);
CREATE INDEX IF NOT EXISTS idx_history_application ON application_history(application_id);
CREATE INDEX IF NOT EXISTS idx_history_changed_at ON application_history(changed_at);
CREATE INDEX IF NOT EXISTS idx_interviews_date ON interview_rounds(scheduled_date);
CREATE INDEX IF NOT EXISTS idx_interviews_status ON interview_rounds(status);
CREATE INDEX IF NOT EXISTS idx_feedback_recommendation ON interview_feedback(recommendation);
CREATE INDEX IF NOT EXISTS idx_offers_status ON offers(offer_status);
CREATE INDEX IF NOT EXISTS idx_placements_candidate ON placements(candidate_id);
CREATE INDEX IF NOT EXISTS idx_placements_company ON placements(company_id);
CREATE INDEX IF NOT EXISTS idx_placements_joining ON placements(joining_status);
CREATE INDEX IF NOT EXISTS idx_activity_user ON activity_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_activity_module ON activity_logs(module_name);
CREATE INDEX IF NOT EXISTS idx_activity_logged_at ON activity_logs(logged_at);
