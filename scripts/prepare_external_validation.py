#!/usr/bin/env python3
"""Build an immutable, reproducible external-validation snapshot.

This script is additive and non-destructive:

- It downloads public MTC and Caltrans workbooks in memory.
- It reads an existing derived detector snapshot.
- It refuses to overwrite an existing validation directory.
- It does not modify Prometheus, Grafana, Docker, or prior snapshots.

The output provides high-level directional reference multipliers. They are not
point-by-point calibration factors or claims of known detector accuracy.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path

import pandas as pd
import requests

MTC_MONTHLY_URL = (
    "https://mtc.ca.gov/sites/default/files/documents/2026-07/"
    "Monthly-Transportation-Statistics-07-11-2026.xlsx?cb=dfd1a873"
)
CALTRANS_AADT_URL = (
    "https://dot.ca.gov/-/media/dot-media/programs/traffic-operations/"
    "documents/census/2024/2024-traffic-volumes-ca-a11y.xlsx"
)
CALTRANS_PEAK_URL = (
    "https://dot.ca.gov/-/media/dot-media/programs/traffic-operations/"
    "documents/census/2024/2024-ca-peak-hours-a11y.xlsx"
)
PRE_LIGHTS_END = pd.Timestamp("2026-02-19")


def download(url: str) -> bytes:
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    return response.content


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_mtc_monthly(content: bytes) -> pd.DataFrame:
    monthly = pd.read_excel(
        io.BytesIO(content),
        sheet_name="Bay-Bridge",
        header=1,
    )
    monthly.columns = ["month", "official_westbound_crossings"]
    monthly["month"] = pd.to_datetime(monthly["month"], errors="coerce")
    monthly["official_westbound_crossings"] = pd.to_numeric(
        monthly["official_westbound_crossings"],
        errors="coerce",
    )
    monthly = monthly.dropna(
        subset=["month", "official_westbound_crossings"]
    ).copy()
    monthly["days_in_month"] = monthly["month"].dt.days_in_month
    monthly["official_westbound_daily_mean"] = (
        monthly["official_westbound_crossings"] / monthly["days_in_month"]
    )
    return monthly


def read_caltrans_references(
    aadt_content: bytes,
    peak_content: bytes,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    aadt = pd.read_excel(
        io.BytesIO(aadt_content),
        sheet_name="2024 AADT DATA",
    )
    bridge = aadt[
        (aadt["RTE"] == 80)
        & (aadt["CNTY"] == "SF")
        & (aadt["PM"].round(3) == 7.719)
    ].copy()

    lower = bridge[bridge["PM_SFX"].astype(str).str.strip() == "R"].iloc[0]
    upper = bridge[bridge["PM_SFX"].astype(str).str.strip() == "L"].iloc[0]
    references = pd.DataFrame(
        [
            {
                "direction": "left",
                "destination": "Oakland-bound",
                "deck": "lower / eastbound",
                "official_reference_daily": float(lower["BACK_AADT"]),
                "reference_year": 2024,
                "reference_location": "West span at Treasure Island",
                "source": "Caltrans 2024 AADT",
            },
            {
                "direction": "right",
                "destination": "SF-bound",
                "deck": "upper / westbound",
                "official_reference_daily": float(upper["BACK_AADT"]),
                "reference_year": 2024,
                "reference_location": "West span at Treasure Island",
                "source": "Caltrans 2024 AADT; corroborated by MTC toll totals",
            },
        ]
    )

    peak = pd.read_excel(
        io.BytesIO(peak_content),
        sheet_name="2024 PEAK HOURS REPORT",
    )
    toll_plaza = peak[
        (peak["RTE"] == 80)
        & (peak["CO"] == "ALA")
        & (peak["PM"].round(3) == 1.989)
    ].copy()
    return references, toll_plaza


def build_direction_summary(
    daily: pd.DataFrame,
    references: pd.DataFrame,
) -> pd.DataFrame:
    daily["local_date"] = pd.to_datetime(daily["local_date"])
    baseline = daily[
        daily["complete_day"]
        & (daily["local_date"] < PRE_LIGHTS_END)
    ].copy()

    detector = (
        baseline.groupby("direction", observed=True)
        .agg(
            detector_days=("local_date", "nunique"),
            detector_daily_mean=("counter_positive_increments", "mean"),
            detector_daily_median=("counter_positive_increments", "median"),
            detector_daily_std=("counter_positive_increments", "std"),
            detector_total=("counter_positive_increments", "sum"),
        )
        .reset_index()
    )
    total = detector["detector_total"].sum()
    detector["detector_direction_share"] = detector["detector_total"] / total

    result = references.merge(detector, on="direction", how="left")
    official_total = result["official_reference_daily"].sum()
    result["official_direction_share"] = (
        result["official_reference_daily"] / official_total
    )
    result["indicative_multiplier_mean"] = (
        result["official_reference_daily"] / result["detector_daily_mean"]
    )
    result["indicative_multiplier_median"] = (
        result["official_reference_daily"] / result["detector_daily_median"]
    )
    result["interpretation"] = (
        "High-level directional reference only; not a calibrated correction factor"
    )
    return result


def build_westbound_monthly_match(
    daily: pd.DataFrame,
    mtc_monthly: pd.DataFrame,
) -> pd.DataFrame:
    data = daily[
        daily["complete_day"] & (daily["direction"] == "right")
    ].copy()
    data["month"] = pd.to_datetime(data["local_date"]).dt.to_period("M").dt.to_timestamp()
    detector = (
        data.groupby("month", observed=True)
        .agg(
            detector_complete_days=("local_date", "nunique"),
            detector_daily_mean=("counter_positive_increments", "mean"),
            detector_daily_median=("counter_positive_increments", "median"),
        )
        .reset_index()
    )
    result = mtc_monthly.merge(detector, on="month", how="inner")
    result["indicative_multiplier"] = (
        result["official_westbound_daily_mean"] / result["detector_daily_mean"]
    )
    result["lighting_period"] = result["month"].map(
        lambda month: (
            "pre_lights"
            if month < pd.Timestamp("2026-02-01")
            else "mixed_or_illuminated"
        )
    )
    return result[result["month"] >= pd.Timestamp("2025-08-01")].copy()


def write_snapshot(
    output_dir: Path,
    tables: tuple[tuple[str, pd.DataFrame], ...],
    provenance: dict[str, object],
) -> None:
    if output_dir.exists():
        raise FileExistsError(
            f"Refusing to overwrite existing validation directory: {output_dir}"
        )
    output_dir.mkdir(parents=True)

    written: list[Path] = []
    for filename, table in tables:
        path = output_dir / filename
        table.to_csv(path, index=False, float_format="%.6f")
        written.append(path)

    provenance_path = output_dir / "provenance.json"
    provenance_path.write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    written.append(provenance_path)

    manifest = pd.DataFrame(
        [
            {
                "path": path.name,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in sorted(written)
        ]
    )
    manifest.to_csv(output_dir / "manifest.csv", index=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--detector-daily",
        type=Path,
        default=Path("site/src/data/archive-v2/daily.csv"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("site/src/data/validation-v1"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    daily = pd.read_csv(args.detector_daily)

    mtc_content = download(MTC_MONTHLY_URL)
    aadt_content = download(CALTRANS_AADT_URL)
    peak_content = download(CALTRANS_PEAK_URL)

    mtc_monthly = read_mtc_monthly(mtc_content)
    references, peak = read_caltrans_references(aadt_content, peak_content)
    direction_summary = build_direction_summary(daily, references)
    westbound_monthly = build_westbound_monthly_match(daily, mtc_monthly)

    peak_extract = peak[
        [
            "AM_DIR",
            "AM_WAY_PHV",
            "AM_HOUR",
            "AM_DAY",
            "AM_MONTH",
            "PM_DIR",
            "PM_WAY_PHV",
            "PM_HOUR",
            "PM_DAY",
            "PM_MONTH",
        ]
    ].copy()
    peak_extract.insert(0, "location", "I-80 Bay Bridge toll plaza")
    peak_extract.insert(1, "reference_year", 2024)

    write_snapshot(
        args.output_dir,
        (
            ("direction-summary.csv", direction_summary),
            ("westbound-monthly-match.csv", westbound_monthly),
            ("official-direction-reference.csv", references),
            ("official-peak-hour-reference.csv", peak_extract),
        ),
        {
            "purpose": "high-level third-party validation; not detector calibration",
            "detector_daily_source": str(args.detector_daily),
            "detector_baseline": "complete pre-lights days before 2026-02-19",
            "mtc_monthly_url": MTC_MONTHLY_URL,
            "caltrans_aadt_url": CALTRANS_AADT_URL,
            "caltrans_peak_hour_url": CALTRANS_PEAK_URL,
            "retrieved_utc": pd.Timestamp.now(tz="UTC").isoformat(),
            "non_destructive": True,
            "warning": (
                "Reference multipliers average over time and cannot correct "
                "hour-, weather-, congestion-, direction-, or lighting-dependent errors."
            ),
        },
    )

    print(f"Wrote immutable external validation snapshot: {args.output_dir}")
    for path in sorted(args.output_dir.iterdir()):
        print(f"{path.name}\t{path.stat().st_size} bytes")


if __name__ == "__main__":
    main()
