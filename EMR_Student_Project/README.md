# CareTrack EMR — Student Project

A working learning prototype for the proposed cloud-based Electronic Medical Records project. It includes a Flask backend, HTML/CSS frontend, SQLite database, login, role restrictions, patient registration/search/profiles, visit records, medicine inventory, basic reports, administrator user management and audit events.

**Prototype warning:** This is not production healthcare software. Use fictional data only. It has not undergone an independent security review and must not be used to store real patient records.

## Run on Windows / VS Code
1. Extract the ZIP to a normal folder and open it in VS Code.
2. Open Terminal → New Terminal.
3. Create a virtual environment: `py -m venv .venv`
4. Activate in PowerShell: `.\.venv\Scripts\Activate.ps1` (or in Command Prompt: `.venv\Scripts\activate.bat`).
5. Install dependencies: `python -m pip install -r requirements.txt`
6. Run: `python app.py`
7. Open `http://127.0.0.1:5000` in your browser.

## Demo accounts
Created automatically the first time the app runs:

| Role | Username | Password |
|---|---|---|
| Administrator | `admin` | `Admin123!` |
| Receptionist | `reception` | `Reception123!` |
| Clinician | `clinician` | `Clinician123!` |
| Pharmacist | `pharmacy` | `Pharmacy123!` |

Change/remove demo accounts before deployment. The SQLite database `emr.db` is generated automatically. To reset demo data, stop the app and delete `emr.db`, then restart (this permanently deletes local records).

## Modules
- Landing page and login/logout
- Password hashing and basic role-based page restrictions
- Dashboard totals and recent visits
- Patient registration, search and profile
- Visit/consultation records
- Medicine catalogue, low-stock flag and stock adjustments
- Monthly visit-count report
- Admin user creation and activation/deactivation
- Basic audit events
- Server-side validation, parameterized SQL and CSRF form tokens

## Project structure
```text
EMR_Student_Project/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── templates/ (HTML pages)
└── static/css/style.css, static/js/app.js
```

## Important limitations / next work
- SQLite is used to make the project easy to run locally. The team can migrate to MySQL/PostgreSQL after agreeing on the schema.
- This version uses Flask templates; it does **not** yet expose a separate REST API. If frontend and backend are separate applications, agree and implement API endpoints before integration.
- Not implemented: prescriptions, appointment scheduling, laboratory records, payments, password-reset email, cloud deployment or automated test suite.
- Development server and `debug=True` are for local development only.
- Set a strong `EMR_SECRET_KEY` before deployment. Only set `EMR_HTTPS=1` when the app is actually served over HTTPS.
- Add automated tests, a security review, reliable backup/restore, monitoring, stronger record-level access control, privacy review and applicable legal/regulatory review before considering real deployment.
- Clinical decisions must be made by qualified healthcare professionals; this application does not provide clinical advice.
