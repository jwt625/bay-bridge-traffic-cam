from pathlib import Path
import sys
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.prepare_external_validation import (
    build_direction_summary,
    build_westbound_monthly_match,
)


class ExternalValidationTest(unittest.TestCase):
    def test_direction_summary_keeps_separate_reference_ratios(self):
        daily = pd.DataFrame(
            {
                "local_date": ["2026-01-01"] * 2,
                "complete_day": [True, True],
                "direction": ["left", "right"],
                "counter_positive_increments": [50_000, 100_000],
            }
        )
        references = pd.DataFrame(
            {
                "direction": ["left", "right"],
                "official_reference_daily": [100_000, 120_000],
            }
        )

        result = build_direction_summary(daily, references).set_index("direction")

        self.assertAlmostEqual(
            result.loc["left", "indicative_multiplier_mean"],
            2.0,
        )
        self.assertAlmostEqual(
            result.loc["right", "indicative_multiplier_mean"],
            1.2,
        )
        self.assertAlmostEqual(
            result.loc["left", "detector_direction_share"],
            1 / 3,
        )

    def test_monthly_match_uses_only_complete_right_direction_days(self):
        daily = pd.DataFrame(
            {
                "local_date": [
                    "2026-01-01",
                    "2026-01-01",
                    "2026-01-02",
                    "2026-01-03",
                ],
                "complete_day": [True, True, False, True],
                "direction": ["right", "left", "right", "right"],
                "counter_positive_increments": [80, 500, 9_999, 120],
            }
        )
        mtc = pd.DataFrame(
            {
                "month": [pd.Timestamp("2026-01-01")],
                "official_westbound_crossings": [3_100],
                "days_in_month": [31],
                "official_westbound_daily_mean": [100],
            }
        )

        result = build_westbound_monthly_match(daily, mtc)

        self.assertEqual(result.loc[0, "detector_complete_days"], 2)
        self.assertEqual(result.loc[0, "detector_daily_mean"], 100)
        self.assertEqual(result.loc[0, "indicative_multiplier"], 1)


if __name__ == "__main__":
    unittest.main()
