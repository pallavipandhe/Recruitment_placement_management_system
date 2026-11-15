# Orbit Hire — Recruitment & Placement Management System

A responsive, full-stack recruitment workspace based on the two project specifications in this folder. It includes a Flask API, a MySQL-ready relational schema, a zero-setup SQLite demo mode, and an interactive browser UI.

## Run on Windows

1. Install Python 3.10+ and MySQL 8+ (MySQL is optional for the local demo).
2. Double-click `run.bat`, or run these commands from this folder:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   Copy-Item .env.example .env
   python seed.py
   python -m flask --app app run
   ```

3. Open [http://127.0.0.1:5000](http://127.0.0.1:5000).

The default SQLite database is created at `instance/recruitment.db`. To use MySQL, create a database, update `DATABASE_URL` in `.env` with your own connection details, then run `python seed.py`. The MySQL schema is in `database/mysql_schema.sql`.

## Demo sign-in

Recruiters can create their own account from the login page or sign in with their registered email and password, so activity remains associated with their account. Public registration creates recruiter accounts only; Admin and Placement accounts are managed separately. The demo database includes two recruiter accounts; all demo accounts use the password `demo123`. On the login screen, choose Admin or Placement to fill in the matching demo account.

| Role | Email |
|---|---|
| Recruiter | `recruiter@demo.com`, `rohan.recruiter@demo.com` |
| Administrator | `admin@demo.com` |
| Placement officer | `placement@demo.com` |

## Included screens

The shared responsive workspace provides routes for login, dashboard, candidate list/form/details, company directory, job list/form, applications, interviews, offer/placement management, and reports. The sidebar has its own scrollable navigation area on shorter screens, and sign-out is available from the top bar and profile dialog on desktop and mobile. Search, forms, status transitions, tables, dialogs, CSV exports, and responsive layouts are interactive.

## Role-based data access

- Admins can view and manage the full workspace, including reports.
- Recruiters see candidates they created or candidates attached to their assigned applications. Their application and interview lists are limited to their own assignments. Open job postings and active companies are shared reference data; recruiters can only edit jobs they created.
- Placement officers see candidates and applications that have reached selection, offer, or joining, and can manage offers and placement outcomes. They cannot browse the recruiter workspace or reports.
- Recruiters cannot access placement records or reports. The API enforces the same restrictions as the role-specific navigation and dashboard.
- Existing databases are migrated on startup to record candidate ownership. Legacy candidates without an owner remain available to admins and to recruiters with an assigned application for that candidate.

## Recruitment workflows

- Candidate records validate email, 10-digit mobile, academic scores, unique identifiers, and soft deactivation.
- Jobs validate openings, compensation ranges, dates, eligibility cutoffs, and active companies.
- Applications reject duplicates and check profile, qualification, passing-year, backlog, and percentage criteria.
- Application status changes are recorded in an audit history.
- Interview rounds prevent duplicate round numbers; feedback is limited to 0–5 and updates the application pipeline.
- Offers require a selected application; placement confirmation requires an accepted offer and updates candidate, application, and history records in one transaction.
- The database includes all 17 tables, foreign keys, uniqueness rules, indexes, and status constraints described in the database design.

## Project layout

```text
app.py                      Flask application and JSON API
seed.py                     Schema setup and realistic demo data
database/mysql_schema.sql   MySQL 8 schema
database/sqlite_schema.sql  Local demo schema
templates/index.html        Shared application shell and login screen
static/css/style.css        Responsive UI styles
static/js/app.js            Navigation, rendering, forms, and API client
tests/test_app.py           API and workflow tests
```

The demo seed creates 3 roles, 5 users, 30 candidates, 12 skills, 8 companies, 12 jobs, 45 applications, 20 interview rounds, feedback, offers, and placement records. Running the seed again does not overwrite existing data.

## Tests

```powershell
python -m unittest discover -s tests -v
```
