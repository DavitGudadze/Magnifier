#!/usr/bin/env python3
"""
Script 4: Generate Contingency Table
Reads the joined DEA + VEP CSV and produces a 2 × 2 contingency table
for each variant (chrom/pos/ref/alt) crossing:

    Rows    – variant present (ALT genotype) vs absent (REF homozygous)
    Columns – gene expressed (expression_level ≥ threshold) vs not expressed

Output columns per variant:
    chrom, pos, ref, alt, gene_id,
    n_variant_expressed, n_variant_not_expressed,
    n_no_variant_expressed, n_no_variant_not_expressed,
    total_samples

The thresholds used can be tuned via CLI flags.
"""

import argparse
import csv
import sys
from pathlib import Path
from collections import defaultdict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_csv(filepath: Path) -> tuple[list[str], list[dict]]:
    with open(filepath, newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError(f"Empty or header-less CSV: {filepath}")
        rows = [row for row in reader if not list(row.values())[0].startswith("#")]
        return list(reader.fieldnames), rows


def has_alt_allele(gt: str) -> bool | None:
    """
    Return True  if the genotype carries at least one ALT allele,
           False if homozygous REF,
           None  if missing / unknown.
    """
    gt = gt.replace("|", "/")
    alleles = gt.split("/")
    if any(a in (".", "") for a in alleles):
        return None
    try:
        int_alleles = [int(a) for a in alleles]
        return any(a > 0 for a in int_alleles)
    except ValueError:
        return None


def detect_sample_columns(fieldnames: list[str]) -> list[str]:
    """Return all columns that look like per-sample GT columns."""
    return [f for f in fieldnames if f.endswith("_gt")]


# ---------------------------------------------------------------------------
# Contingency logic
# ---------------------------------------------------------------------------

def build_contingency(
    rows: list[dict],
    fieldnames: list[str],
    expr_threshold: float,
) -> list[dict]:
    """
    For each unique variant (chrom, pos, ref, alt, gene_id) build a 2×2
    contingency table across all samples.

    Returns a list of result dicts.
    """
    sample_gt_cols = detect_sample_columns(fieldnames)

    # Group rows by variant key
    variant_groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        key = (
            row.get("chrom", ""),
            row.get("pos", ""),
            row.get("ref", ""),
            row.get("alt", ""),
            row.get("gene_id", ""),
        )
        variant_groups[key].append(row)

    results: list[dict] = []

    for (chrom, pos, ref, alt, gene_id), group_rows in variant_groups.items():
        # Take expression level from first row (same gene → same value)
        try:
            expr_level = float(group_rows[0].get("expression_level", 0))
        except (ValueError, TypeError):
            expr_level = 0.0

        gene_expressed = expr_level >= expr_threshold

        n_var_expr     = 0   # variant present AND expressed
        n_var_no_expr  = 0   # variant present AND NOT expressed
        n_no_var_expr  = 0   # variant absent  AND expressed
        n_no_var_no_expr = 0 # variant absent  AND NOT expressed
        n_missing      = 0

        for gt_col in sample_gt_cols:
            gt = group_rows[0].get(gt_col, ".")  # same variant → same GT per sample
            carrier = has_alt_allele(gt)

            if carrier is None:
                n_missing += 1
                continue

            if carrier and gene_expressed:
                n_var_expr += 1
            elif carrier and not gene_expressed:
                n_var_no_expr += 1
            elif not carrier and gene_expressed:
                n_no_var_expr += 1
            else:
                n_no_var_no_expr += 1

        total = n_var_expr + n_var_no_expr + n_no_var_expr + n_no_var_no_expr

        results.append({
            "chrom":                    chrom,
            "pos":                      pos,
            "ref":                      ref,
            "alt":                      alt,
            "gene_id":                  gene_id,
            "expression_level":         expr_level,
            "expression_threshold":     expr_threshold,
            "gene_expressed":           gene_expressed,
            "n_variant_expressed":      n_var_expr,
            "n_variant_not_expressed":  n_var_no_expr,
            "n_no_variant_expressed":   n_no_var_expr,
            "n_no_variant_not_expressed": n_no_var_no_expr,
            "total_samples":            total,
            "n_missing_genotype":       n_missing,
        })

    # Sort for deterministic output: chrom → pos (numeric if possible) → alt
    def sort_key(r):
        try:
            p = int(r["pos"])
        except (ValueError, TypeError):
            p = 0
        return (r["chrom"], p, r["alt"])

    results.sort(key=sort_key)
    return results


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

OUTPUT_FIELDS = [
    "chrom", "pos", "ref", "alt", "gene_id",
    "expression_level", "expression_threshold", "gene_expressed",
    "n_variant_expressed", "n_variant_not_expressed",
    "n_no_variant_expressed", "n_no_variant_not_expressed",
    "total_samples", "n_missing_genotype",
]


def main():
    parser = argparse.ArgumentParser(
        description="Script 4 – Generate 2×2 contingency table from joined results."
    )
    parser.add_argument(
        "--input-file",
        required=True,
        help="Path to joined_results.csv produced by join_results.py.",
    )
    parser.add_argument(
        "--output-file",
        required=True,
        help="Destination CSV path for the contingency table.",
    )
    parser.add_argument(
        "--experiment-id",
        required=True,
        type=int,
        help="Experiment ID used for logging/tracking.",
    )
    parser.add_argument(
        "--expr-threshold",
        type=float,
        default=1.0,
        help=(
            "Expression level threshold above which a gene is considered "
            "'expressed' (default: 1.0)."
        ),
    )
    args = parser.parse_args()

    print(
        f"[CONT] Starting contingency table generation for experiment {args.experiment_id}",
        file=sys.stderr,
    )
    print(
        f"[CONT] Expression threshold: {args.expr_threshold}",
        file=sys.stderr,
    )

    try:
        input_path = Path(args.input_file)
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        fieldnames, rows = read_csv(input_path)
        print(f"[CONT] Loaded {len(rows)} rows from joined results.", file=sys.stderr)

        results = build_contingency(rows, fieldnames, args.expr_threshold)
        print(
            f"[CONT] Built contingency table with {len(results)} variant entries.",
            file=sys.stderr,
        )

        output_path = Path(args.output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=OUTPUT_FIELDS)
            writer.writeheader()
            writer.writerows(results)

        print(f"[CONT] Contingency table written to: {output_path}", file=sys.stderr)
        sys.exit(0)

    except Exception as exc:
        print(f"[CONT] ERROR: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
