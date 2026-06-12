"""Collect Hypixel SkyBlock item metadata.

This stores item names and NPC sell prices so the app can compare Bazaar prices
against deterministic NPC sell values.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import urlopen


ITEMS_URL = "https://api.hypixel.net/v2/resources/skyblock/items"
DEFAULT_DB_PATH = Path("data/skyblock_quant.db")
DEFAULT_RAW_DIR = Path("data/raw")


def fetch_item_metadata() -> dict[str, Any]:
    """Fetch SkyBlock item metadata from the Hypixel API."""
    with urlopen(ITEMS_URL, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def create_tables(connection: sqlite3.Connection) -> None:
    """Create the item metadata table if it does not already exist."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS items (
            item_id TEXT PRIMARY KEY,
            item_name TEXT NOT NULL,
            category TEXT,
            tier TEXT,
            npc_sell_price REAL,
            material TEXT,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.commit()


def save_raw_metadata(data: dict[str, Any], raw_dir: Path, collected_at: str) -> Path:
    """Save the full item metadata response for local inspection."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    filename = f"items_{collected_at.replace(':', '-')}.json"
    output_path = raw_dir / filename
    output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return output_path


def save_item_metadata(data: dict[str, Any], db_path: Path, collected_at: str) -> int:
    """Upsert item metadata rows into SQLite."""
    items = data.get("items", [])
    if not isinstance(items, list):
        raise ValueError("Hypixel response did not include a valid items list.")

    db_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for item in items:
        item_id = item.get("id")
        item_name = item.get("name")
        if not item_id or not item_name:
            continue

        rows.append(
            (
                item_id,
                item_name,
                item.get("category"),
                item.get("tier"),
                item.get("npc_sell_price"),
                item.get("material"),
                collected_at,
            )
        )

    with sqlite3.connect(db_path) as connection:
        create_tables(connection)
        connection.executemany(
            """
            INSERT INTO items (
                item_id,
                item_name,
                category,
                tier,
                npc_sell_price,
                material,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(item_id) DO UPDATE SET
                item_name = excluded.item_name,
                category = excluded.category,
                tier = excluded.tier,
                npc_sell_price = excluded.npc_sell_price,
                material = excluded.material,
                updated_at = excluded.updated_at
            """,
            rows,
        )
        connection.commit()

    return len(rows)


def collect_item_metadata(db_path: Path, raw_dir: Path) -> None:
    """Fetch and store the current SkyBlock item metadata."""
    collected_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = fetch_item_metadata()

    if not data.get("success"):
        cause = data.get("cause", "Unknown Hypixel API error")
        raise RuntimeError(f"Hypixel API request failed: {cause}")

    raw_path = save_raw_metadata(data, raw_dir, collected_at)
    row_count = save_item_metadata(data, db_path, collected_at)

    print(f"Collected {row_count} SkyBlock item metadata rows.")
    print(f"Raw metadata: {raw_path}")
    print(f"SQLite database: {db_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect Hypixel item metadata.")
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Path to the SQLite database file.",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=DEFAULT_RAW_DIR,
        help="Directory where raw API metadata is saved.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    collect_item_metadata(args.db, args.raw_dir)


if __name__ == "__main__":
    main()

