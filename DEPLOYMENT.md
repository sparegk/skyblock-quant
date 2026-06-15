# Deployment Notes

SkyBlock Quant currently deploys as two backend processes plus one static frontend:

- FastAPI web API
- scheduler worker for Bazaar collection, signal generation, and backtesting
- Vite frontend served by Vercel or another static host

## Backend

Recommended first host: Render, Railway, or Fly.

Render can use `render.yaml` from the repo root. The web service runs:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

The worker runs:

```bash
python -m app.collectors.scheduler
```

Required backend environment variables:

```bash
SKYBLOCK_QUANT_DATABASE_URL=postgresql://...
SKYBLOCK_QUANT_RAW_DIR=/var/data/raw
SKYBLOCK_QUANT_CORS_ORIGINS=https://your-frontend-domain.vercel.app
SKYBLOCK_QUANT_COLLECT_INTERVAL_MINUTES=5
SKYBLOCK_QUANT_BACKTEST_HORIZONS=next_snapshot,1h,6h,24h,7d
```

`/health` returns API status and database readiness. Use it as the platform health check.

## Database

Local development uses SQLite through `SKYBLOCK_QUANT_DB_PATH`.

Production should use managed Postgres through `SKYBLOCK_QUANT_DATABASE_URL`.
When this variable starts with `postgres://` or `postgresql://`, the API,
collector, signal engine, job logs, and backtests use Postgres. Keep
`SKYBLOCK_QUANT_DB_PATH` unset in production unless you intentionally want the
SQLite fallback.

## Frontend

Recommended first host: Vercel.

Build command:

```bash
npm run build
```

Output directory:

```bash
dist
```

Required frontend environment variable:

```bash
VITE_API_BASE_URL=https://your-backend-domain.onrender.com
```

For local development, keep:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
```
