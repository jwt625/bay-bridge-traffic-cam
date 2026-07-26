from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.export_exact_tsdb import (
    parse_labels,
    parse_sample,
    timestamp_seconds_to_milliseconds,
)


class ExactTsdbExportTest(unittest.TestCase):
    def test_parse_labels_preserves_escaped_values(self):
        self.assertEqual(
            parse_labels(r'app="bridge",note="a,b\\nc",direction="left"'),
            {"app": "bridge", "note": "a,b\\nc", "direction": "left"},
        )

    def test_timestamp_preserves_milliseconds(self):
        self.assertEqual(
            timestamp_seconds_to_milliseconds("1784944802.483"),
            1_784_944_802_483,
        )

    def test_parse_sample_preserves_original_labels(self):
        row = parse_sample(
            'traffic_flow_rate_per_minute{app="bridge",direction="left",'
            'exported_job="imported_data"} 46.5 1784944802.483'
        )

        self.assertEqual(row["metric"], "traffic_flow_rate_per_minute")
        self.assertEqual(row["timestamp_utc"], 1_784_944_802_483)
        self.assertEqual(row["direction"], "left")
        self.assertEqual(row["source_series"], "imported")
        self.assertEqual(
            row["labels_json"],
            '{"app":"bridge","direction":"left","exported_job":"imported_data"}',
        )


if __name__ == "__main__":
    unittest.main()
