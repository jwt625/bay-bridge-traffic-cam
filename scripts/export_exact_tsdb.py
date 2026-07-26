#!/usr/bin/env python3
"""Export exact application samples from a copied Prometheus TSDB to Parquet.

The source must be a disposable working copy of an already verified backup.
The script never connects to the live Prometheus API and refuses to overwrite
an existing output directory.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

APPLICATION_METRICS = (
    "motion_detector_fps",
    "system_status",
    "tracked_objects_active",
    "traffic_flow_rate_per_minute",
    "traffic_speed_average_pixels_per_second",
    "traffic_speed_current_pixels_per_second",
    "traffic_vehicles_created",
    "traffic_vehicles_total",
)
COMMON_LABELS = (
    "direction",
    "window",
    "component",
    "app",
    "instance",
    "job",
    "exported_job",
    "exported_instance",
    "exported_exported_instance",
)
SAMPLE_RE = re.compile(
    r"^(?P<metric>[a-zA-Z_:][a-zA-Z0-9_:]*)"
    r"(?:\{(?P<labels>.*)\})? "
    r"(?P<value>[^ ]+) (?P<timestamp>[^ ]+)$"
)
LABEL_RE = re.compile(
    r'(?P<name>[a-zA-Z_][a-zA-Z0-9_]*)='
    r'(?P<value>"(?:\\.|[^"\\])*")'
    r"(?:,|$)"
)
SCHEMA = pa.schema(
    [
        pa.field("timestamp_utc", pa.timestamp("ms", tz="UTC"), nullable=False),
        pa.field("metric", pa.string(), nullable=False),
        pa.field("value", pa.float64(), nullable=False),
        pa.field("labels_json", pa.string(), nullable=False),
        *[pa.field(label, pa.string()) for label in COMMON_LABELS],
        pa.field("source_series", pa.string(), nullable=False),
    ]
)


def parse_labels(text: str | None) -> dict[str, str]:
    if not text:
        return {}
    labels: dict[str, str] = {}
    position = 0
    while position < len(text):
        match = LABEL_RE.match(text, position)
        if match is None:
            raise ValueError(f"Cannot parse labels at {text[position:]!r}")
        labels[match.group("name")] = json.loads(match.group("value"))
        position = match.end()
    return labels


def timestamp_seconds_to_milliseconds(value: str) -> int:
    whole, dot, fraction = value.partition(".")
    milliseconds = int(whole) * 1000
    if dot:
        milliseconds += int((fraction + "000")[:3])
    return milliseconds


def parse_sample(line: str) -> dict[str, object]:
    match = SAMPLE_RE.match(line)
    if match is None:
        raise ValueError(f"Cannot parse OpenMetrics sample: {line!r}")
    labels = parse_labels(match.group("labels"))
    timestamp_ms = timestamp_seconds_to_milliseconds(match.group("timestamp"))
    result: dict[str, object] = {
        "timestamp_utc": timestamp_ms,
        "metric": match.group("metric"),
        "value": float(match.group("value")),
        "labels_json": json.dumps(
            labels,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ),
        "source_series": (
            "imported" if labels.get("exported_job") == "imported_data" else "direct"
        ),
    }
    for label in COMMON_LABELS:
        result[label] = labels.get(label)
    return result


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def month_for_timestamp_ms(timestamp_ms: int) -> str:
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC).strftime("%Y-%m")


class MetricWriters:
    def __init__(self, root: Path, metric: str, batch_rows: int):
        self.root = root
        self.metric = metric
        self.batch_rows = batch_rows
        self.buffers: dict[str, list[dict[str, object]]] = defaultdict(list)
        self.writers: dict[str, pq.ParquetWriter] = {}
        self.rows_by_month: dict[str, int] = defaultdict(int)

    def append(self, row: dict[str, object]) -> None:
        month = month_for_timestamp_ms(int(row["timestamp_utc"]))
        buffer = self.buffers[month]
        buffer.append(row)
        if len(buffer) >= self.batch_rows:
            self.flush(month)

    def flush(self, month: str) -> None:
        rows = self.buffers[month]
        if not rows:
            return
        table = pa.Table.from_pylist(rows, schema=SCHEMA)
        writer = self.writers.get(month)
        if writer is None:
            output_dir = (
                self.root
                / "raw"
                / self.metric
                / month
            )
            output_dir.mkdir(parents=True)
            writer = pq.ParquetWriter(
                output_dir / "part-00000.parquet",
                SCHEMA,
                compression="zstd",
                compression_level=9,
                use_dictionary=True,
                write_statistics=True,
            )
            self.writers[month] = writer
        writer.write_table(table)
        self.rows_by_month[month] += len(rows)
        rows.clear()

    def close(self) -> None:
        for month in list(self.buffers):
            self.flush(month)
        for writer in self.writers.values():
            writer.close()


def promtool_command(
    *,
    image_id: str,
    source_dir: Path,
    metric: str,
    min_time_ms: int,
    max_time_ms: int,
) -> list[str]:
    return [
        "docker",
        "run",
        "--rm",
        "--entrypoint",
        "/bin/promtool",
        "--mount",
        f"type=bind,source={source_dir},target=/prometheus",
        image_id,
        "tsdb",
        "dump-openmetrics",
        f"--min-time={min_time_ms}",
        f"--max-time={max_time_ms}",
        f'--match={{__name__="{metric}"}}',
        "/prometheus",
    ]


def export_metric(
    *,
    output_dir: Path,
    source_dir: Path,
    image_id: str,
    metric: str,
    min_time_ms: int,
    max_time_ms: int,
    batch_rows: int,
) -> dict[str, int]:
    command = promtool_command(
        image_id=image_id,
        source_dir=source_dir,
        metric=metric,
        min_time_ms=min_time_ms,
        max_time_ms=max_time_ms,
    )
    process = subprocess.Popen(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1024 * 1024,
    )
    if process.stdout is None or process.stderr is None:
        raise RuntimeError("Failed to open promtool output streams")

    writers = MetricWriters(output_dir, metric, batch_rows)
    count = 0
    try:
        for raw_line in process.stdout:
            line = raw_line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            row = parse_sample(line)
            if row["metric"] != metric:
                raise RuntimeError(
                    f"Selector for {metric} returned {row['metric']}"
                )
            writers.append(row)
            count += 1
            if count % 1_000_000 == 0:
                print(f"{metric}: {count:,} exact samples", flush=True)
    finally:
        writers.close()

    stderr = process.stderr.read()
    return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(
            f"promtool failed for {metric} with {return_code}: {stderr}"
        )
    print(f"{metric}: complete ({count:,} exact samples)", flush=True)
    return dict(writers.rows_by_month)


def write_manifest(output_dir: Path) -> None:
    rows = []
    for path in sorted(item for item in output_dir.rglob("*") if item.is_file()):
        relative = path.relative_to(output_dir).as_posix()
        if relative == "manifest.csv":
            continue
        rows.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    with (output_dir / "manifest.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "bytes", "sha256"])
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--image-id",
        default=(
            "sha256:9abc6cf6aea7710d163dbb28d8eeb7dc5baef01e38fa4cd"
            "146a406dd9f07f70d"
        ),
    )
    parser.add_argument(
        "--start",
        default="2025-08-01T00:00:00Z",
    )
    parser.add_argument(
        "--end",
        default="2026-07-27T00:00:00Z",
    )
    parser.add_argument("--batch-rows", type=int, default=25_000)
    parser.add_argument(
        "--metric",
        action="append",
        choices=APPLICATION_METRICS,
        help="Export selected metric; repeat as needed. Defaults to all.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_dir = args.source_dir.resolve()
    output_dir = args.output_dir.resolve()
    if not source_dir.is_dir():
        raise FileNotFoundError(f"TSDB working copy not found: {source_dir}")
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite output: {output_dir}")
    if args.batch_rows <= 0:
        raise ValueError("--batch-rows must be positive")

    start = datetime.fromisoformat(args.start.replace("Z", "+00:00"))
    end = datetime.fromisoformat(args.end.replace("Z", "+00:00"))
    if start.tzinfo is None or end.tzinfo is None or start >= end:
        raise ValueError("Start/end must be ordered timezone-aware timestamps")
    min_time_ms = int(start.timestamp() * 1000)
    max_time_ms = int(end.timestamp() * 1000) - 1

    output_dir.mkdir(parents=True)
    metrics = tuple(args.metric or APPLICATION_METRICS)
    counts: dict[str, dict[str, int]] = {}
    for metric in metrics:
        counts[metric] = export_metric(
            output_dir=output_dir,
            source_dir=source_dir,
            image_id=args.image_id,
            metric=metric,
            min_time_ms=min_time_ms,
            max_time_ms=max_time_ms,
            batch_rows=args.batch_rows,
        )

    provenance = {
        "created_utc": datetime.now(UTC).isoformat(),
        "purpose": "exact application-metric samples for public archival",
        "source_kind": "working copy of verified native Prometheus TSDB backup",
        "source_reference": source_dir.name,
        "prometheus_image_id": args.image_id,
        "start": start.isoformat(),
        "end_exclusive": end.isoformat(),
        "metrics": list(metrics),
        "rows_by_metric_month": counts,
        "schema": str(SCHEMA),
        "timestamp_resolution": "exact Prometheus millisecond timestamps",
        "original_labels": "preserved in sorted labels_json",
        "non_destructive": True,
    }
    (output_dir / "provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n"
    )
    write_manifest(output_dir)
    total_rows = sum(sum(months.values()) for months in counts.values())
    print(f"Export complete: {output_dir}")
    print(f"exact samples: {total_rows:,}")


if __name__ == "__main__":
    main()
