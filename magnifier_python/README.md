# MAGNIFIER — Frontend

Flask-based frontend for the Magnifier bioinformatics pipeline platform.  
Handles authentication, project/experiment management, file uploads, and pipeline monitoring.  
Communicates with the `bioworkflow` backend API over HTTP.

> **For full setup instructions (both frontend + backend), see `SETUP_README.md` in the root `DBW_final/` folder.**

---

## Quick Start

```bash
cd magnifier_python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements_frontend.txt
cp .env.example .env
# Edit .env with your values (see below)
python app.py
```

Open: **http://127.0.0.1:8080**

---

## Environment Variables (`.env`)

Copy `.env.example` to `.env` and fill in:

| Variable | Local value | Description |
|----------|-------------|-------------|
| `SECRET_KEY` | any random string | Flask session secret |
| `BACKEND_URL` | `http://127.0.0.1:5000` | Where the bioworkflow API is running |
| `PREFIX` | *(leave empty)* | URL prefix — empty for local, `/magnifier` on server |
| `GOOGLE_CLIENT_ID` | your client ID | Google OAuth — can be left empty if not using |
| `GOOGLE_CLIENT_SECRET` | your secret | Google OAuth — can be left empty if not using |
| `GOOGLE_REDIRECT_URI` | `http://127.0.0.1:8080/auth/google/callback` | OAuth callback URL |

> ⚠️ Never commit `.env` to Git.

---

## Project Structure

```
magnifier_python/
├── app.py                    # All Flask routes and API communication
├── wsgi.py                   # Production entry point (uwsgi)
├── magnifier.ini             # uwsgi config for professor's server
├── requirements_frontend.txt # Python dependencies
├── .env.example              # Environment variable template
├── .gitignore
├── static/
│   ├── logo.png
│   └── style.css             # Full styling + mobile responsive
└── templates/
    ├── base.html             # Base layout, status bar, flash messages
    ├── index.html            # Landing page
    ├── login.html            # Login (email + Google OAuth)
    ├── register.html         # Registration (email + Google OAuth)
    ├── dashboard.html        # Dashboard with stats + project overview
    ├── projects.html         # Projects list with search + pagination
    ├── project_detail.html   # Single project + experiments table
    ├── experiment_detail.html # Experiment + file uploads + pipeline
    ├── new_project.html      # Create project form
    ├── new_experiment.html   # Create experiment form
    ├── profile.html          # Change password, Google account info
    ├── delete_account.html   # Account deletion with confirmation
    ├── unauthorized.html     # 401 page
    ├── 404.html              # 404 page
    └── 500.html              # 500 page
```

---

## Features

- **Authentication** — email/password + Google OAuth login and registration
- **Projects** — create, view, delete with search and pagination (10 per page)
- **Experiments** — create, track, delete per project
- **File uploads** — expression files (.csv/.tsv/.txt) and VCF files (.vcf/.vcf.gz)
- **Pipeline** — run 4-step bioinformatics pipeline with live status polling every 3 seconds
- **Progress tracking** — visual progress bar, step counter, auto-reload on completion
- **Auto-refresh** — dashboard auto-refreshes every 10 seconds if a pipeline is running
- **Mobile responsive** — tables and layout adapt to tablet and mobile screens
- **Flash messages** — green for success, red for errors, auto-dismiss after 4 seconds
- **Beforeunload warning** — warns user before leaving page if pipeline is running
- **Error pages** — custom 404 and 500 pages matching the app design
- **PREFIX support** — works on localhost with no prefix and on the professor's server with `/magnifier`

---

## Backend API — Endpoints Used

The frontend calls these backend endpoints (base URL set via `BACKEND_URL`):

| Method | Endpoint | Used for |
|--------|----------|---------|
| POST | `/auth/login` | Login |
| POST | `/auth/register` | Register |
| POST | `/auth/logout` | Logout |
| GET | `/auth/me` | Get current user info |
| POST | `/auth/find_by_email` | Find user during Google OAuth |
| POST | `/auth/reset_google_password` | Set password for Google users |
| POST | `/auth/delete_account` | Delete account |
| GET | `/projects/` | List all projects |
| POST | `/projects/` | Create project |
| GET | `/projects/<id>` | Get project + experiments |
| DELETE | `/projects/<id>` | Delete project |
| POST | `/experiments/<project_id>` | Create experiment |
| GET | `/experiments/<id>/status` | Get experiment status + details |
| POST | `/experiments/<id>/upload_expression` | Upload expression file |
| POST | `/experiments/<id>/upload_vcf` | Upload VCF files |
| POST | `/experiments/<id>/delete_expression` | Delete expression file |
| POST | `/experiments/<id>/delete_vcf/<vcf_id>` | Delete VCF file |
| POST | `/experiments/<id>/run` | Run pipeline |
| GET | `/experiments/<id>/status` | Poll pipeline status |
| GET | `/experiments/<id>/download` | Download result file |
| DELETE | `/experiments/<id>` | Delete experiment |

### Status Response Format

The frontend polls `/experiments/<id>/status` every 3 seconds. Expected response:

```json
{
  "status": "running",
  "current_step": 2,
  "name": "My Experiment",
  "project_id": 1,
  "project_name": "My Project",
  "description": "Optional description",
  "has_expression_file": true,
  "has_vcf_files": true,
  "expression_filename": "expr.csv",
  "vcf_files": [{"id": 1, "filename": "sample.vcf"}],
  "has_result": false,
  "can_run": false,
  "error_message": null,
  "created_at": "2025-01-01T12:00:00"
}
```

| `status` value | Meaning |
|----------------|---------|
| `ready` | Files uploaded, ready to run |
| `queued` | Pipeline queued in Celery |
| `running` | Pipeline currently executing |
| `completed` | Done, result available |
| `failed` | Error occurred |

---

## Deployment on Professor's Server

See `SETUP_README.md` in the root folder for the full deployment guide.

**Quick summary:**
1. Set `PREFIX=/magnifier` in `.env`
2. Set `GOOGLE_REDIRECT_URI=https://formacio.bq.ub.edu/magnifier/auth/google/callback`
3. Run: `nohup uwsgi magnifier.ini &`
4. Email the professor: prefix, socket path, venv path, ini path
