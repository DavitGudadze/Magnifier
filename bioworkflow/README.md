# Bioinformatics Workflow Platform — Backend

Flask REST API for managing bioinformatics analysis pipelines.
The frontend (magnifier_python) communicates with this backend.

## Architecture

```
Browser → magnifier_python (frontend) → bioworkflow (this API) → pipeline scripts
```

## Project Structure

```
bioworkflow/
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── models.py                # SQLAlchemy ORM models
│   ├── auth/                    # Authentication blueprint
│   ├── projects/                # Projects management blueprint
│   ├── experiments/             # Experiments management blueprint
│   ├── services/
│   │   ├── pipeline.py          # Pipeline orchestration
│   │   └── tasks.py             # Background task functions (threaded)
│   └── utils/                   # Helper utilities
├── scripts/                     # Bioinformatics scripts
│   ├── dea_analysis.py
│   ├── vep_processing.py
│   ├── join_results.py
│   └── generate_contingency.py
├── migrations/                  # Flask-Migrate database migrations
├── storage/                     # File storage (not committed to git)
│   ├── uploads/
│   ├── intermediate/
│   └── results/
├── config.py                    # Configuration (reads from .env)
├── wsgi.py                      # WSGI entry point (uWSGI + DispatcherMiddleware)
├── bioworkflow.ini              # uWSGI config for shared server deployment
├── requirements_backend.txt     # Python dependencies
└── .env                         # Environment variables (not committed to git)
```

## Local Development Setup

### 1. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements_backend.txt
```

> Note: `uwsgi` may fail to install on Windows. For local dev on Windows use
> `pip install -r requirements_backend.txt --ignore-requires-python` or simply
> comment out the `uwsgi` line and run directly with `python wsgi.py`.

### 3. Configure environment

```bash
cp .env .env.local   # or just edit .env directly
```

For local dev the defaults work as-is (SQLite database, no PREFIX).

### 4. Initialize the database

```bash
flask db upgrade
```

If migrations folder is missing:
```bash
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

### 5. Start the development server

```bash
python wsgi.py
```

The API will be available at `http://127.0.0.1:5000`.

---

## Deployment on formacio.bq.ub.edu

The server uses uWSGI on a shared host. Each app is served under a URL prefix.

### 1. Upload code to your server space

```bash
# From your machine — copy the bioworkflow folder to the server
scp -r bioworkflow youruser@formacio.bq.ub.edu:~/bioworkflow
# Or clone from git if hosted
```

### 2. Set up the Python environment

```bash
cd ~/bioworkflow
python3 -m venv venv
source venv/bin/activate
pip install -r requirements_backend.txt
```

### 3. Request a MySQL database from the professor

Email the professor with:
- Database name (e.g. `bioworkflow_db`)
- Username (e.g. `bw_user`)
- Password (your choice)

### 4. Edit .env for production

```bash
nano .env
```

Set these values:
```
FLASK_ENV=production
SECRET_KEY=<generate with: python3 -c "import secrets; print(secrets.token_hex(32))">
DATABASE_URL=mysql+pymysql://bw_user:yourpassword@localhost:3306/bioworkflow_db
PREFIX=/bioworkflow
SESSION_COOKIE_SECURE=True
```

### 5. Edit bioworkflow.ini

Replace `youruser` with your actual username:
```ini
logto = /home/youruser/bioworkflow/bioworkflow.log
```

### 6. Initialize the database

```bash
source venv/bin/activate
flask db upgrade
```

### 7. Start uWSGI

```bash
uwsgi bioworkflow.ini
```

Test it first in the foreground to catch import errors, then run in the background:
```bash
nohup uwsgi bioworkflow.ini &
```

A file `bioworkflow.sock` will appear in the folder. Check `bioworkflow.log` if it doesn't start.

### 8. Send the professor the proxy information

Email the professor:
- **Prefix**: `/bioworkflow`
- **Socket file path**: `/home/youruser/bioworkflow/bioworkflow.sock`
- **Python environment path**: `/home/youruser/bioworkflow/venv`
- **INI file path**: `/home/youruser/bioworkflow/bioworkflow.ini`

---

## API Endpoints

### Authentication
- `POST /auth/register` — Register new user
- `POST /auth/login` — Login
- `POST /auth/logout` — Logout

### Projects
- `GET /projects/` — List user's projects
- `POST /projects/` — Create new project
- `GET /projects/<id>` — Get project details
- `DELETE /projects/<id>` — Delete project
- `POST /projects/<id>/generate_merged_table` — Merge all experiment results

### Experiments
- `GET /experiments/<project_id>` — List experiments in project
- `POST /experiments/<project_id>` — Create new experiment
- `POST /experiments/<id>/upload_expression` — Upload gene expression file
- `POST /experiments/<id>/upload_vcf` — Upload VCF files
- `POST /experiments/<id>/run` — Execute pipeline (runs in background thread)
- `GET /experiments/<id>/status` — Check execution status
- `GET /experiments/<id>/download` — Download contingency table result

---

## Pipeline Execution

Background jobs run in Python threads (no Celery or Redis required). When a user
triggers a pipeline run, the backend starts a `threading.Thread` that executes the
four bioinformatics scripts sequentially, updating the experiment status in the
database as each step completes. The frontend polls `/experiments/<id>/status` to
show progress.

## Technology Stack

- **Web Framework**: Flask 3.x
- **Database**: SQLite (dev) / MySQL (production)
- **ORM**: SQLAlchemy + Flask-Migrate
- **Background jobs**: Python `threading.Thread`
- **Auth**: Flask-Login + bcrypt
- **Production server**: uWSGI
