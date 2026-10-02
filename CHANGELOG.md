# Changelog

## 2.0.0

A ground-up rework driven by a full code review. Everything the README claims is now implemented, tested or measured.

### Correctness
- **Sanctions/PEP now reach the score.** Real list screening (fuzzy, alias- and transliteration-aware, OFAC SDN loader) replaces five hard-coded strings that the orchestrator never called.
- **Scoring rebuilt.** Noisy-OR evidence fusion with per-category correlation discount; the waterfall sums exactly to the score. Removed the silent +30 baseline (an unparsed LLM answer defaulted to 50 -> capped at 30) and the double counting of factors + component scores.
- **LLM output is parsed, not scraped.** Agents return JSON; `"Confidence score 0.85. Risk score: 70"` used to score 0. Unparsable answers are excluded, never treated as 0, and junk "risk codes" (`CRITICAL`, `WIRE_TRANSFER`) are gone.
- **AI can raise a score, never lower it** (hard, configurable cap) - prompt injection cannot launder a risky transaction.
- Unknown account age no longer means "brand new" in one endpoint and "365 days" in another (`account_age_days: null`).
- `privacy_coin` was read by the crypto logic but missing from the schema (always dropped); fixed.
- One engine and one set of thresholds for `/analyze` and `/analyze/rules` (previously 80/60/40 vs 95/80/60); structuring uses the regime threshold and currency; jurisdiction data lives in one place.
- PEP substring matching ("Kingston", "Viking", "General Manager") replaced with anchored role patterns.
- Fake case objects/IDs and "SAR_FILED" for merely *generated* drafts are gone; batch results report failures with their index.
- Timezone-aware timestamps throughout (mixed naive/aware input no longer crashes).

### Platform
- Real persistence (SQLite default, PostgreSQL in prod), Alembic migration that equals the ORM (tested), atomic rollbacks on SQLite, short transactions around LLM calls.
- Case state machine, alert triage, tamper-evident hash-chained audit log, transaction graph that remembers earlier analyses.
- LangGraph `StateGraph` with conditional routing (previously plain `asyncio`).
- `/metrics`, real health checks, Redis as an optional shared cache / rate-limit store.

### Security & privacy
- API-key RBAC, fail-closed in production, public-demo mode; the rate limiter can no longer be bypassed by rotating a fake key and works across workers with Redis.
- Web search is opt-in, queries are redacted, results are framed as untrusted data, confidential subjects are never searched (tipping-off), prompt injection is sanitised and *scored*.
- Generic 500 responses with an error id; CORS no longer combines `*` with credentials; unused JWT config removed.

### Configuration & deployment
- `.env` copied from `.env.example` no longer crashes startup; nested settings read `.env`.
- `pyproject.toml` is the single dependency source (the old install was missing `langchain-tavily`/`ddgs`); Python >= 3.11.
- Compose/Dockerfile port mismatch fixed; unused Neo4j removed; Grafana provisioning added; Render blueprint updated.
- Frontend: no silent simulation; one source for `frontend/` and `docs/`; landing-page numbers come from the benchmark.

### Logging
- Structured `extra=` fields and request ids actually reach the JSON logs; no double-prefixed logger names; no ANSI codes in file logs.
