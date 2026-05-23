"""
Database models for the bioinformatics workflow platform.

Hierarchy: User → Project → Experiment → Results
"""

from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy import Index
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


def _utcnow() -> datetime:
    """Return the current UTC time as a naive datetime (database-compatible)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(UserMixin, db.Model):
    """User model with authentication capabilities."""

    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    last_login = db.Column(db.DateTime)

    # Account status
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_google_user = db.Column(db.Boolean, default=False, nullable=False)

    # Relationships
    projects = db.relationship('Project', back_populates='owner',
                               lazy='dynamic', cascade='all, delete-orphan')

    def set_password(self, password):
        """Hash and set user password using bcrypt."""
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        """Verify password against stored hash."""
        return check_password_hash(self.password_hash, password)

    def update_last_login(self):
        """Update last login timestamp."""
        self.last_login = _utcnow()
        db.session.commit()

    def __repr__(self):
        return f'<User {self.username}>'


class Project(db.Model):
    """Project model - contains multiple experiments."""

    __tablename__ = 'projects'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)

    # Ownership
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    # Relationships
    owner = db.relationship('User', back_populates='projects')
    experiments = db.relationship(
        'Experiment', back_populates='project',
        lazy='dynamic', cascade='all, delete-orphan'
    )

    # Indexes for performance
    __table_args__ = (
        Index('idx_user_created', 'user_id', 'created_at'),
    )

    def __repr__(self):
        return f'<Project {self.name}>'


class Experiment(db.Model):
    """
    Experiment model - represents a single pipeline execution.

    Each experiment has:
    - One gene expression file
    - Multiple VCF files (folder)
    - Intermediate results
    - Final contingency table
    """

    __tablename__ = 'experiments'

    # Status constants
    STATUS_CREATED = 'created'
    STATUS_UPLOADING = 'uploading'
    STATUS_READY = 'ready'
    STATUS_QUEUED = 'queued'
    STATUS_RUNNING = 'running'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'

    VALID_STATUSES = [
        STATUS_CREATED, STATUS_UPLOADING, STATUS_READY,
        STATUS_QUEUED, STATUS_RUNNING, STATUS_COMPLETED, STATUS_FAILED
    ]

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)

    # Project relationship
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False, index=True)

    # Execution status
    status = db.Column(db.String(20), nullable=False, default=STATUS_CREATED, index=True)

    # File tracking
    has_expression_file = db.Column(db.Boolean, default=False, nullable=False)
    has_vcf_files = db.Column(db.Boolean, default=False, nullable=False)
    expression_filename = db.Column(db.String(255))
    vcf_file_count = db.Column(db.Integer, default=0)

    # Pipeline execution tracking
    celery_task_id = db.Column(db.String(255), unique=True, index=True)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)

    # Pipeline progress tracking
    current_step = db.Column(db.Integer, default=0)  # 0-4 for the 4 scripts
    step_details = db.Column(db.Text)  # JSON string for detailed progress

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    # Relationships
    project = db.relationship('Project', back_populates='experiments')
    result = db.relationship('Result', back_populates='experiment', uselist=False,
                             cascade='all, delete-orphan')

    # Indexes for performance
    __table_args__ = (
        Index('idx_project_status', 'project_id', 'status'),
        Index('idx_project_created', 'project_id', 'created_at'),
    )

    def update_status(self, new_status, error_message=None):
        """Update experiment status with validation."""
        if new_status not in self.VALID_STATUSES:
            raise ValueError(f'Invalid status: {new_status}')

        self.status = new_status
        self.updated_at = _utcnow()

        if new_status == self.STATUS_RUNNING and not self.started_at:
            self.started_at = _utcnow()

        if new_status in [self.STATUS_COMPLETED, self.STATUS_FAILED]:
            self.completed_at = _utcnow()

        if error_message:
            self.error_message = error_message

        db.session.commit()

    def is_ready_to_run(self):
        """Check if experiment has all required files to run pipeline."""
        return self.has_expression_file and self.has_vcf_files

    def can_be_executed(self):
        """Check if experiment can be executed (has files and not already running)."""
        return (self.is_ready_to_run() and
                self.status not in [self.STATUS_RUNNING, self.STATUS_QUEUED, self.STATUS_COMPLETED])

    @property
    def duration_seconds(self):
        """Calculate execution duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def __repr__(self):
        return f'<Experiment {self.name} (status={self.status})>'


class Result(db.Model):
    """
    Result model - stores final contingency table and metadata.

    One result per experiment after successful completion.
    """

    __tablename__ = 'results'

    id = db.Column(db.Integer, primary_key=True)

    # Link to experiment
    experiment_id = db.Column(db.Integer, db.ForeignKey('experiments.id'), nullable=False, unique=True, index=True)

    # Result file information
    contingency_table_path = db.Column(db.String(500), nullable=False)
    file_size_bytes = db.Column(db.BigInteger)
    file_hash = db.Column(db.String(64))  # SHA256 hash for integrity

    # Result statistics (optional - can be populated by parsing the table)
    total_genes = db.Column(db.Integer)
    significant_genes = db.Column(db.Integer)
    metadata_json = db.Column(db.Text)  # Additional metadata in JSON format

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    # Relationships
    experiment = db.relationship('Experiment', back_populates='result')

    def __repr__(self):
        return f'<Result for Experiment {self.experiment_id}>'


class ProjectMergedResult(db.Model):
    """
    Stores merged contingency tables for entire projects.

    Generated by combining results from multiple experiments within a project.
    """

    __tablename__ = 'project_merged_results'

    id = db.Column(db.Integer, primary_key=True)

    # Link to project
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False, index=True)

    # Merged result file
    merged_table_path = db.Column(db.String(500), nullable=False)
    file_size_bytes = db.Column(db.BigInteger)

    # Track which experiments were included
    experiment_ids_included = db.Column(db.Text, nullable=False)  # JSON array of IDs
    experiment_count = db.Column(db.Integer, nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    # Relationship
    project = db.relationship('Project')

    def __repr__(self):
        return f'<ProjectMergedResult for Project {self.project_id}>'
