# Magnifier — Bioinformatics Workflow Platform

[![CI](https://github.com/DavitGudadze/Magnifier/actions/workflows/ci.yml/badge.svg)](https://github.com/DavitGudadze/Magnifier/actions/workflows/ci.yml)

Magnifier is a full-stack web platform for running multi-step bioinformatics pipelines on gene-expression and genomic-variant data. It is structured as two cooperating Flask services: a browser-facing UI frontend (`magnifier_python`) and a REST API backend (`bioworkflow`). Users can register, create projects, upload expression and VCF files, trigger a four-step analysis pipeline, monitor its progress in real time, and download the resulting contingency table.

---

## Features

- **Authentication** — email/password registration with strong-password enforcement + Google OAuth 2.0 login
- **Projects** — create, browse, and delete workspaces that group related experiments
- **Experiments** — per-project experiments each with their own file sets and pipeline runs
- **File uploads** — gene-expression files (`.csv`, `.tsv`, `.txt`) and VCF files (`.vcf`, `.vcf.gz`), up to 5 GB each
- **4-step pipeline** — DEA → VEP → Join → Contingency Table, executed in a background thread
- **Live monitoring** — pipeline status polled every 3 seconds; progress bar shows current step (1–4)
- **Result download** — completed contingency table downloadable as CSV
- **Account management** — change password, delete account (with all associated data)
- **Sub-path deployment** — works at `/` locally and behind a sub-path reverse proxy on shared servers

---

## Architecture

```
┌────────────────────────────────────┐      HTTP      ┌──────────────────────────────────────┐
│        magnifier_python            │  ────────────►  │            bioworkflow               │
│        (Flask frontend)            │                 │         (Flask REST API)             │
│                                    │                 │                                      │
│  • Jinja2 HTML/CSS UI              │                 │  • SQLAlchemy + SQLite / MySQL       │
│  • Session-based auth              │                 │  • Flask-Login + PBKDF2-SHA256       │
│  • Google OAuth 2.0                │                 │  • Background-thread pipeline        │
│  • Project & experiment management │                 │  • File storage (uploads/results)    │
│  • Live pipeline status polling    │                 │  • 4-step bioinformatics pipeline    │
│  Port 8080 (dev) / uWSGI (prod)    │                 │  Port 5000 (dev) / uWSGI (prod)      │
└────────────────────────────────────┘                 └──────────────────────────────────────┘
```

---

## Pipeline steps

| Step | Script | Input | Output |
|------|--------|-------|--------|
| 1 | `dea_analysis.py` | Gene-expression file | Differentially-expressed genes (CSV) |
| 2 | `vep_processing.py` | VCF files folder | Variant-effect predictions (CSV) |
| 3 | `join_results.py` | DEA + VEP outputs | Joined gene–variant table (CSV) |
| 4 | `generate_contingency.py` | Joined table | Final contingency table (CSV) |

Scripts live in `bioworkflow/scripts/`. See the README in that directory for the exact CLI interface each script must expose.

---

## Project structure

```
magnifier/
├── .github/
│   └── workflows/
│       └── ci.yml                  # GitHub Actions CI (lint + tests)
├── tests/
│   ├── test_backend_smoke.py       # Pytest smoke tests for bioworkflow API
│   └── test_frontend_smoke.py      # Pytest smoke tests for magnifier_python UI
│
├── magnifier_python/               # Flask frontend service
│   ├── app.py                      # All routes and backend API communication
│   ├── wsgi.py                     # Production WSGI entry point
│   ├── magnifier.ini               # uWSGI config
│   ├── requirements_frontend.txt
│   ├── .env.example
│   ├── static/
│   │   ├── logo.png
│   │   └── style.css
│   └── templates/
│       ├── base.html               # Layout, status bar, flash messages
│       ├── index.html
│       ├── login.html
│       ├── register.html
│       ├── dashboard.html
│       ├── projects.html
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
└── bioworkflow/                    # Flask REST API backend service
    ├── app/
    │   ├── __init__.py             # Application factory
    │   ├── models.py               # User, Project, Experiment, Result models
    │   ├── auth/routes.py          # Register, login, logout, password management
    │   ├── projects/routes.py      # Project CRUD
    │   ├── experiments/routes.py   # Experiment CRUD, file upload, run, download
    │   ├── services/
    │   │   ├── pipeline.py         # 4-step pipeline orchestration
    │   │   └── tasks.py            # Background task wrappers
    │   └── utils/
    │       ├── auth.py             # Login-required decorators
    │       └── files.py            # Secure file save, hash, cleanup
    ├── scripts/                    # Bioinformatics analysis scripts
    │   ├── README.md               # Script interface specification
    │   ├── dea_analysis.py
    │   ├── vep_processing.py
    │   ├── join_results.py
    │   └── generate_contingency.py
    ├── migrations/                 # Alembic database migrations
    ├── systemd/                    # systemd service files
    ├── config.py                   # Dev / Prod / Testing configuration classes
    ├── wsgi.py                     # Production WSGI entry point
    ├── bioworkflow.ini             # uWSGI config
    ├── requirements_backend.txt
    └── .env.example
```

---

## Getting started

### Prerequisites

- Python 3.11 or 3.12
- `git`

### 1. Backend (`bioworkflow`)

```bash
cd bioworkflow
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements_backend.txt

cp .env.example .env              # then edit .env — set SECRET_KEY at minimum

flask db upgrade                  # initialise the SQLite database
python wsgi.py                    # → http://127.0.0.1:5000
```

### 2. Frontend (`magnifier_python`)

```bash
cd magnifier_python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements_frontend.txt

cp .env.example .env              # review/edit as needed
python app.py                     # → http://127.0.0.1:8080
```

Open **http://127.0.0.1:8080** in your browser. The backend must be running for any authenticated actions to work.

---

## Environment variables

### Frontend — `magnifier_python/.env`

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | *(required)* | Flask session signing key |
| `BACKEND_URL` | `http://127.0.0.1:5000` | Base URL of the bioworkflow API |
| `PREFIX` | *(empty)* | URL sub-path, e.g. `/magnifier` on a shared server |
| `GOOGLE_CLIENT_ID` | *(empty)* | Google OAuth app client ID |
| `GOOGLE_CLIENT_SECRET` | *(empty)* | Google OAuth app client secret |
| `GOOGLE_REDIRECT_URI` | `http://127.0.0.1:8080/auth/google/callback` | OAuth callback URL |

### Backend — `bioworkflow/.env`

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | *(required in production)* | Flask session signing key |
| `DATABASE_URL` | `sqlite:///bioworkflow.db` | SQLAlchemy database URI |
| `FLASK_ENV` | `development` | `development` / `production` / `testing` |
| `PYTHON_INTERPRETER` | `python3` | Python used to launch pipeline scripts |
| `MAX_CONTENT_LENGTH` | `5368709120` | Maximum upload size in bytes (5 GB) |
| `TASK_TIME_LIMIT` | `7200` | Pipeline timeout in seconds |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

---

## REST API reference

### Authentication — `/auth`

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Create account |
| POST | `/auth/login` | Login and create session |
| POST | `/auth/logout` | Destroy session |
| GET | `/auth/me` | Get current user info |
| POST | `/auth/reset_google_password` | Reset password for a Google OAuth user |
| POST | `/auth/find_by_email` | Look up username by email |
| POST | `/auth/delete_account` | Permanently delete account and all data |

### Projects — `/projects`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/projects/` | List all projects |
| POST | `/projects/` | Create project |
| GET | `/projects/<id>` | Get project + experiments |
| PUT | `/projects/<id>` | Update project |
| DELETE | `/projects/<id>` | Delete project and all its experiments |

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

### Experiment status values

| Value | Meaning |
|-------|---------|
| `created` | Experiment created, no files yet |
| `uploading` | Files being uploaded |
| `ready` | All files present, pipeline can be started |
| `queued` | Pipeline queued to run |
| `running` | Pipeline executing |
| `completed` | Done — result available for download |
| `failed` | Error occurred (`error_message` field contains details) |

---

## Development commands

```bash
# Run all tests
pytest tests/ -v

# Lint the backend
cd bioworkflow && flake8 app/ config.py wsgi.py --max-line-length=120

# Lint the frontend
cd magnifier_python && flake8 app.py wsgi.py --max-line-length=120

# Create a new database migration (after editing models.py)
cd bioworkflow && flask db migrate -m "describe your change"
flask db upgrade

# Run backend in development mode
cd bioworkflow && python wsgi.py

# Run frontend in development mode
cd magnifier_python && python app.py
```

---

## Database

SQLite is used by default (`bioworkflow/bioworkflow.db`). For production, set `DATABASE_URL` to a MySQL or PostgreSQL URI:

```
DATABASE_URL=mysql+pymysql://user:password@localhost/bioworkflow
```

Run migrations after any model changes:

```bash
flask db migrate -m "describe change"
flask db upgrade
```

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend framework | Flask 3 + Jinja2 |
| Backend framework | Flask 3 + Flask-Login + Flask-Migrate |
| Database ORM | SQLAlchemy 2 |
| Authentication | PBKDF2-SHA256 (werkzeug) + Google OAuth 2.0 |
| Background tasks | Python `threading` (no Celery required) |
| Production server | uWSGI |
| CI | GitHub Actions |

---

## Security notes

- **Never commit `.env` files** — they are listed in `.gitignore`
- `SECRET_KEY` must be a strong random value in production (`python3 -c "import secrets; print(secrets.token_hex(32))"`)
- `SESSION_COOKIE_SECURE = True` is enforced in `ProductionConfig` (requires HTTPS)
- File uploads are validated by extension and stored with `werkzeug.utils.secure_filename`
- File integrity is verified with SHA-256 hashes
- Google OAuth state parameter prevents CSRF on the callback

---

## License

[MIT](LICENSE) © 2024–present Davit Gudadze
