#!/usr/bin/env python3
"""
Script 1: Expression Data Storage
Reads a gene expression CSV file and stores the expression values cleanly
for use by downstream pipeline steps (join_results.py).

Input:  CSV with columns [gene_id, expression_level]
Output: CSV with columns [gene_id, expression_level] — validated and normalised
"""

import argparse
import sys
import csv
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_expression_file(input_dir: Path) -> Path:
    """Return the first CSV/TSV file found in *input_dir*."""
    for ext in ("*.csv", "*.tsv", "*.txt"):
        matches = list(input_dir.glob(ext))
        if matches:
            return matches[0]
    raise FileNotFoundError(
        f"No CSV/TSV expression file found in: {input_dir}"
    )


def detect_delimiter(filepath: Path) -> str:
    """Detect whether the file uses commas or tabs."""
    with open(filepath, newline="") as fh:
        sample = fh.read(4096)
    return "\t" if sample.count("\t") > sample.count(",") else ","


def load_expression(filepath: Path) -> list[dict]:
    """
    Load and validate gene expression data.

    Expected columns (case-insensitive): gene_id, expression_level
    Additional columns are preserved and passed downstream.
    """
    delimiter = detect_delimiter(filepath)
    rows = []

    with open(filepath, newline="") as fh:
        reader = csv.DictReader(fh, delimiter=delimiter)

        # Normalise header names to lowercase
        if reader.fieldnames is None:
            raise ValueError("Expression file appears to be empty.")

        fieldnames_lower = [f.strip().lower() for f in reader.fieldnames]

        if "gene_id" not in fieldnames_lower:
            raise ValueError(
                f"Expression file must contain a 'gene_id' column. "
                f"Found: {reader.fieldnames}"
            )
        if "expression_level" not in fieldnames_lower:
            raise ValueError(
                f"Expression file must contain an 'expression_level' column. "
                f"Found: {reader.fieldnames}"
            )

        gene_id_col      = reader.fieldnames[fieldnames_lower.index("gene_id")]
        expr_col         = reader.fieldnames[fieldnames_lower.index("expression_level")]
        extra_cols       = [
            f for f in reader.fieldnames
            if f not in (gene_id_col, expr_col)
        ]

        skipped = 0
        for lineno, row in enumerate(reader, start=2):
            gene_id = row[gene_id_col].strip()
            expr_raw = row[expr_col].strip()

            # Skip comment lines or empty gene IDs
            if not gene_id or gene_id.startswith("#"):
                skipped += 1
                continue

            # Validate expression value is numeric
            try:
                expression_level = float(expr_raw)
            except ValueError:
                print(
                    f"[DEA] WARNING: Non-numeric expression value at line {lineno} "
                    f"for gene '{gene_id}' (value='{expr_raw}') — skipping.",
                    file=sys.stderr,
                )
                skipped += 1
                continue

            record = {
                "gene_id": gene_id,
                "expression_level": expression_level,
            }
            # Carry forward any extra columns unchanged
            for col in extra_cols:
                record[col] = row[col].strip()

            rows.append(record)

        if skipped:
            print(f"[DEA] Skipped {skipped} invalid/comment rows.", file=sys.stderr)

    return rows


def write_output(rows: list[dict], output_path: Path) -> None:
    """Write validated expression data to *output_path* as CSV."""
    if not rows:
        raise ValueError("No valid expression rows to write — aborting.")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Preserve column order: gene_id, expression_level, then extras
    base_cols  = ["gene_id", "expression_level"]
    extra_cols = [k for k in rows[0].keys() if k not in base_cols]
    fieldnames = base_cols + extra_cols

    with open(output_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Script 1 – Store gene expression values for downstream analysis."
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        help="Directory containing the gene expression CSV/TSV file.",
    )
    parser.add_argument(
        "--output-file",
        required=True,
        help="Destination CSV path for the stored expression data.",
    )
    parser.add_argument(
        "--experiment-id",
        required=True,
        type=int,
        help="Experiment ID used for logging/tracking.",
    )
    args = parser.parse_args()

    print(
        f"[DEA] Starting expression storage for experiment {args.experiment_id}",
        file=sys.stderr,
    )

    try:
        input_dir = Path(args.input_dir)
        if not input_dir.exists():
            raise FileNotFoundError(f"Input directory not found: {input_dir}")

        expression_file = find_expression_file(input_dir)
        print(f"[DEA] Found expression file: {expression_file.name}", file=sys.stderr)

        rows = load_expression(expression_file)
        print(f"[DEA] Loaded {len(rows)} gene records.", file=sys.stderr)

        output_path = Path(args.output_file)
        write_output(rows, output_path)
        print(f"[DEA] Expression data written to: {output_path}", file=sys.stderr)

        sys.exit(0)

    except Exception as exc:
        print(f"[DEA] ERROR: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
