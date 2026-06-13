"""Database helpers for reading local Bazaar snapshots."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any


DATABASE_PATH = Path(__file__).resolve().parents[2] / "data" / "skyblock_quant.db"

MIN_NPC_ARBITRAGE_SELL_VOLUME = 10_000
MIN_NPC_ARBITRAGE_SELL_ORDERS = 25
MAX_NPC_ARBITRAGE_MARGIN = 0.25
NPC_ARBITRAGE_VOLUME_CAP = 10_000
NPC_ARBITRAGE_HISTORY_SNAPSHOTS = 5
MIN_NPC_ARBITRAGE_PROFITABLE_SNAPSHOTS = 2
MOMENTUM_HISTORY_SNAPSHOTS = 5
MIN_MOMENTUM_OBSERVED_SNAPSHOTS = 3
MIN_MOMENTUM_VOLUME = 10_000
MIN_MOMENTUM_ORDERS = 25
MIN_MOMENTUM_GAIN = 0.03
MAX_MOMENTUM_SINGLE_JUMP = 0.35
MIN_MOMENTUM_RISING_STEPS = 2
STALE_SNAPSHOT_MINUTES = 20


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_connection() -> sqlite3.Connection:
    """Open a SQLite connection that returns rows like dictionaries."""
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def database_exists() -> bool:
    return DATABASE_PATH.exists()


def create_signal_tables(connection: sqlite3.Connection) -> None:
    """Create tables used to persist generated market signals and results."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            source_snapshot TEXT,
            item_id TEXT NOT NULL,
            item_name TEXT NOT NULL,
            signal_type TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            confidence REAL NOT NULL,
            expected_return REAL,
            risk_score REAL NOT NULL,
            severity TEXT NOT NULL,
            explanation_json TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_signals_unique_snapshot
        ON signals (source_snapshot, item_id, signal_type)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_signals_created_at
        ON signals (created_at DESC)
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS backtest_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id INTEGER NOT NULL,
            item_id TEXT NOT NULL,
            signal_type TEXT NOT NULL,
            horizon TEXT NOT NULL,
            entry_time TEXT NOT NULL,
            exit_time TEXT NOT NULL,
            entry_price REAL NOT NULL,
            exit_price REAL NOT NULL,
            return_percent REAL NOT NULL,
            max_drawdown_percent REAL,
            max_gain_percent REAL,
            was_successful INTEGER NOT NULL,
            evaluated_at TEXT NOT NULL,
            notes TEXT,
            FOREIGN KEY(signal_id) REFERENCES signals(id)
        )
        """
    )
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_backtest_results_unique_signal
        ON backtest_results (signal_id, horizon)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_backtest_results_item
        ON backtest_results (item_id, signal_type, horizon)
        """
    )
    connection.commit()


def initialize_analysis_tables() -> None:
    """Ensure signal and backtest tables exist in the configured database."""
    if not database_exists():
        return

    with closing(get_connection()) as connection:
        create_signal_tables(connection)


def get_market_summary() -> dict[str, Any]:
    """Return high-level information about the collected Bazaar data."""
    if not database_exists():
        return {
            "database_ready": False,
            "latest_snapshot": None,
            "tracked_products": 0,
            "total_rows": 0,
        }

    with closing(get_connection()) as connection:
        row = connection.execute(
            """
            SELECT
                MAX(collected_at) AS latest_snapshot,
                COUNT(*) AS total_rows,
                COUNT(DISTINCT item_id) AS tracked_products
            FROM bazaar_snapshots
            """
        ).fetchone()

    return {
        "database_ready": True,
        "latest_snapshot": row["latest_snapshot"],
        "tracked_products": row["tracked_products"],
        "total_rows": row["total_rows"],
    }


def get_latest_snapshot(limit: int = 25) -> list[dict[str, Any]]:
    """Return rows from the most recent Bazaar snapshot."""
    if not database_exists():
        return []

    with closing(get_connection()) as connection:
        rows = connection.execute(
            """
            SELECT
                item_id,
                buy_price,
                sell_price,
                buy_volume,
                sell_volume,
                buy_orders,
                sell_orders,
                spread,
                collected_at
            FROM bazaar_snapshots
            WHERE collected_at = (
                SELECT MAX(collected_at)
                FROM bazaar_snapshots
            )
            ORDER BY buy_volume + sell_volume DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]


def search_items(query: str, limit: int = 25) -> list[dict[str, Any]]:
    """Search item ids in the latest Bazaar snapshot."""
    if not database_exists():
        return []

    with closing(get_connection()) as connection:
        rows = connection.execute(
            """
            SELECT
                item_id,
                buy_price,
                sell_price,
                buy_volume,
                sell_volume,
                buy_orders,
                sell_orders,
                spread,
                collected_at
            FROM bazaar_snapshots
            WHERE collected_at = (
                SELECT MAX(collected_at)
                FROM bazaar_snapshots
            )
            AND item_id LIKE ?
            ORDER BY buy_volume + sell_volume DESC
            LIMIT ?
            """,
            (f"%{query.upper()}%", limit),
        ).fetchall()

    return [dict(row) for row in rows]


def get_top_spreads(limit: int = 25) -> list[dict[str, Any]]:
    """Return items with the largest positive spread in the latest snapshot."""
    if not database_exists():
        return []

    with closing(get_connection()) as connection:
        rows = connection.execute(
            """
            SELECT
                item_id,
                buy_price,
                sell_price,
                buy_volume,
                sell_volume,
                buy_orders,
                sell_orders,
                spread,
                collected_at
            FROM bazaar_snapshots
            WHERE collected_at = (
                SELECT MAX(collected_at)
                FROM bazaar_snapshots
            )
            ORDER BY spread DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]


def get_npc_arbitrage(
    limit: int = 25,
    min_sell_volume: int = MIN_NPC_ARBITRAGE_SELL_VOLUME,
    min_sell_orders: int = MIN_NPC_ARBITRAGE_SELL_ORDERS,
    max_profit_margin: float = MAX_NPC_ARBITRAGE_MARGIN,
    history_snapshots: int = NPC_ARBITRAGE_HISTORY_SNAPSHOTS,
    min_profitable_snapshots: int = MIN_NPC_ARBITRAGE_PROFITABLE_SNAPSHOTS,
) -> list[dict[str, Any]]:
    """Return Bazaar items that can be sold to NPCs for estimated profit."""
    if not database_exists():
        return []

    with closing(get_connection()) as connection:
        table_exists = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            AND name = 'items'
            """
        ).fetchone()

        if table_exists is None:
            return []

        rows = connection.execute(
            """
            WITH recent_snapshots AS (
                SELECT DISTINCT collected_at
                FROM bazaar_snapshots
                ORDER BY collected_at DESC
                LIMIT ?
            ),
            history AS (
                SELECT
                    snapshots.item_id,
                    COUNT(*) AS observed_snapshots,
                    SUM(
                        CASE
                            WHEN items.npc_sell_price IS NOT NULL
                                AND items.npc_sell_price > 0
                                AND snapshots.sell_price > 0
                                AND items.npc_sell_price - snapshots.sell_price > 0
                                AND snapshots.sell_volume >= ?
                                AND snapshots.sell_orders >= ?
                                AND (
                                    items.npc_sell_price - snapshots.sell_price
                                ) / snapshots.sell_price <= ?
                            THEN 1
                            ELSE 0
                        END
                    ) AS profitable_snapshots,
                    AVG(
                        CASE
                            WHEN items.npc_sell_price IS NOT NULL
                                AND items.npc_sell_price > 0
                                AND snapshots.sell_price > 0
                                AND items.npc_sell_price - snapshots.sell_price > 0
                                AND snapshots.sell_volume >= ?
                                AND snapshots.sell_orders >= ?
                                AND (
                                    items.npc_sell_price - snapshots.sell_price
                                ) / snapshots.sell_price <= ?
                            THEN items.npc_sell_price - snapshots.sell_price
                            ELSE NULL
                        END
                    ) AS average_profit_per_item
                FROM bazaar_snapshots AS snapshots
                INNER JOIN items
                    ON items.item_id = snapshots.item_id
                INNER JOIN recent_snapshots
                    ON recent_snapshots.collected_at = snapshots.collected_at
                GROUP BY snapshots.item_id
            ),
            candidates AS (
                SELECT
                    snapshots.item_id,
                    items.item_name,
                    items.category,
                    items.tier,
                    snapshots.sell_price AS bazaar_buy_price,
                    snapshots.buy_price AS bazaar_sell_price,
                    items.npc_sell_price,
                    items.npc_sell_price - snapshots.sell_price AS profit_per_item,
                    (items.npc_sell_price - snapshots.sell_price) / snapshots.sell_price
                        AS profit_margin,
                    snapshots.buy_volume,
                    snapshots.sell_volume,
                    snapshots.buy_orders,
                    snapshots.sell_orders,
                    snapshots.collected_at,
                    history.observed_snapshots,
                    history.profitable_snapshots,
                    history.average_profit_per_item
                FROM bazaar_snapshots AS snapshots
                INNER JOIN items
                    ON items.item_id = snapshots.item_id
                INNER JOIN history
                    ON history.item_id = snapshots.item_id
                WHERE snapshots.collected_at = (
                    SELECT MAX(collected_at)
                    FROM bazaar_snapshots
                )
                AND items.npc_sell_price IS NOT NULL
                AND items.npc_sell_price > 0
                AND snapshots.sell_price > 0
                AND items.npc_sell_price - snapshots.sell_price > 0
                AND snapshots.sell_volume >= ?
                AND snapshots.sell_orders >= ?
                AND history.profitable_snapshots >= ?
            )
            SELECT *
            FROM (
                SELECT
                    item_id,
                    item_name,
                    category,
                    tier,
                    bazaar_buy_price,
                    bazaar_sell_price,
                    npc_sell_price,
                    profit_per_item,
                    profit_margin,
                    profit_per_item *
                        CASE
                            WHEN sell_volume > ? THEN ?
                            ELSE sell_volume
                        END AS estimated_profit,
                    (
                        profit_per_item *
                        CASE
                            WHEN sell_volume > ? THEN ?
                            ELSE sell_volume
                        END
                    ) * profitable_snapshots / observed_snapshots
                        AS history_adjusted_profit,
                    sell_volume / 1000.0 + sell_orders AS liquidity_score,
                    buy_volume,
                    sell_volume,
                    buy_orders,
                    sell_orders,
                    observed_snapshots,
                    profitable_snapshots,
                    average_profit_per_item,
                    profitable_snapshots * 1.0 / observed_snapshots AS profit_consistency,
                    collected_at
                FROM candidates
                WHERE profit_margin <= ?
            )
            ORDER BY
                history_adjusted_profit DESC,
                liquidity_score DESC,
                profit_per_item DESC
            LIMIT ?
            """,
            (
                history_snapshots,
                min_sell_volume,
                min_sell_orders,
                max_profit_margin,
                min_sell_volume,
                min_sell_orders,
                max_profit_margin,
                min_sell_volume,
                min_sell_orders,
                min_profitable_snapshots,
                NPC_ARBITRAGE_VOLUME_CAP,
                NPC_ARBITRAGE_VOLUME_CAP,
                NPC_ARBITRAGE_VOLUME_CAP,
                NPC_ARBITRAGE_VOLUME_CAP,
                max_profit_margin,
                limit,
            ),
        ).fetchall()

    return [dict(row) for row in rows]


def get_npc_arbitrage_detail(
    item_id: str,
    history_snapshots: int = NPC_ARBITRAGE_HISTORY_SNAPSHOTS,
) -> dict[str, Any] | None:
    """Return metadata and recent NPC arbitrage history for one Bazaar item."""
    if not database_exists():
        return None

    normalized_item_id = item_id.strip().upper()
    if not normalized_item_id:
        return None

    with closing(get_connection()) as connection:
        table_exists = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            AND name = 'items'
            """
        ).fetchone()

        if table_exists is None:
            return None

        item = connection.execute(
            """
            SELECT
                items.item_id,
                items.item_name,
                items.category,
                items.tier,
                items.npc_sell_price
            FROM items
            WHERE items.item_id = ?
            """,
            (normalized_item_id,),
        ).fetchone()

        if item is None:
            return None

        history_rows = connection.execute(
            """
            SELECT
                snapshots.collected_at,
                snapshots.sell_price AS bazaar_buy_price,
                snapshots.buy_price AS bazaar_sell_price,
                items.npc_sell_price,
                items.npc_sell_price - snapshots.sell_price AS profit_per_item,
                CASE
                    WHEN snapshots.sell_price > 0
                    THEN (items.npc_sell_price - snapshots.sell_price) / snapshots.sell_price
                    ELSE NULL
                END AS profit_margin,
                snapshots.buy_volume,
                snapshots.sell_volume,
                snapshots.buy_orders,
                snapshots.sell_orders,
                CASE
                    WHEN items.npc_sell_price > 0
                        AND snapshots.sell_price > 0
                        AND items.npc_sell_price - snapshots.sell_price > 0
                    THEN 1
                    ELSE 0
                END AS is_profitable
            FROM bazaar_snapshots AS snapshots
            INNER JOIN items
                ON items.item_id = snapshots.item_id
            WHERE snapshots.item_id = ?
            ORDER BY snapshots.collected_at DESC
            LIMIT ?
            """,
            (normalized_item_id, history_snapshots),
        ).fetchall()

    history = [dict(row) for row in history_rows]
    if not history:
        return None

    latest = history[0]
    profitable_snapshots = sum(row["is_profitable"] for row in history)

    return {
        **dict(item),
        "latest": latest,
        "history": history,
        "observed_snapshots": len(history),
        "profitable_snapshots": profitable_snapshots,
        "profit_consistency": profitable_snapshots / len(history),
    }


def get_investment_momentum(
    limit: int = 25,
    history_snapshots: int = MOMENTUM_HISTORY_SNAPSHOTS,
    min_observed_snapshots: int = MIN_MOMENTUM_OBSERVED_SNAPSHOTS,
    min_volume: int = MIN_MOMENTUM_VOLUME,
    min_orders: int = MIN_MOMENTUM_ORDERS,
    min_gain: float = MIN_MOMENTUM_GAIN,
    max_single_jump: float = MAX_MOMENTUM_SINGLE_JUMP,
    min_rising_steps: int = MIN_MOMENTUM_RISING_STEPS,
) -> list[dict[str, Any]]:
    """Return Bazaar items with recent price momentum and enough liquidity."""
    if not database_exists():
        return []

    with closing(get_connection()) as connection:
        rows = connection.execute(
            """
            WITH recent_snapshots AS (
                SELECT DISTINCT collected_at
                FROM bazaar_snapshots
                ORDER BY collected_at DESC
                LIMIT ?
            ),
            base_prices AS (
                SELECT
                    snapshots.item_id,
                    snapshots.collected_at,
                    snapshots.buy_price,
                    snapshots.sell_price,
                    (snapshots.buy_price + snapshots.sell_price) / 2.0 AS midpoint_price,
                    snapshots.buy_volume,
                    snapshots.sell_volume,
                    snapshots.buy_orders,
                    snapshots.sell_orders,
                    snapshots.spread
                FROM bazaar_snapshots AS snapshots
                INNER JOIN recent_snapshots
                    ON recent_snapshots.collected_at = snapshots.collected_at
                WHERE snapshots.buy_price > 0
                AND snapshots.sell_price > 0
            ),
            priced AS (
                SELECT
                    base_prices.*,
                    ROW_NUMBER() OVER (
                        PARTITION BY item_id
                        ORDER BY collected_at ASC
                    ) AS oldest_rank,
                    ROW_NUMBER() OVER (
                        PARTITION BY item_id
                        ORDER BY collected_at DESC
                    ) AS latest_rank,
                    COUNT(*) OVER (
                        PARTITION BY item_id
                    ) AS observed_snapshots,
                    LAG(midpoint_price) OVER (
                        PARTITION BY item_id
                        ORDER BY collected_at ASC
                    ) AS previous_midpoint_price
                FROM base_prices
            ),
            momentum AS (
                SELECT
                    item_id,
                    observed_snapshots,
                    MAX(
                        CASE
                            WHEN oldest_rank = 1 THEN midpoint_price
                            ELSE NULL
                        END
                    ) AS oldest_midpoint_price,
                    MAX(
                        CASE
                            WHEN latest_rank = 1 THEN midpoint_price
                            ELSE NULL
                        END
                    ) AS latest_midpoint_price,
                    SUM(
                        CASE
                            WHEN previous_midpoint_price IS NOT NULL
                                AND midpoint_price > previous_midpoint_price
                            THEN 1
                            ELSE 0
                        END
                    ) AS rising_steps,
                    MAX(
                        CASE
                            WHEN previous_midpoint_price > 0
                            THEN (midpoint_price - previous_midpoint_price)
                                / previous_midpoint_price
                            ELSE 0
                        END
                    ) AS max_single_jump,
                    AVG(buy_volume + sell_volume) AS average_volume,
                    AVG(buy_orders + sell_orders) AS average_orders
                FROM priced
                GROUP BY item_id
            ),
            latest AS (
                SELECT *
                FROM priced
                WHERE latest_rank = 1
            )
            SELECT
                latest.item_id,
                COALESCE(items.item_name, latest.item_id) AS item_name,
                items.category,
                items.tier,
                latest.buy_price,
                latest.sell_price,
                latest.midpoint_price,
                latest.buy_volume,
                latest.sell_volume,
                latest.buy_orders,
                latest.sell_orders,
                latest.spread,
                latest.collected_at,
                momentum.observed_snapshots,
                momentum.oldest_midpoint_price,
                momentum.latest_midpoint_price,
                (
                    momentum.latest_midpoint_price - momentum.oldest_midpoint_price
                ) / momentum.oldest_midpoint_price AS gain_percent,
                momentum.rising_steps,
                momentum.max_single_jump,
                momentum.average_volume,
                momentum.average_orders,
                (
                    (
                        momentum.latest_midpoint_price - momentum.oldest_midpoint_price
                    ) / momentum.oldest_midpoint_price
                ) * (momentum.average_volume / 1000.0 + momentum.average_orders)
                    AS momentum_score
            FROM latest
            INNER JOIN momentum
                ON momentum.item_id = latest.item_id
            LEFT JOIN items
                ON items.item_id = latest.item_id
            WHERE momentum.observed_snapshots >= ?
            AND latest.buy_volume + latest.sell_volume >= ?
            AND latest.buy_orders + latest.sell_orders >= ?
            AND momentum.average_volume >= ?
            AND momentum.average_orders >= ?
            AND (
                momentum.latest_midpoint_price - momentum.oldest_midpoint_price
            ) / momentum.oldest_midpoint_price >= ?
            AND momentum.max_single_jump <= ?
            AND momentum.rising_steps >= ?
            ORDER BY
                momentum_score DESC,
                gain_percent DESC,
                momentum.average_volume DESC
            LIMIT ?
            """,
            (
                history_snapshots,
                min_observed_snapshots,
                min_volume,
                min_orders,
                min_volume,
                min_orders,
                min_gain,
                max_single_jump,
                min_rising_steps,
                limit,
            ),
        ).fetchall()

    return [dict(row) for row in rows]


def get_snapshot_age_minutes(snapshot_time: str | None) -> int | None:
    if not snapshot_time:
        return None

    normalized = snapshot_time.replace("Z", "+00:00")
    try:
        timestamp = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)

    return max(0, int((datetime.now(UTC) - timestamp).total_seconds() // 60))


def save_signals(signals: list[dict[str, Any]]) -> int:
    if not database_exists() or not signals:
        return 0

    with closing(get_connection()) as connection:
        create_signal_tables(connection)
        rows = [
            (
                signal["created_at"],
                signal.get("source_snapshot"),
                signal["item_id"],
                signal["item_name"],
                signal["signal_type"],
                signal["title"],
                signal["message"],
                signal["confidence"],
                signal.get("expected_return"),
                signal["risk_score"],
                signal["severity"],
                json.dumps(signal["explanation"], sort_keys=True),
            )
            for signal in signals
        ]
        connection.executemany(
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
            ON CONFLICT(source_snapshot, item_id, signal_type) DO UPDATE SET
                created_at = excluded.created_at,
                item_name = excluded.item_name,
                title = excluded.title,
                message = excluded.message,
                confidence = excluded.confidence,
                expected_return = excluded.expected_return,
                risk_score = excluded.risk_score,
                severity = excluded.severity,
                explanation_json = excluded.explanation_json
            """,
            rows,
        )
        connection.commit()

    return len(rows)


def generate_rule_based_signals() -> list[dict[str, Any]]:
    """Generate and persist the current rule-based market signals."""
    summary = get_market_summary()
    if not summary.get("database_ready"):
        return []

    created_at = utc_now()
    source_snapshot = summary.get("latest_snapshot")
    signals: list[dict[str, Any]] = []

    for item in get_npc_arbitrage(limit=5):
        confidence = min(0.98, 0.55 + item["profit_consistency"] * 0.3 + item["profit_margin"])
        risk_score = min(
            1.0,
            0.2
            + max(0, 0.2 - item["profit_margin"])
            + (0.15 if item["sell_volume"] < 20_000 else 0),
        )
        signals.append(
            {
                "created_at": created_at,
                "source_snapshot": source_snapshot,
                "item_id": item["item_id"],
                "item_name": item["item_name"],
                "signal_type": "NPC_FLIP",
                "title": "npc flip found",
                "message": (
                    f"{item['item_name']} can sell to NPC for "
                    f"{item['profit_per_item']:.0f} coins profit each."
                ),
                "confidence": round(confidence, 4),
                "expected_return": item["profit_margin"],
                "risk_score": round(risk_score, 4),
                "severity": "positive",
                "explanation": {
                    "profit_per_item": item["profit_per_item"],
                    "profit_margin": item["profit_margin"],
                    "sell_volume": item["sell_volume"],
                    "sell_orders": item["sell_orders"],
                    "profitable_snapshots": item["profitable_snapshots"],
                    "observed_snapshots": item["observed_snapshots"],
                },
            }
        )

    for item in get_investment_momentum(limit=5):
        confidence = min(0.95, 0.5 + item["gain_percent"] * 3 + item["rising_steps"] * 0.08)
        risk_score = min(1.0, item["max_single_jump"] * 2 + (0.15 if item["average_volume"] < 50_000 else 0))
        signals.append(
            {
                "created_at": created_at,
                "source_snapshot": source_snapshot,
                "item_id": item["item_id"],
                "item_name": item["item_name"],
                "signal_type": "PRICE_MOMENTUM",
                "title": "item heating up",
                "message": (
                    f"{item['item_name']} is up {item['gain_percent'] * 100:.1f}% "
                    "across recent Bazaar snapshots."
                ),
                "confidence": round(confidence, 4),
                "expected_return": item["gain_percent"],
                "risk_score": round(risk_score, 4),
                "severity": "watch",
                "explanation": {
                    "gain_percent": item["gain_percent"],
                    "rising_steps": item["rising_steps"],
                    "observed_snapshots": item["observed_snapshots"],
                    "average_volume": item["average_volume"],
                    "max_single_jump": item["max_single_jump"],
                },
            }
        )

    snapshot_age = get_snapshot_age_minutes(source_snapshot if isinstance(source_snapshot, str) else None)
    if snapshot_age is not None and snapshot_age > STALE_SNAPSHOT_MINUTES:
        signals.append(
            {
                "created_at": created_at,
                "source_snapshot": source_snapshot,
                "item_id": "__MARKET__",
                "item_name": "Market data",
                "signal_type": "STALE_DATA",
                "title": "snapshot is old",
                "message": f"Latest Bazaar snapshot is {snapshot_age} minutes old.",
                "confidence": 1.0,
                "expected_return": None,
                "risk_score": 0.8,
                "severity": "risk",
                "explanation": {
                    "snapshot_age_minutes": snapshot_age,
                    "stale_after_minutes": STALE_SNAPSHOT_MINUTES,
                },
            }
        )

    save_signals(signals)
    return signals


def get_latest_signals(limit: int = 25, refresh: bool = True) -> list[dict[str, Any]]:
    """Return latest persisted signals, optionally refreshing them first."""
    if not database_exists():
        return []

    if refresh:
        generate_rule_based_signals()

    with closing(get_connection()) as connection:
        create_signal_tables(connection)
        rows = connection.execute(
            """
            SELECT
                id,
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
            FROM signals
            ORDER BY created_at DESC, confidence DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    signals = []
    for row in rows:
        signal = dict(row)
        signal["explanation"] = json.loads(signal.pop("explanation_json"))
        signals.append(signal)

    return signals


def evaluate_signal_backtests(
    horizon: str = "next_snapshot",
    success_threshold: float = 0.0,
    limit: int = 100,
) -> int:
    """Evaluate logged signals against the next available Bazaar snapshot."""
    if not database_exists():
        return 0

    evaluated_at = utc_now()

    with closing(get_connection()) as connection:
        create_signal_tables(connection)
        signals = connection.execute(
            """
            SELECT
                id,
                item_id,
                signal_type,
                source_snapshot
            FROM signals
            WHERE item_id != '__MARKET__'
            AND source_snapshot IS NOT NULL
            AND NOT EXISTS (
                SELECT 1
                FROM backtest_results
                WHERE backtest_results.signal_id = signals.id
                AND backtest_results.horizon = ?
            )
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (horizon, limit),
        ).fetchall()

        results = []
        for signal in signals:
            entry = connection.execute(
                """
                SELECT
                    collected_at,
                    (buy_price + sell_price) / 2.0 AS price
                FROM bazaar_snapshots
                WHERE item_id = ?
                AND collected_at = ?
                AND buy_price > 0
                AND sell_price > 0
                """,
                (signal["item_id"], signal["source_snapshot"]),
            ).fetchone()
            exit_row = connection.execute(
                """
                SELECT
                    collected_at,
                    (buy_price + sell_price) / 2.0 AS price
                FROM bazaar_snapshots
                WHERE item_id = ?
                AND collected_at > ?
                AND buy_price > 0
                AND sell_price > 0
                ORDER BY collected_at ASC
                LIMIT 1
                """,
                (signal["item_id"], signal["source_snapshot"]),
            ).fetchone()

            if entry is None or exit_row is None or entry["price"] <= 0:
                continue

            path_rows = connection.execute(
                """
                SELECT
                    (buy_price + sell_price) / 2.0 AS price
                FROM bazaar_snapshots
                WHERE item_id = ?
                AND collected_at >= ?
                AND collected_at <= ?
                AND buy_price > 0
                AND sell_price > 0
                ORDER BY collected_at ASC
                """,
                (signal["item_id"], signal["source_snapshot"], exit_row["collected_at"]),
            ).fetchall()
            price_path = [row["price"] for row in path_rows]
            max_drawdown = (
                (min(price_path) - entry["price"]) / entry["price"]
                if price_path
                else 0.0
            )
            max_gain = (
                (max(price_path) - entry["price"]) / entry["price"]
                if price_path
                else 0.0
            )
            return_percent = (exit_row["price"] - entry["price"]) / entry["price"]
            results.append(
                (
                    signal["id"],
                    signal["item_id"],
                    signal["signal_type"],
                    horizon,
                    entry["collected_at"],
                    exit_row["collected_at"],
                    entry["price"],
                    exit_row["price"],
                    return_percent,
                    max_drawdown,
                    max_gain,
                    1 if return_percent >= success_threshold else 0,
                    evaluated_at,
                    "next available snapshot",
                )
            )

        if results:
            connection.executemany(
                """
                INSERT INTO backtest_results (
                    signal_id,
                    item_id,
                    signal_type,
                    horizon,
                    entry_time,
                    exit_time,
                    entry_price,
                    exit_price,
                    return_percent,
                    max_drawdown_percent,
                    max_gain_percent,
                    was_successful,
                    evaluated_at,
                    notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(signal_id, horizon) DO NOTHING
                """,
                results,
            )
            connection.commit()

    return len(results)


def get_backtest_summary() -> dict[str, Any]:
    """Return aggregate performance metrics for evaluated signals."""
    empty_summary = {
        "total_results": 0,
        "successful_results": 0,
        "win_rate": 0.0,
        "average_return": 0.0,
        "median_return": 0.0,
        "best_return": 0.0,
        "worst_return": 0.0,
        "average_drawdown": 0.0,
        "latest_evaluated_at": None,
    }

    if not database_exists():
        return empty_summary

    with closing(get_connection()) as connection:
        create_signal_tables(connection)
        rows = connection.execute(
            """
            SELECT
                return_percent,
                max_drawdown_percent,
                was_successful,
                evaluated_at
            FROM backtest_results
            ORDER BY return_percent ASC
            """
        ).fetchall()

    if not rows:
        return empty_summary

    returns = [row["return_percent"] for row in rows]
    drawdowns = [row["max_drawdown_percent"] for row in rows]
    total_results = len(rows)
    successful_results = sum(1 for row in rows if row["was_successful"])
    midpoint = total_results // 2
    if total_results % 2:
        median_return = returns[midpoint]
    else:
        median_return = (returns[midpoint - 1] + returns[midpoint]) / 2

    latest_evaluated_at = max(
        (row["evaluated_at"] for row in rows if row["evaluated_at"]),
        default=None,
    )

    return {
        "total_results": total_results,
        "successful_results": successful_results,
        "win_rate": successful_results / total_results,
        "average_return": sum(returns) / total_results,
        "median_return": median_return,
        "best_return": max(returns),
        "worst_return": min(returns),
        "average_drawdown": sum(drawdowns) / total_results,
        "latest_evaluated_at": latest_evaluated_at,
    }


def get_backtest_results(limit: int = 50) -> list[dict[str, Any]]:
    """Return recent evaluated signal results."""
    if not database_exists():
        return []

    with closing(get_connection()) as connection:
        create_signal_tables(connection)
        rows = connection.execute(
            """
            SELECT
                backtest_results.id,
                backtest_results.signal_id,
                backtest_results.item_id,
                COALESCE(signals.item_name, backtest_results.item_id) AS item_name,
                backtest_results.signal_type,
                COALESCE(signals.title, backtest_results.signal_type) AS title,
                backtest_results.horizon,
                backtest_results.entry_time,
                backtest_results.exit_time,
                backtest_results.entry_price,
                backtest_results.exit_price,
                backtest_results.return_percent,
                backtest_results.max_drawdown_percent,
                backtest_results.max_gain_percent,
                backtest_results.was_successful,
                backtest_results.evaluated_at,
                backtest_results.notes
            FROM backtest_results
            LEFT JOIN signals ON signals.id = backtest_results.signal_id
            ORDER BY backtest_results.evaluated_at DESC, backtest_results.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]
