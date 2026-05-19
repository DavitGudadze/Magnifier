"""
Authentication and authorization utilities.

Provides decorators for protecting routes and checking permissions.
"""

from functools import wraps
from flask import jsonify
from flask_login import current_user
from app.models import Project, Experiment


def login_required_api(f):
    """
    Decorator to require authentication for API endpoints.
    
    Returns JSON error instead of redirecting to login page.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function


def project_access_required(f):
    """
    Decorator to verify user has access to a project.
    
    Expects 'project_id' in route parameters.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401
        
        project_id = kwargs.get('project_id')
        if not project_id:
            return jsonify({'error': 'Project ID required'}), 400
        
        project = Project.query.get(project_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        if project.user_id != current_user.id:
            return jsonify({'error': 'Access denied to this project'}), 403
        
        # Add project to kwargs for convenience
        kwargs['project'] = project
        return f(*args, **kwargs)
    
    return decorated_function


def experiment_access_required(f):
    """
    Decorator to verify user has access to an experiment.
    
    Expects 'experiment_id' in route parameters.
    Also verifies project ownership.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401
        
        experiment_id = kwargs.get('experiment_id') or kwargs.get('id')
        if not experiment_id:
            return jsonify({'error': 'Experiment ID required'}), 400
        
        experiment = Experiment.query.get(experiment_id)
        if not experiment:
            return jsonify({'error': 'Experiment not found'}), 404
        
        # Check project ownership
        if experiment.project.user_id != current_user.id:
            return jsonify({'error': 'Access denied to this experiment'}), 403
        
        # Add experiment to kwargs for convenience
        kwargs['experiment'] = experiment
        return f(*args, **kwargs)
    
    return decorated_function


def active_user_required(f):
    """
    Decorator to ensure user account is active.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401
        
        if not current_user.is_active:
            return jsonify({'error': 'Account is disabled'}), 403
        
        return f(*args, **kwargs)
    
    return decorated_function
