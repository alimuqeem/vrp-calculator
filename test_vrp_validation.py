import csv
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from validate_vrp import markdown_report
from vrp_scan import append_spy_snapshot, signal, term_structure_shape


class SnapshotTests(unittest.TestCase):
    def test_snapshot_writes_one_row_per_tenor(self):
        rows = [
            {"tenor": 7, "expiry": "2026-08-14", "dte": 6, "iv_pct": 12.0, "rv_pct": 10.0, "vrp": 2.0, "signal": "NEUTRAL"},
            {"tenor": 30, "expiry": "2026-09-05", "dte": 28, "iv_pct": 14.0, "rv_pct": 11.0, "vrp": 3.0, "signal": "NEUTRAL"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            history = Path(directory) / "history.csv"
            saved = append_spy_snapshot(
                history, "SPY", 645.0, rows, datetime(2026, 8, 8, tzinfo=timezone.utc)
            )
            with history.open() as history_file:
                written = list(csv.DictReader(history_file))

        self.assertEqual(saved, 2)
        self.assertEqual(len(written), 2)
        self.assertEqual(written[0]["curve_shape"], "contango")
        self.assertEqual(written[0]["observation_date"], "2026-08-08")

    def test_curve_shape_handles_flat_and_missing_data(self):
        self.assertEqual(term_structure_shape([]), "insufficient_data")
        self.assertEqual(term_structure_shape([{"iv_pct": 10.0}, {"iv_pct": 10.0}]), "flat")

    def test_screening_signals_cover_each_threshold_band(self):
        self.assertEqual(signal(10.01), "STRONG SELL")
        self.assertEqual(signal(10.0), "SELL")
        self.assertEqual(signal(5.0), "NEUTRAL")
        self.assertEqual(signal(-0.01), "AVOID")


class ReportTests(unittest.TestCase):
    def test_report_includes_key_statistics(self):
        results = pd.DataFrame([
            {"captured_at": "2026-01-01T00:00:00+00:00", "tenor_days": 7, "signal": "SELL", "curve_shape": "backwardation", "forward_rv_pct": 15.0, "realized_vrp_pct": 5.0, "vrp_pct": 4.0},
            {"captured_at": "2026-01-08T00:00:00+00:00", "tenor_days": 7, "signal": "NEUTRAL", "curve_shape": "contango", "forward_rv_pct": 12.0, "realized_vrp_pct": -1.0, "vrp_pct": 1.0},
        ])
        report = markdown_report(results, "history.csv")
        self.assertIn("Completed observations", report)
        self.assertIn("By signal", report)
        self.assertIn("Front-tenor outcome by curve shape", report)


if __name__ == "__main__":
    unittest.main()
