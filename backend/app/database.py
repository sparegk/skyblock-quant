"""Database helpers for reading local Bazaar snapshots."""

from __future__ import annotations

import sqlite3
from contextlib import closing
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


def get_connection() -> sqlite3.Connection:
    """Open a SQLite connection that returns rows like dictionaries."""
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def database_exists() -> bool:
    return DATABASE_PATH.exists()


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
