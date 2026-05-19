"""
Authentication routes.

Handles user registration, login, and logout with secure password hashing.
"""

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_user, logout_user, current_user
from app.models import db, User
from app.auth.forms import RegistrationForm, LoginForm

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['POST'])
def register():
    """
    Register a new user.
    
    Expected JSON:
        {
            "username": "string",
            "email": "string",
            "password": "string",
            "confirm_password": "string"
        }
    
    Returns:
        201: User created successfully
        400: Validation errors
    """
    if current_user.is_authenticated:
        return jsonify({'error': 'Already logged in'}), 400
    
    form = RegistrationForm(data=request.get_json())
    
    if form.validate():
        try:
            # Create new user with hashed password
            user = User(
                username=form.username.data,
                email=form.email.data
            )
            user.set_password(form.password.data)
            
            db.session.add(user)
            db.session.commit()
            
            current_app.logger.info(f'New user registered: {user.username}')
            
            return jsonify({
                'message': 'Registration successful',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email
                }
            }), 201
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Registration error: {str(e)}')
            return jsonify({'error': 'Registration failed', 'message': str(e)}), 500
    
    # Return validation errors
    return jsonify({'error': 'Validation failed', 'errors': form.errors}), 400


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Authenticate user and create session.
    
    Expected JSON:
        {
            "username": "string",
            "password": "string",
            "remember_me": boolean (optional)
        }
    
    Returns:
        200: Login successful
        401: Invalid credentials
    """
    if current_user.is_authenticated:
        return jsonify({'error': 'Already logged in'}), 400
    
    form = LoginForm(data=request.get_json())
    
    if form.validate():
        user = User.query.filter_by(username=form.username.data).first()
        
        if user and user.check_password(form.password.data):
            if not user.is_active:
                return jsonify({'error': 'Account is disabled'}), 403
            
            # Log user in
            login_user(user, remember=form.remember_me.data)
            user.update_last_login()
            
            current_app.logger.info(f'User logged in: {user.username}')
            
            return jsonify({
                'message': 'Login successful',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'last_login': user.last_login.isoformat() if user.last_login else None
                }
            }), 200
        
        return jsonify({'error': 'Invalid username or password'}), 401
    
    return jsonify({'error': 'Validation failed', 'errors': form.errors}), 400


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """
    Logout current user and destroy session.
    
    Returns:
        200: Logout successful
    """
    if not current_user.is_authenticated:
        return jsonify({'error': 'Not logged in'}), 400
    
    username = current_user.username
    logout_user()
    
    current_app.logger.info(f'User logged out: {username}')
    
    return jsonify({'message': 'Logout successful'}), 200


@auth_bp.route('/me', methods=['GET'])
def get_current_user():
    """
    Get current authenticated user information.
    
    Returns:
        200: User information
        401: Not authenticated
    """
    if not current_user.is_authenticated:
        return jsonify({'error': 'Not authenticated'}), 401
    
    return jsonify({
        'user': {
            'id': current_user.id,
            'username': current_user.username,
            'email': current_user.email,
            'created_at': current_user.created_at.isoformat(),
            'is_google_user': current_user.is_google_user,
            'last_login': current_user.last_login.isoformat() if current_user.last_login else None
        }
    }), 200


@auth_bp.route('/delete_account', methods=['POST'])
def delete_account():
    """
    Permanently delete the currently authenticated user account and all data.

    For regular users: requires 'password' in JSON body for confirmation.
    For Google OAuth users: deletion is allowed without a password since they
    authenticated via Google and have no local password to verify.

    Returns:
        200: Account deleted
        400: Wrong password / bad request
        401: Not authenticated
    """
    if not current_user.is_authenticated:
        return jsonify({'error': 'Not authenticated'}), 401

    user = User.query.get(current_user.id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    # Google users have no local password — skip password verification
    if not user.is_google_user:
        data = request.get_json() or {}
        password = data.get('password', '')
        if not password:
            return jsonify({'error': 'Password is required to delete account'}), 400
        if not user.check_password(password):
            return jsonify({'error': 'Incorrect password'}), 400

    try:
        username = user.username
        logout_user()
        db.session.delete(user)
        db.session.commit()
        current_app.logger.info(f'Account deleted: {username}')
        return jsonify({'message': 'Account deleted successfully'}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Account deletion error: {str(e)}')
        return jsonify({'error': 'Failed to delete account', 'message': str(e)}), 500


@auth_bp.route('/find_by_email', methods=['POST'])
def find_by_email():
    """
    Find a username by email address.
    Used by Google OAuth flow to recover username when session is lost.
    Only works for Google-registered users.
    """
    data = request.get_json() or {}
    email = data.get('email', '').strip()
    if not email:
        return jsonify({'error': 'Email required'}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    return jsonify({'username': user.username}), 200


@auth_bp.route('/reset_google_password', methods=['POST'])
def reset_google_password():
    """
    Reset password for a Google OAuth user.
    Allows Google users to get a new password when their session is lost.
    """
    data = request.get_json() or {}
    email = data.get('email', '').strip()
    new_password = data.get('new_password', '')

    if not email or not new_password:
        return jsonify({'error': 'Email and new_password required'}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    try:
        user.set_password(new_password)
        db.session.commit()
        return jsonify({'message': 'Password reset successful', 'username': user.username}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
