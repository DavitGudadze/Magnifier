"""
WSGI entry point.

For local development:
    python wsgi.py

For production (uWSGI on shared server):
    uwsgi bioworkflow.ini
"""

import os
from flask import Flask
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.exceptions import NotFound
from app import create_app

# The real Flask application
app = create_app(os.environ.get('FLASK_ENV', 'development'))

PREFIX = os.environ.get('PREFIX', '')

if PREFIX:
    # Professor's deployment pattern:
    # A separate wrapper app owns the DispatcherMiddleware so there is no
    # circular reference (the middleware calls `app`, not the wrapper itself).
    hostedApp = Flask(__name__)
    hostedApp.wsgi_app = DispatcherMiddleware(NotFound(), {PREFIX: app})
    # uWSGI's `module = wsgi:app` must point to the wrapper when PREFIX is set
    app = hostedApp

if __name__ == '__main__':
    # Local dev — run the original Flask app directly (PREFIX not needed)
    create_app(os.environ.get('FLASK_ENV', 'development')).run(debug=True, port=5000)
