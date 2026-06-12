"""FastAPI app for the SkyBlock Quant backend."""

from __future__ import annotations

from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.database import (
    MAX_NPC_ARBITRAGE_MARGIN,
    MIN_NPC_ARBITRAGE_PROFITABLE_SNAPSHOTS,
    MIN_NPC_ARBITRAGE_SELL_ORDERS,
    MIN_NPC_ARBITRAGE_SELL_VOLUME,
    NPC_ARBITRAGE_HISTORY_SNAPSHOTS,
    get_latest_snapshot,
    get_market_summary,
    get_npc_arbitrage,
    get_npc_arbitrage_detail,
    get_top_spreads,
    search_items,
)


app = FastAPI(title="SkyBlock Quant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


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
