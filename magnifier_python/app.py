"""
Magnifier - Python/Flask version
Full featured: login, register, Google OAuth, delete account, projects, experiments.
"""

import os
import re
import secrets
import string
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

import requests  # noqa: E402
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response  # noqa: E402
from werkzeug.exceptions import NotFound  # noqa: E402
from werkzeug.middleware.dispatcher import DispatcherMiddleware  # noqa: E402
from werkzeug.middleware.proxy_fix import ProxyFix  # noqa: E402

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.secret_key = os.environ.get('SECRET_KEY', 'magnifier-secret-key-2024')
BACKEND_URL = os.environ.get('BACKEND_URL', 'http://127.0.0.1:5000')
PREFIX = os.environ.get('PREFIX', '')


@app.context_processor
def inject_prefix():
    return dict(PREFIX=PREFIX, backend_online=True)


# ── Google OAuth config ──────────────────────────────────────────────────────
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', 'http://127.0.0.1:8080/auth/google/callback')
GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_URL = 'https://www.googleapis.com/oauth2/v3/userinfo'


def random_password(length=24):
    """Generate a secure random password for OAuth users.
    Guaranteed to meet validation: uppercase + digit + symbol.
    """
    # Guarantee at least one of each required type
    upper = secrets.choice(string.ascii_uppercase)
    digit = secrets.choice(string.digits)
    symbol = secrets.choice('!@#$%^&*')
    rest_chars = string.ascii_letters + string.digits + '!@#$%^&*'
    rest = ''.join(secrets.choice(rest_chars) for _ in range(length - 3))
    # Shuffle so the guaranteed chars aren't always at the start
    combined = list(upper + digit + symbol + rest)
    secrets.SystemRandom().shuffle(combined)
    return ''.join(combined)


# Cache backend sessions per user to avoid re-login on every request
_backend_sessions = {}


def backend(method, path, **kwargs):
    """Authenticated request to bioworkflow backend with session caching."""
    url = f"{BACKEND_URL}{path}"
    username = session.get('backend_username')
    password = session.get('backend_password')
    if not username or not password:
        return None
    try:
        s = _backend_sessions.get(username)
        if not s:
            s = requests.Session()
            lr = s.post(f"{BACKEND_URL}/auth/login",
                        json={'username': username, 'password': password}, timeout=30)
            if lr.status_code != 200:
                return None
            _backend_sessions[username] = s
        resp = s.request(method, url, timeout=30, **kwargs)
        if resp.status_code == 401:
            s = requests.Session()
            lr = s.post(f"{BACKEND_URL}/auth/login",
                        json={'username': username, 'password': password}, timeout=30)
            if lr.status_code != 200:
                return None
            _backend_sessions[username] = s
            resp = s.request(method, url, timeout=30, **kwargs)
        return resp
    except requests.exceptions.ConnectionError:
        _backend_sessions.pop(username, None)
        return None
    except Exception:
        _backend_sessions.pop(username, None)
        return None


def login_or_register_google_user(email, name):
    """
    Try to login with Google email. If user doesn't exist, register them.
    If session was lost (server restart), recover by resetting the password.
    Returns (success, error_message).
    """
    username_base = email.split('@')[0].replace('.', '_').replace('-', '_')

    # Generate a fresh secure password for this attempt
    pwd = random_password()

    # Step 1: Try to register
    username = username_base
    email_already_exists = False

    for attempt in range(10):
        try_username = username if attempt == 0 else f"{username}{attempt}"
        try:
            r = requests.post(f"{BACKEND_URL}/auth/register", json={
                'username': try_username,
                'email': email,
                'password': pwd,
                'confirm_password': pwd
            }, timeout=30)
        except requests.exceptions.ConnectionError:
            return False, 'TERMINAL ERROR: BACKEND UNREACHABLE'

        if r.status_code == 201:
            # Freshly registered
            username = try_username
            break
        elif r.status_code == 400:
            errors = r.json().get('errors', {})
            if 'username' in errors and 'email' not in errors:
                # Username taken, try next number
                continue
            elif 'email' in errors:
                # Email already exists — session was lost, need to recover
                email_already_exists = True
                break
            else:
                return False, 'REGISTRATION FAILED'
    else:
        return False, 'COULD NOT CREATE ACCOUNT'

    # Step 2: If email already existed, reset the password so we can login
    if email_already_exists:
        try:
            reset_resp = requests.post(f"{BACKEND_URL}/auth/reset_google_password", json={
                'email': email,
                'new_password': pwd
            }, timeout=30)
            if reset_resp.status_code == 200:
                username = reset_resp.json().get('username', username_base)
            else:
                return False, 'COULD NOT RECOVER ACCOUNT'
        except requests.exceptions.ConnectionError:
            return False, 'TERMINAL ERROR: BACKEND UNREACHABLE'

    # Step 3: Login with the (new or reset) password
    try:
        s = requests.Session()
        resp = s.post(f"{BACKEND_URL}/auth/login",
                      json={'username': username, 'password': pwd}, timeout=30)
        if resp.status_code == 200:
            user = resp.json().get('user', {})
            if 'google_user_passwords' not in session:
                session['google_user_passwords'] = {}
            session['google_user_passwords'][email] = {'username': username, 'password': pwd}
            session['authorized'] = True
            session['user_name'] = name or username
            session['user_id'] = user.get('id')
            session['user_email'] = email
            session['backend_username'] = username
            session['backend_password'] = pwd
            session['is_google_user'] = True
            return True, None
    except Exception as e:
        return False, str(e)

    return False, 'LOGIN FAILED AFTER REGISTRATION'


# ── INDEX ───────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html',
                           auth=session.get('authorized', False),
                           user_name=session.get('user_name', ''))


# ── LOGIN ───────────────────────────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('authorized'):
        return redirect(url_for('index'))
    error = ''
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        try:
            s = requests.Session()
            resp = s.post(f"{BACKEND_URL}/auth/login",
                          json={'username': username, 'password': password}, timeout=30)
        except requests.exceptions.ConnectionError:
            error = 'TERMINAL ERROR: BACKEND UNREACHABLE'
            return render_template('login.html', error=error)
        if resp.status_code == 200:
            user = resp.json().get('user', {})
            session['authorized'] = True
            session['user_name'] = user.get('username', username)
            session['user_id'] = user.get('id')
            session['user_email'] = user.get('email', '')
            session['backend_username'] = username
            session['backend_password'] = password
            return redirect(url_for('index'))
        else:
            error = 'TERMINAL ERROR: INVALID ACCESS KEY'
    return render_template('login.html', error=error)


# ── GOOGLE OAUTH ────────────────────────────────────────────────────────────
@app.route('/auth/google')
def google_login():
    """Redirect user to Google login page."""
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    params = {
        'client_id': GOOGLE_CLIENT_ID,
        'redirect_uri': GOOGLE_REDIRECT_URI,
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': state,
        'access_type': 'offline',
        'prompt': 'select_account',
    }
    query = '&'.join(f"{k}={v}" for k, v in params.items())
    return redirect(f"{GOOGLE_AUTH_URL}?{query}")


@app.route('/auth/google/callback')
def google_callback():
    """Handle Google OAuth callback."""
    # Verify state to prevent CSRF
    if request.args.get('state') != session.get('oauth_state'):
        flash('TERMINAL ERROR: INVALID SECURITY STATE')
        return redirect(url_for('login'))

    code = request.args.get('code')
    if not code:
        flash('TERMINAL ERROR: GOOGLE AUTH FAILED')
        return redirect(url_for('login'))

    # Exchange code for token
    try:
        token_resp = requests.post(GOOGLE_TOKEN_URL, data={
            'code': code,
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'redirect_uri': GOOGLE_REDIRECT_URI,
            'grant_type': 'authorization_code',
        }, timeout=30)
        token_data = token_resp.json()
        access_token = token_data.get('access_token')
    except Exception:
        flash('TERMINAL ERROR: FAILED TO GET TOKEN')
        return redirect(url_for('login'))

    if not access_token:
        flash('TERMINAL ERROR: NO ACCESS TOKEN')
        return redirect(url_for('login'))

    # Get user info from Google
    try:
        userinfo_resp = requests.get(GOOGLE_USERINFO_URL,
                                     headers={'Authorization': f'Bearer {access_token}'},
                                     timeout=30)
        userinfo = userinfo_resp.json()
        email = userinfo.get('email')
        name = userinfo.get('name', email)
    except Exception:
        flash('TERMINAL ERROR: FAILED TO GET USER INFO')
        return redirect(url_for('login'))

    if not email:
        flash('TERMINAL ERROR: NO EMAIL FROM GOOGLE')
        return redirect(url_for('login'))

    # Login or register the user
    success, error = login_or_register_google_user(email, name)
    if success:
        return redirect(url_for('index'))
    else:
        flash(f'GOOGLE AUTH ERROR: {error}')
        return redirect(url_for('login'))


# ── REGISTER ────────────────────────────────────────────────────────────────
@app.route('/register', methods=['GET', 'POST'])
def register():
    if session.get('authorized'):
        return redirect(url_for('index'))
    error = ''
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')
        if not username or not email or not password:
            error = 'TERMINAL ERROR: ALL FIELDS REQUIRED'
        elif password != confirm:
            error = 'TERMINAL ERROR: KEYS DO NOT MATCH'
        else:
            try:
                r = requests.post(f"{BACKEND_URL}/auth/register", json={
                    'username': username, 'email': email,
                    'password': password, 'confirm_password': confirm
                }, timeout=30)
            except requests.exceptions.ConnectionError:
                error = 'TERMINAL ERROR: BACKEND UNREACHABLE'
                return render_template('register.html', error=error)
            if r.status_code == 201:
                session['authorized'] = True
                session['user_name'] = full_name or username
                session['backend_username'] = username
                session['backend_password'] = password
                flash('CLEARANCE INITIALIZED SUCCESSFULLY', 'success')
                return redirect(url_for('index'))
            else:
                data = r.json()
                errors = data.get('errors', {})
                if errors:
                    error = ' | '.join(e[0] for e in errors.values()).upper()
                else:
                    error = data.get('error', 'REGISTRATION FAILED').upper()
    return render_template('register.html', error=error)


# ── LOGOUT ──────────────────────────────────────────────────────────────────
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ── PROFILE / CHANGE PASSWORD ───────────────────────────────────────────────
@app.route('/account/profile', methods=['GET', 'POST'])
def profile():
    if not session.get('authorized'):
        return redirect(url_for('login'))
    error = ''
    success = ''
    is_google = session.get('is_google_user', False)

    if request.method == 'POST':
        new_pw = request.form.get('new_password', '')
        confirm_pw = request.form.get('confirm_password', '')
        current_pw = request.form.get('current_password', '')

        if not new_pw or not confirm_pw:
            error = 'TERMINAL ERROR: ALL FIELDS REQUIRED'
        elif new_pw != confirm_pw:
            error = 'TERMINAL ERROR: NEW KEYS DO NOT MATCH'
        else:
            if not re.search(r'[A-Z]', new_pw):
                error = 'TERMINAL ERROR: PASSWORD NEEDS UPPERCASE LETTER'
            elif not re.search(r'\d', new_pw):
                error = 'TERMINAL ERROR: PASSWORD NEEDS A NUMBER'
            elif not re.search(r'[!@#$%^&*(),.?":{}|<>]', new_pw):
                error = 'TERMINAL ERROR: PASSWORD NEEDS A SYMBOL'
            elif len(new_pw) < 8:
                error = 'TERMINAL ERROR: PASSWORD TOO SHORT'
            else:
                if not is_google:
                    # Regular users must verify current password first
                    if not current_pw:
                        error = 'TERMINAL ERROR: CURRENT PASSWORD REQUIRED'
                    else:
                        try:
                            r = requests.post(f"{BACKEND_URL}/auth/login", json={
                                'username': session.get('backend_username'),
                                'password': current_pw
                            }, timeout=30)
                            if r.status_code != 200:
                                error = 'TERMINAL ERROR: CURRENT PASSWORD INCORRECT'
                        except Exception as e:
                            error = f'TERMINAL ERROR: {str(e)}'

                if not error:
                    # Update password using reset endpoint
                    try:
                        s2 = requests.Session()
                        s2.post(f"{BACKEND_URL}/auth/login", json={
                            'username': session.get('backend_username'),
                            'password': session.get('backend_password')
                        }, timeout=30)
                        reset = s2.post(f"{BACKEND_URL}/auth/reset_google_password", json={
                            'email': session.get('user_email', ''),
                            'new_password': new_pw
                        }, timeout=30)
                        if reset.status_code == 200:
                            session['backend_password'] = new_pw
                            _backend_sessions.pop(session.get('backend_username'), None)
                            success = 'PASSWORD UPDATED SUCCESSFULLY'
                        else:
                            error = 'TERMINAL ERROR: COULD NOT UPDATE PASSWORD'
                    except Exception as e:
                        error = f'TERMINAL ERROR: {str(e)}'

    return render_template('profile.html', error=error, success=success,
                           is_google=is_google,
                           user_name=session.get('user_name', ''),
                           username=session.get('backend_username', ''))


# ── DELETE FILES ─────────────────────────────────────────────────────────────
@app.route('/experiments/<int:experiment_id>/delete_expression', methods=['POST'])
def delete_expression(experiment_id):
    if not session.get('authorized'):
        return jsonify({'error': 'Unauthorized'}), 401
    resp = backend('POST', f'/experiments/{experiment_id}/delete_expression')
    if resp and resp.status_code == 200:
        return jsonify({'message': 'Deleted'}), 200
    return jsonify({'error': 'Could not delete file'}), 500


@app.route('/experiments/<int:experiment_id>/delete_vcf/<int:vcf_id>', methods=['POST'])
def delete_vcf(experiment_id, vcf_id):
    if not session.get('authorized'):
        return jsonify({'error': 'Unauthorized'}), 401
    resp = backend('POST', f'/experiments/{experiment_id}/delete_vcf/{vcf_id}')
    if resp and resp.status_code == 200:
        return jsonify({'message': 'Deleted'}), 200
    return jsonify({'error': 'Could not delete file'}), 500


# ── DELETE ACCOUNT ──────────────────────────────────────────────────────────
@app.route('/account/delete', methods=['GET', 'POST'])
def delete_account():
    if not session.get('authorized'):
        return redirect(url_for('login'))
    error = ''

    if request.method == 'POST':
        confirm = request.form.get('confirm_word', '').strip()
        if confirm != 'DELETE':
            error = 'TERMINAL ERROR: TYPE "DELETE" TO CONFIRM'
            return render_template('delete_account.html', error=error)

        # Keyword confirmed — delete all projects then clear session
        try:
            s = requests.Session()
            login_resp = s.post(f"{BACKEND_URL}/auth/login", json={
                'username': session.get('backend_username'),
                'password': session.get('backend_password')
            }, timeout=30)
            if login_resp.status_code == 200:
                projects_resp = s.get(f"{BACKEND_URL}/projects/", timeout=30)
                if projects_resp.status_code == 200:
                    for p in projects_resp.json().get('projects', []):
                        s.delete(f"{BACKEND_URL}/projects/{p['id']}", timeout=30)
        except requests.exceptions.ConnectionError:
            error = 'TERMINAL ERROR: BACKEND UNREACHABLE'
            return render_template('delete_account.html', error=error)

        session.clear()
        flash('ACCOUNT AND ALL DATA DELETED SUCCESSFULLY', 'success')
        return redirect(url_for('login'))

    return render_template('delete_account.html', error=error)


# ── DASHBOARD ───────────────────────────────────────────────────────────────
@app.route('/dashboard')
def dashboard():
    if not session.get('authorized'):
        return redirect(url_for('index'))
    resp = backend('GET', '/projects/')
    projects = resp.json().get('projects', []) if resp and resp.status_code == 200 else []
    total_experiments = sum(p.get('experiment_count', 0) for p in projects)
    completed = sum(p.get('status_counts', {}).get('completed', 0) for p in projects)
    running = sum(
        p.get('status_counts', {}).get('running', 0) + p.get('status_counts', {}).get('queued', 0)
        for p in projects
    )
    return render_template('dashboard.html',
                           user_name=session.get('user_name', 'USER'),
                           user_email=session.get('user_email', ''),
                           is_google_user=session.get('is_google_user', False),
                           projects=projects,
                           total_experiments=total_experiments,
                           total_projects=len(projects),
                           completed_experiments=completed,
                           running_experiments=running)


# ── PROJECTS ────────────────────────────────────────────────────────────────
@app.route('/projects')
def projects():
    if not session.get('authorized'):
        return redirect(url_for('index'))
    resp = backend('GET', '/projects/')
    project_list = resp.json().get('projects', []) if resp and resp.status_code == 200 else []
    return render_template('projects.html', projects=project_list,
                           user_name=session.get('user_name', ''))


@app.route('/projects/new', methods=['GET', 'POST'])
def new_project():
    if not session.get('authorized'):
        return redirect(url_for('index'))
    error = ''
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        desc = request.form.get('description', '').strip()
        if not name:
            error = 'Project name is required'
        else:
            resp = backend('POST', '/projects/', json={'name': name, 'description': desc})
            if resp and resp.status_code == 201:
                flash('PROJECT INITIALIZED SUCCESSFULLY', 'success')
                return redirect(url_for('project_detail',
                                        project_id=resp.json()['project']['id']))
            else:
                error = resp.json().get('error', 'Failed') if resp else 'Backend unreachable'
    return render_template('new_project.html', error=error,
                           user_name=session.get('user_name', ''))


@app.route('/projects/<int:project_id>')
def project_detail(project_id):
    if not session.get('authorized'):
        return redirect(url_for('index'))
    resp = backend('GET', f'/projects/{project_id}')
    if not resp or resp.status_code != 200:
        flash('Project not found')
        return redirect(url_for('projects'))
    data = resp.json()
    return render_template('project_detail.html',
                           project=data['project'],
                           experiments=data.get('experiments', []),
                           user_name=session.get('user_name', ''))


@app.route('/projects/<int:project_id>/status')
def project_status(project_id):
    """JSON endpoint for live-polling experiment statuses on the project detail page."""
    if not session.get('authorized'):
        return jsonify({'error': 'unauthorized'}), 401
    resp = backend('GET', f'/projects/{project_id}')
    if not resp or resp.status_code != 200:
        return jsonify({'error': 'not found'}), 404
    data = resp.json()
    project = data.get('project', {})
    experiments = data.get('experiments', [])
    active_statuses = {'running', 'queued'}
    has_active = any(e.get('status') in active_statuses for e in experiments)
    return jsonify({
        'experiment_count': project.get('experiment_count', 0),
        'status_counts': project.get('status_counts', {}),
        'has_active': has_active,
        'experiments': [
            {
                'id': e['id'],
                'status': e.get('status', ''),
                'current_step': e.get('current_step', 0),
            }
            for e in experiments
        ]
    })


@app.route('/projects/<int:project_id>/delete', methods=['POST'])
def delete_project(project_id):
    if not session.get('authorized'):
        return redirect(url_for('index'))
    backend('DELETE', f'/projects/{project_id}')
    flash('PROJECT DELETED', 'success')
    return redirect(url_for('projects'))


# ── EXPERIMENTS ─────────────────────────────────────────────────────────────
@app.route('/projects/<int:project_id>/experiments/new', methods=['GET', 'POST'])
def new_experiment(project_id):
    if not session.get('authorized'):
        return redirect(url_for('index'))
    error = ''
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        desc = request.form.get('description', '').strip()
        if not name:
            error = 'Experiment name is required'
        else:
            resp = backend('POST', f'/experiments/{project_id}',
                           json={'name': name, 'description': desc})
            if resp and resp.status_code == 201:
                flash('EXPERIMENT CREATED SUCCESSFULLY', 'success')
                return redirect(url_for('experiment_detail',
                                        experiment_id=resp.json()['experiment']['id']))
            else:
                error = resp.json().get('error', 'Failed') if resp else 'Backend unreachable'
    return render_template('new_experiment.html', project_id=project_id,
                           error=error, user_name=session.get('user_name', ''))


@app.route('/experiments/<int:experiment_id>')
def experiment_detail(experiment_id):
    if not session.get('authorized'):
        return redirect(url_for('index'))
    # Fetch full experiment detail directly (includes has_result, error_message, current_step, etc.)
    # Use /status endpoint to avoid URL collision with list-experiments route
    resp = backend('GET', f'/experiments/{experiment_id}/status')
    if not resp or resp.status_code != 200:
        status_code = resp.status_code if resp else 'None'
        body = resp.text[:300] if resp else 'no response'
        flash(f'Experiment not found (status={status_code}, body={body})')
        return redirect(url_for('projects'))
    status_data = resp.json()

    # Also get project info so we have project_name
    # Build experiment dict combining status data with what we need
    experiment = {
        'id': experiment_id,
        'name': status_data.get('name', ''),
        'description': status_data.get('description', ''),
        'status': status_data.get('status', ''),
        'current_step': status_data.get('current_step', 0),
        'has_expression_file': status_data.get('has_expression_file', False),
        'has_vcf_files': status_data.get('has_vcf_files', False),
        'expression_filename': status_data.get('expression_filename', ''),
        'vcf_file_count': status_data.get('vcf_file_count', 0),
        'has_result': status_data.get('has_result', False),
        'can_run': status_data.get('can_run', False),
        'error_message': status_data.get('error_message', ''),
        'started_at': status_data.get('started_at'),
        'completed_at': status_data.get('completed_at'),
        'project_id': status_data.get('project_id', ''),
        'project_name': status_data.get('project_name', ''),
        'vcf_files': status_data.get('vcf_files', []),
    }
    if not experiment['status']:
        flash('Experiment not found')
        return redirect(url_for('projects'))
    return render_template('experiment_detail.html', experiment=experiment,
                           user_name=session.get('user_name', ''))


@app.route('/experiments/<int:experiment_id>/upload_expression', methods=['POST'])
def upload_expression(experiment_id):
    if not session.get('authorized'):
        return jsonify({'error': 'Unauthorized'}), 401
    f = request.files.get('expression_file')
    if not f:
        return jsonify({'error': 'No file provided'}), 400
    resp = backend('POST', f'/experiments/{experiment_id}/upload_expression',
                   files={'expression_file': (f.filename, f.stream, f.content_type)})
    if resp is None:
        return jsonify({"error": "Backend unreachable"}), 503
    return jsonify(resp.json()), resp.status_code


@app.route('/experiments/<int:experiment_id>/upload_vcf', methods=['POST'])
def upload_vcf(experiment_id):
    if not session.get('authorized'):
        return jsonify({'error': 'Unauthorized'}), 401
    files = request.files.getlist('vcf_files')
    if not files:
        return jsonify({'error': 'No files provided'}), 400
    file_tuples = [('vcf_files', (f.filename, f.stream, f.content_type)) for f in files]
    resp = backend('POST', f'/experiments/{experiment_id}/upload_vcf', files=file_tuples)
    if resp is None:
        return jsonify({"error": "Backend unreachable"}), 503
    return jsonify(resp.json()), resp.status_code


@app.route('/experiments/<int:experiment_id>/run', methods=['POST'])
def run_experiment(experiment_id):
    if not session.get('authorized'):
        return jsonify({'error': 'Unauthorized'}), 401
    resp = backend('POST', f'/experiments/{experiment_id}/run')
    if resp is None:
        return jsonify({"error": "Backend unreachable"}), 503
    return jsonify(resp.json()), resp.status_code


@app.route('/experiments/<int:experiment_id>/status')
def experiment_status(experiment_id):
    if not session.get('authorized'):
        return jsonify({'error': 'Unauthorized'}), 401
    resp = backend('GET', f'/experiments/{experiment_id}/status')
    if resp is None:
        return jsonify({"error": "Backend unreachable"}), 503
    return jsonify(resp.json()), resp.status_code


@app.route('/experiments/<int:experiment_id>/download')
def download_result(experiment_id):
    if not session.get('authorized'):
        return redirect(url_for('index'))
    resp = backend('GET', f'/experiments/{experiment_id}/download', stream=True)
    if resp and resp.status_code == 200:
        return Response(
            resp.iter_content(chunk_size=8192),
            content_type=resp.headers.get('Content-Type', 'text/csv'),
            headers={'Content-Disposition': resp.headers.get(
                'Content-Disposition', f'attachment; filename=result_{experiment_id}.csv')})
    flash('Result not available yet')
    return redirect(url_for('experiment_detail', experiment_id=experiment_id))


@app.route('/experiments/<int:experiment_id>/delete', methods=['POST'])
def delete_experiment(experiment_id):
    if not session.get('authorized'):
        return redirect(url_for('index'))
    project_id = request.form.get('project_id')
    backend('DELETE', f'/experiments/{experiment_id}')
    flash('EXPERIMENT DELETED', 'success')
    if project_id:
        return redirect(url_for('project_detail', project_id=int(project_id)))
    return redirect(url_for('projects'))


@app.route('/unauthorized')
def unauthorized():
    return render_template('unauthorized.html')


@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


# ── Deployment (professor's server) ─────────────────────────────────────────
hostedApp = Flask(__name__)
hostedApp.wsgi_app = DispatcherMiddleware(NotFound(), {PREFIX: app}) if PREFIX else app


if __name__ == '__main__':
    app.run(debug=False, port=8080)
