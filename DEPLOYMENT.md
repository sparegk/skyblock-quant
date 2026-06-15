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
SKYBLOCK_QUANT_DB_PATH=/var/data/skyblock_quant.db
SKYBLOCK_QUANT_RAW_DIR=/var/data/raw
SKYBLOCK_QUANT_CORS_ORIGINS=https://your-frontend-domain.vercel.app
SKYBLOCK_QUANT_COLLECT_INTERVAL_MINUTES=5
SKYBLOCK_QUANT_BACKTEST_HORIZONS=next_snapshot,1h,6h,24h
```

`/health` returns API status and database readiness. Use it as the platform health check.

## Database

Local development uses SQLite through `SKYBLOCK_QUANT_DB_PATH`.

`SKYBLOCK_QUANT_DATABASE_URL` is reserved for the Postgres migration path. If it is set to a `postgres://` or `postgresql://` URL today, the backend reports Postgres as configured but does not run SQLite-specific queries against it. The next infrastructure milestone is migrating the SQL layer to Postgres-compatible execution.

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
