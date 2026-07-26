#!/usr/bin/env python3
"""Package a validated exact export and derived tables for Hugging Face.

This is an additive operation: the command refuses to overwrite its output and
does not modify the exact export, derived snapshots, or validation inputs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(root: Path) -> None:
    rows = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative == "manifest.csv":
            continue
        rows.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    with (root / "manifest.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "bytes", "sha256"])
        writer.writeheader()
        writer.writerows(rows)


def dataset_card(provenance: dict[str, object]) -> str:
    counts = provenance["rows_by_metric_month"]
    totals = {
        metric: sum(months.values())
        for metric, months in counts.items()
    }
    total_rows = sum(totals.values())
    metric_rows = "\n".join(
        f"| `{metric}` | {rows:,} |" for metric, rows in sorted(totals.items())
    )
    return f"""---
license: cc-by-4.0
pretty_name: Bay Bridge Traffic Camera
task_categories:
- time-series-forecasting
tags:
- traffic
- computer-vision
- prometheus
- time-series
- san-francisco
size_categories:
- 100M<n<1B
---

# Bay Bridge Traffic Camera

Exact and derived time-series outputs from an experimental window-camera
detector observing the San Francisco-Oakland Bay Bridge from August 2025
through July 2026.

**These are algorithmic detections, not official or ground-truth traffic
counts.** Precision, recall, false-positive rate, and false-negative rate are
unknown. Pixel-speed fields are detector features, not mph or km/h.

## Contents

- `raw/<metric>/<YYYY-MM>/part-00000.parquet`: {total_rows:,} exact Prometheus
  application samples with millisecond timestamps, raw values, and original
  labels.
- `derived/browser-v3/`: compact five-minute, half-hour, hourly, daily, profile,
  coverage, lighting-regime, and analysis tables used by the static site.
- `validation/external-v1/`: comparisons with MTC and Caltrans high-level
  reference statistics, including provenance.
- `exact-export-provenance.json`: export boundaries, image identity, schema,
  and row counts.
- `manifest.csv`: checksums for the complete published package.

Native Prometheus TSDB blocks and the Grafana database are deliberately not
published because they can contain operational metadata or credentials. No
continuous video archive was collected.

## Exact raw schema

Each Parquet shard uses the same schema:

- `timestamp_utc`: timezone-aware millisecond timestamp
- `metric`: Prometheus metric name
- `value`: unmodified floating-point sample value
- `labels_json`: every original Prometheus label, sorted as JSON
- typed convenience label columns: `direction`, `window`, `component`, `app`,
  `instance`, `job`, `exported_job`, `exported_instance`, and
  `exported_exported_instance`
- `source_series`: `direct` or `imported`

Historical import repairs created duplicate-looking label series. The exact
layer preserves both. For most traffic analysis, select `source_series ==
"direct"` or use the already reconciled derived tables.

## Row inventory

| Metric | Exact samples |
| --- | ---: |
{metric_rows}

## Loading examples

```python
import pyarrow.dataset as ds

flow = ds.dataset(
    "raw/traffic_flow_rate_per_minute",
    format="parquet",
    partitioning=None,
)
table = flow.to_table(
    filter=ds.field("source_series") == "direct",
    columns=["timestamp_utc", "direction", "value"],
)
```

Or after publication:

```python
from datasets import load_dataset

flow = load_dataset(
    "jwt625/bay-bridge-traffic-cam",
    data_files={{
        "train": "raw/traffic_flow_rate_per_minute/**/*.parquet"
    }},
)
```

## Interpretation and known discontinuities

The two camera directions have materially different view and occlusion
responses. A comparison with 2024 Caltrans AADT suggests indicative
presentation multipliers of 2.447544× for Oakland-bound (`left`) and 1.356866×
for SF-bound (`right`). These are reversible reference-scaling factors, not
calibration constants. Published raw and derived files remain unscaled.

Bay Lights LED commissioning began approximately 2026-02-19, followed by the
official relighting on 2026-03-20. Nighttime detector spike excess and
within-night variability increased by roughly 3×, consistent with animated
lights being detected as motion. Use the `pre_lights`, `commissioning`, and
`illuminated` fields to separate optical regimes; do not interpret the
post-lighting nighttime surge as traffic growth.

Coverage gaps, one observed direct-counter reset, DST handling, external
validation, and detailed methodology are documented in the project repository:
https://github.com/jwt625/bay-bridge-traffic-cam

## License and citation

Data and derived tables are released under CC BY 4.0. Code is separately
released under MIT. Suggested attribution:

> Jiang, Wentao. *Bay Bridge Traffic Camera Dataset* (2025-2026).
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-export", type=Path, required=True)
    parser.add_argument("--derived-dir", type=Path, required=True)
    parser.add_argument("--validation-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--data-license", type=Path, default=Path("DATA_LICENSE.md"))
    parser.add_argument("--citation", type=Path, default=Path("CITATION.cff"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    exact_export = args.exact_export.resolve()
    derived_dir = args.derived_dir.resolve()
    validation_dir = args.validation_dir.resolve()
    output_dir = args.output_dir.resolve()
    required = [
        exact_export / "raw",
        exact_export / "provenance.json",
        exact_export / "manifest.csv",
        derived_dir,
        validation_dir,
        args.data_license.resolve(),
        args.citation.resolve(),
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Required release inputs missing: {missing}")
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite output: {output_dir}")

    provenance = json.loads((exact_export / "provenance.json").read_text())
    output_dir.mkdir(parents=True)
    shutil.copytree(exact_export / "raw", output_dir / "raw")
    shutil.copytree(derived_dir, output_dir / "derived" / "browser-v3")
    shutil.copytree(
        validation_dir,
        output_dir / "validation" / "external-v1",
    )
    public_export_provenance = dict(provenance)
    public_export_provenance.pop("source_dir", None)
    public_export_provenance.setdefault(
        "source_reference",
        "export-work-v1/prometheus-tsdb",
    )
    (output_dir / "exact-export-provenance.json").write_text(
        json.dumps(public_export_provenance, indent=2, sort_keys=True) + "\n"
    )
    shutil.copy2(args.data_license, output_dir / "DATA_LICENSE.md")
    shutil.copy2(args.citation, output_dir / "CITATION.cff")
    (output_dir / "README.md").write_text(dataset_card(provenance))
    release_provenance = {
        "created_utc": datetime.now(UTC).isoformat(),
        "exact_export_reference": exact_export.name,
        "derived_reference": derived_dir.name,
        "validation_reference": validation_dir.name,
        "non_destructive": True,
        "native_tsdb_published": False,
        "grafana_database_published": False,
    }
    (output_dir / "release-provenance.json").write_text(
        json.dumps(release_provenance, indent=2, sort_keys=True) + "\n"
    )
    write_manifest(output_dir)
    print(f"Prepared additive release: {output_dir}")


if __name__ == "__main__":
    main()
