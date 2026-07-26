#!/usr/bin/env python3
"""Validate checksums, schemas, row counts, and statistics in an exact export."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import pyarrow.parquet as pq

from export_exact_tsdb import APPLICATION_METRICS, SCHEMA


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate(root: Path) -> dict[str, object]:
    manifest_path = root / "manifest.csv"
    provenance_path = root / "provenance.json"
    if not manifest_path.is_file() or not provenance_path.is_file():
        raise FileNotFoundError("manifest.csv and provenance.json are required")

    with manifest_path.open(newline="") as handle:
        manifest = list(csv.DictReader(handle))
    if not manifest:
        raise ValueError("Manifest is empty")

    expected_paths = {row["path"] for row in manifest}
    actual_paths = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path != manifest_path
    }
    if expected_paths != actual_paths:
        raise ValueError(
            f"Manifest path mismatch: missing={expected_paths - actual_paths}, "
            f"unexpected={actual_paths - expected_paths}"
        )
    for row in manifest:
        path = root / row["path"]
        if path.stat().st_size != int(row["bytes"]):
            raise ValueError(f"Byte-size mismatch: {row['path']}")
        if sha256(path) != row["sha256"]:
            raise ValueError(f"SHA-256 mismatch: {row['path']}")

    provenance = json.loads(provenance_path.read_text())
    expected_counts = provenance["rows_by_metric_month"]
    observed_counts: dict[str, dict[str, int]] = defaultdict(dict)
    timestamps: list[int] = []
    parquet_files = sorted((root / "raw").glob("*/*/*.parquet"))
    if not parquet_files:
        raise ValueError("No raw Parquet shards found")
    for path in parquet_files:
        metric = path.parent.parent.name
        month = path.parent.name
        if metric not in APPLICATION_METRICS:
            raise ValueError(f"Unexpected metric directory: {metric}")
        parquet = pq.ParquetFile(path)
        if parquet.schema_arrow != SCHEMA:
            raise ValueError(f"Schema mismatch: {path.relative_to(root)}")
        observed_counts[metric][month] = parquet.metadata.num_rows
        for row_group_index in range(parquet.metadata.num_row_groups):
            row_group = parquet.metadata.row_group(row_group_index)
            column = row_group.column(0)
            statistics = column.statistics
            if statistics is None or not statistics.has_min_max:
                raise ValueError(f"Timestamp statistics absent: {path}")
            timestamps.extend(
                [
                    int(statistics.min.timestamp() * 1000),
                    int(statistics.max.timestamp() * 1000),
                ]
            )

    if dict(observed_counts) != expected_counts:
        raise ValueError("Parquet row counts do not match provenance")

    observed_metrics = set(observed_counts)
    if observed_metrics != set(provenance["metrics"]):
        raise ValueError("Metric set does not match provenance")

    total_rows = sum(sum(months.values()) for months in observed_counts.values())
    result = {
        "files_verified": len(manifest),
        "parquet_shards": len(parquet_files),
        "exact_samples": total_rows,
        "minimum_timestamp_ms": min(timestamps),
        "maximum_timestamp_ms": max(timestamps),
        "metrics": sorted(observed_metrics),
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset_dir", type=Path)
    args = parser.parse_args()
    result = validate(args.dataset_dir.resolve())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
