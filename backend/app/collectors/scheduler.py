"""Run market data collectors on a simple interval."""

from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path

from bazaar_collector import DEFAULT_DB_PATH, DEFAULT_RAW_DIR, collect_bazaar_snapshot


def run_bazaar_scheduler(
    db_path: Path, raw_dir: Path, interval_minutes: int, max_runs: int | None
) -> None:
    """Run the Bazaar collector forever with a pause between snapshots."""
    interval_seconds = interval_minutes * 60
    completed_runs = 0

    print(f"Starting Bazaar scheduler. Interval: {interval_minutes} minute(s).")
    print("Press Ctrl+C to stop.")

    while True:
        started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{started_at}] Collecting Bazaar snapshot...")

        try:
            collect_bazaar_snapshot(db_path, raw_dir)
        except Exception as error:
            print(f"Collector failed: {error}")

        completed_runs += 1
        if max_runs is not None and completed_runs >= max_runs:
            print("Reached max run count. Stopping scheduler.")
            break

        print(f"Waiting {interval_minutes} minute(s) for the next snapshot...")
        time.sleep(interval_seconds)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect Hypixel Bazaar snapshots every few minutes."
    )
    parser.add_argument(
        "--interval-minutes",
        type=int,
        default=5,
        help="How many minutes to wait between Bazaar snapshots.",
    )
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
    parser.add_argument(
        "--max-runs",
        type=int,
        default=None,
        help="Optional number of snapshots to collect before stopping.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.interval_minutes < 1:
        raise ValueError("--interval-minutes must be at least 1.")

    if args.max_runs is not None and args.max_runs < 1:
        raise ValueError("--max-runs must be at least 1 when provided.")

    run_bazaar_scheduler(args.db, args.raw_dir, args.interval_minutes, args.max_runs)


if __name__ == "__main__":
    main()
