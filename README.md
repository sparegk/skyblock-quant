# SkyBlock Quant

SkyBlock Quant is a market intelligence project for Hypixel SkyBlock. The goal is to collect Bazaar and Auction House data, find useful trading signals, and explain why an item may be worth buying, watching, or avoiding.

This project is not an auto-trading bot. It is an educational analytics tool for studying a virtual economy.

## Project Goals

- Track Hypixel SkyBlock market data over time
- Detect Bazaar-to-NPC arbitrage opportunities
- Rank items by profit, volume, risk, and confidence
- Generate explainable buy, watch, or avoid signals
- Backtest signals to see if they worked historically

## Main Features

### Market Data Collection

The system will collect recurring snapshots from official Hypixel API data where possible, including:

- Bazaar prices
- Buy and sell volume
- Order counts
- Item metadata
- Auction House data
- SkyBlock news and event information

### NPC Arbitrage Scanner

The first useful feature is a scanner that checks whether an item can be bought from the Bazaar and sold to an NPC for profit.

It will rank opportunities using:

- Profit per item
- Available volume
- Spread
- Liquidity
- Risk of manipulation

### Signal Engine

The signal engine will look for items that may be underpriced or moving unusually.

Example signals:

- `BUY`
- `WATCH`
- `AVOID`

Each signal should include a reason, such as:

- Price is below its recent average
- Volume is increasing
- Spread is narrowing
- Item was mentioned in a recent update
- Similar past events caused price movement

### Backtesting

Every signal should be saved and checked later to see if it was correct.

The project will track results such as:

- Win rate
- Average return
- Best and worst item categories
- False positives
- Risk and drawdown

This makes the project more than just a price tracker. It shows whether the strategy actually works.

### Dashboard

The main product should be a web dashboard for viewing market data, signals, and backtesting results.

The dashboard should include:

- Top buy signals
- NPC arbitrage opportunities
- Market movers
- Item detail pages
- Price and volume charts
- Backtesting results

## Planned Tech Stack

- Python
- FastAPI
- PostgreSQL
- Redis
- pandas
- scikit-learn
- LightGBM or XGBoost
- Next.js
- React
- Tailwind CSS
- Docker

## Build Plan

1. Build a Bazaar data collector
2. Store historical market snapshots
3. Create basic price and volume charts
4. Add the NPC arbitrage scanner
5. Log generated signals
6. Add backtesting results
7. Build rule-based signals
8. Add machine learning after enough data has been collected

## Current Implementation

The first version of the Bazaar data collector has been added.

Run it with:

```bash
py backend/app/collectors/bazaar_collector.py
```

The collector will:

- Fetch live Bazaar data from the Hypixel API
- Save a raw JSON snapshot in `data/raw`
- Save cleaned product rows in `data/skyblock_quant.db`

The generated database and raw snapshots are ignored by Git because they are local data files.

To keep collecting data every few minutes, run:

```bash
py backend/app/collectors/scheduler.py --interval-minutes 5
```

Stop the scheduler with `Ctrl+C`.

To test the scheduler once without leaving it running, use:

```bash
py backend/app/collectors/scheduler.py --interval-minutes 5 --max-runs 1
```

The Vite frontend has also been started.

Run it with:

```bash
cd frontend
npm install
npm run dev
```

## Project Status

This project now has a working Bazaar data collector, a simple scheduler for recurring snapshots, and a starter Vite dashboard. The next step is to connect the frontend to a backend API so the dashboard can display real snapshot data.

## Disclaimer

This project is not affiliated with, endorsed by, or sponsored by Hypixel. It is an educational project for analyzing market behavior in Hypixel SkyBlock.
