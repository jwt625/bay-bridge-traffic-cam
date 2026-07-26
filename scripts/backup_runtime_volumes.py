#!/usr/bin/env python3
"""Create a consistency-safe, additive backup of the live monitoring volumes.

Safety properties:

- Resolves and verifies exact container volume names before pausing anything.
- Refuses to overwrite an existing output directory.
- Pauses Grafana and Prometheus only while copying their mounted data paths.
- Always attempts to resume paused containers in a ``finally`` block.
- Never removes, prunes, recreates, or reconfigures a container or volume.
- Writes per-file SHA-256 checksums and sanitized runtime metadata.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

TARGETS = {
    "prometheus": {
        "destination": "/prometheus",
        "volume": "20250802_bay_bridge_traffic_cam_prometheus-storage",
        "backup_dir": "prometheus-tsdb",
    },
    "grafana": {
        "destination": "/var/lib/grafana",
        "volume": "bay-bridge-traffic-cam_grafana-storage",
        "backup_dir": "grafana-data",
    },
}


def run(*args: str, capture: bool = False) -> str:
    result = subprocess.run(
        args,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )
    return result.stdout if capture else ""


def inspect_container(name: str) -> dict[str, object]:
    payload = json.loads(run("docker", "inspect", name, capture=True))
    if len(payload) != 1:
        raise RuntimeError(f"Expected exactly one container named {name}")
    return payload[0]


def verify_target(name: str, target: dict[str, str]) -> dict[str, object]:
    inspected = inspect_container(name)
    if inspected["State"]["Status"] != "running":
        raise RuntimeError(f"{name} is not running")

    matches = [
        mount
        for mount in inspected["Mounts"]
        if mount["Type"] == "volume"
        and mount["Destination"] == target["destination"]
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one volume at {name}:{target['destination']}; got {matches}"
        )
    if matches[0]["Name"] != target["volume"]:
        raise RuntimeError(
            f"Refusing unexpected volume for {name}: {matches[0]['Name']}"
        )
    return {
        "container": name,
        "container_id": inspected["Id"],
        "image": inspected["Config"]["Image"],
        "image_id": inspected["Image"],
        "destination": target["destination"],
        "volume": matches[0]["Name"],
    }


def wait_for_url(url: str, timeout_seconds: int = 30) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if 200 <= response.status < 300:
                    return
        except Exception as error:  # pragma: no cover - environment dependent
            last_error = error
        time.sleep(1)
    raise RuntimeError(f"Health check failed for {url}: {last_error}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(output_dir: Path) -> None:
    rows = ["path,bytes,sha256"]
    excluded = {"manifest.csv", "backup-metadata.json"}
    for path in sorted(item for item in output_dir.rglob("*") if item.is_file()):
        relative = path.relative_to(output_dir).as_posix()
        if relative in excluded:
            continue
        rows.append(f"{relative},{path.stat().st_size},{sha256(path)}")
    (output_dir / "manifest.csv").write_text("\n".join(rows) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("archive/source-v1"),
        help="New backup directory; must not already exist",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing path: {output_dir}")

    verified = {
        name: verify_target(name, target)
        for name, target in TARGETS.items()
    }
    started = datetime.now(UTC)
    output_dir.mkdir(parents=True)
    for target in TARGETS.values():
        (output_dir / target["backup_dir"]).mkdir()

    paused: list[str] = []
    copy_error: str | None = None
    try:
        # Pause the dashboard first so it cannot issue new queries while the
        # source database is being frozen.
        for name in ("grafana", "prometheus"):
            run("docker", "pause", name)
            paused.append(name)

        for name in ("prometheus", "grafana"):
            target = TARGETS[name]
            run(
                "docker",
                "cp",
                f"{name}:{target['destination']}/.",
                str(output_dir / target["backup_dir"]),
            )
    except Exception as error:
        copy_error = repr(error)
        raise
    finally:
        for name in reversed(paused):
            try:
                run("docker", "unpause", name)
            except Exception:
                # Continue attempting to resume every paused container.
                pass
        metadata = {
            "started_utc": started.isoformat(),
            "finished_utc": datetime.now(UTC).isoformat(),
            "non_destructive": True,
            "copy_error": copy_error,
            "targets": verified,
        }
        (output_dir / "backup-metadata.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n"
        )

    wait_for_url("http://localhost:9090/-/ready")
    wait_for_url("http://localhost:3000/api/health")
    write_manifest(output_dir)

    print(f"Backup complete: {output_dir}")
    for target in TARGETS.values():
        path = output_dir / target["backup_dir"]
        total = sum(item.stat().st_size for item in path.rglob("*") if item.is_file())
        print(f"{target['backup_dir']}\t{total} bytes")
    print(f"manifest entries\t{sum(1 for _ in (output_dir / 'manifest.csv').open()) - 1}")


if __name__ == "__main__":
    main()
