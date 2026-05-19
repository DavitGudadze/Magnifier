"""
celery_worker.py — kept for reference only.

Celery has been replaced by Python threading for background pipeline execution.
Tasks are now plain functions in app/services/tasks.py, called via threading.Thread
from the experiment and project routes.

This file is no longer used. You can safely delete it.
"""
