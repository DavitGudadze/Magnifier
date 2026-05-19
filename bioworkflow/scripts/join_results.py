#!/usr/bin/env python3
"""
Script 3: Join DEA Expression Data with VEP Variant Data
Performs a left join of VEP results onto expression data using 'gene_id'
as the key. Genes with no matching variant retain their expression values
with empty variant columns.

Input:
    --dea-file   : CSV output of dea_analysis.py   (gene_id, expression_level, ...)
    --vep-file   : CSV output of vep_processing.py (gene_id, chrom, pos, ...)
Output:
    --output-file: Joined CSV with all columns from both inputs
"""

import argparse
import csv
import sys
from pathlib import Path
from collections import defaultdict


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def read_csv(filepath: Path) -> tuple[list[str], list[dict]]:
    """Return (fieldnames, rows) from a CSV file."""
    with open(filepath, newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError(f"Empty or header-less CSV: {filepath}")
        fieldnames = list(reader.fieldnames)
        rows = [row for row in reader if not list(row.values())[0].startswith("#")]
    return fieldnames, rows


def build_vep_index(vep_rows: list[dict]) -> dict[str, list[dict]]:
    """Group VEP rows by gene_id for fast lookup."""
    index: dict[str, list[dict]] = defaultdict(list)
    for row in vep_rows:
        gene_id = row.get("gene_id", "").strip()
        if gene_id:
            index[gene_id].append(row)
    return index


# ---------------------------------------------------------------------------
# Join logic
# ---------------------------------------------------------------------------

def join(
    dea_rows: list[dict],
    dea_fields: list[str],
    vep_rows: list[dict],
    vep_fields: list[str],
) -> tuple[list[str], list[dict]]:
    """
    Left-join VEP data onto DEA data using gene_id.

    One output row is produced per (DEA gene × matching VEP variant).
    DEA genes with no VEP match produce one row with empty VEP columns.
    """
    vep_index = build_vep_index(vep_rows)

    # Output columns: all DEA columns first, then VEP columns (excluding
    # duplicate gene_id which already comes from DEA side).
    vep_extra = [f for f in vep_fields if f != "gene_id"]
    out_fields = dea_fields + [f for f in vep_extra if f not in dea_fields]

    empty_vep = {col: "" for col in vep_extra}

    joined: list[dict] = []
    matched = unmatched = 0

    for dea_row in dea_rows:
        gene_id = dea_row.get("gene_id", "").strip()
        vep_hits = vep_index.get(gene_id, [])

        if vep_hits:
            matched += 1
            for vep_row in vep_hits:
                out_row = dict(dea_row)
                for col in vep_extra:
                    out_row[col] = vep_row.get(col, "")
                joined.append(out_row)
        else:
            unmatched += 1
            out_row = dict(dea_row)
            out_row.update(empty_vep)
            joined.append(out_row)

    print(
        f"[JOIN] {matched} DEA genes matched VEP variants; "
        f"{unmatched} genes had no variant data.",
        file=sys.stderr,
    )

    return out_fields, joined


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Script 3 – Join DEA expression data with VEP variant data."
    )
    parser.add_argument(
        "--dea-file",
        required=True,
        help="Path to dea_results.csv produced by dea_analysis.py.",
    )
    parser.add_argument(
        "--vep-file",
        required=True,
        help="Path to vep_results.csv produced by vep_processing.py.",
    )
    parser.add_argument(
        "--output-file",
        required=True,
        help="Destination CSV path for the joined results.",
    )
    parser.add_argument(
        "--experiment-id",
        required=True,
        type=int,
        help="Experiment ID used for logging/tracking.",
    )
    args = parser.parse_args()

    print(
        f"[JOIN] Starting join for experiment {args.experiment_id}",
        file=sys.stderr,
    )

    try:
        dea_path = Path(args.dea_file)
        vep_path = Path(args.vep_file)

        if not dea_path.exists():
            raise FileNotFoundError(f"DEA file not found: {dea_path}")
        if not vep_path.exists():
            raise FileNotFoundError(f"VEP file not found: {vep_path}")

        dea_fields, dea_rows = read_csv(dea_path)
        vep_fields, vep_rows = read_csv(vep_path)
        print(
            f"[JOIN] Loaded {len(dea_rows)} DEA rows and {len(vep_rows)} VEP rows.",
            file=sys.stderr,
        )

        out_fields, joined_rows = join(dea_rows, dea_fields, vep_rows, vep_fields)
        print(f"[JOIN] Produced {len(joined_rows)} joined rows.", file=sys.stderr)

        output_path = Path(args.output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=out_fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(joined_rows)

        print(f"[JOIN] Joined results written to: {output_path}", file=sys.stderr)
        sys.exit(0)

    except Exception as exc:
        print(f"[JOIN] ERROR: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
