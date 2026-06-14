"""Database helpers for reading local Bazaar snapshots."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
import json
import math
import os
from pathlib import Path
from typing import Any


DATABASE_PATH = Path(
    os.getenv(
        "SKYBLOCK_QUANT_DB_PATH",
        str(Path(__file__).resolve().parents[2] / "data" / "skyblock_quant.db"),
    )
)
OCCURRENCE_INVESTMENTS_PATH = Path(__file__).resolve().parents[2] / "data" / "occurrence_investments.json"

MIN_NPC_ARBITRAGE_SELL_VOLUME = 10_000
MIN_NPC_ARBITRAGE_SELL_ORDERS = 25
MAX_NPC_ARBITRAGE_MARGIN = 0.25
NPC_ARBITRAGE_VOLUME_CAP = 10_000
NPC_ARBITRAGE_HISTORY_SNAPSHOTS = 5
MIN_NPC_ARBITRAGE_PROFITABLE_SNAPSHOTS = 2
NPC_ARBITRAGE_STABLE_SELL_VOLUME = 20_000
NPC_ARBITRAGE_STABLE_SELL_ORDERS = 50
NPC_ARBITRAGE_HIGH_MARGIN = 0.20
NPC_ARBITRAGE_HIGH_PRICE_JUMP = 0.25
NPC_ARBITRAGE_WIDE_SPREAD = 0.20
MOMENTUM_HISTORY_SNAPSHOTS = 5
MIN_MOMENTUM_OBSERVED_SNAPSHOTS = 3
MIN_MOMENTUM_VOLUME = 10_000
MIN_MOMENTUM_ORDERS = 25
MIN_MOMENTUM_GAIN = 0.03
MAX_MOMENTUM_SINGLE_JUMP = 0.35
MIN_MOMENTUM_RISING_STEPS = 2
MIN_INVESTMENT_UNIT_PRICE = 50.0
MIN_INVESTMENT_STACK_SIZE = 1
MIN_INVESTMENT_SLOT_VALUE = 5_000.0
TARGET_INVESTMENT_SLOT_VALUE = 250_000.0
TARGET_INVESTMENT_PROFIT_PER_SLOT = 25_000.0
TARGET_NPC_PROFIT_PER_SELL_ACTION = 20_000.0
STALE_SNAPSHOT_MINUTES = 20
BACKTEST_HORIZONS = {
    "next_snapshot": None,
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
}


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_snapshot_time(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC)


def format_snapshot_time(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_backtest_target_time(source_snapshot: str, horizon: str) -> str | None:
    if horizon not in BACKTEST_HORIZONS:
        allowed = ", ".join(BACKTEST_HORIZONS)
        raise ValueError(f"Unsupported backtest horizon: {horizon}. Use one of: {allowed}.")

    offset = BACKTEST_HORIZONS[horizon]
    if offset is None:
        return None

    return format_snapshot_time(parse_snapshot_time(source_snapshot) + offset)


def get_backtest_horizon_tolerance(horizon: str) -> timedelta | None:
    offset = BACKTEST_HORIZONS[horizon]
    if offset is None:
        return None

    return max(timedelta(minutes=15), offset / 4)


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


def create_job_tables(connection: sqlite3.Connection) -> None:
    """Create tables used to record scheduled backend work."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS job_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_type TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT NOT NULL,
            message TEXT,
            products_collected INTEGER,
            signals_generated INTEGER,
            backtests_evaluated_json TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_job_runs_started_at
        ON job_runs (started_at DESC)
        """
    )
    connection.commit()


def initialize_analysis_tables() -> None:
    """Ensure signal and backtest tables exist in the configured database."""
    if not database_exists():
        return

    with closing(get_connection()) as connection:
        create_signal_tables(connection)
        create_job_tables(connection)


def start_job_run(job_type: str) -> int:
    """Record the start of a backend job and return its id."""
    if not database_exists():
        return 0

    with closing(get_connection()) as connection:
        create_job_tables(connection)
        cursor = connection.execute(
            """
            INSERT INTO job_runs (
                job_type,
                started_at,
                status,
                backtests_evaluated_json
            )
            VALUES (?, ?, ?, ?)
            """,
            (job_type, utc_now(), "running", "{}"),
        )
        connection.commit()

    return int(cursor.lastrowid)


def finish_job_run(
    job_id: int,
    status: str,
    message: str,
    *,
    products_collected: int | None = None,
    signals_generated: int | None = None,
    backtests_evaluated: dict[str, int] | None = None,
) -> None:
    """Mark a backend job as finished with metrics."""
    if not job_id or not database_exists():
        return

    with closing(get_connection()) as connection:
        create_job_tables(connection)
        connection.execute(
            """
            UPDATE job_runs
            SET
                finished_at = ?,
                status = ?,
                message = ?,
                products_collected = ?,
                signals_generated = ?,
                backtests_evaluated_json = ?
            WHERE id = ?
            """,
            (
                utc_now(),
                status,
                message,
                products_collected,
                signals_generated,
                json.dumps(backtests_evaluated or {}, sort_keys=True),
                job_id,
            ),
        )
        connection.commit()


def get_latest_job_runs(limit: int = 20) -> list[dict[str, Any]]:
    """Return recent backend job runs."""
    if not database_exists():
        return []

    with closing(get_connection()) as connection:
        create_job_tables(connection)
        rows = connection.execute(
            """
            SELECT
                id,
                job_type,
                started_at,
                finished_at,
                status,
                message,
                products_collected,
                signals_generated,
                backtests_evaluated_json
            FROM job_runs
            ORDER BY started_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    job_runs = []
    for row in rows:
        job_run = dict(row)
        job_run["backtests_evaluated"] = json.loads(
            job_run.pop("backtests_evaluated_json")
        )
        job_runs.append(job_run)

    return job_runs


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


def add_npc_arbitrage_risk_fields(row: dict[str, Any]) -> dict[str, Any]:
    """Add risk score, label, and reasons to an NPC arbitrage row."""
    risk_reasons = []
    risk_score = 0.1

    if row.get("profit_consistency", 0) < 0.75:
        risk_score += 0.25
        risk_reasons.append("profit only appears in some recent snapshots")

    if row.get("profit_margin", 0) >= NPC_ARBITRAGE_HIGH_MARGIN:
        risk_score += 0.2
        risk_reasons.append("profit margin is unusually wide")

    if row.get("sell_volume", 0) < NPC_ARBITRAGE_STABLE_SELL_VOLUME:
        risk_score += 0.2
        risk_reasons.append("sell volume is thin")

    if row.get("sell_orders", 0) < NPC_ARBITRAGE_STABLE_SELL_ORDERS:
        risk_score += 0.15
        risk_reasons.append("sell order count is thin")

    if row.get("max_recent_price_jump", 0) >= NPC_ARBITRAGE_HIGH_PRICE_JUMP:
        risk_score += 0.25
        risk_reasons.append("recent price movement is volatile")

    if row.get("spread_percent", 0) >= NPC_ARBITRAGE_WIDE_SPREAD:
        risk_score += 0.1
        risk_reasons.append("bazaar spread is wide")

    if row.get("interaction_efficiency_score", 100) < 25:
        risk_score += 0.15
        risk_reasons.append("profit per sell action is low")

    risk_score = min(1.0, risk_score)

    if row.get("max_recent_price_jump", 0) >= NPC_ARBITRAGE_HIGH_PRICE_JUMP:
        risk_label = "volatile"
    elif (
        row.get("profit_margin", 0) >= NPC_ARBITRAGE_HIGH_MARGIN
        or row.get("spread_percent", 0) >= NPC_ARBITRAGE_WIDE_SPREAD
    ):
        risk_label = "possible manipulation"
    elif (
        row.get("sell_volume", 0) < NPC_ARBITRAGE_STABLE_SELL_VOLUME
        or row.get("sell_orders", 0) < NPC_ARBITRAGE_STABLE_SELL_ORDERS
    ):
        risk_label = "thin liquidity"
    else:
        risk_label = "stable"

    if not risk_reasons:
        risk_reasons.append("liquidity and recent history look stable")

    return {
        **row,
        "risk_score": round(risk_score, 4),
        "risk_label": risk_label,
        "risk_reasons": risk_reasons,
    }


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

    candidate_limit = max(limit * 5, 100)
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
            priced_history AS (
                SELECT
                    snapshots.*,
                    LAG(snapshots.sell_price) OVER (
                        PARTITION BY snapshots.item_id
                        ORDER BY snapshots.collected_at ASC
                    ) AS previous_sell_price
                FROM bazaar_snapshots AS snapshots
                INNER JOIN recent_snapshots
                    ON recent_snapshots.collected_at = snapshots.collected_at
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
                    ) AS average_profit_per_item,
                    MAX(
                        CASE
                            WHEN snapshots.previous_sell_price > 0
                            THEN ABS(snapshots.sell_price - snapshots.previous_sell_price)
                                / snapshots.previous_sell_price
                            ELSE 0
                        END
                    ) AS max_recent_price_jump
                FROM priced_history AS snapshots
                INNER JOIN items
                    ON items.item_id = snapshots.item_id
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
                    history.average_profit_per_item,
                    history.max_recent_price_jump
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
                    max_recent_price_jump,
                    profitable_snapshots * 1.0 / observed_snapshots AS profit_consistency,
                    CASE
                        WHEN bazaar_buy_price > 0
                        THEN ABS(bazaar_sell_price - bazaar_buy_price) / bazaar_buy_price
                        ELSE 0
                    END AS spread_percent,
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
                candidate_limit,
            ),
        ).fetchall()

    enriched_rows = [
        add_npc_arbitrage_risk_fields(add_npc_interaction_fields(dict(row))) for row in rows
    ]
    enriched_rows.sort(
        key=lambda item: (
            item["action_adjusted_profit"],
            item["history_adjusted_profit"],
            item["profit_per_sell_action"],
        ),
        reverse=True,
    )
    return enriched_rows[:limit]


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
    chronological_history = list(reversed(history))
    price_jumps = []
    for previous, current in zip(chronological_history, chronological_history[1:]):
        previous_price = previous["bazaar_buy_price"]
        current_price = current["bazaar_buy_price"]
        if previous_price > 0:
            price_jumps.append(abs(current_price - previous_price) / previous_price)

    detail = {
        **dict(item),
        "latest": latest,
        "history": history,
        "observed_snapshots": len(history),
        "profitable_snapshots": profitable_snapshots,
        "profit_consistency": profitable_snapshots / len(history),
        "profit_margin": latest["profit_margin"] or 0,
        "sell_volume": latest["sell_volume"],
        "sell_orders": latest["sell_orders"],
        "max_recent_price_jump": max(price_jumps, default=0),
        "spread_percent": (
            abs(latest["bazaar_sell_price"] - latest["bazaar_buy_price"])
            / latest["bazaar_buy_price"]
            if latest["bazaar_buy_price"] > 0
            else 0
        ),
    }

    return add_npc_arbitrage_risk_fields(add_npc_interaction_fields(detail))


NON_STACKABLE_CATEGORY_KEYWORDS = (
    "ACCESSORY",
    "ARMOR",
    "BELT",
    "BOOTS",
    "BOW",
    "BRACELET",
    "CHESTPLATE",
    "CLOAK",
    "GARDEN_CHIP",
    "GLOVES",
    "HELMET",
    "LEGGINGS",
    "NECKLACE",
    "PET",
    "SWORD",
    "WEAPON",
)

NON_STACKABLE_ITEM_KEYWORDS = (
    "ACCESSORY",
    "ARTIFACT",
    "AXE",
    "BELT",
    "BOOTS",
    "BOW",
    "BRACELET",
    "CHESTPLATE",
    "CHIP",
    "CLOAK",
    "DRILL",
    "FISHING_ROD",
    "GAUNTLET",
    "GLOVES",
    "HELMET",
    "HOE",
    "LEGGINGS",
    "NECKLACE",
    "PET_ITEM",
    "PICKAXE",
    "RING",
    "ROD",
    "SHOVEL",
    "SWORD",
    "TALISMAN",
    "WAND",
)


def estimate_investment_stack_size(item: dict[str, Any]) -> int:
    """Estimate storage stack size when Hypixel metadata has no max-stack field."""
    item_id = str(item.get("item_id") or "").upper()
    category = str(item.get("category") or "").upper()

    if any(keyword in category for keyword in NON_STACKABLE_CATEGORY_KEYWORDS):
        return 1

    if any(keyword in item_id for keyword in NON_STACKABLE_ITEM_KEYWORDS):
        return 1

    return 64


def add_investment_storage_fields(item: dict[str, Any]) -> dict[str, Any]:
    stack_size = estimate_investment_stack_size(item)
    storage_slot_value = item["latest_midpoint_price"] * stack_size
    item["estimated_stack_size"] = stack_size
    item["storage_slot_value"] = storage_slot_value
    item["storage_efficiency_score"] = min(
        100.0,
        max(0.0, storage_slot_value / TARGET_INVESTMENT_SLOT_VALUE * 100),
    )
    return item


def add_npc_interaction_fields(item: dict[str, Any]) -> dict[str, Any]:
    stack_size = estimate_investment_stack_size(item)
    profit_per_item = item.get("profit_per_item")
    if profit_per_item is None and isinstance(item.get("latest"), dict):
        profit_per_item = item["latest"].get("profit_per_item", 0)

    profit_per_item = float(profit_per_item or 0)
    profit_per_sell_action = profit_per_item * stack_size
    interaction_efficiency_score = min(
        100.0,
        max(0.0, profit_per_sell_action / TARGET_NPC_PROFIT_PER_SELL_ACTION * 100),
    )

    item["estimated_stack_size"] = stack_size
    item["profit_per_sell_action"] = profit_per_sell_action
    item["interaction_efficiency_score"] = interaction_efficiency_score
    item["action_adjusted_profit"] = (
        item.get("history_adjusted_profit", profit_per_item)
        * max(0.1, interaction_efficiency_score / 100)
    )
    return item


def add_investment_projection_fields(item: dict[str, Any]) -> dict[str, Any]:
    """Estimate near-term upside from recent momentum, liquidity, and jump risk."""
    add_investment_storage_fields(item)
    observed_steps = max(item["observed_snapshots"] - 1, 1)
    trend_consistency = min(max(item["rising_steps"] / observed_steps, 0), 1)
    trend_multiplier = 0.75 + trend_consistency * 0.5
    liquidity_multiplier = min(
        1.15,
        0.85
        + min(item["average_volume"] / 200_000, 1) * 0.2
        + min(item["average_orders"] / 300, 1) * 0.1,
    )
    jump_penalty = max(0.55, 1 - item["max_single_jump"] * 1.5)
    projected_rise_percent = min(
        0.5,
        max(0, item["gain_percent"] * trend_multiplier * liquidity_multiplier * jump_penalty),
    )

    item["projected_rise_percent"] = projected_rise_percent
    item["projected_target_price"] = item["latest_midpoint_price"] * (
        1 + projected_rise_percent
    )
    item["projected_profit_per_unit"] = item["latest_midpoint_price"] * projected_rise_percent
    item["projected_profit_per_slot"] = (
        item["storage_slot_value"] * projected_rise_percent
    )
    item["profit_efficiency_score"] = min(
        100.0,
        max(
            0.0,
            item["projected_profit_per_slot"]
            / TARGET_INVESTMENT_PROFIT_PER_SLOT
            * 100,
        ),
    )
    item["projection_confidence"] = min(
        0.95,
        max(
            0.1,
            0.3
            + trend_consistency * 0.35
            + min(math.log10(max(item["average_volume"], 1)) / 6, 1) * 0.2
            + min(item["average_orders"] / 300, 1) * 0.1
            - min(item["max_single_jump"], 0.5) * 0.4,
        ),
    )
    item["investment_score"] = (
        item["projected_profit_per_slot"]
        * item["projection_confidence"]
        * (0.5 + item["storage_efficiency_score"] / 200)
        * (0.5 + item["profit_efficiency_score"] / 200)
    )
    return item


def get_investment_momentum(
    limit: int = 25,
    history_snapshots: int = MOMENTUM_HISTORY_SNAPSHOTS,
    min_observed_snapshots: int = MIN_MOMENTUM_OBSERVED_SNAPSHOTS,
    min_volume: int = MIN_MOMENTUM_VOLUME,
    min_orders: int = MIN_MOMENTUM_ORDERS,
    min_gain: float = MIN_MOMENTUM_GAIN,
    max_single_jump: float = MAX_MOMENTUM_SINGLE_JUMP,
    min_rising_steps: int = MIN_MOMENTUM_RISING_STEPS,
    min_unit_price: float = MIN_INVESTMENT_UNIT_PRICE,
    min_stack_size: int = MIN_INVESTMENT_STACK_SIZE,
    min_slot_value: float = MIN_INVESTMENT_SLOT_VALUE,
) -> list[dict[str, Any]]:
    """Return Bazaar items with recent price momentum and enough liquidity."""
    if not database_exists():
        return []

    candidate_limit = max(limit * 8, 100)
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
                candidate_limit,
            ),
        ).fetchall()

    enriched_rows = [add_investment_projection_fields(dict(row)) for row in rows]
    practical_rows = [
        item
        for item in enriched_rows
        if item["latest_midpoint_price"] >= min_unit_price
        and item["estimated_stack_size"] >= min_stack_size
        and item["storage_slot_value"] >= min_slot_value
    ]
    practical_rows.sort(
        key=lambda item: (
            item["investment_score"],
            item["projected_rise_percent"],
            item["storage_slot_value"],
        ),
        reverse=True,
    )
    return practical_rows[:limit]


def get_occurrence_investments(limit: int = 10) -> list[dict[str, Any]]:
    """Return curated event/update-driven investment theses enriched with market context."""
    if not OCCURRENCE_INVESTMENTS_PATH.exists():
        return []

    try:
        raw_data = json.loads(OCCURRENCE_INVESTMENTS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    raw_items = raw_data.get("items", []) if isinstance(raw_data, dict) else []
    if not isinstance(raw_items, list):
        return []

    market_rows: dict[str, dict[str, Any]] = {}
    if database_exists():
        with closing(get_connection()) as connection:
            latest_rows = connection.execute(
                """
                SELECT
                    snapshots.item_id,
                    COALESCE(items.item_name, snapshots.item_id) AS item_name,
                    items.category,
                    items.tier,
                    (snapshots.buy_price + snapshots.sell_price) / 2.0 AS latest_midpoint_price,
                    snapshots.buy_volume,
                    snapshots.sell_volume,
                    snapshots.buy_orders,
                    snapshots.sell_orders,
                    snapshots.collected_at
                FROM bazaar_snapshots AS snapshots
                LEFT JOIN items ON items.item_id = snapshots.item_id
                INNER JOIN (
                    SELECT item_id, MAX(collected_at) AS latest_snapshot
                    FROM bazaar_snapshots
                    GROUP BY item_id
                ) AS latest
                    ON latest.item_id = snapshots.item_id
                    AND latest.latest_snapshot = snapshots.collected_at
                """
            ).fetchall()
        market_rows = {row["item_id"]: dict(row) for row in latest_rows}

    occurrence_items = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue

        item_id = str(raw_item.get("item_id", "")).strip().upper()
        if not item_id:
            continue

        market_item = market_rows.get(item_id, {})
        item_name = raw_item.get("item_name") or market_item.get("item_name") or item_id
        latest_midpoint_price = float(
            raw_item.get("estimated_unit_price")
            or market_item.get("latest_midpoint_price")
            or 0
        )
        item = {
            "item_id": item_id,
            "item_name": item_name,
            "category": market_item.get("category") or raw_item.get("category"),
            "tier": market_item.get("tier") or raw_item.get("tier"),
            "latest_midpoint_price": latest_midpoint_price,
            "catalyst_type": raw_item.get("catalyst_type", "occurrence"),
            "catalyst_summary": raw_item.get("catalyst_summary", ""),
            "thesis": raw_item.get("thesis", ""),
            "source_label": raw_item.get("source_label", "curated source"),
            "source_url": raw_item.get("source_url"),
            "source_date": raw_item.get("source_date"),
            "confidence": min(max(float(raw_item.get("confidence", 0.5)), 0), 1),
            "expected_impact": min(max(float(raw_item.get("expected_impact", 0)), -1), 5),
            "urgency": raw_item.get("urgency", "watch"),
            "buy_volume": market_item.get("buy_volume", 0),
            "sell_volume": market_item.get("sell_volume", 0),
            "buy_orders": market_item.get("buy_orders", 0),
            "sell_orders": market_item.get("sell_orders", 0),
            "collected_at": market_item.get("collected_at"),
        }
        add_investment_storage_fields(item)
        item["occurrence_score"] = (
            item["confidence"]
            * max(item["expected_impact"], 0)
            * max(0.1, item["storage_efficiency_score"] / 100)
            * 100
        )
        occurrence_items.append(item)

    occurrence_items.sort(
        key=lambda item: (
            item["occurrence_score"],
            item["confidence"],
            item["storage_slot_value"],
        ),
        reverse=True,
    )
    return occurrence_items[:limit]


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
                "risk_score": item["risk_score"],
                "severity": "positive",
                "explanation": {
                    "profit_per_item": item["profit_per_item"],
                    "profit_margin": item["profit_margin"],
                    "sell_volume": item["sell_volume"],
                    "sell_orders": item["sell_orders"],
                    "profitable_snapshots": item["profitable_snapshots"],
                    "observed_snapshots": item["observed_snapshots"],
                    "risk_label": item["risk_label"],
                    "risk_reasons": item["risk_reasons"],
                },
            }
        )

    for item in get_investment_momentum(limit=5):
        confidence = item["projection_confidence"]
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
                "expected_return": item["projected_rise_percent"],
                "risk_score": round(risk_score, 4),
                "severity": "watch",
                "explanation": {
                    "gain_percent": item["gain_percent"],
                    "projected_rise_percent": item["projected_rise_percent"],
                    "projected_target_price": item["projected_target_price"],
                    "projection_confidence": item["projection_confidence"],
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
    """Evaluate logged signals against a future Bazaar snapshot."""
    if horizon not in BACKTEST_HORIZONS:
        allowed = ", ".join(BACKTEST_HORIZONS)
        raise ValueError(f"Unsupported backtest horizon: {horizon}. Use one of: {allowed}.")

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
                source_snapshot,
                expected_return
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
            target_time = get_backtest_target_time(signal["source_snapshot"], horizon)
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
            if target_time is None:
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
                notes = "next available snapshot"
            else:
                exit_row = connection.execute(
                    """
                    SELECT
                        collected_at,
                        (buy_price + sell_price) / 2.0 AS price
                    FROM bazaar_snapshots
                    WHERE item_id = ?
                    AND collected_at >= ?
                    AND buy_price > 0
                    AND sell_price > 0
                    ORDER BY collected_at ASC
                    LIMIT 1
                    """,
                    (signal["item_id"], target_time),
                ).fetchone()
                if exit_row is not None:
                    tolerance = get_backtest_horizon_tolerance(horizon)
                    target = parse_snapshot_time(target_time)
                    exit_time = parse_snapshot_time(exit_row["collected_at"])
                    if tolerance is not None and exit_time > target + tolerance:
                        exit_row = None
                notes = f"first snapshot within {horizon} horizon tolerance"

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
            projection_note = (
                f"{notes}; projected {signal['expected_return'] * 100:.2f}%, "
                f"actual {return_percent * 100:.2f}%"
                if signal["signal_type"] == "PRICE_MOMENTUM"
                and signal["expected_return"] is not None
                else notes
            )
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
                    projection_note,
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
        "projection_results": 0,
        "projection_hit_rate": 0.0,
        "average_projection_error": 0.0,
        "average_absolute_projection_error": 0.0,
        "average_projected_return": 0.0,
        "average_realized_projection_return": 0.0,
        "latest_evaluated_at": None,
    }

    if not database_exists():
        return empty_summary

    with closing(get_connection()) as connection:
        create_signal_tables(connection)
        rows = connection.execute(
            """
            SELECT
                backtest_results.return_percent,
                backtest_results.max_drawdown_percent,
                backtest_results.was_successful,
                backtest_results.evaluated_at,
                signals.expected_return,
                signals.signal_type
            FROM backtest_results
            LEFT JOIN signals ON signals.id = backtest_results.signal_id
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
    projection_rows = [
        row
        for row in rows
        if row["signal_type"] == "PRICE_MOMENTUM" and row["expected_return"] is not None
    ]
    projection_errors = [
        row["return_percent"] - row["expected_return"] for row in projection_rows
    ]
    projection_hits = [
        row
        for row in projection_rows
        if row["return_percent"] >= row["expected_return"]
    ]

    return {
        "total_results": total_results,
        "successful_results": successful_results,
        "win_rate": successful_results / total_results,
        "average_return": sum(returns) / total_results,
        "median_return": median_return,
        "best_return": max(returns),
        "worst_return": min(returns),
        "average_drawdown": sum(drawdowns) / total_results,
        "projection_results": len(projection_rows),
        "projection_hit_rate": (
            len(projection_hits) / len(projection_rows) if projection_rows else 0.0
        ),
        "average_projection_error": (
            sum(projection_errors) / len(projection_errors) if projection_errors else 0.0
        ),
        "average_absolute_projection_error": (
            sum(abs(error) for error in projection_errors) / len(projection_errors)
            if projection_errors
            else 0.0
        ),
        "average_projected_return": (
            sum(row["expected_return"] for row in projection_rows) / len(projection_rows)
            if projection_rows
            else 0.0
        ),
        "average_realized_projection_return": (
            sum(row["return_percent"] for row in projection_rows) / len(projection_rows)
            if projection_rows
            else 0.0
        ),
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
                signals.expected_return,
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
