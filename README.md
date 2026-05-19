# MAGNIFIER — Bioinformatics Workflow Platform

A full-stack web platform for running multi-step bioinformatics pipelines on gene expression and genomic variant data. Built with two cooperating Flask services: a UI frontend (**magnifier_python**) and a REST API backend (**bioworkflow**).

---

## Architecture

```
┌─────────────────────────────────────┐      HTTP      ┌──────────────────────────────────────┐
│         magnifier_python            │  ────────────►  │            bioworkflow               │
│         (Flask frontend)            │                 │         (Flask REST API)             │
│                                     │                 │                                      │
│  • HTML/CSS UI (dark terminal style)│                 │  • SQLAlchemy + SQLite / MySQL       │
│  • Session-based auth               │                 │  • Flask-Login + bcrypt              │
│  • Google OAuth 2.0                 │                 │  • Background thread pipeline        │
│  • Project & experiment management  │                 │  • File storage (uploads/results)    │
│  • Live pipeline status polling     │                 │  • 4-step bioinformatics pipeline    │
│  Port 8080 (dev) / uWSGI (prod)     │                 │  Port 5000 (dev) / uWSGI (prod)      │
└─────────────────────────────────────┘                 └──────────────────────────────────────┘
```

---

## Features

- **Authentication** — email/password registration + Google OAuth 2.0 login
- **Projects** — create, browse, delete workspaces that group experiments
- **Experiments** — per-project experiments with individual file sets and pipeline runs
- **File uploads** — gene expression files (`.csv`, `.tsv`, `.txt`) and VCF files (`.vcf`, `.vcf.gz`), up to 5 GB
- **4-step pipeline** — DEA → VEP → Join → Contingency Table, executed in a background thread
- **Live monitoring** — status polled every 3 seconds; progress bar showing current step (1–4)
- **Result download** — completed contingency table downloadable as CSV
- **Account management** — change password, delete account (with all data)
- **Prefix support** — works at `/` locally and behind a sub-path proxy on a shared server
- **Custom error pages** — styled 404 and 500 pages

---

## Pipeline Steps

| Step | Script | Input | Output |
|------|--------|-------|--------|
| 1 | `dea_analysis.py` | Gene expression file | Differentially expressed genes (CSV) |
| 2 | `vep_processing.py` | VCF files folder | Variant effect predictions (CSV) |
| 3 | `join_results.py` | DEA + VEP outputs | Joined gene–variant table (CSV) |
| 4 | `generate_contingency.py` | Joined table | Final contingency table (CSV) |

Scripts live in `bioworkflow/scripts/`. Each must accept `--input-dir`/`--output-file`/`--experiment-id` arguments (see `bioworkflow/app/services/pipeline.py` for exact invocation).

---

## Project Structure

```
magnifier/
├── magnifier_python/           # Flask frontend
│   ├── app.py                  # All routes and backend API communication
│   ├── wsgi.py                 # Production WSGI entry point
│   ├── magnifier.ini           # uWSGI config
│   ├── requirements_frontend.txt
│   ├── .env.example
│   ├── static/
│   │   ├── logo.png
│   │   └── style.css
│   └── templates/
│       ├── base.html           # Layout, status bar, flash messages
│       ├── index.html          # Landing page
│       ├── login.html
│       ├── register.html
│       ├── dashboard.html      # Stats + quick actions
│       ├── projects.html       # Projects list
│       ├── project_detail.html
│       ├── experiment_detail.html  # File uploads + pipeline controls
│       ├── new_project.html
│       ├── new_experiment.html
│       ├── profile.html
│       ├── delete_account.html
│       ├── unauthorized.html
│       ├── 404.html
│       └── 500.html
│
└── bioworkflow/                # Flask REST API backend
    ├── app/
    │   ├── __init__.py         # App factory
    │   ├── models.py           # User, Project, Experiment, Result models
    │   ├── auth/routes.py      # Register, login, logout, password reset
    │   ├── projects/routes.py  # Project CRUD
    │   ├── experiments/routes.py   # Experiment CRUD, file upload, run, download
    │   ├── services/
    │   │   ├── pipeline.py     # 4-step pipeline orchestration
    │   │   └── tasks.py        # Background task wrappers
    │   └── utils/
    │       ├── auth.py         # Login-required decorators
    │       └── files.py        # Secure file save, hash, cleanup
    ├── scripts/                # Your bioinformatics Python scripts go here
    │   ├── dea_analysis.py
    │   ├── vep_processing.py
    │   ├── join_results.py
    │   └── generate_contingency.py
    ├── migrations/             # Alembic database migrations
    ├── systemd/                # systemd service files
    ├── config.py               # Config classes (Dev / Prod / Testing)
    ├── wsgi.py
    ├── bioworkflow.ini         # uWSGI config
    ├── requirements_backend.txt
    └── .env.example
```

---

## Local Setup

### 1. Backend (bioworkflow)

```bash
cd bioworkflow
python3 -m venv venv
source venv/bin/activate
pip install -r requirements_backend.txt

cp .env.example .env   # edit SECRET_KEY and DATABASE_URL at minimum

flask db upgrade       # create database tables
python wsgi.py         # runs on http://127.0.0.1:5000
```

### 2. Frontend (magnifier_python)

```bash
cd magnifier_python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements_frontend.txt

cp .env.example .env   # edit as needed (see table below)
python app.py          # runs on http://127.0.0.1:8080
```

Open **http://127.0.0.1:8080** in your browser.

---

## Environment Variables

### Frontend (`magnifier_python/.env`)

| Variable | Local default | Description |
|----------|--------------|-------------|
| `SECRET_KEY` | any random string | Flask session secret |
| `BACKEND_URL` | `http://127.0.0.1:5000` | Bioworkflow API URL |
| `PREFIX` | *(empty)* | URL sub-path prefix, e.g. `/magnifier` on shared server |
| `GOOGLE_CLIENT_ID` | *(empty)* | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | *(empty)* | Google OAuth client secret |
| `GOOGLE_REDIRECT_URI` | `http://127.0.0.1:8080/auth/google/callback` | OAuth callback URL |

### Backend (`bioworkflow/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | **required in production** | Flask session secret |
| `DATABASE_URL` | `sqlite:///bioworkflow.db` | SQLAlchemy database URI |
| `FLASK_ENV` | `development` | `development` / `production` |
| `PYTHON_INTERPRETER` | `python3` | Python used to run pipeline scripts |
| `MAX_CONTENT_LENGTH` | `5368709120` | Max upload size in bytes (5 GB) |
| `TASK_TIME_LIMIT` | `7200` | Pipeline timeout in seconds |
| `LOG_LEVEL` | `INFO` | Logging level |

---

## Backend REST API

### Authentication — `/auth`

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Create account |
| POST | `/auth/login` | Login and create session |
| POST | `/auth/logout` | Destroy session |
| GET | `/auth/me` | Get current user info |
| POST | `/auth/reset_google_password` | Reset password for Google OAuth users |
| POST | `/auth/find_by_email` | Look up username by email |
| POST | `/auth/delete_account` | Permanently delete account + all data |

### Projects — `/projects`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/projects/` | List all projects |
| POST | `/projects/` | Create project |
| GET | `/projects/<id>` | Get project + experiments |
| PUT | `/projects/<id>` | Update project name/description |
| DELETE | `/projects/<id>` | Delete project and all experiments |

### Experiments — `/experiments`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/experiments/<project_id>` | List experiments in a project |
| POST | `/experiments/<project_id>` | Create experiment |
| GET | `/experiments/<id>` | Get experiment details |
| DELETE | `/experiments/<id>` | Delete experiment |
| POST | `/experiments/<id>/upload_expression` | Upload expression file |
| POST | `/experiments/<id>/upload_vcf` | Upload VCF files |
| POST | `/experiments/<id>/delete_expression` | Remove expression file |
| POST | `/experiments/<id>/delete_vcf/<vcf_id>` | Remove a VCF file |
| POST | `/experiments/<id>/run` | Start pipeline |
| GET | `/experiments/<id>/status` | Poll pipeline status |
| GET | `/experiments/<id>/download` | Download result CSV |

### Status values

| Value | Meaning |
|-------|---------|
| `created` | Experiment created, no files yet |
| `uploading` | Files being uploaded |
| `ready` | All files present, ready to run |
| `queued` | Pipeline queued |
| `running` | Pipeline executing |
| `completed` | Done — result available for download |
| `failed` | Error occurred (`error_message` contains details) |

---

## Production Deployment (uWSGI + shared server)

### Backend

```bash
# In bioworkflow/
source venv/bin/activate
# Edit .env: FLASK_ENV=production, SECRET_KEY=<strong random>, DATABASE_URL=...
flask db upgrade
nohup uwsgi bioworkflow.ini &
```

### Frontend

```bash
# In magnifier_python/
source venv/bin/activate
# Edit .env: PREFIX=/magnifier, BACKEND_URL=http://127.0.0.1:5001
nohup uwsgi magnifier.ini &
```

The professor's nginx proxy routes `/magnifier` → frontend socket and `/bioworkflow` → backend socket.

For systemd service files see `bioworkflow/systemd/`.

---

## Database

SQLite is used by default (file: `bioworkflow/bioworkflow.db`). For production, set `DATABASE_URL` to a MySQL or PostgreSQL URI:

```
DATABASE_URL=mysql+pymysql://user:password@localhost/bioworkflow
```

Run migrations after any model changes:

```bash
flask db migrate -m "describe change"
flask db upgrade
```

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend framework | Flask 3 + Jinja2 |
| Backend framework | Flask 3 + Flask-Login + Flask-Migrate |
| Database ORM | SQLAlchemy 2 |
| Authentication | bcrypt (PBKDF2-SHA256) + Google OAuth 2.0 |
| Background tasks | Python `threading` (Celery-ready) |
| Production server | uWSGI |
| Fonts | Inter + JetBrains Mono (Google Fonts) |

---

## Security Notes

- Never commit `.env` files — they are in `.gitignore`
- `SECRET_KEY` must be a strong random value in production
- `SESSION_COOKIE_SECURE = True` is enforced in `ProductionConfig`
- File uploads are validated by extension and saved with `werkzeug.utils.secure_filename`
- File integrity is verified using SHA-256 hashes
- Google OAuth state parameter prevents CSRF on the callback
- Passwords are hashed with PBKDF2-SHA256; plain-text passwords are never stored
