#!/usr/bin/env python3
"""Prepare versioned, coverage-aware datasets for the static archive site.

This script is intentionally non-destructive:

- It only reads Prometheus through the HTTP query API.
- It refuses to write into an existing output directory.
- It never modifies Prometheus, Grafana, Docker, or prior analysis artifacts.
- It writes a new versioned derived-data directory with checksums.

The output is a browser-sized analytical snapshot, not the lossless raw archive.
An exact raw export must be produced separately from an immutable TSDB copy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import requests

PACIFIC = "America/Los_Angeles"
DEFAULT_START = "2025-08-01T00:00:00Z"
DEFAULT_END = "2026-07-27T00:00:00Z"
STEP_SECONDS = 300
CHUNK_DAYS = 21
WEEKDAYS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]
LIGHTING_BURN_IN_DATE = date(2026, 2, 19)
LIGHTING_PUBLIC_LAUNCH_DATE = date(2026, 3, 20)
LIGHTING_PERIODS = ("pre_lights", "commissioning", "illuminated")


@dataclass(frozen=True)
class QuerySpec:
    name: str
    expression: str


QUERY_SPECS = (
    QuerySpec(
        "flow",
        'traffic_flow_rate_per_minute{exported_job=""}',
    ),
    QuerySpec(
        "counter",
        'traffic_vehicles_total{exported_job=""}',
    ),
    QuerySpec(
        "speed_15min",
        'traffic_speed_average_pixels_per_second{exported_job="",window="15min"}',
    ),
)


class PrometheusSnapshotReader:
    """Chunked read-only Prometheus range-query client."""

    def __init__(self, base_url: str, timeout_seconds: int = 120):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()

    def query_range(
        self,
        expression: str,
        start: pd.Timestamp,
        end: pd.Timestamp,
        step_seconds: int = STEP_SECONDS,
    ) -> pd.DataFrame:
        rows: list[dict[str, object]] = []
        cursor = start

        while cursor < end:
            chunk_end = min(cursor + pd.Timedelta(days=CHUNK_DAYS), end)
            response = self.session.get(
                f"{self.base_url}/api/v1/query_range",
                params={
                    "query": expression,
                    "start": cursor.isoformat(),
                    "end": chunk_end.isoformat(),
                    "step": f"{step_seconds}s",
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("status") != "success":
                raise RuntimeError(
                    f"Prometheus query failed for {expression}: {payload}"
                )

            for series in payload["data"]["result"]:
                labels = series["metric"]
                for timestamp, value in series["values"]:
                    rows.append(
                        {
                            "timestamp_utc": pd.to_datetime(
                                timestamp, unit="s", utc=True
                            ),
                            "value": float(value),
                            "direction": labels.get("direction", ""),
                            "window": labels.get("window", ""),
                        }
                    )

            cursor = chunk_end

        if not rows:
            raise RuntimeError(f"No samples returned for {expression}")

        return (
            pd.DataFrame(rows)
            .drop_duplicates(["timestamp_utc", "direction", "window"])
            .sort_values(["timestamp_utc", "direction", "window"])
            .reset_index(drop=True)
        )


def expected_samples_for_local_date(day: date, step_seconds: int) -> int:
    """Return timezone-aware expected samples for a Pacific calendar day."""
    start = pd.Timestamp(day).tz_localize(PACIFIC)
    end = (pd.Timestamp(day) + pd.Timedelta(days=1)).tz_localize(PACIFIC)
    return int((end.tz_convert("UTC") - start.tz_convert("UTC")).total_seconds()) // (
        step_seconds
    )


def add_local_time_columns(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    local = result["timestamp_utc"].dt.tz_convert(PACIFIC)
    result["timestamp_local"] = local
    result["local_date"] = local.dt.date
    result["weekday"] = local.dt.day_name()
    result["weekday_number"] = local.dt.dayofweek
    result["hour"] = local.dt.hour
    result["minute"] = local.dt.minute
    result["minute_of_day"] = result["hour"] * 60 + result["minute"]
    result["quarter_hour"] = (result["minute_of_day"] // 15) * 15
    return result


def lighting_period_for_date(day: date) -> str:
    """Classify a local date against the documented Bay Lights timeline."""
    if day < LIGHTING_BURN_IN_DATE:
        return "pre_lights"
    if day < LIGHTING_PUBLIC_LAUNCH_DATE:
        return "commissioning"
    return "illuminated"


def add_lighting_period(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["lighting_period"] = result["local_date"].map(lighting_period_for_date)
    return result


def build_hourly(flow: pd.DataFrame) -> pd.DataFrame:
    data = add_local_time_columns(flow)
    # Bucket in UTC so the repeated Pacific 01:00 hour at DST fallback remains
    # unambiguous. Converting a UTC hour back to Pacific preserves its offset.
    data["hour_utc"] = data["timestamp_utc"].dt.floor("h")
    hourly = (
        data.groupby(["hour_utc", "direction"], observed=True)["value"]
        .agg(mean_flow="mean", median_flow="median", max_flow="max", sample_count="size")
        .reset_index()
    )
    hourly["coverage"] = (hourly["sample_count"] / (3600 / STEP_SECONDS)).clip(
        upper=1
    )
    hourly["hour_local"] = hourly["hour_utc"].dt.tz_convert(PACIFIC)
    hourly["local_date"] = hourly["hour_local"].dt.date
    hourly["lighting_period"] = hourly["local_date"].map(lighting_period_for_date)
    hourly["estimated_detections"] = hourly["mean_flow"] * 60 * hourly["coverage"]
    return hourly[
        [
            "hour_utc",
            "hour_local",
            "lighting_period",
            "direction",
            "mean_flow",
            "median_flow",
            "max_flow",
            "estimated_detections",
            "sample_count",
            "coverage",
        ]
    ]


def build_half_hour(flow: pd.DataFrame) -> pd.DataFrame:
    """Aggregate five-minute flow samples into unambiguous 30-minute bins."""
    data = flow.copy()
    # Bucket in UTC so both occurrences of a repeated Pacific half-hour during
    # DST fallback remain distinct.
    data["half_hour_utc"] = data["timestamp_utc"].dt.floor("30min")
    result = (
        data.groupby(["half_hour_utc", "direction"], observed=True)["value"]
        .agg(mean_flow="mean", sample_count="size")
        .reset_index()
    )
    result["coverage"] = (
        result["sample_count"] / (30 * 60 / STEP_SECONDS)
    ).clip(upper=1)
    result["half_hour_local"] = result["half_hour_utc"].dt.tz_convert(PACIFIC)
    result["local_date"] = result["half_hour_local"].dt.date
    result["lighting_period"] = result["local_date"].map(
        lighting_period_for_date
    )
    return result[
        [
            "half_hour_utc",
            "half_hour_local",
            "lighting_period",
            "direction",
            "mean_flow",
            "sample_count",
            "coverage",
        ]
    ]


def build_daily(flow: pd.DataFrame, counter: pd.DataFrame) -> pd.DataFrame:
    flow_local = add_local_time_columns(flow)
    daily_flow = (
        flow_local.groupby(["local_date", "direction"], observed=True)["value"]
        .agg(mean_flow="mean", median_flow="median", max_flow="max", sample_count="size")
        .reset_index()
    )
    expected = {
        day: expected_samples_for_local_date(day, STEP_SECONDS)
        for day in daily_flow["local_date"].unique()
    }
    daily_flow["expected_samples"] = daily_flow["local_date"].map(expected)
    daily_flow["coverage"] = (
        daily_flow["sample_count"] / daily_flow["expected_samples"]
    ).clip(upper=1)
    daily_flow["flow_integral_detections"] = (
        daily_flow["mean_flow"]
        * (STEP_SECONDS / 60)
        * daily_flow["sample_count"]
    )

    counter_local = add_local_time_columns(counter)
    counter_local["delta"] = counter_local.groupby("direction", observed=True)[
        "value"
    ].diff()
    counter_local["positive_delta"] = counter_local["delta"].clip(lower=0)
    counter_local["reset"] = counter_local["delta"] < 0
    daily_counter = (
        counter_local.groupby(["local_date", "direction"], observed=True)
        .agg(
            counter_positive_increments=("positive_delta", "sum"),
            counter_resets=("reset", "sum"),
        )
        .reset_index()
    )

    daily = daily_flow.merge(
        daily_counter, on=["local_date", "direction"], how="left"
    )
    daily["weekday"] = pd.to_datetime(daily["local_date"]).dt.day_name()
    daily["complete_day"] = daily["coverage"] >= 0.95
    daily["lighting_period"] = daily["local_date"].map(lighting_period_for_date)
    return daily


def build_weekday_profile(flow: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    data = add_lighting_period(add_local_time_columns(flow))
    complete_keys = daily.loc[
        daily["complete_day"], ["local_date", "direction"]
    ].drop_duplicates()
    data = data.merge(complete_keys, on=["local_date", "direction"], how="inner")

    data = pd.concat(
        [data.assign(analysis_period="all"), data.assign(analysis_period=data["lighting_period"])],
        ignore_index=True,
    )
    profile = (
        data.groupby(
            [
                "analysis_period",
                "weekday",
                "weekday_number",
                "quarter_hour",
                "direction",
            ]
        )["value"]
        .agg(
            mean="mean",
            median="median",
            p10=lambda values: values.quantile(0.10),
            p25=lambda values: values.quantile(0.25),
            p75=lambda values: values.quantile(0.75),
            p90=lambda values: values.quantile(0.90),
            sample_count="size",
        )
        .reset_index()
        .sort_values(
            ["analysis_period", "weekday_number", "quarter_hour", "direction"]
        )
    )
    profile["time_label"] = profile["quarter_hour"].map(
        lambda minute: f"{minute // 60:02d}:{minute % 60:02d}"
    )
    return profile


def build_speed_profile(speed: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    data = add_lighting_period(add_local_time_columns(speed))
    complete_dates = set(
        daily.loc[daily["complete_day"], "local_date"].drop_duplicates()
    )
    data = data[data["local_date"].isin(complete_dates)]
    data = pd.concat(
        [data.assign(analysis_period="all"), data.assign(analysis_period=data["lighting_period"])],
        ignore_index=True,
    )
    return (
        data.groupby(
            [
                "analysis_period",
                "weekday",
                "weekday_number",
                "quarter_hour",
                "direction",
            ]
        )["value"]
        .agg(
            mean="mean",
            median="median",
            p25=lambda values: values.quantile(0.25),
            p75=lambda values: values.quantile(0.75),
            sample_count="size",
        )
        .reset_index()
        .sort_values(
            ["analysis_period", "weekday_number", "quarter_hour", "direction"]
        )
    )


def build_night_noise(flow: pd.DataFrame) -> pd.DataFrame:
    """Summarize the fixed 22:00–05:00 local window without interpolation."""
    data = add_local_time_columns(flow)
    data = data[data["hour"].isin([22, 23, 0, 1, 2, 3, 4])].copy()
    shifted = data["timestamp_local"] - pd.to_timedelta(
        (data["hour"] < 5).astype(int), unit="D"
    )
    data["night_date"] = shifted.dt.date

    grouped = (
        data.groupby(["night_date", "direction"], observed=True)["value"]
        .agg(
            mean_flow="mean",
            median_flow="median",
            std_flow="std",
            p95_flow=lambda values: values.quantile(0.95),
            max_flow="max",
            median_abs_change=lambda values: values.diff().abs().median(),
            sample_count="size",
        )
        .reset_index()
    )
    grouped["spike_excess"] = grouped["p95_flow"] - grouped["median_flow"]
    grouped["coverage"] = (grouped["sample_count"] / (7 * 3600 / STEP_SECONDS)).clip(
        upper=1
    )
    grouped["lighting_period"] = grouped["night_date"].map(
        lighting_period_for_date
    )
    return grouped


def build_lighting_impact_summary(night_noise: pd.DataFrame) -> pd.DataFrame:
    complete = night_noise[night_noise["coverage"] >= 0.95]
    return (
        complete.groupby(["lighting_period", "direction"], observed=True)
        .agg(
            nights=("night_date", "nunique"),
            median_night_mean=("mean_flow", "median"),
            median_night_std=("std_flow", "median"),
            median_night_p95=("p95_flow", "median"),
            median_night_max=("max_flow", "median"),
            median_spike_excess=("spike_excess", "median"),
            median_abs_change=("median_abs_change", "median"),
        )
        .reset_index()
    )


def build_lighting_events() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "local_date": LIGHTING_BURN_IN_DATE,
                "event": "Documented 48,000-LED burn-in begins (approximate)",
                "event_type": "external",
                "note": (
                    "A February 26 report said all LEDs had been twinkling 24/7 "
                    "for about one week; February 19 is used as the analysis boundary."
                ),
                "source_url": (
                    "https://www.sfchronicle.com/sf/article/"
                    "bay-lights-return-bay-bridge-21944006.php/"
                ),
            },
            {
                "local_date": date(2026, 3, 8),
                "event": "Detector-observed high-noise onset",
                "event_type": "derived",
                "note": (
                    "Nighttime flow spikes rise sharply during commissioning; "
                    "this is a dataset observation, not an independently reported switch."
                ),
                "source_url": "",
            },
            {
                "local_date": LIGHTING_PUBLIC_LAUNCH_DATE,
                "event": "Official public Grand Lighting",
                "event_type": "external",
                "note": (
                    "The primary north-facing installation entered nightly operation "
                    "from dusk until dawn."
                ),
                "source_url": (
                    "https://illuminate.org/2026/02/19/"
                    "the-bay-lights-to-return-friday-march-20-2026/"
                ),
            },
        ]
    )


def build_monthly(daily: pd.DataFrame) -> pd.DataFrame:
    result = daily.copy()
    result["month"] = pd.to_datetime(result["local_date"]).dt.to_period("M").astype(str)
    return (
        result.groupby(["month", "direction"], observed=True)
        .agg(
            mean_flow=("mean_flow", "mean"),
            median_daily_detections=("flow_integral_detections", "median"),
            total_counter_increments=("counter_positive_increments", "sum"),
            mean_coverage=("coverage", "mean"),
            complete_days=("complete_day", "sum"),
            observed_days=("local_date", "nunique"),
        )
        .reset_index()
    )


def build_coverage_intervals(flow: pd.DataFrame) -> pd.DataFrame:
    timestamps = (
        flow.loc[flow["direction"] == "left", "timestamp_utc"]
        .drop_duplicates()
        .sort_values()
        .reset_index(drop=True)
    )
    delta = timestamps.diff()
    gaps = []
    for index in delta[delta > pd.Timedelta(minutes=10)].index:
        previous = timestamps.iloc[index - 1]
        current = timestamps.iloc[index]
        gaps.append(
            {
                "last_sample_utc": previous,
                "next_sample_utc": current,
                "last_sample_local": previous.tz_convert(PACIFIC),
                "next_sample_local": current.tz_convert(PACIFIC),
                "duration_minutes": delta.iloc[index].total_seconds() / 60,
            }
        )
    return pd.DataFrame(gaps)


def build_reset_events(counter: pd.DataFrame) -> pd.DataFrame:
    data = add_local_time_columns(counter)
    data["delta"] = data.groupby("direction", observed=True)["value"].diff()
    return data.loc[
        data["delta"] < 0,
        ["timestamp_utc", "timestamp_local", "direction", "value", "delta"],
    ].reset_index(drop=True)


def build_summary(
    flow: pd.DataFrame,
    counter: pd.DataFrame,
    daily: pd.DataFrame,
    coverage: pd.DataFrame,
) -> pd.DataFrame:
    start = flow["timestamp_utc"].min()
    end = flow["timestamp_utc"].max()
    span_days = (end - start).total_seconds() / 86400
    direct_samples = len(flow) + len(counter)
    positive_increments = (
        counter.sort_values("timestamp_utc")
        .groupby("direction", observed=True)["value"]
        .diff()
        .clip(lower=0)
        .sum()
    )
    direction_means = flow.groupby("direction", observed=True)["value"].mean()
    complete_dates = daily.groupby("local_date")["complete_day"].all()

    values = {
        "collection_start_utc": start.isoformat(),
        "collection_end_utc": end.isoformat(),
        "collection_start_local": start.tz_convert(PACIFIC).isoformat(),
        "collection_end_local": end.tz_convert(PACIFIC).isoformat(),
        "observed_span_days": round(span_days, 2),
        "flow_samples_5min": len(flow),
        "counter_samples_5min": len(counter),
        "queried_samples_5min": direct_samples,
        "complete_calendar_days": int(complete_dates.sum()),
        "observed_calendar_days": int(len(complete_dates)),
        "coverage_gaps_over_10min": len(coverage),
        "positive_counter_increments_5min": int(positive_increments),
        "left_mean_flow": round(float(direction_means.get("left", math.nan)), 2),
        "right_mean_flow": round(float(direction_means.get("right", math.nan)), 2),
        "lighting_burn_in_boundary": LIGHTING_BURN_IN_DATE.isoformat(),
        "lighting_public_launch": LIGHTING_PUBLIC_LAUNCH_DATE.isoformat(),
        "source_resolution": "5-minute Prometheus query-range snapshot",
        "raw_archive_status": "pending immutable TSDB copy",
        "data_interpretation": "algorithmic crossing detections; not ground truth",
    }
    return pd.DataFrame(
        [{"key": key, "value": value} for key, value in values.items()]
    )


def format_for_csv(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in result.columns:
        if isinstance(result[column].dtype, pd.DatetimeTZDtype):
            result[column] = result[column].map(lambda value: value.isoformat())
    return result


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_snapshot(
    output_dir: Path,
    tables: Iterable[tuple[str, pd.DataFrame]],
    provenance: dict[str, object],
) -> None:
    if output_dir.exists():
        raise FileExistsError(
            f"Refusing to overwrite existing snapshot directory: {output_dir}"
        )
    output_dir.mkdir(parents=True)

    written: list[Path] = []
    for filename, table in tables:
        path = output_dir / filename
        format_for_csv(table).to_csv(path, index=False, float_format="%.6f")
        written.append(path)

    provenance_path = output_dir / "provenance.json"
    provenance_path.write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    written.append(provenance_path)

    manifest_rows = [
        {
            "path": path.name,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(written)
    ]
    pd.DataFrame(manifest_rows).to_csv(output_dir / "manifest.csv", index=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prometheus-url",
        default="http://localhost:9090",
        help="Read-only Prometheus base URL",
    )
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=DEFAULT_END)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("site/src/data/archive-v1"),
        help="New versioned output directory; must not already exist",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    start = pd.Timestamp(args.start)
    end = pd.Timestamp(args.end)
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("--start and --end must include a timezone")

    reader = PrometheusSnapshotReader(args.prometheus_url)
    queried = {
        spec.name: reader.query_range(spec.expression, start, end)
        for spec in QUERY_SPECS
    }

    flow = queried["flow"]
    counter = queried["counter"]
    speed = queried["speed_15min"]

    hourly = build_hourly(flow)
    half_hour = build_half_hour(flow)
    daily = build_daily(flow, counter)
    weekday = build_weekday_profile(flow, daily)
    speed_profile = build_speed_profile(speed, daily)
    night_noise = build_night_noise(flow)
    lighting_impact = build_lighting_impact_summary(night_noise)
    lighting_events = build_lighting_events()
    monthly = build_monthly(daily)
    coverage = build_coverage_intervals(flow)
    resets = build_reset_events(counter)
    summary = build_summary(flow, counter, daily, coverage)

    provenance = {
        "purpose": "browser-sized derived snapshot for the static archive site",
        "source": args.prometheus_url,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "step_seconds": STEP_SECONDS,
        "timezone": PACIFIC,
        "queries": {spec.name: spec.expression for spec in QUERY_SPECS},
        "non_destructive": True,
        "raw_archive": False,
        "lighting_periods": {
            "pre_lights": f"before {LIGHTING_BURN_IN_DATE.isoformat()}",
            "commissioning": (
                f"{LIGHTING_BURN_IN_DATE.isoformat()} through "
                f"{(LIGHTING_PUBLIC_LAUNCH_DATE - pd.Timedelta(days=1)).isoformat()}"
            ),
            "illuminated": f"on or after {LIGHTING_PUBLIC_LAUNCH_DATE.isoformat()}",
        },
        "warning": (
            "This is a query-range analytical snapshot, not the lossless exact-sample "
            "Prometheus archive."
        ),
    }

    write_snapshot(
        args.output_dir,
        (
            ("summary.csv", summary),
            ("hourly.csv", hourly),
            ("half-hour.csv", half_hour),
            ("daily.csv", daily),
            ("weekday-profile.csv", weekday),
            ("speed-profile.csv", speed_profile),
            ("night-noise.csv", night_noise),
            ("lighting-impact-summary.csv", lighting_impact),
            ("lighting-events.csv", lighting_events),
            ("monthly.csv", monthly),
            ("coverage-gaps.csv", coverage),
            ("counter-resets.csv", resets),
        ),
        provenance,
    )

    print(f"Wrote immutable derived snapshot: {args.output_dir}")
    for path in sorted(args.output_dir.iterdir()):
        print(f"{path.name}\t{path.stat().st_size} bytes")


if __name__ == "__main__":
    main()
