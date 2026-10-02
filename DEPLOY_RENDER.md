# Deploying on Render

1. **Blueprint**: New + → Blueprint → select this repo; Render reads `render.yaml` (Docker web service + free PostgreSQL).
2. **Secrets** (Dashboard → Environment): `GROQ_API_KEY` (optional), `SENTINEL_API_KEYS` (`name:role:key,...`), `TAVILY_API_KEY` (optional).
3. Defaults in the blueprint: migrations run on start, `SENTINEL_API_PUBLIC_DEMO=true` (unauthenticated, rate-limited, nothing persisted - turn it off for a private deployment),
   web search **off**.
4. Verify: `curl https://<service>.onrender.com/health` → `"status":"healthy"`; the UI is served at `/`.

## GitHub Pages front-end (optional)
`docs/` is a generated copy of `frontend/` that talks to the hosted API:
```bash
SENTINEL_PAGES_API=https://<service>.onrender.com make docs-sync   # then commit docs/
```
Enable Pages on the `main` branch, `/docs` folder. CI fails if `docs/` drifts from `frontend/`.

Notes: the free tier sleeps - the first request can take ~30 s, and the UI shows an explicit retry instead of a fake result.
Set `SENTINEL_API_CORS_ORIGINS='["https://<user>.github.io"]'` to restrict the API to your Pages origin.
