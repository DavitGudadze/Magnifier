#!/usr/bin/env python3
"""
Script 2: VCF / VEP Processing
Parses one or more VCF files from a directory, extracts variant information,
and writes a flat CSV suitable for joining with expression data.

Input:  directory of *.vcf / *.vcf.gz files
Output: CSV with columns:
            chrom, pos, id, ref, alt, qual, filter,
            af, dp, gene_id,
            sample_<name>_gt, sample_<name>_gq, sample_<name>_dp
        (one row per variant × ALT allele)
"""

import argparse
import csv
import gzip
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# VCF parsing helpers
# ---------------------------------------------------------------------------

def open_vcf(filepath: Path):
    """Open a plain or gzipped VCF file and return a line iterator."""
    if filepath.suffix == ".gz":
        return gzip.open(filepath, "rt")
    return open(filepath, "r")


def split_vcf_line(line: str) -> list[str]:
    """
    Split a VCF data/header line on tab; fall back to whitespace splitting
    for non-standard space-delimited files.
    """
    if "\t" in line:
        return line.split("\t")
    return line.split()


def parse_info(info_str: str) -> dict:
    """
    Parse the INFO column into a dict.
    Flags (no '=') get value True; multi-value fields keep their raw string.
    """
    info = {}
    for field in info_str.split(";"):
        if "=" in field:
            key, value = field.split("=", 1)
            info[key] = value
        else:
            info[field] = True
    return info


def parse_genotype(format_str: str, sample_str: str) -> dict:
    """Return a dict mapping FORMAT keys → sample values."""
    keys   = format_str.split(":")
    values = sample_str.split(":")
    # Pad with '.' if fewer values than keys
    values += ["."] * (len(keys) - len(values))
    return dict(zip(keys, values))


def parse_vcf_file(filepath: Path) -> tuple[list[str], list[dict]]:
    """
    Parse a single VCF file.

    Returns
    -------
    sample_names : list[str]
    rows         : list of dicts (one per variant × ALT allele)
    """
    sample_names: list[str] = []
    rows: list[dict] = []

    with open_vcf(filepath) as fh:
        for raw_line in fh:
            line = raw_line.rstrip("\n")

            # --- Header lines ---
            if line.startswith("##"):
                continue

            if line.startswith("#CHROM"):
                parts = split_vcf_line(line.lstrip("#"))
                # Standard VCF columns are the first 9; samples follow
                sample_names = parts[9:] if len(parts) > 9 else []
                continue

            # --- Data lines ---
            parts = split_vcf_line(line)
            if len(parts) < 8:
                continue  # malformed line

            chrom   = parts[0]
            pos     = parts[1]
            var_id  = parts[2]
            ref     = parts[3]
            alt_raw = parts[4]
            qual    = parts[5]
            filt    = parts[6]
            info_str = parts[7]
            fmt_str  = parts[8] if len(parts) > 8 else ""

            info = parse_info(info_str)

            # One row per ALT allele
            alts = alt_raw.split(",")
            afs  = info.get("AF", "").split(",") if "AF" in info else [""] * len(alts)
            afs += [""] * (len(alts) - len(afs))   # pad if shorter

            for i, alt in enumerate(alts):
                if alt == ".":
                    continue  # no alternative allele

                base_row = {
                    "chrom":  chrom,
                    "pos":    pos,
                    "id":     var_id,
                    "ref":    ref,
                    "alt":    alt,
                    "qual":   qual,
                    "filter": filt,
                    "af":     afs[i],
                    "dp":     info.get("DP", ""),
                    # gene_id: use variant ID when available; otherwise chrom_pos
                    "gene_id": var_id if var_id != "." else f"{chrom}_{pos}",
                }

                # Per-sample genotype fields
                sample_data = parts[9:] if len(parts) > 9 else []
                for s_idx, s_name in enumerate(sample_names):
                    if s_idx < len(sample_data):
                        gt_dict = parse_genotype(fmt_str, sample_data[s_idx])
                    else:
                        gt_dict = {}

                    safe = re.sub(r"\W+", "_", s_name)
                    base_row[f"sample_{safe}_gt"] = gt_dict.get("GT", ".")
                    base_row[f"sample_{safe}_gq"] = gt_dict.get("GQ", ".")
                    base_row[f"sample_{safe}_dp"] = gt_dict.get("DP", ".")

                rows.append(base_row)

    return sample_names, rows


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def find_vcf_files(vcf_dir: Path) -> list[Path]:
    vcfs = list(vcf_dir.glob("*.vcf")) + list(vcf_dir.glob("*.vcf.gz"))
    if not vcfs:
        raise FileNotFoundError(f"No VCF files found in: {vcf_dir}")
    return sorted(vcfs)


def write_output(all_rows: list[dict], output_path: Path) -> None:
    if not all_rows:
        raise ValueError("No VCF variants parsed — aborting.")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Union of all keys (order: fixed cols first, sample cols after)
    fixed = ["chrom", "pos", "id", "ref", "alt", "qual", "filter", "af", "dp", "gene_id"]
    sample_cols = sorted({k for row in all_rows for k in row if k.startswith("sample_")})
    fieldnames  = fixed + sample_cols

    with open(output_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in all_rows:
            # Fill missing sample columns with '.'
            for col in sample_cols:
                row.setdefault(col, ".")
            writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(
        description="Script 2 – Parse VCF files and extract variant/VEP data."
    )
    parser.add_argument(
        "--vcf-dir",
        required=True,
        help="Directory containing VCF (or VCF.gz) files.",
    )
    parser.add_argument(
        "--output-file",
        required=True,
        help="Destination CSV path for the parsed VEP results.",
    )
    parser.add_argument(
        "--experiment-id",
        required=True,
        type=int,
        help="Experiment ID used for logging/tracking.",
    )
    args = parser.parse_args()

    print(
        f"[VEP] Starting VCF processing for experiment {args.experiment_id}",
        file=sys.stderr,
    )

    try:
        vcf_dir = Path(args.vcf_dir)
        if not vcf_dir.exists():
            raise FileNotFoundError(f"VCF directory not found: {vcf_dir}")

        vcf_files = find_vcf_files(vcf_dir)
        print(f"[VEP] Found {len(vcf_files)} VCF file(s).", file=sys.stderr)

        all_rows: list[dict] = []
        for vcf_file in vcf_files:
            print(f"[VEP] Parsing: {vcf_file.name}", file=sys.stderr)
            _, rows = parse_vcf_file(vcf_file)
            all_rows.extend(rows)
            print(f"[VEP]   → {len(rows)} variant rows extracted.", file=sys.stderr)

        print(f"[VEP] Total variants: {len(all_rows)}", file=sys.stderr)

        output_path = Path(args.output_file)
        write_output(all_rows, output_path)
        print(f"[VEP] VEP results written to: {output_path}", file=sys.stderr)

        sys.exit(0)

    except Exception as exc:
        print(f"[VEP] ERROR: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
