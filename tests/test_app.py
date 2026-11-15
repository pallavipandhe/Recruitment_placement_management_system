import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from werkzeug.security import generate_password_hash

from app import commit, create_app, execute, initialize_database


class RecruitmentWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "test.db"
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-key",
                "DATABASE_URL": f"sqlite:///{database_path}",
            }
        )
        initialize_database(self.app)
        with self.app.app_context():
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
            for email, name, role_code in (
                ("recruiter@test.com", "Test Recruiter", "RECRUITER"),
                ("another-recruiter@test.com", "Another Recruiter", "RECRUITER"),
                ("admin@test.com", "Test Admin", "ADMIN"),
                ("placement@test.com", "Test Placement Officer", "PLACEMENT_OFFICER"),
            ):
                execute(
                    """INSERT INTO users (username, password_hash, full_name, email, role_id)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        email,
                        generate_password_hash(
                            {
                                "recruiter@test.com": "recruiterpass",
                                "another-recruiter@test.com": "anotherpass",
                            }.get(email, "testpass")
                        ),
                        name,
                        email,
                        role_ids[role_code],
                    ),
                )
            execute(
                """INSERT INTO companies
                   (company_code, company_name, industry, location, hr_name)
                   VALUES (?, ?, ?, ?, ?)""",
                ("COM-001", "Northstar Labs", "Software", "Pune", "Asha Rao"),
            )
            company_id = execute("SELECT company_id FROM companies WHERE company_code = ?", ("COM-001",))[0][0]["company_id"]
            execute(
                """INSERT INTO jobs
                   (job_code, company_id, job_title, location, openings, min_percentage,
                    max_backlogs, posted_date, application_deadline)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    "JOB-TEST-001",
                    company_id,
                    "Associate Developer",
                    "Pune",
                    4,
                    65,
                    0,
                    date.today().isoformat(),
                    (date.today() + timedelta(days=30)).isoformat(),
                ),
            )
            self.job_id = execute("SELECT job_id FROM jobs WHERE job_code = ?", ("JOB-TEST-001",))[0][0]["job_id"]
            self.company_id = company_id
            self.recruiter_id = execute(
                "SELECT user_id FROM users WHERE email = ?", ("recruiter@test.com",)
            )[0][0]["user_id"]
            commit()
        self.client = self.app.test_client()
        response = self.client.post(
            "/api/auth/login",
            json={
                "email": "recruiter@test.com",
                "password": "recruiterpass",
                "role": "RECRUITER",
            },
        )
        self.assertEqual(response.status_code, 200)

    def tearDown(self):
        self.temp_dir.cleanup()

    def login_as(self, email, password, role):
        response = self.client.post(
            "/api/auth/login",
            json={"email": email, "password": password, "role": role},
        )
        self.assertEqual(response.status_code, 200)

    def add_candidate(self, email="aarav@test.com", mobile="9876543210", percentage=82):
        return self.client.post(
            "/api/candidates",
            json={
                "full_name": "Aarav Kulkarni",
                "email": email,
                "mobile": mobile,
                "qualification": "BE",
                "college": "Pune Institute of Technology",
                "passing_year": 2025,
                "percentage": percentage,
                "backlog_count": 0,
                "primary_technology": "Java",
                "secondary_skills": "SQL, Git",
                "profile_status": "ACTIVE",
            },
        )

    def test_demo_roles_sign_in_and_role_mismatch_is_explained(self):
        mismatched = self.client.post(
            "/api/auth/login",
            json={
                "email": "recruiter@test.com",
                "password": "recruiterpass",
                "role": "ADMIN",
            },
        )
        self.assertEqual(mismatched.status_code, 401)
        self.assertIn("account is for Recruiter", mismatched.get_json()["error"])
        wrong_password = self.client.post(
            "/api/auth/login",
            json={
                "email": "recruiter@test.com",
                "password": "incorrect",
                "role": "ADMIN",
            },
        )
        self.assertEqual(wrong_password.status_code, 401)
        self.assertEqual(
            wrong_password.get_json()["error"],
            "Email, password or selected role is incorrect.",
        )
        individual_recruiter_login = self.client.post(
            "/api/auth/login",
            json={
                "email": "another-recruiter@test.com",
                "password": "anotherpass",
                "role": "RECRUITER",
            },
        )
        self.assertEqual(individual_recruiter_login.status_code, 200)
        self.assertEqual(
            individual_recruiter_login.get_json()["user"]["email"],
            "another-recruiter@test.com",
        )
        wrong_recruiter_password = self.client.post(
            "/api/auth/login",
            json={
                "email": "another-recruiter@test.com",
                "password": "recruiterpass",
                "role": "RECRUITER",
            },
        )
        self.assertEqual(wrong_recruiter_password.status_code, 401)
        for email, role, password in (
            ("recruiter@test.com", "RECRUITER", "recruiterpass"),
            ("admin@test.com", "ADMIN", "testpass"),
            ("placement@test.com", "PLACEMENT_OFFICER", "testpass"),
        ):
            response = self.client.post(
                "/api/auth/login",
                json={"email": email, "password": password, "role": role},
            )
            self.assertEqual(response.status_code, 200, email)
            self.assertEqual(response.get_json()["user"]["role"], role)

    def test_recruiter_registration_creates_and_signs_in_account(self):
        response = self.client.post(
            "/api/auth/register",
            json={
                "full_name": "New Recruiter",
                "email": "  NEW.RECRUITER@test.com ",
                "password": "securepass123",
                "role": "ADMIN",
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.get_json()["user"],
            {
                "id": response.get_json()["user"]["id"],
                "name": "New Recruiter",
                "email": "new.recruiter@test.com",
                "role": "RECRUITER",
                "role_name": "Recruiter",
            },
        )
        self.assertEqual(self.client.get("/api/dashboard").status_code, 200)

        with self.app.app_context():
            saved_user = execute(
                "SELECT password_hash FROM users WHERE email = ?",
                ("new.recruiter@test.com",),
            )[0][0]
            self.assertNotEqual(saved_user["password_hash"], "securepass123")

        duplicate = self.client.post(
            "/api/auth/register",
            json={
                "full_name": "Duplicate Recruiter",
                "email": "new.recruiter@test.com",
                "password": "securepass123",
            },
        )
        self.assertEqual(duplicate.status_code, 409)

    def test_recruiter_registration_validates_email_and_password(self):
        invalid_email = self.client.post(
            "/api/auth/register",
            json={"full_name": "New Recruiter", "email": "not-an-email", "password": "securepass123"},
        )
        self.assertEqual(invalid_email.status_code, 400)
        short_password = self.client.post(
            "/api/auth/register",
            json={"full_name": "New Recruiter", "email": "new@test.com", "password": "short"},
        )
        self.assertEqual(short_password.status_code, 400)

    def test_authentication_and_candidate_validation(self):
        self.assertEqual(self.client.get("/api/dashboard").status_code, 200)
        self.assertEqual(self.add_candidate().status_code, 201)
        candidate = self.client.get("/api/candidates").get_json()["items"][0]
        self.assertIn("SQL", candidate["skills"])
        duplicate = self.add_candidate(email="other@test.com")
        self.assertEqual(duplicate.status_code, 409)
        invalid_mobile = self.add_candidate(email="new@test.com", mobile="1234")
        self.assertEqual(invalid_mobile.status_code, 400)

    def test_application_eligibility_and_duplicate_prevention(self):
        candidate = self.add_candidate(percentage=61).get_json()["item"]
        response = self.client.post(
            "/api/applications",
            json={"candidate_id": candidate["candidate_id"], "job_id": self.job_id, "source": "Recruiter"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["item"]["eligibility_status"], "NOT_ELIGIBLE")
        duplicate = self.client.post(
            "/api/applications",
            json={"candidate_id": candidate["candidate_id"], "job_id": self.job_id},
        )
        self.assertEqual(duplicate.status_code, 409)

    def test_required_job_skills_are_checked(self):
        with self.app.app_context():
            execute("INSERT INTO skills (skill_name, category) VALUES (?, ?)", ("Python", "Programming"))
            python_id = execute("SELECT skill_id FROM skills WHERE skill_name = ?", ("Python",))[0][0]["skill_id"]
            execute(
                """INSERT INTO job_skills (job_id, skill_id, mandatory_flag, is_primary)
                   VALUES (?, ?, 1, 1)""",
                (self.job_id, python_id),
            )
            commit()
        candidate = self.add_candidate().get_json()["item"]
        application = self.client.post(
            "/api/applications",
            json={"candidate_id": candidate["candidate_id"], "job_id": self.job_id},
        ).get_json()["item"]
        self.assertEqual(application["eligibility_status"], "NOT_ELIGIBLE")
        self.assertIn("Python", application["eligibility_reason"])

    def test_company_and_job_records_can_be_updated(self):
        self.login_as("admin@test.com", "testpass", "ADMIN")
        new_company = self.client.post(
            "/api/companies",
            json={
                "company_name": "Horizon Works",
                "industry": "Technology",
                "location": "Mumbai",
                "hr_name": "Mira Sen",
                "hr_email": "mira@horizon.example",
                "company_type": "STARTUP",
            },
        )
        self.assertEqual(new_company.status_code, 201)
        company_id = new_company.get_json()["item"]["company_id"]
        updated_company = self.client.patch(
            f"/api/companies/{company_id}",
            json={
                "company_name": "Horizon Works India",
                "industry": "Product Technology",
                "location": "Pune",
                "hr_name": "Mira Sen",
                "hr_email": "mira@horizon.example",
                "company_type": "MID_SIZE",
                "status": "ACTIVE",
            },
        )
        self.assertEqual(updated_company.status_code, 200)

        payload = {
            "company_id": company_id,
            "job_title": "Python Engineer",
            "employment_type": "FULL_TIME",
            "location": "Pune",
            "openings": 3,
            "min_package_lpa": 5,
            "max_package_lpa": 8,
            "min_percentage": 60,
            "min_passing_year": 2024,
            "max_passing_year": 2026,
            "max_backlogs": 0,
            "qualification_rule": "BE",
            "required_technology": "Python",
            "required_skills": "SQL, Git",
            "posted_date": date.today().isoformat(),
            "application_deadline": (date.today() + timedelta(days=30)).isoformat(),
            "status": "OPEN",
        }
        created_job = self.client.post("/api/jobs", json=payload)
        self.assertEqual(created_job.status_code, 201)
        job_id = created_job.get_json()["item"]["job_id"]
        listed_job = next(
            item for item in self.client.get("/api/jobs").get_json()["items"]
            if item["job_id"] == job_id
        )
        self.assertEqual(listed_job["primary_technology"], "Python")
        self.assertIn("SQL", listed_job["required_skills"])
        payload["job_title"] = "Senior Python Engineer"
        payload["status"] = "CLOSED"
        updated_job = self.client.patch(f"/api/jobs/{job_id}", json=payload)
        self.assertEqual(updated_job.status_code, 200)
        self.assertEqual(
            next(
                item for item in self.client.get("/api/jobs").get_json()["items"]
                if item["job_id"] == job_id
            )["job_title"],
            "Senior Python Engineer",
        )

    def test_interview_to_offer_to_placement_transaction(self):
        candidate = self.add_candidate().get_json()["item"]
        application = self.client.post(
            "/api/applications",
            json={"candidate_id": candidate["candidate_id"], "job_id": self.job_id},
        ).get_json()["item"]
        self.assertEqual(application["eligibility_status"], "ELIGIBLE")
        self.client.patch(
            f"/api/applications/{application['application_id']}/status",
            json={"status": "SHORTLISTED"},
        )
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        interview = self.client.post(
            "/api/interviews",
            json={
                "application_id": application["application_id"],
                "round_type": "TECHNICAL",
                "scheduled_date": tomorrow,
                "scheduled_time": "11:30",
                "mode": "ONLINE",
                "interviewer_name": "Asha Rao",
            },
        ).get_json()["item"]
        feedback = self.client.post(
            f"/api/interviews/{interview['interview_id']}/feedback",
            json={"recommendation": "SELECTED", "overall_rating": 4.5, "remarks": "Great fundamentals."},
        )
        self.assertEqual(feedback.status_code, 200)
        self.login_as("placement@test.com", "testpass", "PLACEMENT_OFFICER")
        offer = self.client.post(
            "/api/offers",
            json={
                "application_id": application["application_id"],
                "designation": "Associate Developer",
                "offered_package_lpa": 5.2,
                "offer_date": date.today().isoformat(),
            },
        )
        self.assertEqual(offer.status_code, 201)
        offer_id = offer.get_json()["item"]["offer_id"]
        self.client.patch(f"/api/offers/{offer_id}", json={"offer_status": "ACCEPTED"})
        placement = self.client.post(
            f"/api/placements/{offer_id}",
            json={"joining_status": "JOINED", "actual_joining_date": date.today().isoformat()},
        )
        self.assertEqual(placement.status_code, 201)
        history = self.client.get(f"/api/applications/{application['application_id']}/history").get_json()["items"]
        self.assertEqual(history[0]["new_status"], "JOINED")
        self.assertEqual(self.client.get("/api/dashboard").get_json()["counts"]["placed"], 1)
        self.assertEqual(len(self.client.get("/api/placements").get_json()["items"]), 1)
        self.assertEqual(self.client.get("/api/reports").status_code, 403)
        self.login_as("recruiter@test.com", "recruiterpass", "RECRUITER")
        self.assertEqual(self.client.get("/api/dashboard").get_json()["counts"]["placed"], 0)
        self.assertEqual(self.client.get("/api/placements").status_code, 403)

    def test_recruiter_data_is_scoped_and_placement_routes_are_private(self):
        candidate = self.add_candidate().get_json()["item"]
        application = self.client.post(
            "/api/applications",
            json={"candidate_id": candidate["candidate_id"], "job_id": self.job_id},
        )
        self.assertEqual(application.status_code, 201)
        self.assertEqual(len(self.client.get("/api/candidates").get_json()["items"]), 1)
        self.assertEqual(len(self.client.get("/api/applications").get_json()["items"]), 1)

        self.login_as("another-recruiter@test.com", "anotherpass", "RECRUITER")
        self.assertEqual(self.client.get("/api/candidates").get_json()["items"], [])
        self.assertEqual(self.client.get("/api/applications").get_json()["items"], [])
        self.assertEqual(self.client.get("/api/dashboard").get_json()["counts"]["candidates"], 0)
        self.assertEqual(self.client.get("/api/dashboard").get_json()["counts"]["applications"], 0)
        self.assertEqual(self.client.get("/api/placements").status_code, 403)

        self.login_as("admin@test.com", "testpass", "ADMIN")
        self.assertEqual(len(self.client.get("/api/candidates").get_json()["items"]), 1)
        self.assertEqual(len(self.client.get("/api/applications").get_json()["items"]), 1)


if __name__ == "__main__":
    unittest.main()
