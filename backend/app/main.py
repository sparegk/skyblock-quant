"""FastAPI app for the SkyBlock Quant backend."""

from __future__ import annotations

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from app.database import (
    get_latest_snapshot,
    get_market_summary,
    get_npc_arbitrage,
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
    limit: int = Query(default=25, ge=1, le=100),
) -> dict[str, object]:
    return {"items": get_latest_snapshot(limit)}


@app.get("/api/bazaar/items")
def bazaar_items(
    search: str = Query(default="", max_length=80),
    limit: int = Query(default=25, ge=1, le=100),
) -> dict[str, object]:
    if not search.strip():
        return {"items": get_latest_snapshot(limit)}

    return {"items": search_items(search.strip(), limit)}


@app.get("/api/bazaar/top-spreads")
def bazaar_top_spreads(
    limit: int = Query(default=25, ge=1, le=100),
) -> dict[str, object]:
    return {"items": get_top_spreads(limit)}


@app.get("/api/arbitrage/npc")
def npc_arbitrage(
    limit: int = Query(default=25, ge=1, le=100),
) -> dict[str, object]:
    return {"items": get_npc_arbitrage(limit)}
