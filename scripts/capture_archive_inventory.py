#!/usr/bin/env python3
"""Capture a versioned, read-only inventory of the live archive sources.

The script performs only diagnostic reads against Docker, Prometheus, and
Grafana. It refuses to overwrite an existing output directory and does not
stop, restart, recreate, compact, snapshot, or modify any service or volume.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd
import requests

APPLICATION_METRICS = [
    "traffic_vehicles_total",
    "traffic_vehicles_created",
    "traffic_flow_rate_per_minute",
    "traffic_speed_current_pixels_per_second",
    "traffic_speed_average_pixels_per_second",
    "motion_detector_fps",
    "tracked_objects_active",
    "system_status",
]


def get_json(url: str, **kwargs: Any) -> Any:
    response = requests.get(url, timeout=30, **kwargs)
    response.raise_for_status()
    return response.json()


def command_json(*command: str) -> Any:
    output = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return json.loads(output)


def command_text(*command: str) -> str:
    return subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def sanitize_container(container: dict[str, Any]) -> dict[str, Any]:
    config = container.get("Config", {})
    return {
        "id": container.get("Id"),
        "name": container.get("Name", "").lstrip("/"),
        "image": config.get("Image"),
        "image_digest": container.get("Image"),
        "created": container.get("Created"),
        "state": {
            key: container.get("State", {}).get(key)
            for key in ("Status", "Running", "StartedAt")
        },
        "mounts": [
            {
                key.lower(): mount.get(key)
                for key in ("Type", "Name", "Source", "Destination", "Mode", "RW")
            }
            for mount in container.get("Mounts", [])
        ],
        "ports": container.get("NetworkSettings", {}).get("Ports", {}),
        # Intentionally omit environment variables and other secret-bearing
        # container configuration.
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("archive/metadata-v1"),
        help="New versioned output directory; must not already exist",
    )
    parser.add_argument(
        "--prometheus-url",
        default="http://localhost:9090",
    )
    parser.add_argument(
        "--grafana-url",
        default="http://localhost:3000",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(
            f"Refusing to overwrite existing inventory: {args.output_dir}"
        )
    args.output_dir.mkdir(parents=True)

    containers = command_json("docker", "inspect", "prometheus", "grafana")
    runtime_inventory = {
        "non_destructive": True,
        "containers": [sanitize_container(container) for container in containers],
    }
    write_json(args.output_dir / "runtime-inventory.json", runtime_inventory)

    flags = get_json(f"{args.prometheus_url}/api/v1/status/flags")
    build_info = get_json(f"{args.prometheus_url}/api/v1/status/buildinfo")
    tsdb_status = get_json(f"{args.prometheus_url}/api/v1/status/tsdb")
    write_json(args.output_dir / "prometheus-flags.json", flags)
    write_json(args.output_dir / "prometheus-build-info.json", build_info)
    write_json(args.output_dir / "prometheus-tsdb-status.json", tsdb_status)

    block_list = command_text(
        "docker", "exec", "prometheus", "promtool", "tsdb", "list", "/prometheus"
    )
    (args.output_dir / "prometheus-blocks.txt").write_text(
        block_list,
        encoding="utf-8",
    )

    series: dict[str, Any] = {}
    for metric in APPLICATION_METRICS:
        series[metric] = get_json(
            f"{args.prometheus_url}/api/v1/series",
            params={
                "match[]": metric,
                "start": "2025-07-01T00:00:00Z",
                "end": "2026-07-27T00:00:00Z",
            },
        )
    write_json(args.output_dir / "prometheus-application-series.json", series)

    grafana_health = get_json(f"{args.grafana_url}/api/health")
    grafana_search = get_json(
        f"{args.grafana_url}/api/search",
        params={"type": "dash-db"},
    )
    dashboard = get_json(
        f"{args.grafana_url}/api/dashboards/uid/bay-bridge-traffic"
    )
    write_json(args.output_dir / "grafana-health.json", grafana_health)
    write_json(args.output_dir / "grafana-dashboard-search.json", grafana_search)
    write_json(args.output_dir / "grafana-dashboard.json", dashboard)

    files = sorted(path for path in args.output_dir.iterdir() if path.is_file())
    manifest = pd.DataFrame(
        [
            {
                "path": path.name,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in files
        ]
    )
    manifest.to_csv(args.output_dir / "manifest.csv", index=False)

    print(f"Wrote read-only archive inventory: {args.output_dir}")
    for path in sorted(args.output_dir.iterdir()):
        print(f"{path.name}\t{path.stat().st_size} bytes")


if __name__ == "__main__":
    main()
