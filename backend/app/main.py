"""FastAPI app for the SkyBlock Quant backend."""

from __future__ import annotations

from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.database import (
    BACKTEST_HORIZONS,
    MAX_NPC_ARBITRAGE_MARGIN,
    MAX_MOMENTUM_SINGLE_JUMP,
    MIN_INVESTMENT_SLOT_VALUE,
    MIN_INVESTMENT_STACK_SIZE,
    MIN_INVESTMENT_UNIT_PRICE,
    MIN_MOMENTUM_GAIN,
    MIN_MOMENTUM_OBSERVED_SNAPSHOTS,
    MIN_MOMENTUM_ORDERS,
    MIN_MOMENTUM_RISING_STEPS,
    MIN_MOMENTUM_VOLUME,
    MIN_NPC_ARBITRAGE_PROFITABLE_SNAPSHOTS,
    MIN_NPC_ARBITRAGE_SELL_ORDERS,
    MIN_NPC_ARBITRAGE_SELL_VOLUME,
    MOMENTUM_HISTORY_SNAPSHOTS,
    NPC_ARBITRAGE_HISTORY_SNAPSHOTS,
    evaluate_signal_backtests,
    get_backtest_results,
    get_backtest_summary,
    get_database_status,
    get_investment_momentum,
    get_latest_job_runs,
    get_latest_snapshot,
    get_latest_signals,
    get_market_summary,
    get_npc_arbitrage,
    get_npc_arbitrage_detail,
    get_occurrence_investments,
    get_top_spreads,
    search_items,
)
from app.settings import get_cors_origins


app = FastAPI(title="SkyBlock Quant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def refresh_backtests_on_startup(limit: int = 1000) -> dict[str, int]:
    """Evaluate all supported backtest horizons when the API starts."""
    evaluated: dict[str, int] = {}
    for horizon in BACKTEST_HORIZONS:
        evaluated[horizon] = evaluate_signal_backtests(
            limit=limit,
            horizon=horizon,
            refresh_existing=True,
        )

    return evaluated


@app.on_event("startup")
def startup_refresh_backtests() -> None:
    refresh_backtests_on_startup()


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "database": get_database_status(),
    }


@app.get("/api/bazaar/summary")
def bazaar_summary() -> dict[str, object]:
    return get_market_summary()


@app.get("/api/bazaar/latest")
def bazaar_latest(
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> dict[str, object]:
    return {"items": get_latest_snapshot(limit)}


@app.get("/api/bazaar/items")
def bazaar_items(
    search: Annotated[str, Query(max_length=80)] = "",
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> dict[str, object]:
    if not search.strip():
        return {"items": get_latest_snapshot(limit)}

    return {"items": search_items(search.strip(), limit)}


@app.get("/api/bazaar/top-spreads")
def bazaar_top_spreads(
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> dict[str, object]:
    return {"items": get_top_spreads(limit)}


@app.get("/api/arbitrage/npc")
def npc_arbitrage(
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    min_sell_volume: Annotated[int, Query(ge=0, le=10_000_000)] = (
        MIN_NPC_ARBITRAGE_SELL_VOLUME
    ),
    min_sell_orders: Annotated[int, Query(ge=0, le=10_000)] = (
        MIN_NPC_ARBITRAGE_SELL_ORDERS
    ),
    max_profit_margin: Annotated[float, Query(gt=0, le=10)] = MAX_NPC_ARBITRAGE_MARGIN,
    history_snapshots: Annotated[int, Query(ge=1, le=100)] = NPC_ARBITRAGE_HISTORY_SNAPSHOTS,
    min_profitable_snapshots: Annotated[int, Query(ge=1, le=100)] = (
        MIN_NPC_ARBITRAGE_PROFITABLE_SNAPSHOTS
    ),
) -> dict[str, object]:
    return {
        "items": get_npc_arbitrage(
            limit=limit,
            min_sell_volume=min_sell_volume,
            min_sell_orders=min_sell_orders,
            max_profit_margin=max_profit_margin,
            history_snapshots=history_snapshots,
            min_profitable_snapshots=min_profitable_snapshots,
        )
    }


@app.get("/api/arbitrage/npc/{item_id}")
def npc_arbitrage_detail(
    item_id: str,
    history_snapshots: Annotated[int, Query(ge=1, le=100)] = NPC_ARBITRAGE_HISTORY_SNAPSHOTS,
) -> dict[str, object]:
    item = get_npc_arbitrage_detail(item_id, history_snapshots)

    if item is None:
        raise HTTPException(status_code=404, detail="NPC arbitrage item not found.")

    return {"item": item}


@app.get("/api/investments/momentum")
def investment_momentum(
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    history_snapshots: Annotated[int, Query(ge=2, le=100)] = MOMENTUM_HISTORY_SNAPSHOTS,
    min_observed_snapshots: Annotated[int, Query(ge=2, le=100)] = (
        MIN_MOMENTUM_OBSERVED_SNAPSHOTS
    ),
    min_volume: Annotated[int, Query(ge=0, le=100_000_000)] = MIN_MOMENTUM_VOLUME,
    min_orders: Annotated[int, Query(ge=0, le=100_000)] = MIN_MOMENTUM_ORDERS,
    min_gain: Annotated[float, Query(ge=0, le=10)] = MIN_MOMENTUM_GAIN,
    max_single_jump: Annotated[float, Query(ge=0, le=10)] = MAX_MOMENTUM_SINGLE_JUMP,
    min_rising_steps: Annotated[int, Query(ge=1, le=100)] = MIN_MOMENTUM_RISING_STEPS,
    min_unit_price: Annotated[float, Query(ge=0, le=1_000_000_000)] = (
        MIN_INVESTMENT_UNIT_PRICE
    ),
    min_stack_size: Annotated[int, Query(ge=1, le=64)] = MIN_INVESTMENT_STACK_SIZE,
    min_slot_value: Annotated[float, Query(ge=0, le=1_000_000_000)] = (
        MIN_INVESTMENT_SLOT_VALUE
    ),
) -> dict[str, object]:
    return {
        "items": get_investment_momentum(
            limit=limit,
            history_snapshots=history_snapshots,
            min_observed_snapshots=min_observed_snapshots,
            min_volume=min_volume,
            min_orders=min_orders,
            min_gain=min_gain,
            max_single_jump=max_single_jump,
            min_rising_steps=min_rising_steps,
            min_unit_price=min_unit_price,
            min_stack_size=min_stack_size,
            min_slot_value=min_slot_value,
        )
    }


@app.get("/api/investments/occurrences")
def occurrence_investments(
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> dict[str, object]:
    return {"items": get_occurrence_investments(limit=limit)}


@app.get("/api/signals/latest")
def latest_signals(
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    refresh: bool = True,
) -> dict[str, object]:
    return {"signals": get_latest_signals(limit=limit, refresh=refresh)}


@app.post("/api/backtests/evaluate")
def evaluate_backtests(
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    horizon: Annotated[str, Query(max_length=20)] = "next_snapshot",
    refresh_existing: bool = True,
) -> dict[str, object]:
    try:
        evaluated = evaluate_signal_backtests(
            limit=limit,
            horizon=horizon,
            refresh_existing=refresh_existing,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {
        "evaluated": evaluated,
        "horizon": horizon,
        "refreshed_existing": refresh_existing,
    }


@app.post("/api/backtests/evaluate-all")
def evaluate_all_backtests(
    limit: Annotated[int, Query(ge=1, le=1000)] = 1000,
    refresh_existing: bool = True,
) -> dict[str, object]:
    evaluated: dict[str, int] = {}

    for horizon in BACKTEST_HORIZONS:
        evaluated[horizon] = evaluate_signal_backtests(
            limit=limit,
            horizon=horizon,
            refresh_existing=refresh_existing,
        )

    return {
        "evaluated": evaluated,
        "total_evaluated": sum(evaluated.values()),
        "refreshed_existing": refresh_existing,
    }


@app.get("/api/backtests/summary")
def backtest_summary() -> dict[str, object]:
    return get_backtest_summary()


@app.get("/api/backtests/results")
def backtest_results(
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> dict[str, object]:
    return {"results": get_backtest_results(limit=limit)}


@app.get("/api/jobs/latest")
def latest_jobs(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, object]:
    return {"jobs": get_latest_job_runs(limit=limit)}
