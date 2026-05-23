"""
Configuration module for the bioinformatics workflow platform.

Loads configuration from environment variables and provides
configuration classes for different deployment environments.
"""

import os
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
basedir = Path(__file__).parent.absolute()
load_dotenv(basedir / '.env')


class Config:
    """Base configuration class with common settings."""

    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f'sqlite:///{basedir / "bioworkflow.db"}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }

    # File Storage
    STORAGE_ROOT = basedir / 'storage'
    UPLOAD_FOLDER = STORAGE_ROOT / 'uploads'
    INTERMEDIATE_FOLDER = STORAGE_ROOT / 'intermediate'
    RESULTS_FOLDER = STORAGE_ROOT / 'results'

    # Create storage directories if they don't exist
    for folder in [UPLOAD_FOLDER, INTERMEDIATE_FOLDER, RESULTS_FOLDER]:
        folder.mkdir(parents=True, exist_ok=True)

    # File Upload Settings
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 5368709120))  # 5GB
    ALLOWED_EXPRESSION_EXTENSIONS = set(
        os.environ.get('ALLOWED_EXPRESSION_EXTENSIONS', '.csv,.tsv,.txt,.tab').split(',')
    )
    ALLOWED_VCF_EXTENSIONS = set(
        os.environ.get('ALLOWED_VCF_EXTENSIONS', '.vcf,.vcf.gz').split(',')
    )

    # Session Configuration
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(
        seconds=int(os.environ.get('PERMANENT_SESSION_LIFETIME', 86400))
    )

    # Security
    WTF_CSRF_ENABLED = False
    WTF_CSRF_TIME_LIMIT = None  # CSRF tokens don't expire

    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = basedir / 'logs' / 'bioworkflow.log'

    # Create logs directory
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Deployment prefix for shared server (e.g. '/bioworkflow')
    # Must match the path the professor proxies to your socket
    PREFIX = os.environ.get('PREFIX', '')

    # Pipeline time limit in seconds (default 2 hours)
    TASK_TIME_LIMIT = int(os.environ.get('TASK_TIME_LIMIT', 7200))

    # Pipeline Scripts Configuration
    SCRIPTS_DIR = basedir / 'scripts'
    SCRIPT_DEA = SCRIPTS_DIR / 'dea_analysis.py'
    SCRIPT_VEP = SCRIPTS_DIR / 'vep_processing.py'
    SCRIPT_JOIN = SCRIPTS_DIR / 'join_results.py'
    SCRIPT_CONTINGENCY = SCRIPTS_DIR / 'generate_contingency.py'

    # Python interpreter (can point to conda environment)
    PYTHON_INTERPRETER = os.environ.get('PYTHON_INTERPRETER', 'python3')


class DevelopmentConfig(Config):
    """Development environment configuration."""
    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    """Production environment configuration."""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True

    # Override with environment variable or fail
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY or SECRET_KEY == 'dev-secret-key-change-in-production':
        raise ValueError('SECRET_KEY must be set in production environment')


class TestingConfig(Config):
    """Testing environment configuration."""
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config(env=None):
    """Get configuration object based on environment."""
    if env is None:
        env = os.environ.get('FLASK_ENV', 'development')
    return config.get(env, config['default'])
