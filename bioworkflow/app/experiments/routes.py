"""
Experiments routes.

Handles experiment creation, file uploads, pipeline execution, and result downloads.
"""

from flask import Blueprint, request, jsonify, current_app, send_file
from app.models import db, Experiment
from app.utils.auth import project_access_required, experiment_access_required
from app.utils.files import (
    save_expression_file, save_vcf_files,
    get_experiment_paths, cleanup_experiment_files
)
from app.services.tasks import run_pipeline_task

experiments_bp = Blueprint('experiments', __name__)


def _get_vcf_files_list(experiment):
    """Return list of VCF files stored on disk for this experiment."""
    import os
    try:
        paths = get_experiment_paths(experiment.project.user_id, experiment.project_id, experiment.id)
        vcf_dir = paths['vcf_dir']
        if not os.path.isdir(vcf_dir):
            return []
        files = []
        for i, fname in enumerate(sorted(os.listdir(vcf_dir))):
            if fname.startswith('.'):
                continue
            files.append({'id': i, 'filename': fname})
        return files
    except Exception:
        return []


@experiments_bp.route('/<int:project_id>', methods=['GET'])
@project_access_required
def list_experiments(project_id, project):
    """
    List all experiments in a project.

    Query parameters:
        status: Filter by status (optional)

    Returns:
        200: List of experiments
    """
    query = Experiment.query.filter_by(project_id=project_id)

    # Optional status filter
    status_filter = request.args.get('status')
    if status_filter:
        query = query.filter_by(status=status_filter)

    experiments = query.order_by(Experiment.created_at.desc()).all()

    return jsonify({
        'experiments': [
            {
                'id': exp.id,
                'name': exp.name,
                'description': exp.description,
                'status': exp.status,
                'created_at': exp.created_at.isoformat(),
                'updated_at': exp.updated_at.isoformat(),
                'has_expression_file': exp.has_expression_file,
                'has_vcf_files': exp.has_vcf_files,
                'vcf_file_count': exp.vcf_file_count,
                'started_at': exp.started_at.isoformat() if exp.started_at else None,
                'completed_at': exp.completed_at.isoformat() if exp.completed_at else None,
                'current_step': exp.current_step,
                'has_result': exp.result is not None
            }
            for exp in experiments
        ]
    }), 200


@experiments_bp.route('/<int:project_id>', methods=['POST'])
@project_access_required
def create_experiment(project_id, project):
    """
    Create a new experiment in a project.

    Expected JSON:
        {
            "name": "string",
            "description": "string" (optional)
        }

    Returns:
        201: Experiment created
        400: Validation error
    """
    data = request.get_json()

    if not data or 'name' not in data:
        return jsonify({'error': 'Experiment name is required'}), 400

    name = data['name'].strip()
    if not name:
        return jsonify({'error': 'Experiment name cannot be empty'}), 400

    if len(name) > 200:
        return jsonify({'error': 'Experiment name too long (max 200 characters)'}), 400

    try:
        experiment = Experiment(
            name=name,
            description=data.get('description', ''),
            project_id=project_id,
            status=Experiment.STATUS_CREATED
        )

        db.session.add(experiment)
        db.session.commit()

        current_app.logger.info(
            f'Experiment created: {experiment.id} in project {project_id}'
        )

        return jsonify({
            'message': 'Experiment created successfully',
            'experiment': {
                'id': experiment.id,
                'name': experiment.name,
                'description': experiment.description,
                'status': experiment.status,
                'created_at': experiment.created_at.isoformat()
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Experiment creation error: {str(e)}')
        return jsonify({'error': 'Failed to create experiment'}), 500


@experiments_bp.route('/<int:id>', methods=['GET'])
@experiment_access_required
def get_experiment(id, experiment):
    """
    Get detailed information about an experiment.

    Returns:
        200: Experiment details
    """
    return jsonify({
        'experiment': {
            'id': experiment.id,
            'name': experiment.name,
            'description': experiment.description,
            'project_id': experiment.project_id,
            'project_name': experiment.project.name,
            'status': experiment.status,
            'created_at': experiment.created_at.isoformat(),
            'updated_at': experiment.updated_at.isoformat(),
            'has_expression_file': experiment.has_expression_file,
            'expression_filename': experiment.expression_filename,
            'has_vcf_files': experiment.has_vcf_files,
            'vcf_file_count': experiment.vcf_file_count,
            'started_at': experiment.started_at.isoformat() if experiment.started_at else None,
            'completed_at': experiment.completed_at.isoformat() if experiment.completed_at else None,
            'duration_seconds': experiment.duration_seconds,
            'current_step': experiment.current_step,
            'celery_task_id': experiment.celery_task_id,
            'error_message': experiment.error_message,
            'has_result': experiment.result is not None,
            'can_run': experiment.can_be_executed()
        }
    }), 200


@experiments_bp.route('/<int:id>/upload_expression', methods=['POST'])
@experiment_access_required
def upload_expression_file(id, experiment):
    """
    Upload gene expression file for an experiment.

    Form data:
        expression_file: File upload

    Returns:
        200: File uploaded successfully
        400: Validation error
    """
    if experiment.status in [Experiment.STATUS_RUNNING, Experiment.STATUS_QUEUED]:
        return jsonify({
            'error': 'Cannot upload files while pipeline is running'
        }), 400

    if 'expression_file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['expression_file']

    if file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400

    try:
        # Update status
        if experiment.status == Experiment.STATUS_CREATED:
            experiment.update_status(Experiment.STATUS_UPLOADING)

        # Save file
        file_info = save_expression_file(
            file,
            experiment.project.user_id,
            experiment.project_id,
            experiment.id
        )

        # Update experiment
        experiment.has_expression_file = True
        experiment.expression_filename = file_info['filename']

        # Check if ready to run
        if experiment.is_ready_to_run():
            experiment.status = Experiment.STATUS_READY

        db.session.commit()

        current_app.logger.info(
            f'Expression file uploaded for experiment {experiment.id}: {file_info["filename"]}'
        )

        return jsonify({
            'message': 'Expression file uploaded successfully',
            'file': {
                'filename': file_info['filename'],
                'size_bytes': file_info['file_size']
            },
            'experiment': {
                'id': experiment.id,
                'status': experiment.status,
                'can_run': experiment.can_be_executed()
            }
        }), 200

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Expression file upload error: {str(e)}')
        return jsonify({'error': 'File upload failed'}), 500


@experiments_bp.route('/<int:id>/upload_vcf', methods=['POST'])
@experiment_access_required
def upload_vcf_files(id, experiment):
    """
    Upload VCF files for an experiment.

    Form data:
        vcf_files[]: Multiple file uploads

    Returns:
        200: Files uploaded successfully
        400: Validation error
    """
    if experiment.status in [Experiment.STATUS_RUNNING, Experiment.STATUS_QUEUED]:
        return jsonify({
            'error': 'Cannot upload files while pipeline is running'
        }), 400

    if 'vcf_files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400

    files = request.files.getlist('vcf_files')

    if not files or all(f.filename == '' for f in files):
        return jsonify({'error': 'No valid files provided'}), 400

    try:
        # Update status
        if experiment.status == Experiment.STATUS_CREATED:
            experiment.update_status(Experiment.STATUS_UPLOADING)

        # Save files
        saved_files = save_vcf_files(
            files,
            experiment.project.user_id,
            experiment.project_id,
            experiment.id
        )

        # Update experiment
        experiment.has_vcf_files = True
        experiment.vcf_file_count = len(saved_files)

        # Check if ready to run
        if experiment.is_ready_to_run():
            experiment.status = Experiment.STATUS_READY

        db.session.commit()

        current_app.logger.info(
            f'VCF files uploaded for experiment {experiment.id}: {len(saved_files)} files'
        )

        return jsonify({
            'message': f'{len(saved_files)} VCF files uploaded successfully',
            'files': [
                {
                    'filename': f['filename'],
                    'size_bytes': f['file_size']
                }
                for f in saved_files
            ],
            'experiment': {
                'id': experiment.id,
                'status': experiment.status,
                'vcf_file_count': experiment.vcf_file_count,
                'can_run': experiment.can_be_executed()
            }
        }), 200

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'VCF files upload error: {str(e)}')
        return jsonify({'error': 'File upload failed'}), 500


@experiments_bp.route('/<int:id>/run', methods=['POST'])
@experiment_access_required
def run_experiment(id, experiment):
    """
    Execute the bioinformatics pipeline for an experiment.

    Starts a background thread to run all 4 scripts sequentially.

    Returns:
        202: Pipeline execution started
        400: Experiment not ready or already running
    """
    if not experiment.can_be_executed():
        return jsonify({
            'error': 'Experiment cannot be executed',
            'reason': 'Check that all files are uploaded and experiment is not already running',
            'status': experiment.status,
            'has_expression_file': experiment.has_expression_file,
            'has_vcf_files': experiment.has_vcf_files
        }), 400

    try:
        import threading
        import uuid

        task_id = str(uuid.uuid4())

        # Update experiment before starting thread
        experiment.update_status(Experiment.STATUS_QUEUED)
        experiment.celery_task_id = task_id
        db.session.commit()

        # Run pipeline in a background thread (no Celery needed)
        app = current_app._get_current_object()
        exp_id = experiment.id

        def run_in_context():
            with app.app_context():
                run_pipeline_task(exp_id)

        thread = threading.Thread(target=run_in_context, daemon=True)
        thread.start()

        current_app.logger.info(
            f'Pipeline started for experiment {experiment.id}: thread {task_id}'
        )

        return jsonify({
            'message': 'Pipeline execution started',
            'task_id': task_id,
            'experiment': {
                'id': experiment.id,
                'status': experiment.status
            }
        }), 202

    except Exception as e:
        current_app.logger.error(f'Failed to start pipeline: {str(e)}')
        return jsonify({'error': 'Failed to start pipeline execution'}), 500


@experiments_bp.route('/<int:id>/status', methods=['GET'])
@experiment_access_required
def get_experiment_status(id, experiment):
    """
    Get current execution status of an experiment.

    Returns:
        200: Status information
    """
    response = {
        'experiment_id': experiment.id,
        'id': experiment.id,
        'name': experiment.name,
        'description': experiment.description,
        'status': experiment.status,
        'current_step': experiment.current_step,
        'total_steps': 4,
        'project_id': experiment.project_id,
        'project_name': experiment.project.name,
        'has_expression_file': experiment.has_expression_file,
        'expression_filename': experiment.expression_filename,
        'has_vcf_files': experiment.has_vcf_files,
        'vcf_file_count': experiment.vcf_file_count,
        'has_result': experiment.result is not None,
        'can_run': experiment.can_be_executed(),
        'error_message': experiment.error_message,
        'vcf_files': _get_vcf_files_list(experiment),
        'created_at': experiment.created_at.isoformat(),
        'updated_at': experiment.updated_at.isoformat(),
    }

    if experiment.started_at:
        response['started_at'] = experiment.started_at.isoformat()

    if experiment.completed_at:
        response['completed_at'] = experiment.completed_at.isoformat()
        response['duration_seconds'] = experiment.duration_seconds

    if experiment.celery_task_id:
        response['task_id'] = experiment.celery_task_id

    return jsonify(response), 200


@experiments_bp.route('/<int:id>/download', methods=['GET'])
@experiment_access_required
def download_result(id, experiment):
    """
    Download the final contingency table for a completed experiment.

    Returns:
        200: File download
        404: No result available
    """
    if not experiment.result:
        return jsonify({
            'error': 'No result available',
            'status': experiment.status
        }), 404

    try:
        return send_file(
            experiment.result.contingency_table_path,
            as_attachment=True,
            download_name=f'contingency_table_exp_{experiment.id}.csv'
        )
    except Exception as e:
        current_app.logger.error(f'Download error: {str(e)}')
        return jsonify({'error': 'File not found'}), 404


@experiments_bp.route('/<int:id>', methods=['DELETE'])
@experiment_access_required
def delete_experiment(id, experiment):
    """
    Delete an experiment and its associated files.

    Returns:
        200: Experiment deleted
    """
    try:
        experiment_name = experiment.name
        user_id = experiment.project.user_id
        project_id = experiment.project_id

        # Delete from database
        db.session.delete(experiment)
        db.session.commit()

        # Clean up files (optional - can be done async)
        try:
            cleanup_experiment_files(user_id, project_id, id, keep_results=False)
        except Exception as e:
            current_app.logger.warning(f'File cleanup error: {str(e)}')

        current_app.logger.info(f'Experiment deleted: {id} ({experiment_name})')

        return jsonify({
            'message': 'Experiment deleted successfully',
            'experiment_id': id
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Experiment deletion error: {str(e)}')
        return jsonify({'error': 'Failed to delete experiment'}), 500


@experiments_bp.route('/<int:id>/delete_expression', methods=['POST'])
@experiment_access_required
def delete_expression_file(id, experiment):
    """Delete the expression file from an experiment."""
    import os
    if experiment.status in [Experiment.STATUS_RUNNING, Experiment.STATUS_QUEUED]:
        return jsonify({'error': 'Cannot delete files while pipeline is running'}), 400
    try:
        # Find and delete the actual file from disk
        paths = get_experiment_paths(experiment.project.user_id, experiment.project_id, experiment.id)
        expr_dir = paths['expression_dir']
        if os.path.isdir(expr_dir):
            for f in os.listdir(expr_dir):
                fp = os.path.join(expr_dir, f)
                if os.path.isfile(fp):
                    os.remove(fp)
        experiment.expression_filename = None
        experiment.has_expression_file = False
        experiment.status = Experiment.STATUS_CREATED
        db.session.commit()
        return jsonify({'message': 'Expression file deleted'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@experiments_bp.route('/<int:id>/delete_vcf/<int:vcf_id>', methods=['POST'])
@experiment_access_required
def delete_vcf_file(id, experiment, vcf_id):
    """Delete a specific VCF file from an experiment (identified by index)."""
    import os
    if experiment.status in [Experiment.STATUS_RUNNING, Experiment.STATUS_QUEUED]:
        return jsonify({'error': 'Cannot delete files while pipeline is running'}), 400
    try:
        vcf_files = _get_vcf_files_list(experiment)
        if vcf_id < 0 or vcf_id >= len(vcf_files):
            return jsonify({'error': 'VCF file not found'}), 404
        filename = vcf_files[vcf_id]['filename']
        paths = get_experiment_paths(experiment.project.user_id, experiment.project_id, experiment.id)
        filepath = os.path.join(paths['vcf_dir'], filename)
        if os.path.exists(filepath):
            os.remove(filepath)
        # Recalculate count from disk
        remaining = len(_get_vcf_files_list(experiment))
        experiment.has_vcf_files = remaining > 0
        experiment.vcf_file_count = remaining
        if remaining == 0:
            experiment.status = Experiment.STATUS_CREATED
        db.session.commit()
        return jsonify({'message': 'VCF file deleted'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
