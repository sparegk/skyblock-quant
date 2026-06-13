from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.collectors import scheduler


class SchedulerTests(unittest.TestCase):
    def test_parse_horizons_splits_and_trims_values(self) -> None:
        self.assertEqual(
            ("next_snapshot", "1h", "24h"),
            scheduler.parse_horizons("next_snapshot, 1h,24h"),
        )

    def test_parse_horizons_rejects_empty_values(self) -> None:
        with self.assertRaises(ValueError):
            scheduler.parse_horizons(" , ")

    def test_run_analysis_cycle_generates_signals_and_backtests(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"

            with (
                patch.object(scheduler.database, "initialize_analysis_tables") as initialize,
                patch.object(
                    scheduler.database,
                    "generate_rule_based_signals",
                    return_value=[{"item_id": "TEST"}],
                ) as generate,
                patch.object(
                    scheduler.database,
                    "evaluate_signal_backtests",
                    side_effect=[2, 0],
                ) as evaluate,
            ):
                result = scheduler.run_analysis_cycle(db_path, ("next_snapshot", "1h"))

        self.assertEqual({"signals": 1, "evaluated": {"next_snapshot": 2, "1h": 0}}, result)
        self.assertEqual(db_path, scheduler.database.DATABASE_PATH)
        initialize.assert_called_once_with()
        generate.assert_called_once_with()
        self.assertEqual(2, evaluate.call_count)
        evaluate.assert_any_call(horizon="next_snapshot")
        evaluate.assert_any_call(horizon="1h")

    def test_scheduler_runs_collector_and_analysis_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"
            raw_dir = Path(temp_dir) / "raw"

            with (
                patch.object(scheduler, "collect_bazaar_snapshot", return_value=1933) as collect,
                patch.object(
                    scheduler,
                    "run_analysis_cycle",
                    return_value={"signals": 1, "evaluated": {"next_snapshot": 0}},
                ) as analysis,
                patch.object(scheduler.database, "start_job_run", return_value=42) as start_job,
                patch.object(scheduler.database, "finish_job_run") as finish_job,
            ):
                scheduler.run_bazaar_scheduler(
                    db_path,
                    raw_dir,
                    interval_minutes=5,
                    max_runs=1,
                    backtest_horizons=("next_snapshot",),
                )

        collect.assert_called_once_with(db_path, raw_dir)
        analysis.assert_called_once_with(db_path, ("next_snapshot",))
        start_job.assert_called_once_with("market_cycle")
        finish_job.assert_called_once_with(
            42,
            "success",
            "Collector and analysis completed.",
            products_collected=1933,
            signals_generated=1,
            backtests_evaluated={"next_snapshot": 0},
        )

    def test_scheduler_records_partial_run_when_analysis_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"
            raw_dir = Path(temp_dir) / "raw"

            with (
                patch.object(scheduler, "collect_bazaar_snapshot", return_value=1933),
                patch.object(
                    scheduler,
                    "run_analysis_cycle",
                    side_effect=RuntimeError("analysis error"),
                ),
                patch.object(scheduler.database, "start_job_run", return_value=42),
                patch.object(scheduler.database, "finish_job_run") as finish_job,
            ):
                scheduler.run_bazaar_scheduler(
                    db_path,
                    raw_dir,
                    interval_minutes=5,
                    max_runs=1,
                    backtest_horizons=("next_snapshot",),
                )

        finish_job.assert_called_once_with(
            42,
            "partial",
            "Collector completed, analysis failed: analysis error",
            products_collected=1933,
        )

    def test_scheduler_records_failed_run_when_collection_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"
            raw_dir = Path(temp_dir) / "raw"

            with (
                patch.object(
                    scheduler,
                    "collect_bazaar_snapshot",
                    side_effect=RuntimeError("collector error"),
                ),
                patch.object(scheduler.database, "start_job_run", return_value=42),
                patch.object(scheduler.database, "finish_job_run") as finish_job,
            ):
                scheduler.run_bazaar_scheduler(
                    db_path,
                    raw_dir,
                    interval_minutes=5,
                    max_runs=1,
                )

        finish_job.assert_called_once_with(
            42,
            "failed",
            "Collector failed: collector error",
            products_collected=None,
        )


if __name__ == "__main__":
    unittest.main()
