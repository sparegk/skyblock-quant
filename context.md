# Context: Hypixel SkyBlock Market Prediction Project

## Project Idea

Build an event-driven market intelligence and signal engine for Hypixel SkyBlock items.

The system should help identify Bazaar or Auction House items that may be profitable to buy, hold, flip, or sell to NPCs. It should combine finance-style market analysis with computer science techniques such as APIs, data pipelines, time-series modeling, NLP, backtesting, and dashboard-based reporting.

This should not be an auto-trading bot. It should be an analytics and recommendation tool that gives signals, explanations, and risk estimates.

---

## Project Goal

Create a system that can answer questions like:

- Which Bazaar items are currently underpriced?
- Which items can be bought from Bazaar and sold to NPCs for immediate profit?
- Which items may rise in price because of current or future game updates?
- Which items are experiencing unusual volume, spread, or price movement?
- Which items have enough liquidity to make a trade realistic?
- Which signals have historically performed well after similar events?

---

## Core Product

The project should produce a ranked list of item opportunities.

Example output:

```text
Item: Enchanted Example Item
Signal: BUY / WATCH / AVOID
Confidence: 72%
Expected Move: +6% to +10% over 24h
Risk: Medium
Reason:
- Price is below recent average
- Volume is increasing
- Item was mentioned in a recent update
- Sell-side liquidity is low
- Similar past events caused price increases
Suggested Max Allocation: 5% of available coins
```

---

## Main Components

### 1. Market Data Collector

Collect recurring snapshots of Bazaar, Auction House, and item metadata.

Possible data fields:

```text
timestamp
item_id
item_name
bazaar_buy_price
bazaar_sell_price
buy_volume
sell_volume
buy_orders
sell_orders
spread
mid_price
npc_sell_price
auction_lowest_bin
auction_volume
auction_recent_sales
```

Primary data source should be official Hypixel API endpoints where possible.

Useful official API categories:

- Bazaar data
- SkyBlock items metadata
- Auctions
- Recently ended auctions
- SkyBlock news
- Mayor and election data
- Bingo data
- Fire sales

---

### 2. Deterministic Arbitrage Engine

This part does not need machine learning.

It should scan for cases where an item can be bought from the Bazaar and sold to an NPC for guaranteed or near-guaranteed profit.

Basic formula:

```text
expected_profit = npc_sell_price - bazaar_buy_cost - fees - risk_buffer
```

Rank opportunities by:

```text
profit_per_item
available_volume
expected_fill_probability
coins_per_hour
daily_npc_limit_risk
market_manipulation_risk
```

Important: this should only notify the user. It should not automate buying or selling in-game.

---

### 3. Predictive Investment Engine

This is the more advanced finance + CS part.

The model predicts whether an item is likely to rise or fall over a future time window.

Example prediction targets:

```text
Will this item rise by at least 5% in the next 1 hour?
Will this item rise by at least 10% in the next 24 hours?
Will this item outperform the average Bazaar market over the next 7 days?
Will this item crash after a temporary hype event?
```

Possible model types:

```text
Baseline rules:
- rolling z-score
- volume spike detection
- spread widening/narrowing
- momentum and mean reversion rules

Machine learning:
- logistic regression
- random forest
- XGBoost / LightGBM
- gradient boosting classifier
- time-series models after enough data is collected
```

Recommended starting model:

```text
LightGBM or XGBoost classifier
```

Reason: these models work well with structured tabular features, missing values, nonlinear relationships, and mixed market/event data.

---

## Features for the Model

### Price Features

```text
1h_return
6h_return
24h_return
7d_return
rolling_mean_price
rolling_price_z_score
rolling_volatility
max_drawdown
price_acceleration
```

### Liquidity Features

```text
buy_volume
sell_volume
buy_order_depth
sell_order_depth
number_of_buy_orders
number_of_sell_orders
spread
spread_percentage
order_book_imbalance
estimated_fill_probability
```

### Event Features

```text
mayor_active
mayor_candidate
election_phase
bingo_active
fire_sale_active
seasonal_event_active
patch_note_mention
alpha_update_mention
new_item_added
recipe_changed
drop_rate_changed
npc_price_changed
```

### Text/NLP Features

Use update posts, patch notes, or official news to detect item mentions and game-system changes.

Possible NLP features:

```text
item_name_mentioned
item_category_mentioned
update_sentiment
change_type
patch_importance_score
mention_count
recency_of_mention
```

Example change types:

```text
buff
nerf
recipe_change
drop_rate_change
npc_sell_price_change
new_collection
new crafting use
limited-time event
new mayor perk
```

### Risk Features

```text
low_liquidity_flag
high_spread_flag
possible_manipulation_flag
abnormal_volume_spike
thin_order_book
recent_crash
recent_pump
low_confidence_flag
```

---

## Backtesting

Backtesting is essential to make the project credible.

For every generated signal, store:

```text
signal_timestamp
item_id
signal_type
confidence
entry_price
exit_price_1h
exit_price_6h
exit_price_24h
exit_price_7d
max_drawdown
max_gain
realistic_fill_estimate
profit_after_fees
was_signal_successful
```

Useful metrics:

```text
precision
recall
win_rate
average_return
median_return
Sharpe-like ratio
max_drawdown
profit_factor
false_positive_rate
performance_by_item_category
performance_by_event_type
```

This turns the project from a simple alert bot into a real market prediction and evaluation system.

---

## Use of Bazaar Meta and SkyBlock Finance

Reference links:

- https://www.skyblock.bz/
- https://skyblock.finance/

These sites can make the project stronger as:

```text
competitive analysis
feature inspiration
UI/UX inspiration
benchmarking
sanity-checking signals
understanding existing market tools
```

They should not be used by copying proprietary rankings, scraping restricted data, or cloning the interface.

Safe and original use:

```text
Compare your generated signals against public market trackers.
Use them to understand what features already exist.
Use them to identify gaps your project can improve on.
Mention them as existing tools in the project writeup.
Build your own data pipeline and model.
```

Avoid:

```text
copying their UI
scraping premium or restricted pages
using their proprietary rankings as your own
training directly on their private signals
presenting their data as original
```

Original angle:

```text
Existing tools mostly track current Bazaar/Auction opportunities.
This project focuses on event-driven prediction, backtesting, explainable recommendations, and risk-adjusted signal generation.
```

---

## Possible Additional Data Sources

Potentially useful sources:

```text
Official Hypixel API
Hypixel SkyBlock news and patch notes
Hypixel forums
SkyBlock Wiki item data
CoflNet / SkyCofl historical auction and market data, if terms allow
```

Important: use official or permitted data sources whenever possible.

---

## System Architecture

Recommended stack:

```text
Backend:
- Python
- FastAPI
- PostgreSQL or TimescaleDB
- Redis for caching
- Celery or APScheduler for scheduled jobs

Data/ML:
- pandas
- numpy
- scikit-learn
- LightGBM or XGBoost
- MLflow or simple experiment tracking

Frontend:
- Next.js or React dashboard
- charts for price, volume, spread, and backtest results

Deployment:
- Docker
- GitHub Actions
- Railway, Render, Fly.io, or VPS
```

---

## Suggested Database Tables

```text
items
- item_id
- item_name
- category
- rarity
- npc_sell_price
- metadata_json

bazaar_snapshots
- timestamp
- item_id
- buy_price
- sell_price
- buy_volume
- sell_volume
- buy_orders
- sell_orders
- spread

auction_snapshots
- timestamp
- item_id
- lowest_bin
- median_price
- volume
- recent_sales

events
- event_id
- timestamp
- event_type
- title
- source_url
- text
- extracted_items_json

signals
- signal_id
- timestamp
- item_id
- signal_type
- confidence
- expected_return
- risk_score
- explanation_json

backtest_results
- signal_id
- horizon
- entry_price
- exit_price
- return
- max_drawdown
- success
```

---

## MVP Roadmap

### Phase 1: Data Collection

Build a collector that regularly stores Bazaar snapshots and item metadata.

Deliverables:

```text
working API collector
database schema
basic dashboard showing historical price and volume
```

### Phase 2: Arbitrage Scanner

Detect Bazaar-to-NPC opportunities.

Deliverables:

```text
ranked list of NPC arbitrage opportunities
profit and volume estimates
risk filters
dashboard view for high-profit opportunities
```

### Phase 3: Backtesting Framework

Track whether signals would have worked.

Deliverables:

```text
signal logging
future price evaluation
win-rate and return metrics
basic strategy report
```

### Phase 4: Event Intelligence

Add update/event awareness.

Deliverables:

```text
patch note parser
item mention extractor
event calendar
event impact analysis
```

### Phase 5: Predictive Model

Train the first machine learning model.

Deliverables:

```text
feature pipeline
train/test split by time
baseline model
LightGBM/XGBoost model
explainable signal output
```

### Phase 6: Dashboard

Make the system usable.

Deliverables:

```text
web dashboard
watchlist alerts
risk-adjusted signal rankings
```

---

## Academic Framing

This project can be presented as a finance and computer science project.

Finance concepts:

```text
market efficiency
arbitrage
liquidity
spread
volatility
event studies
risk-adjusted returns
portfolio allocation
market manipulation detection
```

Computer science concepts:

```text
API integration
data engineering
time-series analysis
machine learning
natural language processing
backtesting
database design
dashboard development
software architecture
```

Possible project title:

```text
Event-Driven Market Prediction and Arbitrage Detection in a Virtual Economy
```

Alternative title:

```text
Explainable Trading Signals for Hypixel SkyBlock's Bazaar and Auction Markets
```

---

## Important Safety and Compliance Notes

The project should remain an analytics and notification tool.

Do:

```text
provide recommendations
send alerts
show historical analysis
backtest strategies
explain risk
respect API limits
cache responses
attribute third-party data sources
```

Do not:

```text
automate in-game buying or selling
bypass API rate limits
exploit bugs
use unauthorized scraping
copy other sites' proprietary data
misrepresent third-party data as your own
```

Add a disclaimer:

```text
This project is not affiliated with, endorsed by, or sponsored by Hypixel.
It is an educational analytics project for studying virtual market behavior.
```

---

## Recommended Unique Value Proposition

The project should not try to be just another Bazaar tracker.

The strongest unique value is:

```text
event-driven prediction
explainable recommendations
risk-adjusted opportunity ranking
backtested signal performance
dashboard-based monitoring
```

One-sentence pitch:

```text
A predictive market intelligence system for Hypixel SkyBlock that detects arbitrage opportunities and event-driven investment signals using Bazaar/Auction data, game update intelligence, and backtested machine learning models.
```

---

## First Build Target

The first useful version should do this:

```text
1. Pull Bazaar and item data.
2. Store time-series snapshots.
3. Detect Bazaar-to-NPC profit opportunities.
4. Rank opportunities by profit, volume, and risk.
5. Display high-priority opportunities in the dashboard.
6. Log every signal for later backtesting.
```

This gives a working project quickly while creating the dataset needed for the more advanced predictive model.
