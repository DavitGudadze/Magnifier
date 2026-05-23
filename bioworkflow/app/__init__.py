"""
Flask application factory.

Initializes all extensions, registers blueprints, and configures the application.
"""

import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, jsonify
from flask_cors import CORS
from flask_login import LoginManager
from flask_migrate import Migrate

from config import get_config
from app.models import db, User

# Initialize extensions
login_manager = LoginManager()
migrate = Migrate()


def create_app(config_name=None):
    """
    Application factory pattern.

    Args:
        config_name: Configuration environment ('development', 'production', 'testing')

    Returns:
        Configured Flask application instance
    """
    app = Flask(__name__)
    CORS(app)

    # Load configuration
    config_obj = get_config(config_name)
    app.config.from_object(config_obj)

    # Initialize extensions
    initialize_extensions(app)

    # Register blueprints
    register_blueprints(app)

    # Configure logging
    configure_logging(app)

    # Register error handlers
    register_error_handlers(app)

    return app


def initialize_extensions(app):
    """Initialize Flask extensions."""

    # Database
    db.init_app(app)

    # Migrations
    migrate.init_app(app, db)

    # Auto-create tables on first run if no migrations have been applied yet.
    # This is a safety net only — on a fresh install run `flask db upgrade` instead.
    with app.app_context():
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        if not inspector.has_table('users'):
            db.create_all()

    # Login manager
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

    @login_manager.user_loader
    def load_user(user_id):
        """Load user by ID for Flask-Login."""
        return db.session.get(User, int(user_id))


def register_blueprints(app):
    """Register application blueprints."""

    from app.auth.routes import auth_bp
    from app.projects.routes import projects_bp
    from app.experiments.routes import experiments_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(projects_bp, url_prefix='/projects')
    app.register_blueprint(experiments_bp, url_prefix='/experiments')

    # Health check endpoint
    @app.route('/health')
    def health_check():
        """Simple health check endpoint for monitoring."""
        return jsonify({
            'status': 'healthy',
            'service': 'bioinformatics-workflow-platform'
        }), 200

    @app.route('/')
    def index():
        """Root endpoint."""
        return jsonify({
            'message': 'Bioinformatics Workflow Platform API',
            'version': '1.0.0',
            'endpoints': {
                'auth': '/auth',
                'projects': '/projects',
                'experiments': '/experiments'
            }
        }), 200


def configure_logging(app):
    """Configure application logging."""

    if not app.debug and not app.testing:
        # File handler for production
        file_handler = RotatingFileHandler(
            app.config['LOG_FILE'],
            maxBytes=10485760,  # 10MB
            backupCount=10
        )

        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))

        file_handler.setLevel(getattr(logging, app.config['LOG_LEVEL']))
        app.logger.addHandler(file_handler)
        app.logger.setLevel(getattr(logging, app.config['LOG_LEVEL']))

        app.logger.info('Bioinformatics Workflow Platform startup')


def register_error_handlers(app):
    """Register custom error handlers."""

    @app.errorhandler(400)
    def bad_request(error):
        """Handle 400 Bad Request errors."""
        return jsonify({'error': 'Bad request', 'message': str(error)}), 400

    @app.errorhandler(401)
    def unauthorized(error):
        """Handle 401 Unauthorized errors."""
        return jsonify({'error': 'Unauthorized', 'message': 'Authentication required'}), 401

    @app.errorhandler(403)
    def forbidden(error):
        """Handle 403 Forbidden errors."""
        return jsonify({'error': 'Forbidden', 'message': 'You do not have permission to access this resource'}), 403

    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 Not Found errors."""
        return jsonify({'error': 'Not found', 'message': 'The requested resource was not found'}), 404

    @app.errorhandler(413)
    def request_entity_too_large(error):
        """Handle 413 Request Entity Too Large errors."""
        return jsonify({'error': 'File too large', 'message': 'The uploaded file exceeds the maximum allowed size'}), 413

    @app.errorhandler(500)
    def internal_server_error(error):
        """Handle 500 Internal Server Error."""
        app.logger.error(f'Internal server error: {error}')
        return jsonify({'error': 'Internal server error', 'message': 'An unexpected error occurred'}), 500
