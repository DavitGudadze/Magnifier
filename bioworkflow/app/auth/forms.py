"""
Authentication forms with validation.

Uses Flask-WTF for CSRF protection and validation.
"""

import re
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
from app.models import User


class RegistrationForm(FlaskForm):
    """User registration form."""
    
    username = StringField('Username', validators=[
        DataRequired(),
        Length(min=3, max=80, message='Username must be between 3 and 80 characters')
    ])
    
    email = StringField('Email', validators=[
        DataRequired(),
        Email(message='Invalid email address')
    ])
    
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters long')
    ])

    def validate_password(self, password):
        """Enforce strong password: 1 uppercase, 1 digit, 1 symbol."""
        pwd = password.data or ''
        errors = []
        if not re.search(r'[A-Z]', pwd):
            errors.append('at least one uppercase letter')
        if not re.search(r'\d', pwd):
            errors.append('at least one number')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\\/~`\';\s]', pwd):
            errors.append('at least one special character (e.g. !@#$%)')
        if errors:
            raise ValidationError('Password must contain ' + ', '.join(errors) + '.')
    
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    
    def validate_username(self, username):
        """Check if username already exists."""
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already taken. Please choose a different one.')
    
    def validate_email(self, email):
        """Check if email already exists."""
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered. Please use a different one.')


class LoginForm(FlaskForm):
    """User login form."""
    
    username = StringField('Username', validators=[
        DataRequired()
    ])
    
    password = PasswordField('Password', validators=[
        DataRequired()
    ])
    
    remember_me = BooleanField('Remember Me')
