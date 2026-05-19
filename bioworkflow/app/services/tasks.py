"""
Background task functions for pipeline execution.

These run in plain Python threads instead of Celery workers,
so no Celery installation is required on the server.
"""

import logging
from app import db
from app.models import Experiment
from app.services.pipeline import execute_pipeline, merge_project_contingency_tables

logger = logging.getLogger(__name__)


def run_pipeline_task(experiment_id):
    """Run the bioinformatics pipeline for an experiment."""
    logger.info(f'Starting pipeline task for experiment {experiment_id}')
    try:
        result = execute_pipeline(experiment_id)
        logger.info(f'Pipeline task completed for experiment {experiment_id}')
        return result
    except Exception as e:
        logger.error(f'Pipeline task failed for experiment {experiment_id}: {str(e)}')
        experiment = Experiment.query.get(experiment_id)
        if experiment:
            experiment.update_status(Experiment.STATUS_FAILED, error_message=str(e))
            db.session.commit()
        raise


def merge_project_results_task(project_id):
    """Merge all experiment results for a project."""
    logger.info(f'Starting project merge task for project {project_id}')
    try:
        result = merge_project_contingency_tables(project_id)
        logger.info(f'Project merge completed for project {project_id}')
        return result
    except Exception as e:
        logger.error(f'Project merge failed for project {project_id}: {str(e)}')
        raise


def cleanup_old_intermediates_task():
    """Delete intermediate files from experiments older than 7 days."""
    from datetime import datetime, timedelta
    from app.utils.files import cleanup_experiment_files
    cutoff_date = datetime.utcnow() - timedelta(days=7)
    old_experiments = Experiment.query.filter(
        Experiment.status.in_([Experiment.STATUS_COMPLETED, Experiment.STATUS_FAILED]),
        Experiment.completed_at < cutoff_date
    ).all()
    total_cleaned = 0
    total_bytes_freed = 0
    for experiment in old_experiments:
        try:
            result = cleanup_experiment_files(
                experiment.project.user_id, experiment.project_id,
                experiment.id, keep_results=True
            )
            total_cleaned += result['deleted_files']
            total_bytes_freed += result['deleted_bytes']
        except Exception as e:
            logger.error(f'Cleanup failed for experiment {experiment.id}: {str(e)}')
    return {
        'experiments_cleaned': len(old_experiments),
        'files_deleted': total_cleaned,
        'bytes_freed': total_bytes_freed
    }
