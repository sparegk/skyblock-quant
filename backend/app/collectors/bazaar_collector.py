"""Collect Hypixel SkyBlock Bazaar snapshots.

This script fetches the current Bazaar data from Hypixel, saves the raw API
response, and stores the useful market fields in a local SQLite database.
"""

from __future__ import annotations

import argparse
import json
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from app import database
from app.settings import get_database_config, get_raw_dir


BAZAAR_URL = "https://api.hypixel.net/v2/skyblock/bazaar"
DEFAULT_DB_PATH = get_database_config().sqlite_path
DEFAULT_RAW_DIR = get_raw_dir()


def fetch_bazaar_data() -> dict[str, Any]:
    """Fetch the latest Bazaar response from the Hypixel API."""
    with urlopen(BAZAAR_URL, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def create_tables(connection: Any) -> None:
    """Create the local tables if they do not already exist."""
    id_type = (
        "BIGSERIAL PRIMARY KEY"
        if database.is_postgres()
        else "INTEGER PRIMARY KEY AUTOINCREMENT"
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS bazaar_snapshots (
            id {id_type},
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
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_bazaar_snapshots_collected_at
        ON bazaar_snapshots (collected_at)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_bazaar_snapshots_item_history
        ON bazaar_snapshots (item_id, collected_at DESC)
        """
    )
    connection.commit()


def save_raw_snapshot(data: dict[str, Any], raw_dir: Path, collected_at: str) -> Path:
    """Save the full API response so it can be inspected later."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    filename = f"bazaar_{collected_at.replace(':', '-').replace('+', 'Z')}.json"
    output_path = raw_dir / filename
    output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return output_path


def save_clean_snapshot(
    data: dict[str, Any], db_path: Path, collected_at: str
) -> int:
    """Save normalized Bazaar product rows into SQLite."""
    products = data.get("products", {})
    if not isinstance(products, dict):
        raise ValueError("Hypixel response did not include a valid products object.")

    if not database.is_postgres():
        db_path.parent.mkdir(parents=True, exist_ok=True)

    with closing(database.get_write_connection(db_path)) as connection:
        create_tables(connection)

        rows = []
        for item_id, item_data in products.items():
            quick_status = item_data.get("quick_status", {})
            buy_price = float(quick_status.get("buyPrice", 0))
            sell_price = float(quick_status.get("sellPrice", 0))

            rows.append(
                (
                    collected_at,
                    item_id,
                    buy_price,
                    sell_price,
                    int(quick_status.get("buyVolume", 0)),
                    int(quick_status.get("sellVolume", 0)),
                    int(quick_status.get("buyOrders", 0)),
                    int(quick_status.get("sellOrders", 0)),
                    buy_price - sell_price,
                )
            )

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
            rows,
        )
        connection.commit()

    return len(rows)


def collect_bazaar_snapshot(db_path: Path, raw_dir: Path) -> int:
    """Fetch one Bazaar snapshot and save both raw and clean versions."""
    collected_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = fetch_bazaar_data()

    if not data.get("success"):
        cause = data.get("cause", "Unknown Hypixel API error")
        raise RuntimeError(f"Hypixel API request failed: {cause}")

    raw_path = save_raw_snapshot(data, raw_dir, collected_at)
    row_count = save_clean_snapshot(data, db_path, collected_at)

    print(f"Collected {row_count} Bazaar products.")
    print(f"Raw snapshot: {raw_path}")
    print(f"SQLite database: {db_path}")
    return row_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect one Hypixel Bazaar snapshot.")
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
        help="Directory where raw API snapshots are saved.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    collect_bazaar_snapshot(args.db, args.raw_dir)


if __name__ == "__main__":
    main()
