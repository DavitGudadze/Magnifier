"""
Projects routes.

Handles CRUD operations for projects and project-level analysis.
"""

from flask import Blueprint, request, jsonify, current_app, send_file
from flask_login import current_user
from app.models import db, Project, Experiment, ProjectMergedResult
from app.utils.auth import login_required_api, project_access_required
from app.utils.files import get_project_storage_usage
from app.services.tasks import merge_project_results_task

projects_bp = Blueprint('projects', __name__)


@projects_bp.route('/', methods=['GET'])
@login_required_api
def list_projects():
    """
    List all projects for the current user.
    
    Query parameters:
        sort: Sort by 'created' (default) or 'updated'
        order: 'asc' or 'desc' (default)
    
    Returns:
        200: List of projects
    """
    sort_by = request.args.get('sort', 'created')
    order = request.args.get('order', 'desc')
    
    query = Project.query.filter_by(user_id=current_user.id)
    
    # Apply sorting
    if sort_by == 'updated':
        query = query.order_by(
            Project.updated_at.desc() if order == 'desc' 
            else Project.updated_at.asc()
        )
    else:  # default to created
        query = query.order_by(
            Project.created_at.desc() if order == 'desc' 
            else Project.created_at.asc()
        )
    
    projects = query.all()
    
    return jsonify({
        'projects': [
            {
                'id': p.id,
                'name': p.name,
                'description': p.description,
                'created_at': p.created_at.isoformat(),
                'updated_at': p.updated_at.isoformat(),
                'experiment_count': p.experiments.count(),
                'status_counts': {
                    'completed': p.experiments.filter_by(status=Experiment.STATUS_COMPLETED).count(),
                    'running':   p.experiments.filter_by(status=Experiment.STATUS_RUNNING).count(),
                    'queued':    p.experiments.filter_by(status=Experiment.STATUS_QUEUED).count(),
                    'failed':    p.experiments.filter_by(status=Experiment.STATUS_FAILED).count(),
                }
            }
            for p in projects
        ]
    }), 200


@projects_bp.route('/', methods=['POST'])
@login_required_api
def create_project():
    """
    Create a new project.
    
    Expected JSON:
        {
            "name": "string",
            "description": "string" (optional)
        }
    
    Returns:
        201: Project created
        400: Validation error
    """
    data = request.get_json()
    
    if not data or 'name' not in data:
        return jsonify({'error': 'Project name is required'}), 400
    
    name = data['name'].strip()
    if not name:
        return jsonify({'error': 'Project name cannot be empty'}), 400
    
    if len(name) > 200:
        return jsonify({'error': 'Project name too long (max 200 characters)'}), 400
    
    try:
        project = Project(
            name=name,
            description=data.get('description', ''),
            user_id=current_user.id
        )
        
        db.session.add(project)
        db.session.commit()
        
        current_app.logger.info(
            f'Project created: {project.id} by user {current_user.username}'
        )
        
        return jsonify({
            'message': 'Project created successfully',
            'project': {
                'id': project.id,
                'name': project.name,
                'description': project.description,
                'created_at': project.created_at.isoformat()
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Project creation error: {str(e)}')
        return jsonify({'error': 'Failed to create project'}), 500


@projects_bp.route('/<int:project_id>', methods=['GET'])
@project_access_required
def get_project(project_id, project):
    """
    Get detailed information about a project.
    
    Returns:
        200: Project details with experiments
        404: Project not found
        403: Access denied
    """
    # Get storage usage
    storage = get_project_storage_usage(current_user.id, project_id)
    
    # Get experiments
    experiments = project.experiments.all()
    
    # Count by status
    status_counts = {}
    for exp in experiments:
        status_counts[exp.status] = status_counts.get(exp.status, 0) + 1
    
    return jsonify({
        'project': {
            'id': project.id,
            'name': project.name,
            'description': project.description,
            'created_at': project.created_at.isoformat(),
            'updated_at': project.updated_at.isoformat(),
            'experiment_count': len(experiments),
            'status_counts': status_counts,
            'storage': {
                'uploads_mb': storage['uploads_bytes'] / (1024**2),
                'intermediate_mb': storage['intermediate_bytes'] / (1024**2),
                'results_mb': storage['results_bytes'] / (1024**2),
                'total_mb': sum(storage.values()) / (1024**2)
            }
        },
        'experiments': [
            {
                'id': exp.id,
                'name': exp.name,
                'status': exp.status,
                'created_at': exp.created_at.isoformat(),
                'has_expression_file': exp.has_expression_file,
                'has_vcf_files': exp.has_vcf_files,
                'vcf_file_count': exp.vcf_file_count
            }
            for exp in experiments
        ]
    }), 200


@projects_bp.route('/<int:project_id>', methods=['PUT'])
@project_access_required
def update_project(project_id, project):
    """
    Update project details.
    
    Expected JSON:
        {
            "name": "string" (optional),
            "description": "string" (optional)
        }
    
    Returns:
        200: Project updated
        400: Validation error
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    try:
        if 'name' in data:
            name = data['name'].strip()
            if not name:
                return jsonify({'error': 'Project name cannot be empty'}), 400
            if len(name) > 200:
                return jsonify({'error': 'Project name too long'}), 400
            project.name = name
        
        if 'description' in data:
            project.description = data['description']
        
        db.session.commit()
        
        current_app.logger.info(f'Project updated: {project.id}')
        
        return jsonify({
            'message': 'Project updated successfully',
            'project': {
                'id': project.id,
                'name': project.name,
                'description': project.description,
                'updated_at': project.updated_at.isoformat()
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Project update error: {str(e)}')
        return jsonify({'error': 'Failed to update project'}), 500


@projects_bp.route('/<int:project_id>', methods=['DELETE'])
@project_access_required
def delete_project(project_id, project):
    """
    Delete a project and all its experiments.
    
    WARNING: This will delete all associated data including files.
    
    Returns:
        200: Project deleted
    """
    try:
        project_name = project.name
        
        # SQLAlchemy cascade will handle experiments deletion
        db.session.delete(project)
        db.session.commit()
        
        current_app.logger.info(
            f'Project deleted: {project_id} ({project_name}) by user {current_user.username}'
        )
        
        # TODO: Optionally delete files from storage
        # This could be done asynchronously
        
        return jsonify({
            'message': 'Project deleted successfully',
            'project_id': project_id
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Project deletion error: {str(e)}')
        return jsonify({'error': 'Failed to delete project'}), 500


@projects_bp.route('/<int:project_id>/generate_merged_table', methods=['POST'])
@project_access_required
def generate_merged_table(project_id, project):
    """
    Generate a merged contingency table from all completed experiments.
    
    This triggers an asynchronous task to merge all experiment results.
    
    Returns:
        202: Task queued
        400: No experiments to merge
    """
    # Check if there are completed experiments
    completed_count = Experiment.query.filter_by(
        project_id=project_id,
        status=Experiment.STATUS_COMPLETED
    ).count()
    
    if completed_count == 0:
        return jsonify({
            'error': 'No completed experiments to merge'
        }), 400
    
    try:
        import threading
        import uuid

        task_id = str(uuid.uuid4())

        app = current_app._get_current_object()
        proj_id = project_id

        def run_in_context():
            with app.app_context():
                merge_project_results_task(proj_id)

        thread = threading.Thread(target=run_in_context, daemon=True)
        thread.start()

        current_app.logger.info(
            f'Merge task started for project {project_id}: thread {task_id}'
        )

        return jsonify({
            'message': 'Merge task started',
            'task_id': task_id,
            'experiments_to_merge': completed_count
        }), 202

    except Exception as e:
        current_app.logger.error(f'Failed to start merge task: {str(e)}')
        return jsonify({'error': 'Failed to start merge task'}), 500


@projects_bp.route('/<int:project_id>/merged_results', methods=['GET'])
@project_access_required
def get_merged_results(project_id, project):
    """
    Get list of merged result tables for this project.
    
    Returns:
        200: List of merged results
    """
    merged_results = ProjectMergedResult.query.filter_by(
        project_id=project_id
    ).order_by(ProjectMergedResult.created_at.desc()).all()
    
    return jsonify({
        'merged_results': [
            {
                'id': mr.id,
                'created_at': mr.created_at.isoformat(),
                'experiment_count': mr.experiment_count,
                'file_size_mb': mr.file_size_bytes / (1024**2) if mr.file_size_bytes else 0
            }
            for mr in merged_results
        ]
    }), 200


@projects_bp.route('/<int:project_id>/merged_results/<int:result_id>/download', methods=['GET'])
@project_access_required
def download_merged_result(project_id, result_id, project):
    """
    Download a merged contingency table.
    
    Returns:
        200: File download
        404: Result not found
    """
    merged_result = ProjectMergedResult.query.filter_by(
        id=result_id,
        project_id=project_id
    ).first()
    
    if not merged_result:
        return jsonify({'error': 'Merged result not found'}), 404
    
    try:
        return send_file(
            merged_result.merged_table_path,
            as_attachment=True,
            download_name=f'merged_contingency_project_{project_id}.csv'
        )
    except Exception as e:
        current_app.logger.error(f'Download error: {str(e)}')
        return jsonify({'error': 'File not found'}), 404
