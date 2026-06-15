from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app import main


class ApiRouteTests(unittest.TestCase):
    def test_get_cors_origins_reads_env_values(self) -> None:
        with patch.dict(
            "os.environ",
            {"SKYBLOCK_QUANT_CORS_ORIGINS": "https://app.example.com, http://localhost:5173"},
        ):
            self.assertEqual(
                ["https://app.example.com", "http://localhost:5173"],
                main.get_cors_origins(),
            )

    def test_startup_refresh_backtests_can_be_disabled(self) -> None:
        with (
            patch.dict(
                "os.environ",
                {"SKYBLOCK_QUANT_REFRESH_BACKTESTS_ON_STARTUP": "false"},
            ),
            patch("app.main.refresh_backtests_on_startup") as refresh,
        ):
            main.startup_refresh_backtests()

        refresh.assert_not_called()

    def test_npc_arbitrage_passes_filter_query_params(self) -> None:
        with patch("app.main.get_npc_arbitrage", return_value=[]) as get_npc_arbitrage:
            response = main.npc_arbitrage(
                limit=7,
                min_sell_volume=20_000,
                min_sell_orders=40,
                max_profit_margin=0.2,
                history_snapshots=3,
                min_profitable_snapshots=2,
            )

        self.assertEqual({"items": []}, response)
        get_npc_arbitrage.assert_called_once_with(
            limit=7,
            min_sell_volume=20_000,
            min_sell_orders=40,
            max_profit_margin=0.2,
            history_snapshots=3,
            min_profitable_snapshots=2,
        )

    def test_npc_arbitrage_detail_returns_item(self) -> None:
        expected_item = {"item_id": "TEST_ITEM", "history": []}

        with patch("app.main.get_npc_arbitrage_detail", return_value=expected_item) as detail:
            response = main.npc_arbitrage_detail("test_item", history_snapshots=4)

        self.assertEqual({"item": expected_item}, response)
        detail.assert_called_once_with("test_item", 4)

    def test_npc_arbitrage_detail_raises_404_for_missing_item(self) -> None:
        with patch("app.main.get_npc_arbitrage_detail", return_value=None):
            with self.assertRaises(HTTPException) as error:
                main.npc_arbitrage_detail("missing")

        self.assertEqual(404, error.exception.status_code)

    def test_investment_momentum_passes_filter_query_params(self) -> None:
        with patch("app.main.get_investment_momentum", return_value=[]) as momentum:
            response = main.investment_momentum(
                limit=6,
                history_snapshots=4,
                min_observed_snapshots=3,
                min_volume=25_000,
                min_orders=50,
                min_gain=0.04,
                max_single_jump=0.25,
                min_rising_steps=2,
                min_unit_price=500,
                min_stack_size=64,
                min_slot_value=50_000,
            )

        self.assertEqual({"items": []}, response)
        momentum.assert_called_once_with(
            limit=6,
            history_snapshots=4,
            min_observed_snapshots=3,
            min_volume=25_000,
            min_orders=50,
            min_gain=0.04,
            max_single_jump=0.25,
            min_rising_steps=2,
            min_unit_price=500,
            min_stack_size=64,
            min_slot_value=50_000,
        )

    def test_occurrence_investments_passes_limit(self) -> None:
        with patch("app.main.get_occurrence_investments", return_value=[]) as occurrences:
            response = main.occurrence_investments(limit=4)

        self.assertEqual({"items": []}, response)
        occurrences.assert_called_once_with(limit=4)

    def test_latest_signals_passes_query_params(self) -> None:
        with patch("app.main.get_latest_signals", return_value=[]) as latest_signals:
            response = main.latest_signals(limit=8, refresh=False)

        self.assertEqual({"signals": []}, response)
        latest_signals.assert_called_once_with(limit=8, refresh=False)

    def test_evaluate_backtests_passes_limit(self) -> None:
        with patch("app.main.evaluate_signal_backtests", return_value=3) as evaluate:
            response = main.evaluate_backtests(limit=12, horizon="1h")

        self.assertEqual(
            {"evaluated": 3, "horizon": "1h", "refreshed_existing": True},
            response,
        )
        evaluate.assert_called_once_with(
            limit=12,
            horizon="1h",
            refresh_existing=True,
        )

    def test_evaluate_backtests_raises_400_for_bad_horizon(self) -> None:
        with patch(
            "app.main.evaluate_signal_backtests",
            side_effect=ValueError("Unsupported backtest horizon"),
        ):
            with self.assertRaises(HTTPException) as error:
                main.evaluate_backtests(limit=12, horizon="3h")

        self.assertEqual(400, error.exception.status_code)

    def test_evaluate_all_backtests_refreshes_every_horizon(self) -> None:
        with patch("app.main.evaluate_signal_backtests", return_value=2) as evaluate:
            response = main.evaluate_all_backtests(limit=12)

        self.assertEqual(
            {
                "evaluated": {
                    horizon: 2
                    for horizon in main.BACKTEST_HORIZONS
                },
                "total_evaluated": 2 * len(main.BACKTEST_HORIZONS),
                "refreshed_existing": True,
            },
            response,
        )
        self.assertEqual(len(main.BACKTEST_HORIZONS), evaluate.call_count)
        evaluate.assert_any_call(
            limit=12,
            horizon="next_snapshot",
            refresh_existing=True,
        )

    def test_backtest_summary_returns_metrics(self) -> None:
        expected_summary = {"total_results": 4, "win_rate": 0.75}

        with patch("app.main.get_backtest_summary", return_value=expected_summary) as summary:
            response = main.backtest_summary()

        self.assertEqual(expected_summary, response)
        summary.assert_called_once_with()

    def test_backtest_results_passes_limit(self) -> None:
        expected_results = [{"item_id": "TEST_ITEM"}]

        with patch("app.main.get_backtest_results", return_value=expected_results) as results:
            response = main.backtest_results(limit=9)

        self.assertEqual({"results": expected_results}, response)
        results.assert_called_once_with(limit=9)

    def test_latest_jobs_passes_limit(self) -> None:
        expected_jobs = [{"job_type": "market_cycle"}]

        with patch("app.main.get_latest_job_runs", return_value=expected_jobs) as jobs:
            response = main.latest_jobs(limit=6)

        self.assertEqual({"jobs": expected_jobs}, response)
        jobs.assert_called_once_with(limit=6)


if __name__ == "__main__":
    unittest.main()
