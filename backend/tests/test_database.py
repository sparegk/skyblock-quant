from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from app import database
from app.settings import DatabaseConfig


class NpcArbitrageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_database_path = database.DATABASE_PATH
        self.original_occurrence_investments_path = database.OCCURRENCE_INVESTMENTS_PATH
        database.DATABASE_PATH = Path(self.temp_dir.name) / "test.db"
        database.OCCURRENCE_INVESTMENTS_PATH = (
            Path(self.temp_dir.name) / "occurrence_investments.json"
        )
        self._create_test_database(database.DATABASE_PATH)

    def tearDown(self) -> None:
        database.DATABASE_PATH = self.original_database_path
        database.OCCURRENCE_INVESTMENTS_PATH = self.original_occurrence_investments_path
        self.temp_dir.cleanup()

    def test_filters_and_sorts_npc_arbitrage_candidates(self) -> None:
        rows = database.get_npc_arbitrage(limit=10)
        item_ids = [row["item_id"] for row in rows]

        self.assertEqual(["BOBBIN_SCRIPTURES", "HIGH_ESTIMATED", "LOW_MARGIN"], item_ids)
        self.assertNotIn("LOW_VOLUME", item_ids)
        self.assertNotIn("LOW_ORDERS", item_ids)
        self.assertNotIn("HIGH_MARGIN_OUTLIER", item_ids)
        self.assertNotIn("ONE_SNAPSHOT_SPIKE", item_ids)

    def test_uses_sell_price_as_bazaar_buy_cost(self) -> None:
        rows = database.get_npc_arbitrage(limit=10)
        high_estimated = self._find_item(rows, "HIGH_ESTIMATED")

        self.assertEqual(90.0, high_estimated["bazaar_buy_price"])
        self.assertEqual(100.0, high_estimated["bazaar_sell_price"])
        self.assertEqual(10.0, high_estimated["profit_per_item"])
        self.assertEqual(64, high_estimated["estimated_stack_size"])
        self.assertEqual(640.0, high_estimated["profit_per_sell_action"])
        self.assertIn("action_adjusted_profit", high_estimated)

    def test_returns_history_fields_for_stable_candidates(self) -> None:
        rows = database.get_npc_arbitrage(limit=10)
        high_estimated = self._find_item(rows, "HIGH_ESTIMATED")

        self.assertEqual(3, high_estimated["observed_snapshots"])
        self.assertEqual(3, high_estimated["profitable_snapshots"])
        self.assertEqual(1.0, high_estimated["profit_consistency"])
        self.assertEqual(
            high_estimated["estimated_profit"],
            high_estimated["history_adjusted_profit"],
        )
        self.assertEqual("stable", high_estimated["risk_label"])
        self.assertLess(high_estimated["risk_score"], 0.3)
        self.assertIn("risk_reasons", high_estimated)
        self.assertIn("max_recent_price_jump", high_estimated)
        self.assertIn("spread_percent", high_estimated)
        self.assertIn("interaction_efficiency_score", high_estimated)
        self.assertIn("sell_depth_score", high_estimated)
        self.assertIn("volume_balance_score", high_estimated)
        self.assertIn("order_balance_score", high_estimated)
        self.assertIn("risk_adjusted_profit", high_estimated)
        self.assertGreater(high_estimated["sell_depth_score"], 0.3)
        self.assertLess(
            high_estimated["risk_adjusted_profit"],
            high_estimated["action_adjusted_profit"],
        )

    def test_allows_custom_filter_thresholds(self) -> None:
        rows = database.get_npc_arbitrage(
            limit=10,
            min_sell_volume=100,
            min_sell_orders=1,
            max_profit_margin=10,
            min_profitable_snapshots=1,
        )
        item_ids = [row["item_id"] for row in rows]

        self.assertIn("LOW_VOLUME", item_ids)
        self.assertIn("LOW_ORDERS", item_ids)
        self.assertIn("HIGH_MARGIN_OUTLIER", item_ids)

        low_volume = self._find_item(rows, "LOW_VOLUME")
        low_orders = self._find_item(rows, "LOW_ORDERS")
        high_margin = self._find_item(rows, "HIGH_MARGIN_OUTLIER")

        self.assertEqual("thin liquidity", low_volume["risk_label"])
        self.assertEqual("thin liquidity", low_orders["risk_label"])
        self.assertEqual("possible manipulation", high_margin["risk_label"])
        self.assertGreater(low_volume["risk_score"], 0.3)
        self.assertGreater(high_margin["risk_score"], 0.3)
        self.assertIn("profit per sell action is low", low_volume["risk_reasons"])
        self.assertIn("profit margin is unusually wide", high_margin["risk_reasons"])
        self.assertIn("profit margin is extreme for an NPC exit", high_margin["risk_reasons"])

    def test_npc_risk_flags_fragile_order_books(self) -> None:
        item = database.add_npc_arbitrage_risk_fields(
            database.add_npc_interaction_fields(
                {
                    "profit_per_item": 400,
                    "profit_margin": 0.08,
                    "profit_consistency": 1.0,
                    "buy_volume": 200_000,
                    "sell_volume": 25_000,
                    "buy_orders": 250,
                    "sell_orders": 60,
                    "average_sell_volume": 80_000,
                    "average_sell_orders": 160,
                    "min_sell_volume": 20_000,
                    "min_sell_orders": 50,
                    "max_recent_price_jump": 0.05,
                    "spread_percent": 0.04,
                    "history_adjusted_profit": 1_000_000,
                }
            )
        )

        self.assertEqual("fragile book", item["risk_label"])
        self.assertGreater(item["risk_score"], 0.25)
        self.assertIn("buy and sell volume are badly imbalanced", item["risk_reasons"])
        self.assertIn("recent sell-side depth has been inconsistent", item["risk_reasons"])

    def test_npc_risk_flags_latest_profit_spikes(self) -> None:
        item = database.add_npc_arbitrage_risk_fields(
            database.add_npc_interaction_fields(
                {
                    "profit_per_item": 220,
                    "average_profit_per_item": 100,
                    "profit_margin": 0.12,
                    "profit_consistency": 1.0,
                    "buy_volume": 80_000,
                    "sell_volume": 80_000,
                    "buy_orders": 120,
                    "sell_orders": 120,
                    "average_sell_volume": 80_000,
                    "average_sell_orders": 120,
                    "min_sell_volume": 75_000,
                    "min_sell_orders": 110,
                    "max_recent_price_jump": 0.05,
                    "spread_percent": 0.04,
                    "history_adjusted_profit": 1_000_000,
                }
            )
        )

        self.assertEqual("possible manipulation", item["risk_label"])
        self.assertIn("latest profit is much higher than recent average", item["risk_reasons"])
        self.assertGreaterEqual(item["profit_spike_ratio"], 2.0)

    def test_returns_empty_without_items_table(self) -> None:
        database.DATABASE_PATH = Path(self.temp_dir.name) / "missing_items.db"
        with closing(sqlite3.connect(database.DATABASE_PATH)) as connection:
            connection.execute(
                """
                CREATE TABLE bazaar_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    collected_at TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    buy_price REAL NOT NULL,
                    sell_price REAL NOT NULL,
                    buy_volume INTEGER NOT NULL,
                    sell_volume INTEGER NOT NULL,
                    buy_orders INTEGER NOT NULL,
                    sell_orders INTEGER NOT NULL,
                    spread REAL NOT NULL
                )
                """
            )

        self.assertEqual([], database.get_npc_arbitrage())

    def test_returns_npc_arbitrage_detail_history(self) -> None:
        item = database.get_npc_arbitrage_detail("high_estimated", history_snapshots=2)

        self.assertIsNotNone(item)
        assert item is not None
        self.assertEqual("HIGH_ESTIMATED", item["item_id"])
        self.assertEqual(2, item["observed_snapshots"])
        self.assertEqual(2, item["profitable_snapshots"])
        self.assertEqual(1.0, item["profit_consistency"])
        self.assertEqual(2, len(item["history"]))
        self.assertEqual("2026-06-12T14:00:00Z", item["latest"]["collected_at"])
        self.assertEqual(90.0, item["latest"]["bazaar_buy_price"])
        self.assertEqual("stable", item["risk_label"])
        self.assertIn("risk_reasons", item)

    def test_returns_none_for_missing_npc_arbitrage_detail(self) -> None:
        self.assertIsNone(database.get_npc_arbitrage_detail("missing"))

    def test_returns_steady_investment_momentum(self) -> None:
        rows = database.get_investment_momentum(
            limit=10,
            history_snapshots=3,
            min_volume=10_000,
            min_orders=25,
            min_gain=0.03,
            max_single_jump=0.35,
            min_rising_steps=2,
        )
        item_ids = [row["item_id"] for row in rows]

        self.assertIn("STEADY_RISE", item_ids)
        self.assertIn("RAREFINDER_GARDEN_CHIP", item_ids)
        self.assertNotIn("ONE_PUMP", item_ids)
        self.assertNotIn("LOW_VOLUME_INVEST", item_ids)

        steady_rise = self._find_item(rows, "STEADY_RISE")
        rarefinder = self._find_item(rows, "RAREFINDER_GARDEN_CHIP")
        self.assertEqual(3, steady_rise["observed_snapshots"])
        self.assertEqual(2, steady_rise["rising_steps"])
        self.assertGreaterEqual(steady_rise["gain_percent"], 0.03)
        self.assertIn("projected_rise_percent", steady_rise)
        self.assertIn("projected_target_price", steady_rise)
        self.assertIn("projection_confidence", steady_rise)
        self.assertIn("market_quality_score", steady_rise)
        self.assertIn("risk_penalty_score", steady_rise)
        self.assertIn("spread_quality_score", steady_rise)
        self.assertIn("order_imbalance", steady_rise)
        self.assertEqual(64, steady_rise["estimated_stack_size"])
        self.assertGreaterEqual(steady_rise["storage_slot_value"], 5_000)
        self.assertIn("investment_score", steady_rise)
        self.assertEqual(1, rarefinder["estimated_stack_size"])
        self.assertGreater(rarefinder["projected_profit_per_slot"], steady_rise["projected_profit_per_slot"])
        self.assertGreater(steady_rise["projected_rise_percent"], steady_rise["gain_percent"])
        self.assertGreater(
            steady_rise["projected_target_price"],
            steady_rise["latest_midpoint_price"],
        )
        self.assertGreater(steady_rise["projection_confidence"], 0)
        self.assertLessEqual(steady_rise["projection_confidence"], 0.95)

    def test_craft_value_soft_caps_investment_projection_targets(self) -> None:
        item = database.add_investment_projection_fields(
            {
                "item_id": "SHARD_ETHERDRAKE",
                "category": None,
                "latest_midpoint_price": 1_900_000.0,
                "buy_price": 2_400_000.0,
                "sell_price": 1_400_000.0,
                "observed_snapshots": 5,
                "gain_percent": 0.2,
                "rising_steps": 4,
                "max_single_jump": 0.05,
                "average_volume": 100_000,
                "average_orders": 100,
            }
        )

        self.assertEqual(0.0, item["projected_rise_percent"])
        self.assertEqual(0.0, item["projected_profit_per_unit"])
        self.assertLess(item["projected_target_price"], item["latest_midpoint_price"])
        self.assertGreater(item["projected_target_price"], 1_600_000.0)
        self.assertEqual("craft-adjusted momentum", item["projection_basis"])
        self.assertEqual(1_500_000.0, item["valuation_anchor_price"])
        self.assertGreater(item["craft_value_premium"], 0)
        self.assertLess(item["craft_value_premium"], 0.1)
        self.assertEqual(
            "market is already above craft-adjusted target",
            item["valuation_warning"],
        )

    def test_craft_value_can_project_above_cost_when_market_quality_is_clean(self) -> None:
        item = database.add_investment_projection_fields(
            {
                "item_id": "SHARD_ETHERDRAKE",
                "category": None,
                "latest_midpoint_price": 1_550_000.0,
                "buy_price": 1_590_000.0,
                "sell_price": 1_510_000.0,
                "observed_snapshots": 5,
                "gain_percent": 0.2,
                "rising_steps": 4,
                "max_single_jump": 0.05,
                "average_volume": 500_000,
                "average_orders": 500,
            }
        )

        self.assertGreater(item["projected_target_price"], 1_600_000.0)
        self.assertGreater(item["projected_rise_percent"], 0)
        self.assertGreater(item["craft_value_premium"], 0.1)
        self.assertEqual("craft-adjusted momentum", item["projection_basis"])

    def test_market_quality_penalizes_wide_spread_and_imbalance(self) -> None:
        base_item = {
            "item_id": "TEST_ITEM",
            "category": None,
            "latest_midpoint_price": 100_000.0,
            "observed_snapshots": 5,
            "gain_percent": 0.12,
            "rising_steps": 4,
            "max_single_jump": 0.04,
            "average_volume": 500_000,
            "average_orders": 500,
        }
        clean_market = database.add_investment_projection_fields(
            {
                **base_item,
                "buy_price": 102_000.0,
                "sell_price": 98_000.0,
                "buy_volume": 250_000,
                "sell_volume": 250_000,
                "buy_orders": 250,
                "sell_orders": 250,
            }
        )
        messy_market = database.add_investment_projection_fields(
            {
                **base_item,
                "buy_price": 150_000.0,
                "sell_price": 50_000.0,
                "buy_volume": 10_000,
                "sell_volume": 490_000,
                "buy_orders": 10,
                "sell_orders": 490,
            }
        )

        self.assertGreater(
            clean_market["market_quality_score"],
            messy_market["market_quality_score"],
        )
        self.assertGreater(clean_market["investment_score"], messy_market["investment_score"])
        self.assertGreater(messy_market["risk_penalty_score"], clean_market["risk_penalty_score"])
        self.assertLess(messy_market["spread_penalty"], clean_market["spread_penalty"])

    def test_returns_occurrence_investments_with_market_context(self) -> None:
        database.OCCURRENCE_INVESTMENTS_PATH.write_text(
            json.dumps(
                {
                    "items": [
                        {
                            "item_id": "STEADY_RISE",
                            "catalyst_type": "alpha update",
                            "catalyst_summary": "new recipe test uses this item",
                            "thesis": "stackable commodity with clear demand catalyst",
                            "source_label": "manual test catalyst",
                            "confidence": 0.7,
                            "expected_impact": 0.2,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        rows = database.get_occurrence_investments(limit=5)

        self.assertEqual(1, len(rows))
        self.assertEqual("STEADY_RISE", rows[0]["item_id"])
        self.assertEqual(64, rows[0]["estimated_stack_size"])
        self.assertGreater(rows[0]["storage_slot_value"], 0)
        self.assertGreater(rows[0]["occurrence_score"], 0)
        self.assertEqual("alpha update", rows[0]["catalyst_type"])

    def test_generates_and_persists_rule_based_signals(self) -> None:
        generated = database.generate_rule_based_signals()
        signal_types = {signal["signal_type"] for signal in generated}

        self.assertIn("NPC_FLIP", signal_types)
        self.assertIn("PRICE_MOMENTUM", signal_types)

        saved = database.get_latest_signals(limit=10, refresh=False)
        saved_types = {signal["signal_type"] for signal in saved}

        self.assertIn("NPC_FLIP", saved_types)
        self.assertIn("PRICE_MOMENTUM", saved_types)
        self.assertTrue(all("explanation" in signal for signal in saved))

    def test_initializes_backtest_results_table(self) -> None:
        database.initialize_analysis_tables()

        with closing(sqlite3.connect(database.DATABASE_PATH)) as connection:
            columns = {
                row[1]
                for row in connection.execute(
                    "PRAGMA table_info(backtest_results)"
                ).fetchall()
            }
            indexes = {
                row[1]
                for row in connection.execute(
                    "PRAGMA index_list(backtest_results)"
                ).fetchall()
            }

        self.assertTrue(
            {
                "signal_id",
                "item_id",
                "signal_type",
                "horizon",
                "entry_price",
                "exit_price",
                "return_percent",
                "was_successful",
            }.issubset(columns)
        )
        self.assertIn("idx_backtest_results_unique_signal", indexes)
        self.assertIn("idx_backtest_results_item", indexes)

    def test_records_and_returns_job_runs(self) -> None:
        database.initialize_analysis_tables()

        job_id = database.start_job_run("market_cycle")
        database.finish_job_run(
            job_id,
            "success",
            "completed",
            products_collected=1933,
            signals_generated=8,
            backtests_evaluated={"next_snapshot": 2, "1h": 0},
        )

        jobs = database.get_latest_job_runs(limit=5)

        self.assertEqual(1, len(jobs))
        self.assertEqual("market_cycle", jobs[0]["job_type"])
        self.assertEqual("success", jobs[0]["status"])
        self.assertEqual("completed", jobs[0]["message"])
        self.assertEqual(1933, jobs[0]["products_collected"])
        self.assertEqual(8, jobs[0]["signals_generated"])
        self.assertEqual({"next_snapshot": 2, "1h": 0}, jobs[0]["backtests_evaluated"])
        self.assertIsNotNone(jobs[0]["finished_at"])

    def test_evaluates_signal_against_next_snapshot(self) -> None:
        with closing(sqlite3.connect(database.DATABASE_PATH)) as connection:
            database.create_signal_tables(connection)
            connection.execute(
                """
                INSERT INTO signals (
                    created_at,
                    source_snapshot,
                    item_id,
                    item_name,
                    signal_type,
                    title,
                    message,
                    confidence,
                    expected_return,
                    risk_score,
                    severity,
                    explanation_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "2026-06-12T13:00:00Z",
                    "2026-06-12T13:00:00Z",
                    "STEADY_RISE",
                    "Steady Rise",
                    "PRICE_MOMENTUM",
                    "item heating up",
                    "Steady Rise is climbing.",
                    0.8,
                    0.05,
                    0.2,
                    "watch",
                    "{}",
                ),
            )
            connection.commit()

        evaluated = database.evaluate_signal_backtests()

        self.assertEqual(1, evaluated)
        with closing(sqlite3.connect(database.DATABASE_PATH)) as connection:
            row = connection.execute(
                """
                SELECT
                    item_id,
                    horizon,
                    entry_price,
                    exit_price,
                    return_percent,
                    was_successful
                FROM backtest_results
                """
            ).fetchone()

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual("STEADY_RISE", row[0])
        self.assertEqual("next_snapshot", row[1])
        self.assertEqual(102.0, row[2])
        self.assertEqual(106.0, row[3])
        self.assertGreater(row[4], 0)
        self.assertEqual(1, row[5])

    def test_evaluates_signal_against_hour_horizon(self) -> None:
        self._insert_evaluated_signal("STEADY_RISE", "2026-06-12T13:00:00Z")

        evaluated = database.evaluate_signal_backtests(horizon="1h")

        self.assertEqual(1, evaluated)
        with closing(sqlite3.connect(database.DATABASE_PATH)) as connection:
            row = connection.execute(
                """
                SELECT
                    horizon,
                    entry_time,
                    exit_time,
                    entry_price,
                    exit_price,
                    notes
                FROM backtest_results
                """
            ).fetchone()

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual("1h", row[0])
        self.assertEqual("2026-06-12T13:00:00Z", row[1])
        self.assertEqual("2026-06-12T14:00:00Z", row[2])
        self.assertEqual(102.0, row[3])
        self.assertEqual(110.0, row[4])
        self.assertIn("first snapshot within 1h horizon tolerance", row[5])
        self.assertIn("projected 5.00%", row[5])
        self.assertIn("actual 7.84%", row[5])

    def test_skips_hour_horizon_without_near_snapshot(self) -> None:
        self._insert_evaluated_signal("STEADY_RISE", "2026-06-12T13:30:00Z")

        evaluated = database.evaluate_signal_backtests(horizon="1h")

        self.assertEqual(0, evaluated)

    def test_rejects_unsupported_backtest_horizon(self) -> None:
        with self.assertRaises(ValueError):
            database.evaluate_signal_backtests(horizon="3h")

    def test_skips_backtest_without_future_snapshot(self) -> None:
        with closing(sqlite3.connect(database.DATABASE_PATH)) as connection:
            database.create_signal_tables(connection)
            connection.execute(
                """
                INSERT INTO signals (
                    created_at,
                    source_snapshot,
                    item_id,
                    item_name,
                    signal_type,
                    title,
                    message,
                    confidence,
                    expected_return,
                    risk_score,
                    severity,
                    explanation_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "2026-06-12T14:00:00Z",
                    "2026-06-12T14:00:00Z",
                    "STEADY_RISE",
                    "Steady Rise",
                    "PRICE_MOMENTUM",
                    "item heating up",
                    "Steady Rise is climbing.",
                    0.8,
                    0.05,
                    0.2,
                    "watch",
                    "{}",
                ),
            )
            connection.commit()

        self.assertEqual(0, database.evaluate_signal_backtests())

    def test_returns_backtest_summary_metrics(self) -> None:
        self._insert_evaluated_signal("STEADY_RISE", "2026-06-12T13:00:00Z")
        self._insert_evaluated_signal("ONE_PUMP", "2026-06-12T13:00:00Z")

        evaluated = database.evaluate_signal_backtests()
        summary = database.get_backtest_summary()

        self.assertEqual(2, evaluated)
        self.assertEqual(2, summary["total_results"])
        self.assertEqual(2, summary["successful_results"])
        self.assertEqual(1.0, summary["win_rate"])
        self.assertGreater(summary["average_return"], 0)
        self.assertGreaterEqual(summary["best_return"], summary["worst_return"])
        self.assertEqual(2, summary["projection_results"])
        self.assertEqual(2, summary["total_signals"])
        self.assertEqual(2 * len(database.BACKTEST_HORIZONS), summary["possible_evaluations"])
        self.assertEqual(2, summary["total_results"])
        self.assertGreater(summary["coverage_rate"], 0)
        self.assertEqual(
            summary["possible_evaluations"] - summary["total_results"],
            summary["pending_evaluations"],
        )
        self.assertTrue(summary["by_horizon"])
        self.assertTrue(summary["by_signal_type"])
        self.assertGreaterEqual(summary["projection_hit_rate"], 0)
        self.assertLessEqual(summary["projection_hit_rate"], 1)
        self.assertIn("average_projection_error", summary)
        self.assertIn("average_absolute_projection_error", summary)
        self.assertGreater(summary["average_projected_return"], 0)
        self.assertGreater(summary["average_realized_projection_return"], 0)
        self.assertIsNotNone(summary["latest_evaluated_at"])

    def test_returns_recent_backtest_results(self) -> None:
        self._insert_evaluated_signal("STEADY_RISE", "2026-06-12T13:00:00Z")
        database.evaluate_signal_backtests()

        results = database.get_backtest_results(limit=5)

        self.assertEqual(1, len(results))
        self.assertEqual("STEADY_RISE", results[0]["item_id"])
        self.assertEqual("Steady Rise", results[0]["item_name"])
        self.assertEqual("PRICE_MOMENTUM", results[0]["signal_type"])
        self.assertEqual("next_snapshot", results[0]["horizon"])
        self.assertIn("return_percent", results[0])
        self.assertEqual(0.05, results[0]["expected_return"])

    def _find_item(
        self, rows: list[dict[str, object]], item_id: str
    ) -> dict[str, object]:
        for row in rows:
            if row["item_id"] == item_id:
                return row

        raise AssertionError(f"Missing item: {item_id}")

    def _insert_evaluated_signal(self, item_id: str, source_snapshot: str) -> None:
        item_name = item_id.title().replace("_", " ")
        with closing(sqlite3.connect(database.DATABASE_PATH)) as connection:
            database.create_signal_tables(connection)
            connection.execute(
                """
                INSERT INTO signals (
                    created_at,
                    source_snapshot,
                    item_id,
                    item_name,
                    signal_type,
                    title,
                    message,
                    confidence,
                    expected_return,
                    risk_score,
                    severity,
                    explanation_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_snapshot,
                    source_snapshot,
                    item_id,
                    item_name,
                    "PRICE_MOMENTUM",
                    "item heating up",
                    f"{item_name} is climbing.",
                    0.8,
                    0.05,
                    0.2,
                    "watch",
                    "{}",
                ),
            )
            connection.commit()

    def _create_test_database(self, db_path: Path) -> None:
        with closing(sqlite3.connect(db_path)) as connection:
            connection.executescript(
                """
                CREATE TABLE bazaar_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    collected_at TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    buy_price REAL NOT NULL,
                    sell_price REAL NOT NULL,
                    buy_volume INTEGER NOT NULL,
                    sell_volume INTEGER NOT NULL,
                    buy_orders INTEGER NOT NULL,
                    sell_orders INTEGER NOT NULL,
                    spread REAL NOT NULL
                );

                CREATE TABLE items (
                    item_id TEXT PRIMARY KEY,
                    item_name TEXT NOT NULL,
                    category TEXT,
                    tier TEXT,
                    npc_sell_price REAL
                );
                """
            )

            snapshot_rows = [
                ("2026-06-12T13:00:00Z", "OLDER_ROW", 5, 5, 50_000, 50_000, 100, 100, 0),
                ("2026-06-12T13:00:00Z", "HIGH_ESTIMATED", 100, 91, 50_000, 30_000, 100, 100, 9),
                ("2026-06-12T13:00:00Z", "LOW_MARGIN", 100, 96, 50_000, 100_000, 100, 100, 4),
                ("2026-06-12T13:30:00Z", "HIGH_ESTIMATED", 100, 92, 50_000, 30_000, 100, 100, 8),
                ("2026-06-12T13:30:00Z", "LOW_MARGIN", 100, 97, 50_000, 100_000, 100, 100, 3),
                (
                    "2026-06-12T13:30:00Z",
                    "BOBBIN_SCRIPTURES",
                    250_000,
                    200_000,
                    50_000,
                    100_000,
                    100,
                    100,
                    50_000,
                ),
                ("2026-06-12T14:00:00Z", "HIGH_ESTIMATED", 100, 90, 50_000, 30_000, 100, 100, 10),
                ("2026-06-12T14:00:00Z", "LOW_MARGIN", 100, 95, 50_000, 100_000, 100, 100, 5),
                (
                    "2026-06-12T14:00:00Z",
                    "BOBBIN_SCRIPTURES",
                    250_000,
                    200_000,
                    50_000,
                    100_000,
                    100,
                    100,
                    50_000,
                ),
                ("2026-06-12T13:00:00Z", "STEADY_RISE", 100, 104, 80_000, 90_000, 120, 130, -4),
                ("2026-06-12T13:30:00Z", "STEADY_RISE", 104, 108, 82_000, 91_000, 125, 132, -4),
                ("2026-06-12T14:00:00Z", "STEADY_RISE", 108, 112, 85_000, 93_000, 130, 135, -4),
                (
                    "2026-06-12T13:00:00Z",
                    "RAREFINDER_GARDEN_CHIP",
                    1_000_000,
                    1_040_000,
                    80_000,
                    90_000,
                    120,
                    130,
                    -40_000,
                ),
                (
                    "2026-06-12T13:30:00Z",
                    "RAREFINDER_GARDEN_CHIP",
                    1_040_000,
                    1_080_000,
                    82_000,
                    91_000,
                    125,
                    132,
                    -40_000,
                ),
                (
                    "2026-06-12T14:00:00Z",
                    "RAREFINDER_GARDEN_CHIP",
                    1_080_000,
                    1_120_000,
                    85_000,
                    93_000,
                    130,
                    135,
                    -40_000,
                ),
                ("2026-06-12T13:00:00Z", "ONE_PUMP", 100, 104, 80_000, 90_000, 120, 130, -4),
                ("2026-06-12T13:30:00Z", "ONE_PUMP", 101, 105, 82_000, 91_000, 125, 132, -4),
                ("2026-06-12T14:00:00Z", "ONE_PUMP", 190, 200, 85_000, 93_000, 130, 135, -10),
                (
                    "2026-06-12T13:00:00Z",
                    "LOW_VOLUME_INVEST",
                    100,
                    104,
                    1_000,
                    1_200,
                    120,
                    130,
                    -4,
                ),
                (
                    "2026-06-12T13:30:00Z",
                    "LOW_VOLUME_INVEST",
                    104,
                    108,
                    1_100,
                    1_300,
                    125,
                    132,
                    -4,
                ),
                (
                    "2026-06-12T14:00:00Z",
                    "LOW_VOLUME_INVEST",
                    108,
                    112,
                    1_200,
                    1_400,
                    130,
                    135,
                    -4,
                ),
                ("2026-06-12T14:00:00Z", "LOW_VOLUME", 100, 90, 50_000, 9_999, 100, 100, 10),
                ("2026-06-12T14:00:00Z", "LOW_ORDERS", 100, 90, 50_000, 30_000, 100, 24, 10),
                (
                    "2026-06-12T14:00:00Z",
                    "ONE_SNAPSHOT_SPIKE",
                    100,
                    90,
                    50_000,
                    30_000,
                    100,
                    100,
                    10,
                ),
                (
                    "2026-06-12T14:00:00Z",
                    "HIGH_MARGIN_OUTLIER",
                    100,
                    10,
                    50_000,
                    30_000,
                    100,
                    100,
                    90,
                ),
                ("2026-06-12T14:00:00Z", "NO_PROFIT", 100, 120, 50_000, 30_000, 100, 100, -20),
            ]
            connection.executemany(
                """
                INSERT INTO bazaar_snapshots (
                    collected_at,
                    item_id,
                    buy_price,
                    sell_price,
                    buy_volume,
                    sell_volume,
                    buy_orders,
                    sell_orders,
                    spread
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                snapshot_rows,
            )

            item_rows = [
                ("OLDER_ROW", "Older Row", "test", "COMMON", 1_000),
                ("HIGH_ESTIMATED", "High Estimated", "test", "COMMON", 100),
                ("LOW_MARGIN", "Low Margin", "test", "COMMON", 100),
                ("LOW_VOLUME", "Low Volume", "test", "COMMON", 100),
                ("LOW_ORDERS", "Low Orders", "test", "COMMON", 100),
                ("ONE_SNAPSHOT_SPIKE", "One Snapshot Spike", "test", "COMMON", 100),
                ("HIGH_MARGIN_OUTLIER", "High Margin Outlier", "test", "COMMON", 100),
                ("NO_PROFIT", "No Profit", "test", "COMMON", 100),
                ("BOBBIN_SCRIPTURES", "Bobbin Scriptures", "test", "RARE", 250_000),
                ("STEADY_RISE", "Steady Rise", "test", "RARE", None),
                ("RAREFINDER_GARDEN_CHIP", "Rarefinder Chip", "GARDEN_CHIP", "RARE", None),
                ("ONE_PUMP", "One Pump", "test", "RARE", None),
                ("LOW_VOLUME_INVEST", "Low Volume Invest", "test", "RARE", None),
            ]
            connection.executemany(
                """
                INSERT INTO items (
                    item_id,
                    item_name,
                    category,
                    tier,
                    npc_sell_price
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                item_rows,
            )
            connection.commit()


class DatabaseDialectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_database_config = database.DATABASE_CONFIG

    def tearDown(self) -> None:
        database.DATABASE_CONFIG = self.original_database_config

    def test_sql_keeps_sqlite_placeholders_by_default(self) -> None:
        self.assertEqual("SELECT ? AS value", database.sql("SELECT ? AS value"))

    def test_sql_translates_placeholders_for_postgres(self) -> None:
        database.DATABASE_CONFIG = DatabaseConfig(
            backend="postgres",
            sqlite_path=Path("unused.db"),
            database_url="postgresql://example",
        )

        self.assertEqual("SELECT %s AS value", database.sql("SELECT ? AS value"))

    def test_postgres_signal_tables_use_serial_primary_keys(self) -> None:
        database.DATABASE_CONFIG = DatabaseConfig(
            backend="postgres",
            sqlite_path=Path("unused.db"),
            database_url="postgresql://example",
        )
        connection = CapturingConnection()

        database.create_signal_tables(connection)

        ddl = "\n".join(connection.statements)
        self.assertIn("id BIGSERIAL PRIMARY KEY", ddl)
        self.assertNotIn("AUTOINCREMENT", ddl)

    def test_postgres_job_insert_returns_generated_id(self) -> None:
        database.DATABASE_CONFIG = DatabaseConfig(
            backend="postgres",
            sqlite_path=Path("unused.db"),
            database_url="postgresql://example",
        )
        connection = CapturingConnection(returning_id=42)

        with patch.object(database, "database_exists", return_value=True):
            with patch.object(database, "get_connection", return_value=connection):
                self.assertEqual(42, database.start_job_run("market_cycle"))

        self.assertTrue(
            any("RETURNING id" in statement for statement in connection.statements)
        )


class CapturingCursor:
    def __init__(self, returning_id: int | None = None):
        self.returning_id = returning_id
        self.lastrowid = returning_id or 1

    def fetchone(self) -> dict[str, int] | None:
        if self.returning_id is None:
            return None

        return {"id": self.returning_id}


class CapturingConnection:
    def __init__(self, returning_id: int | None = None):
        self.returning_id = returning_id
        self.statements: list[str] = []
        self.committed = False
        self.closed = False

    def execute(self, statement: str, params: tuple[object, ...] = ()) -> CapturingCursor:
        self.statements.append(statement)
        return CapturingCursor(self.returning_id if "RETURNING id" in statement else None)

    def commit(self) -> None:
        self.committed = True

    def close(self) -> None:
        self.closed = True


if __name__ == "__main__":
    unittest.main()
