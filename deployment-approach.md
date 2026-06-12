# Deployment and Product Approach for the Hypixel SkyBlock Market Intelligence Project

## Recommended Product Format

The best version of this project should be a **web dashboard**.

The dashboard is where the serious analytics, modeling, charts, and backtesting live.  
The Discord bot is where the project becomes useful in real time by sending alerts and letting users quickly query signals.

The project should not be only a Discord bot and should not be only a simple Bazaar tracker. The strongest version is a full market intelligence platform.

---

## High-Level Architecture

```text
Hypixel API / update sources
        ↓
Scheduled data collector
        ↓
PostgreSQL / TimescaleDB
        ↓
Feature engineering + signal engine
        ↓
Backtesting + model evaluation
        ↓
FastAPI backend
        ↓
Next.js dashboard
```

Simplified version:

```text
Data collectors → Database → Signal engine/model → API → Dashboard
```

The project should feel like a **Bloomberg Terminal / Robinhood / quant dashboard for Hypixel SkyBlock**, not a generic flip website.

---

# How the Project Should Look

## 1. Main Dashboard Page

The dashboard homepage should give a quick overview of the current market.

It should show:

```text
Top Buy Signals
Top NPC Arbitrage Opportunities
Market Movers
High-Risk / Manipulated Items
Recent Event-Based Signals
```

Example layout:

```text
-------------------------------------------------
SkyBlock Market Intelligence

Portfolio/Watchlist Value: 125M coins
Active Signals: 14
High Confidence Signals: 3
NPC Arbitrage Opportunities: 7
Market Risk: Medium
-------------------------------------------------

Top Signals

Item                  Signal   Confidence   Expected Move   Risk
Enchanted Iron         BUY       78%          +6.5% / 24h     Medium
Recombobulator 3000    WATCH     65%          +4.2% / 6h      High
Enchanted Redstone     BUY       72%          +8.1% / 24h     Low
```

Each row should be clickable and lead to a detailed item page.

---

## 2. Item Detail Page

When a user clicks an item, the page should explain why the system generated the signal.

Example:

```text
Item: Enchanted Redstone
Signal: BUY
Confidence: 72%
Expected Move: +8.1% over 24h
Risk: Low-Medium

Reason:
- 24h volume is 2.4x above average
- Buy pressure increased over the last 3 snapshots
- Spread is narrowing
- Item was mentioned in a recent update/event
- Similar historical events produced positive returns
```

Useful charts:

```text
price over time
volume over time
spread over time
buy/sell order imbalance
signal history
```

This page is important because it makes the project **explainable**, not just “AI says buy.”

---

## 3. NPC Arbitrage Page

This page should scan for deterministic profit opportunities.

Example:

```text
Item                  Bazaar Cost   NPC Sell Price   Profit/Item   Volume   Risk
Example Item           97 coins       100 coins        +3 coins      12,000   Low
Another Item           430 coins      450 coins        +20 coins     800      Medium
```

Useful filters:

```text
minimum profit
minimum volume
maximum risk
hide low-liquidity items
hide manipulated items
```

This is a strong first feature because it provides immediate usefulness before the machine learning model is mature.

---

## 4. Event Intelligence Page

This is one of the most original parts of the project.

It should connect game updates and events to item price movements.

Example:

```text
Event: New Farming Update

Detected Items:
- Enchanted Seeds
- Jacob's Tickets
- Farming tools

Predicted Impact:
- Enchanted Seeds: Bullish
- Jacob's Tickets: Bullish
- Farming tools: Watch

Historical Similarity:
Past farming-related updates caused related items to rise 5%–18% within 24h.
```

This part turns the project into a finance-style **event study** system.

---

## 5. Backtesting Page

Backtesting is what makes the project academically and technically serious.

The backtesting page should show whether the generated signals actually worked.

Example:

```text
Model Performance

Total Signals: 1,248
Win Rate: 61.4%
Average 24h Return: +3.2%
Median 24h Return: +1.1%
Max Drawdown: -12.7%
Best Category: Mining Items
Worst Category: Cosmetic/Event Items
```

Also show:

```text
signal performance by confidence level
performance by item category
performance by event type
performance during high volatility
```

This is the difference between a cool app and a real predictive modeling project.

---


# Recommended Deployment Approach

For a college project, the best deployment should be simple enough to manage but professional enough to show real software engineering ability.

## Recommended Stack

```text
Frontend:
- Next.js
- React
- Tailwind CSS
- Recharts or lightweight charting library

Backend:
- Python
- FastAPI

Database:
- PostgreSQL
- TimescaleDB extension if possible

Background Jobs:
- Celery, APScheduler, or cron workers

Cache:
- Redis

Machine Learning:
- pandas
- numpy
- scikit-learn
- LightGBM or XGBoost


Deployment:
- Docker
```

---

## Best Deployment Option for This Project

Use a managed split deployment:

```text
Frontend:
Vercel

Backend/API:
Render, Railway, or Fly.io

Database:
Supabase, Neon, Railway Postgres, or managed PostgreSQL

Redis:
Upstash or platform Redis

Discord Bot:
Same backend service or a separate worker service
```

Architecture:

```text
Vercel
  └── Next.js dashboard

Render / Railway / Fly.io
  ├── FastAPI backend
  ├── scheduled data collector
  ├── model/signal worker
  └── Discord bot

Managed PostgreSQL
  └── stores item prices, snapshots, signals, and backtests

Redis
  └── caching and job queue
```

This is the best first deployment approach because it is easier than managing your own VPS but still looks professional.

---

## Alternative Deployment Option: VPS

If you want full control, you can deploy everything on one VPS with Docker Compose.

```text
VPS
├── Docker Compose
│   ├── frontend
│   ├── backend
│   ├── worker
│   │   ├── postgres
│   └── redis
```

This is more realistic from an infrastructure perspective, but it is harder to maintain.

For the first serious version, use the managed split deployment.  
For a later version, move to a VPS or Kubernetes only if you actually need the control.

---

# Best Build Order

Do **not** start with the machine learning model.

The biggest mistake would be building an ML model before you have enough clean historical data. Start with the data pipeline and signal logging.

---

## Phase 1: Data Collector

Build this first:

```text
Fetch Bazaar data every few minutes
Fetch item metadata
Store snapshots in PostgreSQL
Create basic price history charts
```

Deliverable:

```text
A dashboard where you can search an item and see price/volume history.
```

---

## Phase 2: NPC Arbitrage Scanner

Build deterministic profit detection.

Basic idea:

```text
bazaar_buy_price < npc_sell_price
```

Add risk filters:

```text
minimum volume
minimum profit
spread filter
manipulation filter
```

Deliverable:

```text
A live NPC arbitrage page.
```

This gives you a useful project early.

---

## Phase 3: Signal Engine Without ML

Use rules first.

Possible rule-based signals:

```text
volume spike
price breakout
spread narrowing
buy/sell imbalance
price below moving average
event mention detected
```

Deliverable:

```text
A ranked signal list with explanations.
```

This becomes your baseline model.

---

## Phase 4: Backtesting

Log every signal and check what happened after:

```text
1 hour
6 hours
24 hours
7 days
```

Deliverable:

```text
Win rate, average return, risk, and false positive rate.
```

This is essential before adding ML.

---

## Phase 5: Predictive Model

Only after you have enough historical data, train models such as:

```text
Logistic regression baseline
Random forest
LightGBM
XGBoost
```

Example prediction target:

```text
Will the item rise by more than 5% in the next 24 hours?
```

Deliverable:

```text
Model confidence score + explainable signal reasons.
```

---

# What the Final Project Should Be Called

Possible names:

```text
SkyBlock Quant
Bazaar Signal Engine
SkyBlock Market Intelligence
Hypixel Market Radar
Bazaar Alpha
SkyBlock Event Trading Lab
```

Recommended name:

```text
SkyBlock Market Intelligence
```

It sounds serious and not like a simple flip calculator.

---

# The Best Project Identity

Do not describe it as:

```text
A bot that tells me what to buy.
```

Describe it as:

```text
An event-driven market intelligence platform for a virtual economy that detects arbitrage opportunities, predicts item price movement, backtests signals, and delivers explainable alerts through a dashboard and Discord bot.
```

That sounds better for school, GitHub, and interviews.

---

# Final Recommendation

Build it as:

```text
1. A web dashboard for analysis.
3. A backend signal engine.
4. A historical database.
5. A backtesting system.
6. A predictive model after enough data exists.
```

The strongest MVP is:

```text
Live Bazaar data collector
NPC arbitrage scanner
Signal dashboard
Signal logging
Backtesting results
```

Then add machine learning once you have real historical data.

This gives you a project that is useful immediately and still has a clear path toward real predictive modeling.
