from datetime import date, timedelta

from werkzeug.security import generate_password_hash

from app import app, commit, execute, initialize_database


NAMES = [
    "Aarav Kulkarni", "Ananya Deshmukh", "Rohan Patil", "Isha Joshi", "Vihaan Shah",
    "Sana Khan", "Aditya More", "Mira Nair", "Arjun Mehta", "Neha Pawar",
    "Kabir Chavan", "Diya Iyer", "Omkar Jadhav", "Sara Shaikh", "Ishaan Rao",
    "Aditi Kulkarni", "Reyansh Patil", "Riya Desai", "Atharv Shinde", "Myra Kapoor",
    "Vedant Joshi", "Tanvi Bhosale", "Krish Naik", "Anvi Sane", "Yash Thakur",
    "Nisha Reddy", "Siddharth More", "Ayesha Khan", "Pranav Gokhale", "Tara Menon",
]
TECHNOLOGIES = ["Java", "Python", "Java", "Data Analytics", "Testing", "Python"]
SKILLS = [
    ("Java", "Programming"),
    ("Python", "Programming"),
    ("SQL", "Database"),
    ("JavaScript", "Programming"),
    ("React", "Frontend"),
    ("Flask", "Backend"),
    ("Manual Testing", "Testing"),
    ("Testing", "Testing"),
    ("Power BI", "Analytics"),
    ("Data Analytics", "Analytics"),
    ("AWS", "Cloud"),
    ("Git", "Tools"),
]
COMPANIES = [
    ("Infosys", "IT Services", "Pune", "MNC"),
    ("Tata Consultancy Services", "IT Services", "Mumbai", "MNC"),
    ("Persistent Systems", "Software", "Pune", "MID_SIZE"),
    ("Accenture", "Consulting", "Pune", "MNC"),
    ("Tech Mahindra", "IT Services", "Pune", "MNC"),
    ("Zensar Technologies", "Software", "Pune", "MID_SIZE"),
    ("QuickHeal", "Cybersecurity", "Pune", "MID_SIZE"),
    ("BrightPath Labs", "Product Technology", "Bengaluru", "STARTUP"),
]
JOB_TITLES = [
    "Associate Java Developer", "Python Backend Engineer", "Graduate Engineer Trainee",
    "QA Automation Analyst", "Data Analyst", "Frontend Developer",
    "Cloud Support Associate", "Software Engineer", "Business Analyst",
    "Junior Full Stack Developer", "Application Support Engineer", "Product Analyst",
]


def seed_demo_data():
    if execute("SELECT COUNT(*) AS total FROM roles")[0][0]["total"]:
        print("Database already contains data; no sample records were changed.")
        return

    for role_code, role_name in (
        ("ADMIN", "Administrator"),
        ("RECRUITER", "Recruiter"),
        ("PLACEMENT_OFFICER", "Placement Officer"),
    ):
        execute("INSERT INTO roles (role_code, role_name) VALUES (?, ?)", (role_code, role_name))
    role_ids = {
        row["role_code"]: row["role_id"]
        for row in execute("SELECT role_id, role_code FROM roles")[0]
    }

    demo_users = [
        ("admin@demo.com", "Aarohi Admin", "ADMIN"),
        ("recruiter@demo.com", "Kavya Recruiter", "RECRUITER"),
        ("rohan.recruiter@demo.com", "Rohan Desai", "RECRUITER"),
        ("placement@demo.com", "Neel Placement", "PLACEMENT_OFFICER"),
        ("meera.placement@demo.com", "Meera Iyer", "PLACEMENT_OFFICER"),
    ]
    for email, full_name, role in demo_users:
        execute(
            """INSERT INTO users (username, password_hash, full_name, email, role_id)
               VALUES (?, ?, ?, ?, ?)""",
            (email, generate_password_hash("demo123"), full_name, email, role_ids[role]),
        )
    recruiter_id = execute(
        "SELECT user_id FROM users WHERE email = ?", ("recruiter@demo.com",)
    )[0][0]["user_id"]

    for skill_name, category in SKILLS:
        execute("INSERT INTO skills (skill_name, category) VALUES (?, ?)", (skill_name, category))
    skill_ids = {
        row["skill_name"]: row["skill_id"]
        for row in execute("SELECT skill_id, skill_name FROM skills")[0]
    }

    for index, (name, industry, location, company_type) in enumerate(COMPANIES, 1):
        slug = name.lower().replace(" ", "").replace(".", "")
        execute(
            """INSERT INTO companies
               (company_code, company_name, industry, website, location, company_type,
                hr_name, hr_email, hr_mobile)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                f"COM-{index:03d}",
                name,
                industry,
                f"https://www.{slug}.example",
                location,
                company_type,
                f"{['Aditi', 'Rahul', 'Meera', 'Karan'][index % 4]} Shah",
                f"talent{index}@{slug}.example",
                f"98765432{index:02d}",
            ),
        )
    company_ids = [row["company_id"] for row in execute("SELECT company_id FROM companies ORDER BY company_id")[0]]

    qualifications = ["BE", "BTech", "MCA", "BSc", "BE", "BTech"]
    locations = ["Pune", "Mumbai", "Nashik", "Nagpur", "Bengaluru"]
    for index, name in enumerate(NAMES, 1):
        technology = TECHNOLOGIES[(index - 1) % len(TECHNOLOGIES)]
        email = f"candidate{index:02d}@demo.com"
        mobile = f"980000{index:04d}"
        qualification = qualifications[(index - 1) % len(qualifications)]
        passing_year = 2024 + index % 3
        percentage = round(58 + (index * 7 % 39), 2)
        backlog_count = 1 if index % 9 == 0 else 0
        code = f"CAN-{date.today().year}-{index:04d}"
        execute(
            """INSERT INTO candidates
               (candidate_code, full_name, email, mobile, gender, qualification, college,
                university, passing_year, percentage, cgpa, backlog_count, primary_technology,
                current_location, preferred_location, profile_status, placement_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                code,
                name,
                email,
                mobile,
                "Female" if index % 2 == 0 else "Male",
                qualification,
                f"{['Pune', 'Mumbai', 'Nashik'][index % 3]} Institute of Technology",
                f"{['Savitribai Phule Pune University', 'Mumbai University'][index % 2]}",
                passing_year,
                percentage,
                round(percentage / 10, 2),
                backlog_count,
                technology,
                locations[index % len(locations)],
                locations[(index + 2) % len(locations)],
                "ON_HOLD" if index in {14, 28} else "ACTIVE",
                "NOT_PLACED",
            ),
        )
        candidate_id = execute("SELECT candidate_id FROM candidates WHERE candidate_code = ?", (code,))[0][0]["candidate_id"]
        chosen_skills = list(dict.fromkeys([technology, "SQL", "Git", SKILLS[index % len(SKILLS)][0]]))
        for skill in chosen_skills:
            execute(
                """INSERT INTO candidate_skills
                   (candidate_id, skill_id, proficiency_level, years_experience, is_primary)
                   VALUES (?, ?, ?, ?, ?)""",
                (candidate_id, skill_ids[skill], "INTERMEDIATE", 0, int(skill == technology)),
            )

    today = date.today()
    for index, title in enumerate(JOB_TITLES, 1):
        company_id = company_ids[(index - 1) % len(company_ids)]
        posted = today - timedelta(days=4 + index * 3)
        deadline = today + timedelta(days=12 + index * 2)
        status = "CLOSED" if index in {10, 11} else ("DRAFT" if index == 12 else "OPEN")
        code = f"JOB-{date.today().year}-{index:03d}"
        technology = TECHNOLOGIES[(index - 1) % len(TECHNOLOGIES)]
        execute(
            """INSERT INTO jobs
               (job_code, company_id, job_title, employment_type, location, openings,
                min_package_lpa, max_package_lpa, min_percentage, min_passing_year,
                max_passing_year, max_backlogs, experience_min_years, qualification_rule,
                posted_date, application_deadline, status, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                code,
                company_id,
                title,
                "INTERNSHIP" if index == 7 else "FULL_TIME",
                locations[index % len(locations)],
                5 + index * 2,
                3.5 + index * 0.1,
                6.0 + index * 0.2,
                60,
                2024,
                2026,
                0,
                0,
                None,
                posted.isoformat(),
                deadline.isoformat(),
                status,
                recruiter_id,
            ),
        )
        job_id = execute("SELECT job_id FROM jobs WHERE job_code = ?", (code,))[0][0]["job_id"]
        execute(
            """INSERT INTO job_skills (job_id, skill_id, minimum_level, mandatory_flag, is_primary)
               VALUES (?, ?, 'INTERMEDIATE', 1, 1)""",
            (job_id, skill_ids[technology]),
        )

    candidate_ids = [row["candidate_id"] for row in execute("SELECT candidate_id FROM candidates ORDER BY candidate_id")[0]]
    job_rows = execute("SELECT job_id, status FROM jobs ORDER BY job_id")[0]
    applications = []
    status_cycle = [
        ("JOINED", "ELIGIBLE"),
        ("OFFERED", "ELIGIBLE"),
        ("SELECTED", "ELIGIBLE"),
        ("INTERVIEWED", "ELIGIBLE"),
        ("INTERVIEW_SCHEDULED", "ELIGIBLE"),
        ("SHORTLISTED", "ELIGIBLE"),
        ("ELIGIBILITY_VERIFIED", "ELIGIBLE"),
        ("APPLIED", "NOT_ELIGIBLE"),
        ("REJECTED", "ELIGIBLE"),
    ]
    for index in range(45):
        candidate_id = candidate_ids[index % len(candidate_ids)]
        job = job_rows[(index * 3) % len(job_rows)]
        status, eligibility = status_cycle[index % len(status_cycle)]
        if job["status"] != "OPEN":
            job = next(item for item in job_rows if item["status"] == "OPEN")
        code = f"APP-{date.today().year}-{index + 1:04d}"
        reason = "Meets the job eligibility criteria." if eligibility == "ELIGIBLE" else "Percentage is below the job cutoff."
        execute(
            """INSERT INTO applications
               (application_code, candidate_id, job_id, eligibility_status, eligibility_reason,
                application_status, source, assigned_recruiter_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (code, candidate_id, job["job_id"], eligibility, reason, status, ["Portal", "Recruiter", "Referral"][index % 3], recruiter_id),
        )
        applications.append(
            execute("SELECT application_id, candidate_id, job_id, application_status FROM applications WHERE application_code = ?", (code,))[0][0]
        )
        app = applications[-1]
        execute(
            """INSERT INTO application_history
               (application_id, old_status, new_status, remarks, changed_by)
               VALUES (?, NULL, ?, 'Application created from demo data.', ?)""",
            (app["application_id"], status, recruiter_id),
        )

    offer_ids = []
    offer_candidates = [app for app in applications if app["application_status"] in {"JOINED", "OFFERED"}][:8]
    for index, application in enumerate(offer_candidates, 1):
        job = execute("SELECT job_title FROM jobs WHERE job_id = ?", (application["job_id"],))[0][0]
        status = "ACCEPTED" if index <= 5 else "OFFERED"
        code = f"OFR-{date.today().year}-{index:04d}"
        expected = (today + timedelta(days=20 + index)).isoformat()
        execute(
            """INSERT INTO offers
               (offer_code, application_id, designation, offered_package_lpa, offer_date,
                expected_joining_date, offer_status)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (code, application["application_id"], job["job_title"], 4.5 + index * 0.2, today.isoformat(), expected, status),
        )
        offer_ids.append(execute("SELECT offer_id FROM offers WHERE offer_code = ?", (code,))[0][0]["offer_id"])
    for index, offer_id in enumerate(offer_ids[:5]):
        offer = execute(
            """SELECT o.*, a.candidate_id, a.job_id, j.company_id
               FROM offers o JOIN applications a ON a.application_id = o.application_id
               JOIN jobs j ON j.job_id = a.job_id WHERE o.offer_id = ?""",
            (offer_id,),
        )[0][0]
        candidate = execute("SELECT full_name FROM candidates WHERE candidate_id = ?", (offer["candidate_id"],))[0][0]
        execute(
            """INSERT INTO placements
               (candidate_id, company_id, job_id, offer_id, designation, final_package_lpa,
                expected_joining_date, actual_joining_date, joining_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'JOINED')""",
            (
                offer["candidate_id"],
                offer["company_id"],
                offer["job_id"],
                offer_id,
                offer["designation"],
                offer["offered_package_lpa"],
                offer["expected_joining_date"],
                (today - timedelta(days=5 - index)).isoformat(),
            ),
        )
        execute("UPDATE candidates SET placement_status = 'PLACED' WHERE candidate_id = ?", (offer["candidate_id"],))
        execute(
            """INSERT INTO application_history
               (application_id, old_status, new_status, remarks, changed_by)
               VALUES (?, 'OFFERED', 'JOINED', ?, ?)""",
            (offer["application_id"], f"{candidate['full_name']} joined successfully.", recruiter_id),
        )

    interviews = [app for app in applications if app["application_status"] in {"JOINED", "OFFERED", "SELECTED", "INTERVIEWED", "INTERVIEW_SCHEDULED"}][:20]
    for index, application in enumerate(interviews, 1):
        scheduled = today + timedelta(days=(index % 8) - 2)
        status = "COMPLETED" if index <= 15 else "SCHEDULED"
        interview_type = ["APTITUDE", "TECHNICAL", "MANAGERIAL", "HR"][index % 4]
        execute(
            """INSERT INTO interview_rounds
               (application_id, round_number, round_type, scheduled_date, scheduled_time,
                mode, interviewer_name, meeting_or_location, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                application["application_id"],
                1,
                interview_type,
                scheduled.isoformat(),
                f"{9 + index % 8:02d}:{(index * 5) % 60:02d}:00",
                "ONLINE" if index % 3 else "OFFLINE",
                f"{['Aditi Shah', 'Rahul Joshi', 'Meera Nair'][index % 3]}",
                "Google Meet" if index % 3 else "Pune Office",
                status,
            ),
        )
        interview_id = execute("SELECT interview_id FROM interview_rounds WHERE application_id = ?", (application["application_id"],))[0][0]["interview_id"]
        if index <= 15:
            recommendation = "SELECTED" if application["application_status"] in {"JOINED", "OFFERED", "SELECTED"} else "NEXT_ROUND"
            execute(
                """INSERT INTO interview_feedback
                   (interview_id, technical_rating, communication_rating, problem_solving_rating,
                    overall_rating, recommendation, remarks, submitted_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (interview_id, 4.2, 4.1, 4.3, 4.2, recommendation, "Strong fundamentals and clear communication.", recruiter_id),
            )

    for name in ("BE", "BTech", "MCA", "BSc", "MSc", "BCA"):
        execute("INSERT INTO qualifications (qualification_name) VALUES (?)", (name,))
    for name in ("Pune", "Mumbai", "Nashik", "Nagpur", "Bengaluru", "Hyderabad"):
        execute("INSERT INTO locations (location_name) VALUES (?)", (name,))

    execute(
        """INSERT INTO activity_logs (user_id, module_name, action_name, record_id, description)
           VALUES (?, 'System', 'Demo data loaded', 'seed', 'Recruitment workspace demo data initialized.')""",
        (recruiter_id,),
    )
    commit()
    print("Demo data loaded: 30 candidates, 8 companies, 12 jobs, 45 applications, 20 interviews.")


if __name__ == "__main__":
    initialize_database(app)
    with app.app_context():
        seed_demo_data()
    print("Demo sign-in: use each account's own email and password.")
