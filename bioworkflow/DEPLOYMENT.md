# Deployment Guide — formacio.bq.ub.edu

This guide covers deployment of the bioworkflow backend on the DBW shared server.
See also the main deployment guidelines document provided by the professor.

## What the server provides

- Python environment support (no root access needed)
- MySQL database (request credentials from professor)
- uWSGI for serving Python apps
- A reverse proxy that maps URL prefixes to uWSGI socket files
- No Celery, no Redis, no systemd, no Gunicorn

---

## Step-by-step deployment

### 1. Upload your code

Copy the `bioworkflow` folder to your space on the server:
```bash
scp -r bioworkflow youruser@formacio.bq.ub.edu:~/bioworkflow
```

Or clone from git if the project is in a repository.

Code should NOT go in `public_html` (source code would be publicly visible).

### 2. Set up the Python environment

```bash
cd ~/bioworkflow
python3 -m venv venv
source venv/bin/activate
pip install -r requirements_backend.txt
```

### 3. Request a MySQL database

Email the professor with:
- **Database name**: `bioworkflow_db` (or similar)
- **MySQL username**: choose one (not root, not trivial)
- **Password**: choose a secure one

You will receive confirmation once the database is created.

### 4. Configure .env for production

Edit `~/bioworkflow/.env`:
```
FLASK_ENV=production
SECRET_KEY=<run: python3 -c "import secrets; print(secrets.token_hex(32))">
DATABASE_URL=mysql+pymysql://yourdbuser:yourpassword@localhost:3306/bioworkflow_db
PREFIX=/bioworkflow
SESSION_COOKIE_SECURE=True
LOG_LEVEL=INFO
LOG_FILE=logs/bioworkflow.log
PYTHON_INTERPRETER=python3
```

### 5. Configure bioworkflow.ini

Edit `~/bioworkflow/bioworkflow.ini` and replace `youruser`:
```ini
[uwsgi]
module = wsgi:app
master = true
processes = 1
socket = bioworkflow.sock
chmod-socket = 777
vacuum = true
die-on-term = true
logto = /home/youruser/bioworkflow/bioworkflow.log
```

### 6. Initialize the database

```bash
cd ~/bioworkflow
source venv/bin/activate
flask db upgrade
```

### 7. Start uWSGI

First run in the foreground to check for errors:
```bash
uwsgi bioworkflow.ini
```

If it starts without errors, stop it (Ctrl+C) and run in the background:
```bash
nohup uwsgi bioworkflow.ini &
```

You should see `bioworkflow.sock` appear in the folder.
Check `bioworkflow.log` if it does not start correctly.

### 8. Send proxy information to the professor

Email the professor with:
- **Prefix**: `/bioworkflow`
- **Socket file path**: `/home/youruser/bioworkflow/bioworkflow.sock`
- **Python environment path**: `/home/youruser/bioworkflow/venv`
- **INI file path**: `/home/youruser/bioworkflow/bioworkflow.ini`

Once he sets up the proxy, the API will be accessible at:
`https://formacio.bq.ub.edu/bioworkflow`

---

## Updating the application

```bash
cd ~/bioworkflow

# Stop the running uWSGI process
pkill -f "uwsgi bioworkflow.ini"

# Pull / copy new code

# Update dependencies if requirements changed
source venv/bin/activate
pip install -r requirements_backend.txt

# Run any new migrations
flask db upgrade

# Restart
nohup uwsgi bioworkflow.ini &
```

## Checking logs

```bash
tail -f ~/bioworkflow/bioworkflow.log
```

## Database dump (for migrating local data to server)

On your local machine:
```bash
# SQLite local DB → SQL dump
python3 -c "
import sqlite3, sys
con = sqlite3.connect('bioworkflow.db')
for line in con.iterdump():
    print(line)
" > bioworkflow_dump.sql
```

On the server, restore via phpMyAdmin (`https://formacio.bq.ub.edu/phpMyAdmin`)
or ask the professor to import the dump.

---

## Troubleshooting

**Socket file does not appear** — check `bioworkflow.log` for import errors.
Run `python wsgi.py` directly to see the error in the terminal.

**Database connection error** — verify `DATABASE_URL` in `.env`. Make sure the
database was created by the professor and credentials match.

**App works locally but not on server** — check that `PREFIX=/bioworkflow` is set
in `.env` and matches the prefix the professor configured in the proxy.

**uWSGI won't install** — try `pip install uwsgi --no-cache-dir`. If it still
fails due to missing C headers, ask the professor for help installing it
system-wide.
