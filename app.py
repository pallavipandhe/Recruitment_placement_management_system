import functools
import logging
import os
import re
import sqlite3
from datetime import date, datetime, time
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv
from flask import Flask, current_app, g, jsonify, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.exceptions import HTTPException


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
ALLOWED_APPLICATION_STATUSES = {
    "APPLIED",
    "ELIGIBILITY_VERIFIED",
    "SHORTLISTED",
    "INTERVIEW_SCHEDULED",
    "INTERVIEWED",
    "SELECTED",
    "REJECTED",
    "OFFERED",
    "JOINED",
    "WITHDRAWN",
}


class APIError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def _database_url():
    return current_app.config["DATABASE_URL"]


def _is_sqlite():
    return _database_url().startswith("sqlite:///")


def _open_connection(url):
    if url.startswith("sqlite:///"):
        filename = url[len("sqlite:///") :]
        path = Path(filename)
        if not path.is_absolute():
            path = ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    if not url.startswith("mysql://"):
        raise RuntimeError("DATABASE_URL must start with sqlite:/// or mysql://.")

    from urllib.parse import unquote, urlparse

    parsed = urlparse(url)
    if not parsed.hostname or not parsed.path.strip("/"):
        raise RuntimeError("DATABASE_URL must include a MySQL host and database name.")
    return mysql.connector.connect(
        host=parsed.hostname,
        port=parsed.port or 3306,
        user=unquote(parsed.username or ""),
        password=unquote(parsed.password or ""),
        database=parsed.path.strip("/"),
        autocommit=False,
    )


def get_db():
    if "db" not in g:
        g.db = _open_connection(_database_url())
    return g.db


def close_db(_error=None):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def execute(sql, params=()):
    connection = get_db()
    is_sqlite = isinstance(connection, sqlite3.Connection)
    cursor = connection.cursor() if is_sqlite else connection.cursor(dictionary=True)
    cursor.execute(sql if is_sqlite else sql.replace("?", "%s"), params)
    rows = cursor.fetchall() if cursor.description else []
    if is_sqlite:
        rows = [dict(row) for row in rows]
    else:
        rows = [
            {
                key: value.isoformat() if isinstance(value, (date, datetime, time)) else value
                for key, value in row.items()
            }
            for row in rows
        ]
    last_id = cursor.lastrowid
    row_count = cursor.rowcount
    cursor.close()
    return rows, last_id, row_count


def commit():
    get_db().commit()


def rollback():
    get_db().rollback()


def _body():
    return request.get_json(silent=True) or {}


def _required(data, field, label=None):
    value = str(data.get(field, "")).strip()
    if not value:
        raise APIError(f"{label or field.replace('_', ' ').title()} is required.")
    return value


def _number(data, field, label, minimum=None, maximum=None, optional=False):
    value = data.get(field)
    if optional and value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise APIError(f"{label} must be a number.") from None
    if minimum is not None and number < minimum:
        raise APIError(f"{label} must be at least {minimum}.")
    if maximum is not None and number > maximum:
        raise APIError(f"{label} must be no more than {maximum}.")
    return int(number) if number.is_integer() else number


def _date(value, label, required=True):
    value = str(value or "").strip()
    if not value and not required:
        return None
    try:
        date.fromisoformat(value)
    except ValueError:
        raise APIError(f"{label} must be a valid date.") from None
    return value


def _code(prefix, table, width=4):
    rows, _, _ = execute(f"SELECT COUNT(*) AS total FROM {table}")
    sequence = rows[0]["total"] + 1
    return f"{prefix}-{date.today().year}-{sequence:0{width}d}"


def _activity(module, action, record_id, description):
    execute(
        """INSERT INTO activity_logs
           (user_id, module_name, action_name, record_id, description)
           VALUES (?, ?, ?, ?, ?)""",
        (session.get("user_id"), module, action, str(record_id), description[:500]),
    )


def _save_candidate_skills(candidate_id, primary, secondary, proficiency="INTERMEDIATE"):
    execute("DELETE FROM candidate_skills WHERE candidate_id = ?", (candidate_id,))
    skill_names = []
    for name in [primary, *(secondary or "").split(",")]:
        cleaned = str(name or "").strip()
        if cleaned and cleaned.casefold() not in {item.casefold() for item in skill_names}:
            skill_names.append(cleaned)
    for name in skill_names:
        skill = _find_one("SELECT skill_id FROM skills WHERE LOWER(skill_name) = LOWER(?)", (name,))
        if skill:
            skill_id = skill["skill_id"]
        else:
            _, skill_id, _ = execute(
                "INSERT INTO skills (skill_name, category) VALUES (?, 'Other')",
                (name,),
            )
        execute(
            """INSERT INTO candidate_skills
               (candidate_id, skill_id, proficiency_level, is_primary)
               VALUES (?, ?, ?, ?)""",
            (candidate_id, skill_id, proficiency or "INTERMEDIATE", int(name.casefold() == str(primary or "").casefold())),
        )


def _save_job_skills(job_id, primary, additional):
    execute("DELETE FROM job_skills WHERE job_id = ?", (job_id,))
    skill_names = []
    for name in [primary, *(additional or "").split(",")]:
        cleaned = str(name or "").strip()
        if cleaned and cleaned.casefold() not in {item.casefold() for item in skill_names}:
            skill_names.append(cleaned)
    for name in skill_names:
        skill = _find_one("SELECT skill_id FROM skills WHERE LOWER(skill_name) = LOWER(?)", (name,))
        if skill:
            skill_id = skill["skill_id"]
        else:
            _, skill_id, _ = execute(
                "INSERT INTO skills (skill_name, category) VALUES (?, 'Other')",
                (name,),
            )
        execute(
            """INSERT INTO job_skills (job_id, skill_id, minimum_level, mandatory_flag, is_primary)
               VALUES (?, ?, 'INTERMEDIATE', 1, ?)""",
            (job_id, skill_id, int(name.casefold() == str(primary or "").casefold())),
        )


def _user_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            raise APIError("Please sign in to continue.", 401)
        return view(*args, **kwargs)

    return wrapped


def _find_one(sql, params=()):
    rows, _, _ = execute(sql, params)
    return rows[0] if rows else None


def _require_roles(*roles):
    if session.get("role") not in roles:
        raise APIError("You do not have permission to access this area.", 403)


def _application_scope(alias="a"):
    role = session.get("role")
    if role == "ADMIN":
        return "1 = 1", ()
    if role == "RECRUITER":
        return f"{alias}.assigned_recruiter_id = ?", (session.get("user_id"),)
    if role == "PLACEMENT_OFFICER":
        return f"{alias}.application_status IN ('SELECTED', 'OFFERED', 'JOINED')", ()
    raise APIError("Your account does not have a supported workspace role.", 403)


def _candidate_scope(alias="c"):
    role = session.get("role")
    if role == "ADMIN":
        return "1 = 1", ()
    application_filter, params = _application_scope("a")
    if role == "RECRUITER":
        return (
            f"({alias}.created_by = ? OR EXISTS (SELECT 1 FROM applications a "
            f"WHERE a.candidate_id = {alias}.candidate_id AND {application_filter}))",
            (session.get("user_id"), *params),
        )
    return (
        f"EXISTS (SELECT 1 FROM applications a WHERE a.candidate_id = {alias}.candidate_id "
        f"AND {application_filter})",
        params,
    )


def _job_scope(alias="j"):
    role = session.get("role")
    if role == "ADMIN":
        return "1 = 1", ()
    application_filter, params = _application_scope("a")
    if role == "RECRUITER":
        return (
            f"({alias}.created_by = ? OR {alias}.status = 'OPEN' OR EXISTS (SELECT 1 FROM applications a "
            f"WHERE a.job_id = {alias}.job_id AND {application_filter}))",
            (session.get("user_id"), *params),
        )
    return (
        f"EXISTS (SELECT 1 FROM applications a WHERE a.job_id = {alias}.job_id "
        f"AND {application_filter})",
        params,
    )


def _visible_application(application_id):
    application_filter, params = _application_scope("a")
    return _find_one(
        f"SELECT a.* FROM applications a WHERE a.application_id = ? AND {application_filter}",
        (application_id, *params),
    )


def _visible_candidate(candidate_id):
    candidate_filter, params = _candidate_scope("c")
    return _find_one(
        f"SELECT c.* FROM candidates c WHERE c.candidate_id = ? AND {candidate_filter}",
        (candidate_id, *params),
    )


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", "local-development-key-change-me"),
        DATABASE_URL=os.getenv("DATABASE_URL", "sqlite:///instance/recruitment.db"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if test_config:
        app.config.update(test_config)
    app.teardown_appcontext(close_db)
    app.logger.setLevel(logging.INFO)

    @app.errorhandler(APIError)
    def handle_api_error(error):
        if error.status >= 500:
            rollback()
        return jsonify({"error": error.message}), error.status

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        if isinstance(error, HTTPException):
            return jsonify({"error": error.description}), error.code
        if isinstance(error, (sqlite3.IntegrityError, mysql.connector.IntegrityError)):
            rollback()
            return jsonify({"error": "This record conflicts with existing data."}), 409
        app.logger.exception("Unhandled request error", exc_info=error)
        try:
            rollback()
        except Exception:
            app.logger.exception("Could not roll back failed request")
        return jsonify({"error": "The request could not be completed. Check the server log."}), 500

    @app.get("/")
    @app.get("/login")
    @app.get("/register")
    @app.get("/dashboard")
    @app.get("/candidates")
    @app.get("/candidate-form")
    @app.get("/candidate-details")
    @app.get("/companies")
    @app.get("/jobs")
    @app.get("/job-form")
    @app.get("/applications")
    @app.get("/interviews")
    @app.get("/placement-process")
    @app.get("/reports")
    def index():
        return render_template("index.html")

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    @app.post("/api/auth/login")
    def login():
        data = _body()
        email = _required(data, "email", "Email")
        password = _required(data, "password", "Password")
        role = _required(data, "role", "Role").upper()
        user = _find_one(
            """SELECT u.user_id, u.username, u.full_name, u.email, u.password_hash,
                      u.status, r.role_code, r.role_name
               FROM users u JOIN roles r ON r.role_id = u.role_id
               WHERE LOWER(u.email) = LOWER(?) OR LOWER(u.username) = LOWER(?)""",
            (email, email),
        )
        if not user or user["status"] != "ACTIVE" or not check_password_hash(user["password_hash"], password):
            raise APIError("Email, password or selected role is incorrect.", 401)
        if user["role_code"] != role:
            raise APIError(
                f"Your password is correct, but this account is for {user['role_name']}. "
                "Choose that role and try again.",
                401,
            )
        session.clear()
        session.update(
            user_id=user["user_id"],
            name=user["full_name"],
            email=user["email"],
            role=user["role_code"],
            role_name=user["role_name"],
        )
        execute("UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE user_id = ?", (user["user_id"],))
        commit()
        return jsonify({"user": _current_user()})

    @app.post("/api/auth/register")
    def register():
        data = _body()
        full_name = _required(data, "full_name", "Full name")
        email = _required(data, "email", "Email").lower()
        password = _required(data, "password", "Password")
        if len(full_name) > 120:
            raise APIError("Full name must be no more than 120 characters.")
        if len(email) > 150 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise APIError("Enter a valid email address.")
        if len(password) < 8:
            raise APIError("Password must be at least 8 characters.")
        if _find_one(
            "SELECT user_id FROM users WHERE LOWER(email) = LOWER(?) OR LOWER(username) = LOWER(?)",
            (email, email),
        ):
            raise APIError("An account with this email already exists. Sign in instead.", 409)
        recruiter_role = _find_one(
            "SELECT role_id FROM roles WHERE role_code = 'RECRUITER' AND is_active = 1"
        )
        if not recruiter_role:
            raise APIError("Recruiter registration is unavailable. Please contact your administrator.", 503)
        _, user_id, _ = execute(
            """INSERT INTO users (username, password_hash, full_name, email, role_id)
               VALUES (?, ?, ?, ?, ?)""",
            (email, generate_password_hash(password), full_name, email, recruiter_role["role_id"]),
        )
        commit()
        user = _find_one(
            """SELECT u.user_id, u.full_name, u.email, r.role_code, r.role_name
               FROM users u JOIN roles r ON r.role_id = u.role_id
               WHERE u.user_id = ?""",
            (user_id,),
        )
        session.clear()
        session.update(
            user_id=user["user_id"],
            name=user["full_name"],
            email=user["email"],
            role=user["role_code"],
            role_name=user["role_name"],
        )
        return jsonify({"user": _current_user()}), 201

    @app.post("/api/auth/logout")
    def logout():
        session.clear()
        return jsonify({"status": "signed_out"})

    @app.get("/api/auth/me")
    def current_session():
        if not session.get("user_id"):
            return jsonify({"user": None})
        return jsonify({"user": _current_user()})

    @app.get("/api/dashboard")
    @_user_required
    def dashboard():
        role = session.get("role")
        application_filter, application_params = _application_scope("a")
        candidate_filter, candidate_params = _candidate_scope("c")
        job_filter, job_params = _job_scope("j")
        counts = {}
        queries = {
            "candidates": (
                f"SELECT COUNT(*) AS total FROM candidates c WHERE {candidate_filter}",
                candidate_params,
            ),
            "active_candidates": (
                f"SELECT COUNT(*) AS total FROM candidates c WHERE c.profile_status = 'ACTIVE' AND {candidate_filter}",
                candidate_params,
            ),
            "companies": (
                "SELECT COUNT(*) AS total FROM companies WHERE status = 'ACTIVE'"
                if role in {"ADMIN", "RECRUITER"}
                else f"""SELECT COUNT(DISTINCT co.company_id) AS total FROM companies co
                          JOIN jobs j ON j.company_id = co.company_id
                          JOIN applications a ON a.job_id = j.job_id WHERE {application_filter}""",
                () if role in {"ADMIN", "RECRUITER"} else application_params,
            ),
            "open_jobs": (
                f"SELECT COUNT(*) AS total FROM jobs j WHERE j.status = 'OPEN' AND {job_filter}"
                if role != "PLACEMENT_OFFICER"
                else "SELECT 0 AS total",
                job_params if role != "PLACEMENT_OFFICER" else (),
            ),
            "applications": (
                f"SELECT COUNT(*) AS total FROM applications a WHERE {application_filter}",
                application_params,
            ),
            "interviews": (
                f"""SELECT COUNT(*) AS total FROM interview_rounds i
                    JOIN applications a ON a.application_id = i.application_id
                    WHERE i.status = 'SCHEDULED' AND {application_filter}"""
                if role != "PLACEMENT_OFFICER"
                else "SELECT 0 AS total",
                application_params if role != "PLACEMENT_OFFICER" else (),
            ),
            "selected": (
                f"SELECT COUNT(*) AS total FROM applications a WHERE a.application_status = 'SELECTED' AND {application_filter}",
                application_params,
            ),
            "placed": (
                f"""SELECT COUNT(*) AS total FROM placements p
                    JOIN offers o ON o.offer_id = p.offer_id
                    JOIN applications a ON a.application_id = o.application_id
                    WHERE p.joining_status = 'JOINED' AND {application_filter}"""
                if role != "RECRUITER"
                else "SELECT 0 AS total",
                application_params if role != "RECRUITER" else (),
            ),
            "offers": (
                f"""SELECT COUNT(*) AS total FROM offers o
                    JOIN applications a ON a.application_id = o.application_id
                    WHERE {application_filter}"""
                if role != "RECRUITER"
                else "SELECT 0 AS total",
                application_params if role != "RECRUITER" else (),
            ),
            "accepted_offers": (
                f"""SELECT COUNT(*) AS total FROM offers o
                    JOIN applications a ON a.application_id = o.application_id
                    WHERE o.offer_status = 'ACCEPTED' AND {application_filter}"""
                if role != "RECRUITER"
                else "SELECT 0 AS total",
                application_params if role != "RECRUITER" else (),
            ),
        }
        for key, (sql, params) in queries.items():
            counts[key] = execute(sql, params)[0][0]["total"]
        counts["interviews_today"] = (
            execute(
                f"""SELECT COUNT(*) AS total FROM interview_rounds i
                    JOIN applications a ON a.application_id = i.application_id
                    WHERE i.scheduled_date = ? AND i.status = 'SCHEDULED' AND {application_filter}""",
                (date.today().isoformat(), *application_params),
            )[0][0]["total"]
            if role != "PLACEMENT_OFFICER"
            else 0
        )
        funnel_rows = execute(
            f"""SELECT a.application_status AS label, COUNT(*) AS total
                FROM applications a WHERE {application_filter} GROUP BY a.application_status""",
            application_params,
        )[0]
        funnel = {row["label"]: row["total"] for row in funnel_rows}
        upcoming = execute(
            """SELECT i.interview_id, i.scheduled_date, i.scheduled_time, i.round_type,
                      c.full_name AS candidate, co.company_name AS company,
                      j.job_title AS job_title, i.mode, i.status
               FROM interview_rounds i
               JOIN applications a ON a.application_id = i.application_id
               JOIN candidates c ON c.candidate_id = a.candidate_id
               JOIN jobs j ON j.job_id = a.job_id
               JOIN companies co ON co.company_id = j.company_id
               WHERE i.scheduled_date >= ? AND i.status = 'SCHEDULED' AND """ + application_filter + """
               ORDER BY i.scheduled_date, i.scheduled_time LIMIT 5""",
            (date.today().isoformat(), *application_params),
        )[0] if role != "PLACEMENT_OFFICER" else []
        jobs = execute(
            """SELECT j.job_id, j.job_code, j.job_title, j.location, j.openings,
                      j.min_package_lpa, j.max_package_lpa, co.company_name
               FROM jobs j JOIN companies co ON co.company_id = j.company_id
               WHERE j.status = 'OPEN' AND """ + job_filter + """
               ORDER BY j.created_at DESC LIMIT 5""",
            job_params,
        )[0] if role != "PLACEMENT_OFFICER" else []
        placements = execute(
            """SELECT p.placement_id, c.full_name AS candidate, co.company_name,
                      p.designation, p.final_package_lpa, p.actual_joining_date
               FROM placements p JOIN offers o ON o.offer_id = p.offer_id
               JOIN applications a ON a.application_id = o.application_id
               JOIN candidates c ON c.candidate_id = p.candidate_id
               JOIN companies co ON co.company_id = p.company_id
               WHERE """ + application_filter + """
               ORDER BY p.created_at DESC LIMIT 4""",
            application_params,
        )[0] if role != "RECRUITER" else []
        return jsonify({"counts": counts, "funnel": funnel, "upcoming": upcoming, "jobs": jobs, "placements": placements})

    @app.get("/api/candidates")
    @_user_required
    def candidates():
        search = f"%{request.args.get('q', '').strip()}%"
        technology = request.args.get("technology", "").strip()
        status = request.args.get("status", "").strip()
        candidate_filter, candidate_params = _candidate_scope("c")
        rows, _, _ = execute(
            """SELECT c.*, (SELECT GROUP_CONCAT(s.skill_name)
                   FROM candidate_skills cs JOIN skills s ON s.skill_id = cs.skill_id
                   WHERE cs.candidate_id = c.candidate_id) AS skills
               FROM candidates c
               WHERE """ + candidate_filter + """ AND
                 (c.full_name LIKE ? OR c.candidate_code LIKE ? OR c.email LIKE ? OR c.mobile LIKE ?)
                 AND (? = '' OR c.primary_technology = ?)
                 AND (? = '' OR c.profile_status = ?)
               ORDER BY c.created_at DESC, c.candidate_id DESC""",
            (*candidate_params, search, search, search, search, technology, technology, status, status),
        )
        return jsonify({"items": rows})

    @app.post("/api/candidates")
    @_user_required
    def create_candidate():
        _require_roles("ADMIN", "RECRUITER")
        data = _body()
        name = _required(data, "full_name", "Full name")
        email = _required(data, "email", "Email").lower()
        mobile = _required(data, "mobile", "Mobile")
        qualification = _required(data, "qualification", "Qualification")
        college = _required(data, "college", "College")
        passing_year = _number(data, "passing_year", "Passing year", 1990, 2100)
        percentage = _number(data, "percentage", "Percentage", 0, 100, optional=True)
        backlog_count = _number(data, "backlog_count", "Backlog count", 0)
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise APIError("Enter a valid email address.")
        if not re.fullmatch(r"\d{10}", mobile):
            raise APIError("Mobile number must contain 10 digits.")
        dob = _date(data.get("date_of_birth"), "Date of birth", required=False)
        candidate_code = _code("CAN", "candidates")
        _, candidate_id, _ = execute(
            """INSERT INTO candidates
               (candidate_code, full_name, email, mobile, date_of_birth, gender, qualification,
                college, university, passing_year, percentage, cgpa, backlog_count,
                created_by, primary_technology, current_location, preferred_location, profile_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                candidate_code,
                name,
                email,
                mobile,
                dob,
                data.get("gender") or None,
                qualification,
                college,
                data.get("university") or None,
                passing_year,
                percentage,
                _number(data, "cgpa", "CGPA", 0, 10, optional=True),
                backlog_count,
                session.get("user_id"),
                data.get("primary_technology") or None,
                data.get("current_location") or None,
                data.get("preferred_location") or None,
                data.get("profile_status", "ACTIVE"),
            ),
        )
        _save_candidate_skills(
            candidate_id,
            data.get("primary_technology"),
            data.get("secondary_skills"),
            data.get("skill_level"),
        )
        _activity("Candidates", "Created", candidate_code, f"Created candidate profile for {name}.")
        commit()
        return jsonify({"item": _find_one("SELECT * FROM candidates WHERE candidate_id = ?", (candidate_id,))}), 201

    @app.patch("/api/candidates/<int:candidate_id>")
    @_user_required
    def update_candidate(candidate_id):
        _require_roles("ADMIN", "RECRUITER")
        data = _body()
        existing = _visible_candidate(candidate_id)
        if not existing:
            raise APIError("Candidate not found.", 404)
        fields = {
            "full_name": _required(data, "full_name", "Full name"),
            "email": _required(data, "email", "Email").lower(),
            "mobile": _required(data, "mobile", "Mobile"),
            "qualification": _required(data, "qualification", "Qualification"),
            "college": _required(data, "college", "College"),
            "passing_year": _number(data, "passing_year", "Passing year", 1990, 2100),
            "percentage": _number(data, "percentage", "Percentage", 0, 100, optional=True),
            "backlog_count": _number(data, "backlog_count", "Backlog count", 0),
        }
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", fields["email"]):
            raise APIError("Enter a valid email address.")
        if not re.fullmatch(r"\d{10}", fields["mobile"]):
            raise APIError("Mobile number must contain 10 digits.")
        fields.update(
            date_of_birth=_date(data.get("date_of_birth"), "Date of birth", required=False),
            gender=data.get("gender") or None,
            university=data.get("university") or None,
            cgpa=_number(data, "cgpa", "CGPA", 0, 10, optional=True),
            primary_technology=data.get("primary_technology") or None,
            current_location=data.get("current_location") or None,
            preferred_location=data.get("preferred_location") or None,
            profile_status=data.get("profile_status", "ACTIVE"),
        )
        assignments = ", ".join(f"{key} = ?" for key in fields)
        execute(f"UPDATE candidates SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE candidate_id = ?", (*fields.values(), candidate_id))
        _save_candidate_skills(
            candidate_id,
            fields["primary_technology"],
            data.get("secondary_skills"),
            data.get("skill_level"),
        )
        _activity("Candidates", "Updated", existing["candidate_code"], f"Updated candidate profile for {fields['full_name']}.")
        commit()
        return jsonify({"item": _find_one("SELECT * FROM candidates WHERE candidate_id = ?", (candidate_id,))})

    @app.delete("/api/candidates/<int:candidate_id>")
    @_user_required
    def deactivate_candidate(candidate_id):
        _require_roles("ADMIN", "RECRUITER")
        candidate = _visible_candidate(candidate_id)
        if not candidate:
            raise APIError("Candidate not found.", 404)
        execute("UPDATE candidates SET profile_status = 'INACTIVE', updated_at = CURRENT_TIMESTAMP WHERE candidate_id = ?", (candidate_id,))
        _activity("Candidates", "Deactivated", candidate["candidate_code"], "Candidate profile was deactivated.")
        commit()
        return jsonify({"status": "deactivated"})

    @app.get("/api/companies")
    @_user_required
    def companies():
        search = f"%{request.args.get('q', '').strip()}%"
        role = session.get("role")
        application_filter, application_params = _application_scope("a")
        visibility_filter = (
            "co.status = 'ACTIVE'"
            if role == "RECRUITER"
            else "1 = 1"
            if role == "ADMIN"
            else f"""EXISTS (SELECT 1 FROM jobs j JOIN applications a ON a.job_id = j.job_id
                              WHERE j.company_id = co.company_id AND {application_filter})"""
        )
        rows, _, _ = execute(
            """SELECT co.*, (SELECT COUNT(*) FROM jobs j WHERE j.company_id = co.company_id AND j.status = 'OPEN') AS open_jobs
               FROM companies co WHERE """ + visibility_filter + """ AND
                 (co.company_name LIKE ? OR co.industry LIKE ? OR co.company_code LIKE ?)
               ORDER BY co.company_name""",
            (*(application_params if role == "PLACEMENT_OFFICER" else ()), search, search, search),
        )
        return jsonify({"items": rows})

    @app.post("/api/companies")
    @_user_required
    def create_company():
        _require_roles("ADMIN")
        data = _body()
        name = _required(data, "company_name", "Company name")
        industry = _required(data, "industry", "Industry")
        location = _required(data, "location", "Location")
        hr_name = _required(data, "hr_name", "HR name")
        company_code = f"COM-{execute('SELECT COUNT(*) AS total FROM companies')[0][0]['total'] + 1:03d}"
        _, company_id, _ = execute(
            """INSERT INTO companies
               (company_code, company_name, industry, website, location, company_type, hr_name, hr_email, hr_mobile, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                company_code,
                name,
                industry,
                data.get("website") or None,
                location,
                data.get("company_type") or "MNC",
                hr_name,
                data.get("hr_email") or None,
                data.get("hr_mobile") or None,
                data.get("status", "ACTIVE"),
            ),
        )
        _activity("Companies", "Created", company_code, f"Added {name} as a hiring company.")
        commit()
        return jsonify({"item": _find_one("SELECT * FROM companies WHERE company_id = ?", (company_id,))}), 201

    @app.patch("/api/companies/<int:company_id>")
    @_user_required
    def update_company(company_id):
        _require_roles("ADMIN")
        data = _body()
        status = _required(data, "status", "Company status").upper()
        if status not in {"ACTIVE", "INACTIVE"}:
            raise APIError("Choose a valid company status.")
        company = _find_one("SELECT company_code, company_name FROM companies WHERE company_id = ?", (company_id,))
        if not company:
            raise APIError("Company not found.", 404)
        if set(data) == {"status"}:
            execute("UPDATE companies SET status = ? WHERE company_id = ?", (status, company_id))
            description = f"{company['company_name']} status changed to {status}."
        else:
            name = _required(data, "company_name", "Company name")
            industry = _required(data, "industry", "Industry")
            location = _required(data, "location", "Location")
            hr_name = _required(data, "hr_name", "HR name")
            execute(
                """UPDATE companies SET company_name = ?, industry = ?, website = ?, location = ?,
                   company_type = ?, hr_name = ?, hr_email = ?, hr_mobile = ?, status = ?
                   WHERE company_id = ?""",
                (
                    name, industry, data.get("website") or None, location,
                    data.get("company_type") or "MNC", hr_name,
                    data.get("hr_email") or None, data.get("hr_mobile") or None,
                    status, company_id,
                ),
            )
            description = f"Updated the company profile for {name}."
        _activity("Companies", "Updated", company["company_code"], description)
        commit()
        return jsonify({"status": status})

    @app.get("/api/jobs")
    @_user_required
    def jobs():
        search = f"%{request.args.get('q', '').strip()}%"
        status = request.args.get("status", "").strip()
        job_filter, job_params = _job_scope("j")
        application_filter, application_params = _application_scope("a")
        rows, _, _ = execute(
            """SELECT j.*, co.company_name,
                      (SELECT GROUP_CONCAT(s.skill_name) FROM job_skills js
                       JOIN skills s ON s.skill_id = js.skill_id WHERE js.job_id = j.job_id) AS required_skills,
                      (SELECT s.skill_name FROM job_skills js JOIN skills s ON s.skill_id = js.skill_id
                       WHERE js.job_id = j.job_id AND js.is_primary = 1 LIMIT 1) AS primary_technology,
                      (SELECT COUNT(*) FROM applications a WHERE a.job_id = j.job_id AND """ + application_filter + """) AS applications_count
               FROM jobs j JOIN companies co ON co.company_id = j.company_id
               WHERE """ + job_filter + """ AND
                 (j.job_code LIKE ? OR j.job_title LIKE ? OR co.company_name LIKE ? OR j.location LIKE ?)
                 AND (? = '' OR j.status = ?)
               ORDER BY j.created_at DESC, j.job_id DESC""",
            (*application_params, *job_params, search, search, search, search, status, status),
        )
        return jsonify({"items": rows})

    @app.post("/api/jobs")
    @_user_required
    def create_job():
        _require_roles("ADMIN", "RECRUITER")
        data = _body()
        company_id = _number(data, "company_id", "Company", 1)
        company = _find_one("SELECT company_id FROM companies WHERE company_id = ? AND status = 'ACTIVE'", (company_id,))
        if not company:
            raise APIError("Choose an active company.")
        title = _required(data, "job_title", "Job title")
        location = _required(data, "location", "Location")
        openings = _number(data, "openings", "Number of openings", 1)
        posted_date = _date(data.get("posted_date"), "Posted date")
        deadline = _date(data.get("application_deadline"), "Application deadline")
        if deadline < posted_date:
            raise APIError("Application deadline cannot be before posted date.")
        minimum = _number(data, "min_package_lpa", "Minimum package", 0, optional=True)
        maximum = _number(data, "max_package_lpa", "Maximum package", 0, optional=True)
        if minimum is not None and maximum is not None and minimum > maximum:
            raise APIError("Minimum package cannot exceed maximum package.")
        min_year = _number(data, "min_passing_year", "Minimum passing year", 1990, 2100, optional=True)
        max_year = _number(data, "max_passing_year", "Maximum passing year", 1990, 2100, optional=True)
        if min_year and max_year and min_year > max_year:
            raise APIError("Minimum passing year cannot be after maximum passing year.")
        required_technology = _required(data, "required_technology", "Required technology")
        job_code = _code("JOB", "jobs", width=3)
        _, job_id, _ = execute(
            """INSERT INTO jobs
               (job_code, company_id, job_title, employment_type, location, openings, min_package_lpa,
                max_package_lpa, min_percentage, min_passing_year, max_passing_year, max_backlogs,
                qualification_rule, posted_date, application_deadline, status, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                job_code,
                company_id,
                title,
                data.get("employment_type", "FULL_TIME"),
                location,
                openings,
                minimum,
                maximum,
                _number(data, "min_percentage", "Minimum percentage", 0, 100, optional=True),
                min_year,
                max_year,
                _number(data, "max_backlogs", "Maximum backlogs", 0),
                data.get("qualification_rule") or None,
                posted_date,
                deadline,
                data.get("status", "OPEN"),
                session.get("user_id"),
            ),
        )
        _save_job_skills(job_id, required_technology, data.get("required_skills"))
        _activity("Jobs", "Created", job_code, f"Posted {title} at {location}.")
        commit()
        return jsonify({"item": _find_one("SELECT * FROM jobs WHERE job_id = ?", (job_id,))}), 201

    @app.patch("/api/jobs/<int:job_id>")
    @_user_required
    def update_job(job_id):
        _require_roles("ADMIN", "RECRUITER")
        data = _body()
        status = _required(data, "status", "Job status").upper()
        if status not in {"DRAFT", "OPEN", "CLOSED", "CANCELLED"}:
            raise APIError("Choose a valid job status.")
        job = _find_one("SELECT job_code, job_title, created_by FROM jobs WHERE job_id = ?", (job_id,))
        if not job:
            raise APIError("Job not found.", 404)
        if session.get("role") == "RECRUITER" and job["created_by"] != session.get("user_id"):
            raise APIError("Job not found.", 404)
        if set(data) == {"status"}:
            execute("UPDATE jobs SET status = ? WHERE job_id = ?", (status, job_id))
            description = f"Job status changed to {status}."
        else:
            company_id = _number(data, "company_id", "Company", 1)
            company = _find_one("SELECT company_id FROM companies WHERE company_id = ? AND status = 'ACTIVE'", (company_id,))
            if not company:
                raise APIError("Choose an active company.")
            title = _required(data, "job_title", "Job title")
            location = _required(data, "location", "Location")
            openings = _number(data, "openings", "Number of openings", 1)
            posted_date = _date(data.get("posted_date"), "Posted date")
            deadline = _date(data.get("application_deadline"), "Application deadline")
            if deadline < posted_date:
                raise APIError("Application deadline cannot be before posted date.")
            minimum = _number(data, "min_package_lpa", "Minimum package", 0, optional=True)
            maximum = _number(data, "max_package_lpa", "Maximum package", 0, optional=True)
            if minimum is not None and maximum is not None and minimum > maximum:
                raise APIError("Minimum package cannot exceed maximum package.")
            min_year = _number(data, "min_passing_year", "Minimum passing year", 1990, 2100, optional=True)
            max_year = _number(data, "max_passing_year", "Maximum passing year", 1990, 2100, optional=True)
            if min_year and max_year and min_year > max_year:
                raise APIError("Minimum passing year cannot be after maximum passing year.")
            technology = _required(data, "required_technology", "Required technology")
            execute(
                """UPDATE jobs SET company_id = ?, job_title = ?, employment_type = ?, location = ?,
                   openings = ?, min_package_lpa = ?, max_package_lpa = ?, min_percentage = ?,
                   min_passing_year = ?, max_passing_year = ?, max_backlogs = ?, qualification_rule = ?,
                   posted_date = ?, application_deadline = ?, status = ? WHERE job_id = ?""",
                (
                    company_id, title, data.get("employment_type", "FULL_TIME"), location,
                    openings, minimum, maximum,
                    _number(data, "min_percentage", "Minimum percentage", 0, 100, optional=True),
                    min_year, max_year, _number(data, "max_backlogs", "Maximum backlogs", 0),
                    data.get("qualification_rule") or None, posted_date, deadline, status, job_id,
                ),
            )
            _save_job_skills(job_id, technology, data.get("required_skills"))
            description = f"Updated the job profile for {title}."
        _activity("Jobs", "Updated", job["job_code"], description)
        commit()
        return jsonify({"status": status})

    @app.get("/api/applications")
    @_user_required
    def applications():
        status = request.args.get("status", "").strip()
        search = f"%{request.args.get('q', '').strip()}%"
        application_filter, application_params = _application_scope("a")
        rows, _, _ = execute(
            """SELECT a.*, c.full_name AS candidate, c.candidate_code, c.primary_technology,
                      j.job_code, j.job_title, co.company_name, j.location,
                      (SELECT COUNT(*) FROM interview_rounds i WHERE i.application_id = a.application_id) AS interview_count
               FROM applications a JOIN candidates c ON c.candidate_id = a.candidate_id
               JOIN jobs j ON j.job_id = a.job_id JOIN companies co ON co.company_id = j.company_id
               WHERE """ + application_filter + """ AND
                 (a.application_code LIKE ? OR c.full_name LIKE ? OR j.job_title LIKE ? OR co.company_name LIKE ?)
                 AND (? = '' OR a.application_status = ?)
               ORDER BY a.applied_at DESC, a.application_id DESC""",
            (*application_params, search, search, search, search, status, status),
        )
        return jsonify({"items": rows})

    @app.post("/api/applications")
    @_user_required
    def create_application():
        _require_roles("ADMIN", "RECRUITER")
        data = _body()
        candidate_id = _number(data, "candidate_id", "Candidate", 1)
        job_id = _number(data, "job_id", "Job", 1)
        candidate = _visible_candidate(candidate_id)
        job_filter, job_params = _job_scope("j")
        job = _find_one(
            f"SELECT j.* FROM jobs j WHERE j.job_id = ? AND {job_filter}",
            (job_id, *job_params),
        )
        if not candidate or not job:
            raise APIError("Choose a valid candidate and job.")
        if job["status"] != "OPEN":
            raise APIError("Applications can only be created for open jobs.")
        today = date.today().isoformat()
        if job["application_deadline"] < today:
            raise APIError("The application deadline for this job has passed.")
        reasons = []
        if candidate["profile_status"] != "ACTIVE":
            reasons.append("candidate profile is not active")
        if job["min_percentage"] is not None and (candidate["percentage"] or 0) < job["min_percentage"]:
            reasons.append(f"percentage is below {job['min_percentage']}%")
        if candidate["backlog_count"] > job["max_backlogs"]:
            reasons.append(f"backlogs exceed the allowed {job['max_backlogs']}")
        if job["min_passing_year"] and candidate["passing_year"] < job["min_passing_year"]:
            reasons.append(f"passing year must be {job['min_passing_year']} or later")
        if job["max_passing_year"] and candidate["passing_year"] > job["max_passing_year"]:
            reasons.append(f"passing year must be {job['max_passing_year']} or earlier")
        if job["qualification_rule"] and job["qualification_rule"].lower() not in candidate["qualification"].lower():
            reasons.append(f"qualification must match {job['qualification_rule']}")
        required_skills, _, _ = execute(
            """SELECT s.skill_name FROM job_skills js
               JOIN skills s ON s.skill_id = js.skill_id
               WHERE js.job_id = ? AND js.mandatory_flag = 1""",
            (job_id,),
        )
        candidate_skills, _, _ = execute(
            """SELECT s.skill_name FROM candidate_skills cs
               JOIN skills s ON s.skill_id = cs.skill_id
               WHERE cs.candidate_id = ?""",
            (candidate_id,),
        )
        available_skills = {row["skill_name"].casefold() for row in candidate_skills}
        if candidate["primary_technology"]:
            available_skills.add(candidate["primary_technology"].casefold())
        missing_skills = [
            row["skill_name"] for row in required_skills
            if row["skill_name"].casefold() not in available_skills
        ]
        if missing_skills:
            reasons.append(f"missing required skills: {', '.join(missing_skills)}")
        eligibility = "NOT_ELIGIBLE" if reasons else "ELIGIBLE"
        app_code = _code("APP", "applications")
        _, application_id, _ = execute(
            """INSERT INTO applications
               (application_code, candidate_id, job_id, eligibility_status, eligibility_reason,
                application_status, source, assigned_recruiter_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                app_code,
                candidate_id,
                job_id,
                eligibility,
                "; ".join(reasons) or "Meets the job eligibility criteria.",
                "APPLIED" if reasons else "ELIGIBILITY_VERIFIED",
                data.get("source", "Recruiter"),
                session.get("user_id"),
            ),
        )
        _activity("Applications", "Created", app_code, f"Application created for {candidate['full_name']} at job {job['job_code']}.")
        commit()
        return jsonify({"item": _find_one("SELECT * FROM applications WHERE application_id = ?", (application_id,))}), 201

    @app.patch("/api/applications/<int:application_id>/status")
    @_user_required
    def update_application_status(application_id):
        _require_roles("ADMIN", "RECRUITER")
        data = _body()
        status = _required(data, "status", "Application status").upper()
        if status not in ALLOWED_APPLICATION_STATUSES:
            raise APIError("Choose a valid application status.")
        if session.get("role") == "RECRUITER" and status in {"OFFERED", "JOINED"}:
            raise APIError("Only placement staff can update offer and joining statuses.", 403)
        application = _visible_application(application_id)
        if not application:
            raise APIError("Application not found.", 404)
        if status in {"SHORTLISTED", "INTERVIEW_SCHEDULED", "SELECTED"} and application["eligibility_status"] != "ELIGIBLE":
            raise APIError("This candidate does not meet the eligibility criteria.")
        old_status = application["application_status"]
        execute(
            "UPDATE applications SET application_status = ?, updated_at = CURRENT_TIMESTAMP WHERE application_id = ?",
            (status, application_id),
        )
        execute(
            """INSERT INTO application_history
               (application_id, old_status, new_status, remarks, changed_by)
               VALUES (?, ?, ?, ?, ?)""",
            (application_id, old_status, status, data.get("remarks") or None, session.get("user_id")),
        )
        _activity("Applications", "Status changed", application["application_code"], f"{old_status} -> {status}.")
        commit()
        return jsonify({"status": status})

    @app.get("/api/applications/<int:application_id>/history")
    @_user_required
    def application_history(application_id):
        if not _visible_application(application_id):
            raise APIError("Application not found.", 404)
        rows, _, _ = execute(
            """SELECT h.*, u.full_name AS changed_by_name FROM application_history h
               LEFT JOIN users u ON u.user_id = h.changed_by
               WHERE h.application_id = ? ORDER BY h.changed_at DESC, h.history_id DESC""",
            (application_id,),
        )
        return jsonify({"items": rows})

    @app.get("/api/interviews")
    @_user_required
    def interviews():
        search = f"%{request.args.get('q', '').strip()}%"
        application_filter, application_params = _application_scope("a")
        rows, _, _ = execute(
            """SELECT i.*, a.application_code, a.application_status, c.full_name AS candidate,
                      c.candidate_code, j.job_title, co.company_name,
                      f.overall_rating, f.recommendation
               FROM interview_rounds i JOIN applications a ON a.application_id = i.application_id
               JOIN candidates c ON c.candidate_id = a.candidate_id
               JOIN jobs j ON j.job_id = a.job_id JOIN companies co ON co.company_id = j.company_id
               LEFT JOIN interview_feedback f ON f.interview_id = i.interview_id
               WHERE """ + application_filter + """ AND
                 (c.full_name LIKE ? OR co.company_name LIKE ? OR j.job_title LIKE ?)
               ORDER BY i.scheduled_date DESC, i.scheduled_time DESC""",
            (*application_params, search, search, search),
        )
        return jsonify({"items": rows})

    @app.post("/api/interviews")
    @_user_required
    def create_interview():
        _require_roles("ADMIN", "RECRUITER")
        data = _body()
        application_id = _number(data, "application_id", "Application", 1)
        application = _visible_application(application_id)
        if not application:
            raise APIError("Choose a valid application.")
        if application["eligibility_status"] != "ELIGIBLE" or application["application_status"] in {"REJECTED", "WITHDRAWN"}:
            raise APIError("Only eligible, active applications can be scheduled.")
        scheduled_date = _date(data.get("scheduled_date"), "Interview date")
        if scheduled_date < date.today().isoformat():
            raise APIError("Interview date cannot be in the past.")
        round_type = _required(data, "round_type", "Interview round")
        mode = _required(data, "mode", "Interview mode").upper()
        if mode not in {"ONLINE", "OFFLINE", "TELEPHONIC"}:
            raise APIError("Choose a valid interview mode.")
        previous = execute("SELECT COALESCE(MAX(round_number), 0) AS total FROM interview_rounds WHERE application_id = ?", (application_id,))[0][0]["total"]
        _, interview_id, _ = execute(
            """INSERT INTO interview_rounds
               (application_id, round_number, round_type, scheduled_date, scheduled_time, mode,
                interviewer_name, meeting_or_location, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'SCHEDULED')""",
            (
                application_id,
                previous + 1,
                round_type,
                scheduled_date,
                data.get("scheduled_time") or None,
                mode,
                data.get("interviewer_name") or None,
                data.get("meeting_or_location") or None,
            ),
        )
        execute(
            "UPDATE applications SET application_status = 'INTERVIEW_SCHEDULED', updated_at = CURRENT_TIMESTAMP WHERE application_id = ?",
            (application_id,),
        )
        execute(
            """INSERT INTO application_history (application_id, old_status, new_status, remarks, changed_by)
               VALUES (?, ?, 'INTERVIEW_SCHEDULED', 'Interview scheduled.', ?)""",
            (application_id, application["application_status"], session.get("user_id")),
        )
        _activity("Interviews", "Scheduled", interview_id, f"{round_type} interview scheduled for {scheduled_date}.")
        commit()
        return jsonify({"item": _find_one("SELECT * FROM interview_rounds WHERE interview_id = ?", (interview_id,))}), 201

    @app.patch("/api/interviews/<int:interview_id>/status")
    @_user_required
    def update_interview(interview_id):
        _require_roles("ADMIN", "RECRUITER")
        status = _required(_body(), "status", "Interview status").upper()
        if status not in {"SCHEDULED", "RESCHEDULED", "CANCELLED", "NO_SHOW"}:
            raise APIError("Use the feedback form to complete an interview.")
        interview = _find_one(
            "SELECT application_id FROM interview_rounds WHERE interview_id = ?",
            (interview_id,),
        )
        if not interview or not _visible_application(interview["application_id"]):
            raise APIError("Interview not found.", 404)
        _, _, count = execute("UPDATE interview_rounds SET status = ? WHERE interview_id = ?", (status, interview_id))
        if not count:
            raise APIError("Interview not found.", 404)
        commit()
        return jsonify({"status": status})

    @app.post("/api/interviews/<int:interview_id>/feedback")
    @_user_required
    def save_feedback(interview_id):
        _require_roles("ADMIN", "RECRUITER")
        data = _body()
        interview = _find_one("SELECT * FROM interview_rounds WHERE interview_id = ?", (interview_id,))
        if not interview or not _visible_application(interview["application_id"]):
            raise APIError("Interview not found.", 404)
        recommendation = _required(data, "recommendation", "Interview result").upper()
        if recommendation not in {"NEXT_ROUND", "SELECTED", "REJECTED", "ON_HOLD"}:
            raise APIError("Choose a valid interview result.")
        ratings = [
            _number(data, field, label, 0, 5, optional=True)
            for field, label in (
                ("technical_rating", "Technical rating"),
                ("communication_rating", "Communication rating"),
                ("problem_solving_rating", "Problem-solving rating"),
                ("overall_rating", "Overall rating"),
            )
        ]
        existing = _find_one("SELECT feedback_id FROM interview_feedback WHERE interview_id = ?", (interview_id,))
        if existing:
            execute(
                """UPDATE interview_feedback SET technical_rating = ?, communication_rating = ?,
                   problem_solving_rating = ?, overall_rating = ?, recommendation = ?, remarks = ?,
                   submitted_by = ?, submitted_at = CURRENT_TIMESTAMP WHERE interview_id = ?""",
                (*ratings, recommendation, data.get("remarks") or None, session.get("user_id"), interview_id),
            )
        else:
            execute(
                """INSERT INTO interview_feedback
                   (interview_id, technical_rating, communication_rating, problem_solving_rating,
                    overall_rating, recommendation, remarks, submitted_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (interview_id, *ratings, recommendation, data.get("remarks") or None, session.get("user_id")),
            )
        execute("UPDATE interview_rounds SET status = 'COMPLETED' WHERE interview_id = ?", (interview_id,))
        app_status = {
            "SELECTED": "SELECTED",
            "REJECTED": "REJECTED",
            "ON_HOLD": "ELIGIBILITY_VERIFIED",
            "NEXT_ROUND": "INTERVIEWED",
        }[recommendation]
        application = _find_one("SELECT application_status FROM applications WHERE application_id = ?", (interview["application_id"],))
        execute(
            "UPDATE applications SET application_status = ?, updated_at = CURRENT_TIMESTAMP WHERE application_id = ?",
            (app_status, interview["application_id"]),
        )
        execute(
            """INSERT INTO application_history (application_id, old_status, new_status, remarks, changed_by)
               VALUES (?, ?, ?, ?, ?)""",
            (interview["application_id"], application["application_status"], app_status, data.get("remarks") or recommendation, session.get("user_id")),
        )
        commit()
        return jsonify({"status": "saved", "application_status": app_status})

    @app.get("/api/placements")
    @_user_required
    def placements():
        _require_roles("ADMIN", "PLACEMENT_OFFICER")
        application_filter, application_params = _application_scope("a")
        rows, _, _ = execute(
            """SELECT o.offer_id, o.offer_code, o.application_id, o.designation,
                      o.offered_package_lpa, o.offer_date, o.expected_joining_date, o.offer_status,
                      a.application_code, a.application_status, c.candidate_id, c.full_name AS candidate,
                      co.company_name, j.job_title, p.placement_id, p.joining_status, p.actual_joining_date
               FROM offers o JOIN applications a ON a.application_id = o.application_id
               JOIN candidates c ON c.candidate_id = a.candidate_id
               JOIN jobs j ON j.job_id = a.job_id JOIN companies co ON co.company_id = j.company_id
               LEFT JOIN placements p ON p.offer_id = o.offer_id
               WHERE """ + application_filter + """
               ORDER BY o.created_at DESC""",
            application_params,
        )
        return jsonify({"items": rows})

    @app.post("/api/offers")
    @_user_required
    def create_offer():
        _require_roles("ADMIN", "PLACEMENT_OFFICER")
        data = _body()
        application_id = _number(data, "application_id", "Application", 1)
        application = _visible_application(application_id)
        if not application or application["application_status"] != "SELECTED":
            raise APIError("An offer can only be created for a selected application.")
        designation = _required(data, "designation", "Designation")
        package = _number(data, "offered_package_lpa", "Offered package", 0.01)
        offer_date = _date(data.get("offer_date"), "Offer date")
        joining = _date(data.get("expected_joining_date"), "Expected joining date", required=False)
        offer_code = _code("OFR", "offers")
        _, offer_id, _ = execute(
            """INSERT INTO offers
               (offer_code, application_id, designation, offered_package_lpa, offer_date,
                expected_joining_date, offer_status, remarks)
               VALUES (?, ?, ?, ?, ?, ?, 'OFFERED', ?)""",
            (offer_code, application_id, designation, package, offer_date, joining, data.get("remarks") or None),
        )
        execute(
            "UPDATE applications SET application_status = 'OFFERED', updated_at = CURRENT_TIMESTAMP WHERE application_id = ?",
            (application_id,),
        )
        execute(
            """INSERT INTO application_history (application_id, old_status, new_status, remarks, changed_by)
               VALUES (?, 'SELECTED', 'OFFERED', 'Offer created.', ?)""",
            (application_id, session.get("user_id")),
        )
        _activity("Placement", "Offer created", offer_code, f"Offer issued for {designation}.")
        commit()
        return jsonify({"item": _find_one("SELECT * FROM offers WHERE offer_id = ?", (offer_id,))}), 201

    @app.patch("/api/offers/<int:offer_id>")
    @_user_required
    def update_offer(offer_id):
        _require_roles("ADMIN", "PLACEMENT_OFFICER")
        status = _required(_body(), "offer_status", "Offer status").upper()
        if status not in {"OFFERED", "ACCEPTED", "REJECTED", "EXPIRED", "WITHDRAWN"}:
            raise APIError("Choose a valid offer status.")
        application_filter, application_params = _application_scope("a")
        offer = _find_one(
            f"""SELECT o.offer_code FROM offers o JOIN applications a
                ON a.application_id = o.application_id
                WHERE o.offer_id = ? AND {application_filter}""",
            (offer_id, *application_params),
        )
        if not offer:
            raise APIError("Offer not found.", 404)
        execute("UPDATE offers SET offer_status = ? WHERE offer_id = ?", (status, offer_id))
        _activity("Placement", "Offer status changed", offer["offer_code"], f"Offer status changed to {status}.")
        commit()
        return jsonify({"status": status})

    @app.post("/api/placements/<int:offer_id>")
    @_user_required
    def confirm_placement(offer_id):
        _require_roles("ADMIN", "PLACEMENT_OFFICER")
        data = _body()
        application_filter, application_params = _application_scope("a")
        offer = _find_one(
            f"""SELECT o.*, a.candidate_id, a.job_id, j.company_id
               FROM offers o JOIN applications a ON a.application_id = o.application_id
               JOIN jobs j ON j.job_id = a.job_id
               WHERE o.offer_id = ? AND {application_filter}""",
            (offer_id, *application_params),
        )
        if not offer or offer["offer_status"] != "ACCEPTED":
            raise APIError("The offer must be accepted before confirming placement.")
        if _find_one("SELECT placement_id FROM placements WHERE offer_id = ?", (offer_id,)):
            raise APIError("A placement already exists for this offer.", 409)
        joining_status = _required(data, "joining_status", "Joining status").upper()
        if joining_status not in {"JOINED", "NOT_JOINED", "DEFERRED", "NO_SHOW"}:
            raise APIError("Choose a valid joining status.")
        actual_date = _date(data.get("actual_joining_date"), "Actual joining date", required=False)
        if joining_status == "JOINED" and not actual_date:
            raise APIError("Actual joining date is required when the candidate has joined.")
        _, placement_id, _ = execute(
            """INSERT INTO placements
               (candidate_id, company_id, job_id, offer_id, designation, final_package_lpa,
                expected_joining_date, actual_joining_date, joining_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                offer["candidate_id"],
                offer["company_id"],
                offer["job_id"],
                offer_id,
                offer["designation"],
                offer["offered_package_lpa"],
                offer["expected_joining_date"],
                actual_date,
                joining_status,
            ),
        )
        application = _find_one("SELECT application_id, application_status FROM applications WHERE application_id = ?", (offer["application_id"],))
        next_status = "JOINED" if joining_status == "JOINED" else "OFFERED"
        execute("UPDATE candidates SET placement_status = ?, updated_at = CURRENT_TIMESTAMP WHERE candidate_id = ?", ("PLACED" if joining_status == "JOINED" else "NOT_PLACED", offer["candidate_id"]))
        execute("UPDATE applications SET application_status = ?, updated_at = CURRENT_TIMESTAMP WHERE application_id = ?", (next_status, application["application_id"]))
        execute(
            """INSERT INTO application_history (application_id, old_status, new_status, remarks, changed_by)
               VALUES (?, ?, ?, ?, ?)""",
            (application["application_id"], application["application_status"], next_status, f"Placement status: {joining_status}.", session.get("user_id")),
        )
        _activity("Placement", "Placement confirmed", offer["offer_code"], f"Joining outcome: {joining_status}.")
        commit()
        return jsonify({"placement_id": placement_id, "joining_status": joining_status}), 201

    @app.get("/api/reports")
    @_user_required
    def reports():
        _require_roles("ADMIN")
        funnel, _, _ = execute(
            """SELECT application_status AS label, COUNT(*) AS total
               FROM applications GROUP BY application_status"""
        )
        by_company, _, _ = execute(
            """SELECT co.company_name AS label, COUNT(p.placement_id) AS total
               FROM companies co LEFT JOIN placements p ON p.company_id = co.company_id AND p.joining_status = 'JOINED'
               GROUP BY co.company_id, co.company_name ORDER BY total DESC, label LIMIT 8"""
        )
        by_technology, _, _ = execute(
            """SELECT c.primary_technology AS label, COUNT(p.placement_id) AS total
               FROM candidates c LEFT JOIN placements p ON p.candidate_id = c.candidate_id AND p.joining_status = 'JOINED'
               WHERE c.primary_technology IS NOT NULL
               GROUP BY c.primary_technology ORDER BY total DESC, label"""
        )
        by_recruiter, _, _ = execute(
            """SELECT u.full_name AS label, COUNT(a.application_id) AS total
               FROM users u LEFT JOIN applications a ON a.assigned_recruiter_id = u.user_id
               WHERE u.role_id = (SELECT role_id FROM roles WHERE role_code = 'RECRUITER')
               GROUP BY u.user_id, u.full_name ORDER BY total DESC"""
        )
        counts = {
            "applications": execute("SELECT COUNT(*) AS total FROM applications")[0][0]["total"],
            "interviews": execute("SELECT COUNT(*) AS total FROM interview_rounds")[0][0]["total"],
            "selected": execute("SELECT COUNT(*) AS total FROM applications WHERE application_status IN ('SELECTED', 'OFFERED', 'JOINED')")[0][0]["total"],
            "joined": execute("SELECT COUNT(*) AS total FROM placements WHERE joining_status = 'JOINED'")[0][0]["total"],
            "offers": execute("SELECT COUNT(*) AS total FROM offers")[0][0]["total"],
            "accepted_offers": execute("SELECT COUNT(*) AS total FROM offers WHERE offer_status = 'ACCEPTED'")[0][0]["total"],
        }
        counts["placement_rate"] = round(counts["joined"] / counts["applications"] * 100, 1) if counts["applications"] else 0
        pending, _, _ = execute(
            """SELECT i.scheduled_date, i.scheduled_time, i.round_type, c.full_name AS candidate,
                      co.company_name, j.job_title
               FROM interview_rounds i JOIN applications a ON a.application_id = i.application_id
               JOIN candidates c ON c.candidate_id = a.candidate_id
               JOIN jobs j ON j.job_id = a.job_id JOIN companies co ON co.company_id = j.company_id
               WHERE i.status = 'SCHEDULED' ORDER BY i.scheduled_date, i.scheduled_time LIMIT 8"""
        )
        aging, _, _ = execute(
            """SELECT j.job_code, j.job_title, co.company_name, j.posted_date,
                      j.application_deadline, j.openings,
                      CAST(julianday('now') - julianday(j.posted_date) AS INTEGER) AS age_days
               FROM jobs j JOIN companies co ON co.company_id = j.company_id
               WHERE j.status = 'OPEN' ORDER BY j.posted_date LIMIT 8"""
        ) if _is_sqlite() else ([], None, None)
        if not _is_sqlite():
            aging, _, _ = execute(
                """SELECT j.job_code, j.job_title, co.company_name, j.posted_date,
                          j.application_deadline, j.openings,
                          DATEDIFF(CURRENT_DATE, j.posted_date) AS age_days
                   FROM jobs j JOIN companies co ON co.company_id = j.company_id
                   WHERE j.status = 'OPEN' ORDER BY j.posted_date LIMIT 8"""
            )
        return jsonify(
            {
                "counts": counts,
                "funnel": funnel,
                "companies": by_company,
                "technologies": by_technology,
                "recruiters": by_recruiter,
                "pending_interviews": pending,
                "job_aging": aging,
            }
        )

    return app


def _current_user():
    return {
        "id": session.get("user_id"),
        "name": session.get("name"),
        "email": session.get("email"),
        "role": session.get("role"),
        "role_name": session.get("role_name"),
    }


def initialize_database(app=None):
    application = app or create_app()
    with application.app_context():
        connection = get_db()
        schema_name = "sqlite_schema.sql" if isinstance(connection, sqlite3.Connection) else "mysql_schema.sql"
        schema = (ROOT / "database" / schema_name).read_text(encoding="utf-8")
        if isinstance(connection, sqlite3.Connection):
            connection.executescript(schema)
            job_skill_columns = {row["name"] for row in connection.execute("PRAGMA table_info(job_skills)")}
            if "is_primary" not in job_skill_columns:
                connection.execute("ALTER TABLE job_skills ADD COLUMN is_primary INTEGER NOT NULL DEFAULT 0")
            candidate_columns = {row["name"] for row in connection.execute("PRAGMA table_info(candidates)")}
            if "created_by" not in candidate_columns:
                connection.execute("ALTER TABLE candidates ADD COLUMN created_by INTEGER REFERENCES users(user_id)")
        else:
            cursor = connection.cursor()
            for statement in schema.split(";"):
                if statement.strip():
                    cursor.execute(statement)
            cursor.execute("SHOW COLUMNS FROM job_skills LIKE 'is_primary'")
            if not cursor.fetchall():
                cursor.execute("ALTER TABLE job_skills ADD COLUMN is_primary TINYINT(1) NOT NULL DEFAULT 0")
            cursor.execute("SHOW COLUMNS FROM candidates LIKE 'created_by'")
            if not cursor.fetchall():
                cursor.execute("ALTER TABLE candidates ADD COLUMN created_by INT NULL")
            cursor.close()
        cursor = connection.cursor()
        cursor.execute(
            """SELECT job_id, MIN(job_skill_id), COUNT(*)
               FROM job_skills GROUP BY job_id"""
        )
        update_primary = (
            "UPDATE job_skills SET is_primary = 1 WHERE job_skill_id = ? AND is_primary = 0"
            if isinstance(connection, sqlite3.Connection)
            else "UPDATE job_skills SET is_primary = 1 WHERE job_skill_id = %s AND is_primary = 0"
        )
        for job_id, skill_id, skill_count in cursor.fetchall():
            if skill_count == 1:
                cursor.execute(update_primary, (skill_id,))
        cursor.close()
        connection.commit()


app = create_app()


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
