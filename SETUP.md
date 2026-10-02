# Setup

## Local (no external services)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env          # optional - every key has a default
sentinelai serve              # UI /, API /docs
```
Data lives in `data/sentinelai.db` (SQLite, created on first start).

## Enable AI research
Set `GROQ_API_KEY` (and optionally `SENTINEL_LLM_GROQ_MODEL`). Web search stays **off** unless you also set
`SENTINEL_LLM_WEB_SEARCH_ENABLED=true` (+ `TAVILY_API_KEY` for Tavily; DuckDuckGo needs no key). Requests with
`restrict_external_lookup: true` never trigger a search.

## Real sanctions data
```bash
sentinelai sanctions update   # downloads OFAC SDN (sdn.csv, alt.csv, add.csv) into data/lists/ofac
sentinelai screen "Some Name" --country IR
```
The bundled list is synthetic. Other formats can be supplied as JSON via `SENTINEL_RISK_SANCTIONS_LIST_FILE` (see `sentinelai/data/sanctions_demo.json`).

## PostgreSQL + Redis (production-like)
```bash
export DATABASE_URL=postgresql://user:pass@host:5432/sentinelai REDIS_URL=redis://host:6379/0
export SENTINEL_DB_AUTO_CREATE_TABLES=false
alembic upgrade head
sentinelai serve
```
Or `docker compose up -d` (migrations run on start).

## Authentication
```bash
export SENTINEL_ENVIRONMENT=production
export SENTINEL_API_KEYS="ops:admin:$(openssl rand -hex 24),desk:analyst:$(openssl rand -hex 24)"
```
Roles: `viewer` (read) < `analyst` (analyse, cases, alerts) < `admin` (audit entries). With no keys configured, production rejects
every protected request. `SENTINEL_API_PUBLIC_DEMO=true` opens a rate-limited, analysis-only, non-persisting demo.

## Choosing a regime
`SENTINEL_RISK_REGIME=IN_PMLA` (or per request `"regime": "IN_PMLA"`) switches thresholds, currency and STR/SAR rules.

## Development
```bash
make test lint evaluate docs-sync
```
