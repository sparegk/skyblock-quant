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
