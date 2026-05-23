"""
Pipeline Service - Bioinformatics Workflow Execution

THIS MODULE IS WHERE YOUR 4 BIOINFORMATICS SCRIPTS ARE INTEGRATED.

Pipeline Flow:
1. run_script1_dea() - Differential Expression Analysis on gene expression file
2. run_script2_vep() - Ensembl VEP processing on VCF folder
3. run_script3_join() - Join DEA and VEP outputs
4. run_script4_contingency() - Generate final contingency table

IMPORTANT FOR IMPLEMENTATION:
- Your scripts should be placed in the scripts/ directory at project root
- Each script should accept command-line arguments
- Each script should write output to the path specified
- Scripts should exit with code 0 on success, non-zero on failure
- Scripts can write progress/logs to stderr
"""

import subprocess
import json
from pathlib import Path
from flask import current_app
from app.models import db, Experiment, Result
from app.utils.files import get_experiment_paths, calculate_file_hash


class PipelineExecutionError(Exception):
    """Custom exception for pipeline execution errors."""
    pass


def execute_pipeline(experiment_id):
    """
    Execute the complete bioinformatics pipeline for an experiment.

    This is the main entry point called by the background thread task.
    It orchestrates the execution of all 4 scripts in sequence.

    Args:
        experiment_id: ID of the experiment to process

    Returns:
        Dictionary with execution results

    Raises:
        PipelineExecutionError: If any step fails
    """
    experiment = db.session.get(Experiment, experiment_id)
    if not experiment:
        raise PipelineExecutionError(f'Experiment {experiment_id} not found')

    # Verify experiment is ready
    if not experiment.is_ready_to_run():
        raise PipelineExecutionError('Experiment missing required input files')

    # Update status
    experiment.update_status(Experiment.STATUS_RUNNING)

    try:
        # Get all file paths
        user_id = experiment.project.user_id
        project_id = experiment.project_id
        paths = get_experiment_paths(user_id, project_id, experiment_id)

        current_app.logger.info(f'Starting pipeline for experiment {experiment_id}')

        # STEP 1: Differential Expression Analysis
        current_app.logger.info('Step 1/4: Running DEA analysis')
        experiment.current_step = 1
        db.session.commit()

        dea_output = run_script1_dea(
            expression_dir=paths['expression_dir'],
            output_dir=paths['intermediate_dir'],
            experiment=experiment
        )

        # STEP 2: VEP Processing
        current_app.logger.info('Step 2/4: Running VEP processing')
        experiment.current_step = 2
        db.session.commit()

        vep_output = run_script2_vep(
            vcf_dir=paths['vcf_dir'],
            output_dir=paths['intermediate_dir'],
            experiment=experiment
        )

        # STEP 3: Join Results
        current_app.logger.info('Step 3/4: Joining DEA and VEP results')
        experiment.current_step = 3
        db.session.commit()

        joined_output = run_script3_join(
            dea_file=dea_output['output_path'],
            vep_file=vep_output['output_path'],
            output_dir=paths['intermediate_dir'],
            experiment=experiment
        )

        # STEP 4: Generate Contingency Table
        current_app.logger.info('Step 4/4: Generating contingency table')
        experiment.current_step = 4
        db.session.commit()

        contingency_output = run_script4_contingency(
            joined_file=joined_output['output_path'],
            output_dir=paths['results_dir'],
            experiment=experiment
        )

        # Save result to database
        result = Result(
            experiment_id=experiment_id,
            contingency_table_path=contingency_output['output_path'],
            file_size_bytes=Path(contingency_output['output_path']).stat().st_size,
            file_hash=calculate_file_hash(contingency_output['output_path'])
        )
        db.session.add(result)

        # Update experiment status
        experiment.update_status(Experiment.STATUS_COMPLETED)

        current_app.logger.info(f'Pipeline completed successfully for experiment {experiment_id}')

        return {
            'success': True,
            'experiment_id': experiment_id,
            'result_path': contingency_output['output_path'],
            'steps_completed': 4
        }

    except Exception as e:
        # Log error and update experiment status
        error_msg = str(e)
        current_app.logger.error(f'Pipeline failed for experiment {experiment_id}: {error_msg}')
        experiment.update_status(Experiment.STATUS_FAILED, error_message=error_msg)
        raise PipelineExecutionError(f'Pipeline execution failed: {error_msg}')


def run_script1_dea(expression_dir, output_dir, experiment):
    """
    Execute Script 1: Differential Expression Analysis (DEA)

    YOUR IMPLEMENTATION INSTRUCTIONS:
    ================================
    1. Your DEA script should be at: scripts/dea_analysis.py
    2. Script should accept these arguments:
       --input-dir: Path to directory containing gene expression file
       --output-file: Path where DEA results should be written
       --experiment-id: ID of the experiment (for logging/tracking)

    3. Expected output:
       - A file containing differentially expressed genes
       - Format: CSV/TSV with columns like gene_id, log_fold_change, p_value, adjusted_p_value

    4. Script should:
       - Exit with code 0 on success
       - Exit with non-zero code on failure
       - Write progress messages to stderr
       - Write final output to the specified output file

    EXAMPLE SCRIPT INVOCATION:
    python scripts/dea_analysis.py \
        --input-dir /path/to/expression \
        --output-file /path/to/output/dea_results.csv \
        --experiment-id 123

    Args:
        expression_dir: Directory containing gene expression file
        output_dir: Directory where DEA output should be written
        experiment: Experiment model instance

    Returns:
        Dictionary with output file path and metadata
    """
    # Prepare paths
    output_file = Path(output_dir) / 'dea_results.csv'

    # Build command for YOUR script
    # MODIFY THIS SECTION to match your script's argument structure
    command = [
        current_app.config['PYTHON_INTERPRETER'],
        str(current_app.config['SCRIPT_DEA']),
        '--input-dir', str(expression_dir),
        '--output-file', str(output_file),
        '--experiment-id', str(experiment.id)
    ]

    current_app.logger.info(f'Executing DEA script: {" ".join(command)}')

    try:
        # Execute the script
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=current_app.config.get('TASK_TIME_LIMIT', 3600),
            check=True
        )

        # Log script output
        if result.stdout:
            current_app.logger.info(f'DEA stdout: {result.stdout}')
        if result.stderr:
            current_app.logger.info(f'DEA stderr: {result.stderr}')

        # Verify output file was created
        if not output_file.exists():
            raise PipelineExecutionError('DEA script did not create output file')

        return {
            'output_path': str(output_file),
            'file_size': output_file.stat().st_size,
            'stdout': result.stdout,
            'stderr': result.stderr
        }

    except subprocess.TimeoutExpired:
        raise PipelineExecutionError('DEA script timeout exceeded')
    except subprocess.CalledProcessError as e:
        raise PipelineExecutionError(f'DEA script failed: {e.stderr}')
    except Exception as e:
        raise PipelineExecutionError(f'DEA script execution error: {str(e)}')


def run_script2_vep(vcf_dir, output_dir, experiment):
    """
    Execute Script 2: Ensembl VEP Processing

    YOUR IMPLEMENTATION INSTRUCTIONS:
    ================================
    1. Your VEP script should be at: scripts/vep_processing.py
    2. Script should accept these arguments:
       --vcf-dir: Path to directory containing VCF files
       --output-file: Path where VEP results should be written
       --experiment-id: ID of the experiment

    3. Expected output:
       - A file containing variant effect predictions
       - Format: CSV/TSV with columns like variant_id, gene_id, consequence, impact

    4. Script should process ALL .vcf or .vcf.gz files in the vcf-dir

    EXAMPLE SCRIPT INVOCATION:
    python scripts/vep_processing.py \
        --vcf-dir /path/to/vcf \
        --output-file /path/to/output/vep_results.csv \
        --experiment-id 123

    Args:
        vcf_dir: Directory containing VCF files
        output_dir: Directory where VEP output should be written
        experiment: Experiment model instance

    Returns:
        Dictionary with output file path and metadata
    """
    output_file = Path(output_dir) / 'vep_results.csv'

    # Build command for YOUR script
    command = [
        current_app.config['PYTHON_INTERPRETER'],
        str(current_app.config['SCRIPT_VEP']),
        '--vcf-dir', str(vcf_dir),
        '--output-file', str(output_file),
        '--experiment-id', str(experiment.id)
    ]

    current_app.logger.info(f'Executing VEP script: {" ".join(command)}')

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=current_app.config.get('TASK_TIME_LIMIT', 3600),
            check=True
        )

        if result.stdout:
            current_app.logger.info(f'VEP stdout: {result.stdout}')
        if result.stderr:
            current_app.logger.info(f'VEP stderr: {result.stderr}')

        if not output_file.exists():
            raise PipelineExecutionError('VEP script did not create output file')

        return {
            'output_path': str(output_file),
            'file_size': output_file.stat().st_size,
            'stdout': result.stdout,
            'stderr': result.stderr
        }

    except subprocess.TimeoutExpired:
        raise PipelineExecutionError('VEP script timeout exceeded')
    except subprocess.CalledProcessError as e:
        raise PipelineExecutionError(f'VEP script failed: {e.stderr}')
    except Exception as e:
        raise PipelineExecutionError(f'VEP script execution error: {str(e)}')


def run_script3_join(dea_file, vep_file, output_dir, experiment):
    """
    Execute Script 3: Join DEA and VEP Results

    YOUR IMPLEMENTATION INSTRUCTIONS:
    ================================
    1. Your join script should be at: scripts/join_results.py
    2. Script should accept these arguments:
       --dea-file: Path to DEA results file
       --vep-file: Path to VEP results file
       --output-file: Path where joined results should be written
       --experiment-id: ID of the experiment

    3. Expected output:
       - A file containing joined data from both DEA and VEP
       - Should include: gene_id, expression_data, variant_data
       - This is an intermediate table used by script 4

    EXAMPLE SCRIPT INVOCATION:
    python scripts/join_results.py \
        --dea-file /path/to/dea_results.csv \
        --vep-file /path/to/vep_results.csv \
        --output-file /path/to/output/joined_results.csv \
        --experiment-id 123

    Args:
        dea_file: Path to DEA results
        vep_file: Path to VEP results
        output_dir: Directory where joined output should be written
        experiment: Experiment model instance

    Returns:
        Dictionary with output file path and metadata
    """
    output_file = Path(output_dir) / 'joined_results.csv'

    command = [
        current_app.config['PYTHON_INTERPRETER'],
        str(current_app.config['SCRIPT_JOIN']),
        '--dea-file', str(dea_file),
        '--vep-file', str(vep_file),
        '--output-file', str(output_file),
        '--experiment-id', str(experiment.id)
    ]

    current_app.logger.info(f'Executing join script: {" ".join(command)}')

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=current_app.config.get('TASK_TIME_LIMIT', 3600),
            check=True
        )

        if result.stdout:
            current_app.logger.info(f'Join stdout: {result.stdout}')
        if result.stderr:
            current_app.logger.info(f'Join stderr: {result.stderr}')

        if not output_file.exists():
            raise PipelineExecutionError('Join script did not create output file')

        return {
            'output_path': str(output_file),
            'file_size': output_file.stat().st_size,
            'stdout': result.stdout,
            'stderr': result.stderr
        }

    except subprocess.TimeoutExpired:
        raise PipelineExecutionError('Join script timeout exceeded')
    except subprocess.CalledProcessError as e:
        raise PipelineExecutionError(f'Join script failed: {e.stderr}')
    except Exception as e:
        raise PipelineExecutionError(f'Join script execution error: {str(e)}')


def run_script4_contingency(joined_file, output_dir, experiment):
    """
    Execute Script 4: Generate Contingency Table

    YOUR IMPLEMENTATION INSTRUCTIONS:
    ================================
    1. Your contingency table script should be at: scripts/generate_contingency.py
    2. Script should accept these arguments:
       --input-file: Path to joined results file
       --output-file: Path where contingency table should be written
       --experiment-id: ID of the experiment

    3. Expected output:
       - The FINAL contingency table for this experiment
       - This is what the user will download
       - Format: Your choice (CSV, TSV, Excel, etc.)

    EXAMPLE SCRIPT INVOCATION:
    python scripts/generate_contingency.py \
        --input-file /path/to/joined_results.csv \
        --output-file /path/to/results/contingency_table.csv \
        --experiment-id 123

    Args:
        joined_file: Path to joined DEA+VEP results
        output_dir: Directory where contingency table should be written
        experiment: Experiment model instance

    Returns:
        Dictionary with output file path and metadata
    """
    output_file = Path(output_dir) / f'contingency_table_{experiment.id}.csv'

    command = [
        current_app.config['PYTHON_INTERPRETER'],
        str(current_app.config['SCRIPT_CONTINGENCY']),
        '--input-file', str(joined_file),
        '--output-file', str(output_file),
        '--experiment-id', str(experiment.id)
    ]

    current_app.logger.info(f'Executing contingency script: {" ".join(command)}')

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=current_app.config.get('TASK_TIME_LIMIT', 3600),
            check=True
        )

        if result.stdout:
            current_app.logger.info(f'Contingency stdout: {result.stdout}')
        if result.stderr:
            current_app.logger.info(f'Contingency stderr: {result.stderr}')

        if not output_file.exists():
            raise PipelineExecutionError('Contingency script did not create output file')

        return {
            'output_path': str(output_file),
            'file_size': output_file.stat().st_size,
            'stdout': result.stdout,
            'stderr': result.stderr
        }

    except subprocess.TimeoutExpired:
        raise PipelineExecutionError('Contingency script timeout exceeded')
    except subprocess.CalledProcessError as e:
        raise PipelineExecutionError(f'Contingency script failed: {e.stderr}')
    except Exception as e:
        raise PipelineExecutionError(f'Contingency script execution error: {str(e)}')


def merge_project_contingency_tables(project_id):
    """
    Merge contingency tables from all completed experiments in a project.

    YOUR IMPLEMENTATION INSTRUCTIONS:
    ================================
    You may want to create a 5th script for merging tables, or handle this
    differently based on your specific requirements.

    This function should:
    1. Find all completed experiments in the project
    2. Read their contingency tables
    3. Merge them according to your business logic
    4. Write a combined project-level contingency table

    Args:
        project_id: ID of the project

    Returns:
        Dictionary with merged table path and metadata
    """
    from app.models import Project, ProjectMergedResult

    project = db.session.get(Project, project_id)
    if not project:
        raise PipelineExecutionError(f'Project {project_id} not found')

    # Get all completed experiments with results
    completed_experiments = (
        Experiment.query
        .filter_by(project_id=project_id, status=Experiment.STATUS_COMPLETED)
        .filter(Experiment.result.has())
        .all()
    )

    if not completed_experiments:
        raise PipelineExecutionError('No completed experiments with results found')

    current_app.logger.info(
        f'Merging {len(completed_experiments)} contingency tables for project {project_id}'
    )

    # TODO: Implement your merging logic here
    # This is highly specific to your data format and requirements

    # Placeholder: You would read all result files and merge them
    output_dir = (
        current_app.config['RESULTS_FOLDER'] /
        str(project.user_id) / str(project_id)
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f'merged_contingency_table_{project_id}.csv'

    # Example: Concatenate all tables (YOU SHOULD REPLACE THIS)
    # In reality, you'd have specific merging logic

    experiment_ids = [exp.id for exp in completed_experiments]

    # Save merged result
    merged_result = ProjectMergedResult(
        project_id=project_id,
        merged_table_path=str(output_file),
        file_size_bytes=output_file.stat().st_size if output_file.exists() else 0,
        experiment_ids_included=json.dumps(experiment_ids),
        experiment_count=len(experiment_ids)
    )
    db.session.add(merged_result)
    db.session.commit()

    return {
        'output_path': str(output_file),
        'experiments_merged': len(experiment_ids),
        'experiment_ids': experiment_ids
    }
