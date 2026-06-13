from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app import database


class NpcArbitrageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_database_path = database.DATABASE_PATH
        database.DATABASE_PATH = Path(self.temp_dir.name) / "test.db"
        self._create_test_database(database.DATABASE_PATH)

    def tearDown(self) -> None:
        database.DATABASE_PATH = self.original_database_path
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
        self.assertNotIn("ONE_PUMP", item_ids)
        self.assertNotIn("LOW_VOLUME_INVEST", item_ids)

        steady_rise = self._find_item(rows, "STEADY_RISE")
        self.assertEqual(3, steady_rise["observed_snapshots"])
        self.assertEqual(2, steady_rise["rising_steps"])
        self.assertGreaterEqual(steady_rise["gain_percent"], 0.03)

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

    def _find_item(
        self, rows: list[dict[str, object]], item_id: str
    ) -> dict[str, object]:
        for row in rows:
            if row["item_id"] == item_id:
                return row

        raise AssertionError(f"Missing item: {item_id}")

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


if __name__ == "__main__":
    unittest.main()
