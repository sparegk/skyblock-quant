"""Run market data collectors on a simple interval."""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    from .bazaar_collector import DEFAULT_DB_PATH, DEFAULT_RAW_DIR, collect_bazaar_snapshot
    from .item_metadata_collector import collect_item_metadata
except ImportError:
    from bazaar_collector import DEFAULT_DB_PATH, DEFAULT_RAW_DIR, collect_bazaar_snapshot
    from item_metadata_collector import collect_item_metadata


BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import database


DEFAULT_BACKTEST_HORIZONS = ("next_snapshot", "1h", "6h", "24h")


def parse_horizons(value: str) -> tuple[str, ...]:
    horizons = tuple(horizon.strip() for horizon in value.split(",") if horizon.strip())
    if not horizons:
        raise ValueError("At least one backtest horizon is required.")

    return horizons


def run_analysis_cycle(db_path: Path, backtest_horizons: tuple[str, ...]) -> dict[str, object]:
    """Generate signals and evaluate configured backtest horizons."""
    database.DATABASE_PATH = db_path
    database.initialize_analysis_tables()

    signals = database.generate_rule_based_signals()
    evaluated = {
        horizon: database.evaluate_signal_backtests(horizon=horizon)
        for horizon in backtest_horizons
    }

    return {
        "signals": len(signals),
        "evaluated": evaluated,
    }


def run_bazaar_scheduler(
    db_path: Path,
    raw_dir: Path,
    interval_minutes: int,
    max_runs: int | None,
    *,
    run_analysis: bool = True,
    backtest_horizons: tuple[str, ...] = DEFAULT_BACKTEST_HORIZONS,
    refresh_metadata_first: bool = False,
) -> None:
    """Run the Bazaar collector forever with a pause between snapshots."""
    interval_seconds = interval_minutes * 60
    completed_runs = 0

    print(f"Starting Bazaar scheduler. Interval: {interval_minutes} minute(s).")
    print("Press Ctrl+C to stop.")

    if refresh_metadata_first:
        print("Refreshing item metadata before first snapshot...")
        collect_item_metadata(db_path, raw_dir)

    while True:
        started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{started_at}] Collecting Bazaar snapshot...")
        database.DATABASE_PATH = db_path
        job_id = database.start_job_run("market_cycle")
        products_collected = None

        try:
            products_collected = collect_bazaar_snapshot(db_path, raw_dir)
        except Exception as error:
            print(f"Collector failed: {error}")
            database.finish_job_run(
                job_id,
                "failed",
                f"Collector failed: {error}",
                products_collected=products_collected,
            )
        else:
            if run_analysis:
                try:
                    analysis = run_analysis_cycle(db_path, backtest_horizons)
                    print(
                        "Analysis complete: "
                        f"{analysis['signals']} signal(s), "
                        f"backtests {analysis['evaluated']}."
                    )
                    database.finish_job_run(
                        job_id,
                        "success",
                        "Collector and analysis completed.",
                        products_collected=products_collected,
                        signals_generated=int(analysis["signals"]),
                        backtests_evaluated=analysis["evaluated"],
                    )
                except Exception as error:
                    print(f"Analysis failed: {error}")
                    database.finish_job_run(
                        job_id,
                        "partial",
                        f"Collector completed, analysis failed: {error}",
                        products_collected=products_collected,
                    )
            else:
                database.finish_job_run(
                    job_id,
                    "success",
                    "Collector completed; analysis skipped.",
                    products_collected=products_collected,
                )

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
        default=int(os.getenv("SKYBLOCK_QUANT_COLLECT_INTERVAL_MINUTES", "5")),
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
    parser.add_argument(
        "--skip-analysis",
        action="store_true",
        help="Only collect snapshots; do not generate signals or evaluate backtests.",
    )
    parser.add_argument(
        "--backtest-horizons",
        default=os.getenv(
            "SKYBLOCK_QUANT_BACKTEST_HORIZONS",
            ",".join(DEFAULT_BACKTEST_HORIZONS),
        ),
        help="Comma-separated horizons to evaluate after each snapshot.",
    )
    parser.add_argument(
        "--refresh-metadata-first",
        action="store_true",
        help="Refresh item metadata before the first Bazaar snapshot.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.interval_minutes < 1:
        raise ValueError("--interval-minutes must be at least 1.")

    if args.max_runs is not None and args.max_runs < 1:
        raise ValueError("--max-runs must be at least 1 when provided.")

    run_bazaar_scheduler(
        args.db,
        args.raw_dir,
        args.interval_minutes,
        args.max_runs,
        run_analysis=not args.skip_analysis,
        backtest_horizons=parse_horizons(args.backtest_horizons),
        refresh_metadata_first=args.refresh_metadata_first,
    )


if __name__ == "__main__":
    main()
