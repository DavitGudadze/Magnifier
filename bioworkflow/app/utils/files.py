"""
File handling utilities.

Provides secure file upload, validation, and storage management.
"""

import os
import hashlib
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import current_app


def allowed_file(filename, allowed_extensions):
    """
    Check if file has an allowed extension.

    Args:
        filename: Name of the file
        allowed_extensions: Set of allowed extensions

    Returns:
        Boolean indicating if file is allowed
    """
    return any(filename.lower().endswith(ext) for ext in allowed_extensions)


def get_user_upload_dir(user_id, project_id, experiment_id):
    """
    Get upload directory path for a specific experiment.

    Creates directory structure: storage/uploads/{user_id}/{project_id}/{experiment_id}/

    Args:
        user_id: User ID
        project_id: Project ID
        experiment_id: Experiment ID

    Returns:
        Path object for the upload directory
    """
    upload_dir = (current_app.config['UPLOAD_FOLDER'] /
                  str(user_id) / str(project_id) / str(experiment_id))
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def get_experiment_paths(user_id, project_id, experiment_id):
    """
    Get all relevant paths for an experiment.

    Returns:
        Dictionary with paths for expression, vcf, intermediate, and results
    """
    base_upload = get_user_upload_dir(user_id, project_id, experiment_id)

    expression_dir = base_upload / 'expression'
    vcf_dir = base_upload / 'vcf'

    intermediate_dir = (
        current_app.config['INTERMEDIATE_FOLDER'] /
        str(user_id) / str(project_id) / str(experiment_id)
    )

    results_dir = (
        current_app.config['RESULTS_FOLDER'] /
        str(user_id) / str(project_id) / str(experiment_id)
    )

    # Create directories
    for directory in [expression_dir, vcf_dir, intermediate_dir, results_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    return {
        'expression_dir': expression_dir,
        'vcf_dir': vcf_dir,
        'intermediate_dir': intermediate_dir,
        'results_dir': results_dir
    }


def save_expression_file(file, user_id, project_id, experiment_id):
    """
    Save gene expression file securely.

    Args:
        file: FileStorage object from request
        user_id: User ID
        project_id: Project ID
        experiment_id: Experiment ID

    Returns:
        Dictionary with file path and metadata

    Raises:
        ValueError: If file type is not allowed
    """
    if not allowed_file(file.filename, current_app.config['ALLOWED_EXPRESSION_EXTENSIONS']):
        raise ValueError(f'File type not allowed. Allowed types: {current_app.config["ALLOWED_EXPRESSION_EXTENSIONS"]}')

    paths = get_experiment_paths(user_id, project_id, experiment_id)
    expression_dir = paths['expression_dir']

    # Secure filename and save
    filename = secure_filename(file.filename)
    filepath = expression_dir / filename

    file.save(str(filepath))

    # Calculate file hash for integrity
    file_hash = calculate_file_hash(filepath)

    return {
        'filename': filename,
        'filepath': str(filepath),
        'file_size': filepath.stat().st_size,
        'file_hash': file_hash
    }


def save_vcf_files(files, user_id, project_id, experiment_id):
    """
    Save multiple VCF files securely.

    Args:
        files: List of FileStorage objects
        user_id: User ID
        project_id: Project ID
        experiment_id: Experiment ID

    Returns:
        List of dictionaries with file metadata

    Raises:
        ValueError: If any file type is not allowed
    """
    paths = get_experiment_paths(user_id, project_id, experiment_id)
    vcf_dir = paths['vcf_dir']

    saved_files = []

    for file in files:
        if not allowed_file(file.filename, current_app.config['ALLOWED_VCF_EXTENSIONS']):
            allowed = current_app.config['ALLOWED_VCF_EXTENSIONS']
            raise ValueError(f'File type not allowed: {file.filename}. Allowed types: {allowed}')

        # Secure filename and save
        filename = secure_filename(file.filename)
        filepath = vcf_dir / filename

        file.save(str(filepath))

        saved_files.append({
            'filename': filename,
            'filepath': str(filepath),
            'file_size': filepath.stat().st_size,
            'file_hash': calculate_file_hash(filepath)
        })

    return saved_files


def calculate_file_hash(filepath, algorithm='sha256'):
    """
    Calculate cryptographic hash of a file.

    Args:
        filepath: Path to file
        algorithm: Hash algorithm (default: sha256)

    Returns:
        Hexadecimal hash string
    """
    hash_func = hashlib.new(algorithm)

    with open(filepath, 'rb') as f:
        chunk = f.read(8192)
        while chunk:
            hash_func.update(chunk)
            chunk = f.read(8192)

    return hash_func.hexdigest()


def get_directory_size(directory):
    """
    Calculate total size of all files in a directory.

    Args:
        directory: Path to directory

    Returns:
        Total size in bytes
    """
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(directory):
        for filename in filenames:
            filepath = Path(dirpath) / filename
            total_size += filepath.stat().st_size
    return total_size


def cleanup_experiment_files(user_id, project_id, experiment_id, keep_results=True):
    """
    Clean up intermediate files for an experiment.

    Args:
        user_id: User ID
        project_id: Project ID
        experiment_id: Experiment ID
        keep_results: If True, keep final results (default: True)

    Returns:
        Dictionary with cleanup statistics
    """
    paths = get_experiment_paths(user_id, project_id, experiment_id)

    deleted_size = 0
    deleted_files = 0

    # Clean intermediate directory
    intermediate_dir = paths['intermediate_dir']
    if intermediate_dir.exists():
        for file in intermediate_dir.iterdir():
            if file.is_file():
                deleted_size += file.stat().st_size
                file.unlink()
                deleted_files += 1

    # Optionally clean uploads
    # (Usually keep these for re-running)

    return {
        'deleted_files': deleted_files,
        'deleted_bytes': deleted_size
    }


def get_project_storage_usage(user_id, project_id):
    """
    Calculate total storage usage for a project.

    Args:
        user_id: User ID
        project_id: Project ID

    Returns:
        Dictionary with storage statistics
    """
    project_upload_dir = current_app.config['UPLOAD_FOLDER'] / str(user_id) / str(project_id)
    project_intermediate_dir = current_app.config['INTERMEDIATE_FOLDER'] / str(user_id) / str(project_id)
    project_results_dir = current_app.config['RESULTS_FOLDER'] / str(user_id) / str(project_id)

    return {
        'uploads_bytes': get_directory_size(project_upload_dir) if project_upload_dir.exists() else 0,
        'intermediate_bytes': get_directory_size(project_intermediate_dir) if project_intermediate_dir.exists() else 0,
        'results_bytes': get_directory_size(project_results_dir) if project_results_dir.exists() else 0
    }
