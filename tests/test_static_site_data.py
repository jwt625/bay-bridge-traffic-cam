from datetime import date
from pathlib import Path
import sys
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.prepare_static_site_data import (
    PACIFIC,
    STEP_SECONDS,
    build_half_hour,
    build_night_noise,
    build_reset_events,
    expected_samples_for_local_date,
    lighting_period_for_date,
)


class StaticSiteDataTest(unittest.TestCase):
    def test_half_hour_aggregation_uses_six_five_minute_samples(self):
        frame = pd.DataFrame(
            {
                "timestamp_utc": pd.date_range(
                    "2026-01-01T00:00:00Z",
                    periods=12,
                    freq="5min",
                ),
                "direction": ["left"] * 12,
                "window": [""] * 12,
                "value": list(range(12)),
            }
        )

        result = build_half_hour(frame)

        self.assertEqual(len(result), 2)
        self.assertEqual(result["sample_count"].tolist(), [6, 6])
        self.assertEqual(result["coverage"].tolist(), [1.0, 1.0])
        self.assertEqual(result["mean_flow"].tolist(), [2.5, 8.5])

    def test_expected_samples_accounts_for_dst_days(self):
        self.assertEqual(
            expected_samples_for_local_date(date(2025, 11, 2), STEP_SECONDS),
            300,
        )
        self.assertEqual(
            expected_samples_for_local_date(date(2026, 3, 8), STEP_SECONDS),
            276,
        )
        self.assertEqual(
            expected_samples_for_local_date(date(2026, 1, 15), STEP_SECONDS),
            288,
        )

    def test_reset_events_are_direction_specific(self):
        timestamps = pd.to_datetime(
            [
                "2025-08-09T21:00:00Z",
                "2025-08-09T21:05:00Z",
                "2025-08-09T21:10:00Z",
            ],
            utc=True,
        )
        frame = pd.DataFrame(
            {
                "timestamp_utc": list(timestamps) * 2,
                "direction": ["left"] * 3 + ["right"] * 3,
                "window": [""] * 6,
                "value": [100, 110, 5, 200, 220, 7],
            }
        ).sort_values(["timestamp_utc", "direction"])

        resets = build_reset_events(frame)

        self.assertEqual(set(resets["direction"]), {"left", "right"})
        self.assertEqual(
            resets.set_index("direction").loc["left", "delta"],
            -105,
        )
        self.assertEqual(
            resets.set_index("direction").loc["right", "delta"],
            -213,
        )
        self.assertEqual(str(resets["timestamp_local"].dt.tz), PACIFIC)

    def test_lighting_period_boundaries(self):
        self.assertEqual(
            lighting_period_for_date(date(2026, 2, 18)),
            "pre_lights",
        )
        self.assertEqual(
            lighting_period_for_date(date(2026, 2, 19)),
            "commissioning",
        )
        self.assertEqual(
            lighting_period_for_date(date(2026, 3, 19)),
            "commissioning",
        )
        self.assertEqual(
            lighting_period_for_date(date(2026, 3, 20)),
            "illuminated",
        )

    def test_night_window_assigns_after_midnight_to_previous_date(self):
        timestamps = pd.to_datetime(
            [
                "2026-03-20T06:00:00Z",  # Mar 19 23:00 PDT
                "2026-03-20T08:00:00Z",  # Mar 20 01:00 PDT
            ],
            utc=True,
        )
        frame = pd.DataFrame(
            {
                "timestamp_utc": timestamps,
                "direction": ["left", "left"],
                "window": ["", ""],
                "value": [10.0, 20.0],
            }
        )

        result = build_night_noise(frame)

        self.assertEqual(len(result), 1)
        self.assertEqual(str(result.loc[0, "night_date"]), "2026-03-19")
        self.assertEqual(result.loc[0, "lighting_period"], "commissioning")


if __name__ == "__main__":
    unittest.main()
