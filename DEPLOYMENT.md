# Deployment Notes

SkyBlock Quant can deploy in two modes.

The no-card deployment path is:

- Supabase Postgres
- GitHub Actions scheduled collector
- Vercel FastAPI backend
- Vercel static frontend

A full backend deployment can still use two backend processes plus one static frontend:

- FastAPI web API
- scheduler worker for Bazaar collection, signal generation, and backtesting
- Vite frontend served by Vercel or another static host

## No-Card Deployment

Use this when Render/Railway/Fly asks for billing details.

### Database

Create a Supabase project and copy the Postgres connection string. Add it to
GitHub repository secrets as:

```bash
SKYBLOCK_QUANT_DATABASE_URL=postgresql://...
```

The workflow in `.github/workflows/collect-market-data.yml` can be started
manually from the GitHub Actions tab. It runs:

```bash
python -m app.collectors.scheduler --max-runs 1
```

For the first run, use the manual workflow input `refresh_metadata=true` so the
`items` table is populated before Bazaar snapshots are analyzed.

If you are staying local-only, do not add the GitHub secret and do not run this
workflow. The local backend will use SQLite through `SKYBLOCK_QUANT_DB_PATH`.

### Frontend

Deploy the backend as a separate Vercel project first:

- Root directory: `backend`
- Environment variables:

```bash
SKYBLOCK_QUANT_DATABASE_URL=postgresql://...
SKYBLOCK_QUANT_CORS_ORIGINS=https://your-frontend-domain.vercel.app
SKYBLOCK_QUANT_REFRESH_BACKTESTS_ON_STARTUP=false
```

Vercel uses `backend/index.py` as the FastAPI entrypoint.

Deploy `frontend` to Vercel.

Build command:

```bash
npm run build
```

Output directory:

```bash
dist
```

Set the React API URL to the backend Vercel deployment:

```bash
VITE_API_BASE_URL=https://your-backend-project.vercel.app
```

## Full Backend Deployment

Recommended hosts: Render, Railway, or Fly.

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

## Production Database

Local development uses SQLite through `SKYBLOCK_QUANT_DB_PATH`.

Production should use managed Postgres through `SKYBLOCK_QUANT_DATABASE_URL`.
When this variable starts with `postgres://` or `postgresql://`, the API,
collector, signal engine, job logs, and backtests use Postgres. Keep
`SKYBLOCK_QUANT_DB_PATH` unset in production unless you intentionally want the
SQLite fallback.

## Full Frontend Deployment

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
