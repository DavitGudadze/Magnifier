# Bioinformatics Scripts Integration Guide

This directory is where YOU will place your 4 bioinformatics analysis scripts.

## Overview

The pipeline executes 4 scripts in sequence:

1. **`dea_analysis.py`** - Differential Expression Analysis
2. **`vep_processing.py`** - Ensembl VEP processing
3. **`join_results.py`** - Join DEA and VEP outputs
4. **`generate_contingency.py`** - Generate final contingency table

## Script Requirements

### General Requirements (ALL scripts must follow these)

1. **Exit Codes**:
   - Exit with code `0` on success
   - Exit with non-zero code on failure
   - The pipeline will fail if any script returns non-zero

2. **Output Handling**:
   - Write results to the exact path specified in `--output-file` argument
   - DO NOT write to stdout (reserved for status messages)
   - Progress messages and logs should go to stderr

3. **Command-Line Arguments**:
   - Use `argparse` or similar to parse arguments
   - All arguments are provided as `--arg-name value` format

4. **Error Handling**:
   - Validate input files exist and are readable
   - Provide clear error messages on stderr
   - Clean up temporary files on error

5. **Python Environment**:
   - Scripts will be executed with the Python interpreter specified in `.env`
   - By default: `python3`
   - Can be set to conda environment: `PYTHON_INTERPRETER=/path/to/conda/envs/myenv/bin/python`

## Script 1: Differential Expression Analysis

**File**: `dea_analysis.py`

**Purpose**: Analyze gene expression data to identify differentially expressed genes.

**Arguments**:
```bash
python dea_analysis.py \
    --input-dir /path/to/expression/directory \
    --output-file /path/to/output/dea_results.csv \
    --experiment-id 123
```

**Input**:
- `--input-dir`: Directory containing the gene expression file uploaded by user
- The directory will contain exactly ONE file (the uploaded expression file)
- File format: CSV, TSV, or similar (as configured in `.env`)

**Output**:
- `--output-file`: Path where DEA results should be written
- Format: CSV or TSV with at minimum these columns:
  - `gene_id`: Gene identifier
  - `log_fold_change`: Log fold change value
  - `p_value`: P-value
  - `adjusted_p_value`: Adjusted p-value (FDR, etc.)
  
**Example Implementation Structure**:
```python
#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description='DEA Analysis')
    parser.add_argument('--input-dir', required=True, type=str)
    parser.add_argument('--output-file', required=True, type=str)
    parser.add_argument('--experiment-id', required=True, type=int)
    args = parser.parse_args()
    
    try:
        # 1. Find and load expression file
        input_dir = Path(args.input_dir)
        expression_files = list(input_dir.glob('*'))
        
        if not expression_files:
            raise ValueError("No expression file found")
        
        expression_file = expression_files[0]
        print(f"Processing: {expression_file}", file=sys.stderr)
        
        # 2. YOUR DEA ANALYSIS CODE HERE
        # - Load expression data
        # - Run statistical analysis
        # - Identify differentially expressed genes
        
        # 3. Write results
        output_path = Path(args.output_file)
        # Write your results as CSV/TSV
        # df.to_csv(output_path, index=False)
        
        print(f"DEA analysis complete: {output_path}", file=sys.stderr)
        sys.exit(0)
        
    except Exception as e:
        print(f"ERROR: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
```

## Script 2: VEP Processing

**File**: `vep_processing.py`

**Purpose**: Process VCF files through Ensembl VEP to annotate variants.

**Arguments**:
```bash
python vep_processing.py \
    --vcf-dir /path/to/vcf/directory \
    --output-file /path/to/output/vep_results.csv \
    --experiment-id 123
```

**Input**:
- `--vcf-dir`: Directory containing VCF files uploaded by user
- Multiple files may be present (.vcf or .vcf.gz)
- Process ALL files in the directory

**Output**:
- `--output-file`: Path where VEP results should be written
- Format: CSV or TSV with at minimum these columns:
  - `variant_id`: Variant identifier
  - `gene_id`: Affected gene
  - `consequence`: Variant consequence (missense, synonymous, etc.)
  - `impact`: Impact level (HIGH, MODERATE, LOW, MODIFIER)

**Example Implementation Structure**:
```python
#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description='VEP Processing')
    parser.add_argument('--vcf-dir', required=True, type=str)
    parser.add_argument('--output-file', required=True, type=str)
    parser.add_argument('--experiment-id', required=True, type=int)
    args = parser.parse_args()
    
    try:
        vcf_dir = Path(args.vcf_dir)
        vcf_files = list(vcf_dir.glob('*.vcf')) + list(vcf_dir.glob('*.vcf.gz'))
        
        if not vcf_files:
            raise ValueError("No VCF files found")
        
        print(f"Processing {len(vcf_files)} VCF files", file=sys.stderr)
        
        # YOUR VEP PROCESSING CODE HERE
        # - Iterate through VCF files
        # - Run VEP annotation
        # - Combine results
        
        output_path = Path(args.output_file)
        # Write combined results
        
        print(f"VEP processing complete: {output_path}", file=sys.stderr)
        sys.exit(0)
        
    except Exception as e:
        print(f"ERROR: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
```

## Script 3: Join Results

**File**: `join_results.py`

**Purpose**: Join DEA and VEP results into a single intermediate table.

**Arguments**:
```bash
python join_results.py \
    --dea-file /path/to/dea_results.csv \
    --vep-file /path/to/vep_results.csv \
    --output-file /path/to/output/joined_results.csv \
    --experiment-id 123
```

**Input**:
- `--dea-file`: Output from Script 1 (DEA results)
- `--vep-file`: Output from Script 2 (VEP results)

**Output**:
- `--output-file`: Joined table with combined information
- Should include data from both DEA and VEP
- Join key is typically `gene_id`

**Example Implementation Structure**:
```python
#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description='Join DEA and VEP Results')
    parser.add_argument('--dea-file', required=True, type=str)
    parser.add_argument('--vep-file', required=True, type=str)
    parser.add_argument('--output-file', required=True, type=str)
    parser.add_argument('--experiment-id', required=True, type=int)
    args = parser.parse_args()
    
    try:
        # Load both input files
        # YOUR JOINING LOGIC HERE
        # - Typically join on gene_id
        # - Handle many-to-many relationships
        # - Include all relevant columns
        
        output_path = Path(args.output_file)
        # Write joined results
        
        print(f"Join complete: {output_path}", file=sys.stderr)
        sys.exit(0)
        
    except Exception as e:
        print(f"ERROR: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
```

## Script 4: Generate Contingency Table

**File**: `generate_contingency.py`

**Purpose**: Create the final contingency table from joined data.

**Arguments**:
```bash
python generate_contingency.py \
    --input-file /path/to/joined_results.csv \
    --output-file /path/to/results/contingency_table.csv \
    --experiment-id 123
```

**Input**:
- `--input-file`: Output from Script 3 (joined results)

**Output**:
- `--output-file`: FINAL contingency table
- This is what users will download
- Format is up to you (CSV, TSV, Excel, etc.)
- Should be a summary/aggregate view

**Example Implementation Structure**:
```python
#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description='Generate Contingency Table')
    parser.add_argument('--input-file', required=True, type=str)
    parser.add_argument('--output-file', required=True, type=str)
    parser.add_argument('--experiment-id', required=True, type=int)
    args = parser.parse_args()
    
    try:
        # Load joined data
        # YOUR CONTINGENCY TABLE LOGIC HERE
        # - Aggregate/summarize data
        # - Create contingency table format
        # - Calculate statistics
        
        output_path = Path(args.output_file)
        # Write contingency table
        
        print(f"Contingency table generated: {output_path}", file=sys.stderr)
        sys.exit(0)
        
    except Exception as e:
        print(f"ERROR: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
```

## Testing Your Scripts

Before integrating with the platform, test each script independently:

```bash
# Test Script 1
python scripts/dea_analysis.py \
    --input-dir test_data/expression \
    --output-file test_output/dea.csv \
    --experiment-id 1

# Test Script 2
python scripts/vep_processing.py \
    --vcf-dir test_data/vcf \
    --output-file test_output/vep.csv \
    --experiment-id 1

# Test Script 3
python scripts/join_results.py \
    --dea-file test_output/dea.csv \
    --vep-file test_output/vep.csv \
    --output-file test_output/joined.csv \
    --experiment-id 1

# Test Script 4
python scripts/generate_contingency.py \
    --input-file test_output/joined.csv \
    --output-file test_output/contingency.csv \
    --experiment-id 1
```

## Integration with Platform

Once your scripts are ready:

1. Place them in this `scripts/` directory
2. Make sure they're executable: `chmod +x scripts/*.py`
3. Update `.env` if using a specific Python environment
4. Test through the API:
   - Create experiment
   - Upload files
   - Run pipeline
   - Check logs if it fails

## Pipeline Execution Flow

```
User uploads files
    ↓
User triggers pipeline execution
    ↓
Celery task queued
    ↓
Script 1 (DEA) → intermediate/dea_results.csv
    ↓
Script 2 (VEP) → intermediate/vep_results.csv
    ↓
Script 3 (Join) → intermediate/joined_results.csv
    ↓
Script 4 (Contingency) → results/contingency_table.csv
    ↓
Result saved to database
    ↓
User downloads contingency table
```

## Logging and Debugging

- Script output to stderr is captured in application logs
- Check logs at: `logs/bioworkflow.log`
- Celery worker logs show script execution details
- Use `--experiment-id` argument to correlate logs with specific experiments

## Common Issues

1. **Script not found**: Check paths in `.env` (SCRIPT_DEA, etc.)
2. **Permission denied**: Make scripts executable
3. **Module not found**: Ensure Python environment has all dependencies
4. **Timeout**: Increase CELERY_TASK_TIME_LIMIT in `.env`
5. **File not created**: Verify script writes to exact path specified

## Advanced: Using Conda Environments

If your scripts need a specific conda environment:

```bash
# In .env
PYTHON_INTERPRETER=/home/user/miniconda3/envs/bioinfo/bin/python
```

## Questions?

Refer to:
- `app/services/pipeline.py` - Pipeline orchestration code
- `app/services/tasks.py` - Celery task definitions
- Main `README.md` - Overall architecture
