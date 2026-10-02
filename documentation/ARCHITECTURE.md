# Architecture & design decisions

## 1. Evidence → score
Every detector emits `Signal(code, category, weight p, description, evidence, typology, floor)`.
`weight` is the probability-like strength of that evidence alone. Signals fuse as

```
score = 100 · (1 − Π (1 − pᵢ·dᵢ))        dᵢ = 0.6^rank within its category (correlated evidence discount)
```
With `wᵢ = −ln(1−pᵢ)` this equals `1 − exp(−Σ wᵢ)`, so each signal owns exactly `wᵢ/Σw` of the score (largest-remainder
rounding makes the integer waterfall sum to the score). Properties: monotone, saturating (ten weak signals ≠ 300 points),
exactly explainable, and cheap to compute counterfactuals for (`score without signal X`).
**Policy floors** (verified sanctions MATCH ≥ 95; listed PEP ≥ medium so EDD is triggered, per FATF R12) are applied last and shown as
their own waterfall entry. Alternatives considered: additive-clamp (kept as a benchmark baseline - similar accuracy, no saturation,
no clean decomposition) and a learned model (roadmap; it would enter as one more capped evidence source).

## 2. The LLM is advisory
Research agents return a JSON finding; it is parsed, validated, and converted into **unverified** `AI_*` signals. `combine_with_ai`
bounds the total uplift (`SENTINEL_LLM_MAX_UPLIFT`, default 15) by scaling AI weights - the waterfall still sums to the score - and
by construction `final ≥ deterministic`. A verified sanctions match can only come from the list, never from the web. If the
engine already reached a conclusive block, research is skipped (cost/latency). Failure modes are explicit: `disabled`,
`no_api_key`, `partial`, `failed`.

## 3. Sanctions policy
Normalise (accents, punctuation, corporate suffixes, titles) → candidate lookup through an inverted index (3-char token prefix
and phonetic-skeleton keys) → score with a token-aligned length-weighted F1 of Jaro-Winkler with a voicing-folded consonant
skeleton as a secondary channel, plus containment and short-name caps. Outcomes: `MATCH` (floor) only for exact entity names
(or exact individual names with ≥ 3 tokens / country corroboration); fuzzy hits are `STRONG_POTENTIAL` (higher weight when a
country corroborates) or `POTENTIAL` - routed to an analyst, never auto-blocked. Calibrate with `sentinelai evaluate` (variant
recall / random-name FPR), as OFAC advises testing screening tools routinely.

## 4. Graph
`engine/graph.py` is pure functions over directed time-stamped edges. Edges come from the request (history with
counterparties, `network_transactions`) and from `graph_edges` persisted by earlier analyses (2-hop neighbourhood, 30 days).
Cycle search is time-ordered, amount-conserving and budget-bounded (dense graphs terminate). The current transaction's direction
is explicit (`direction: IN|OUT`) - guessing it produced phantom round-trips in an early version.

## 5. Persistence & atomicity
SQLAlchemy 2.0 async, portable types (SQLite dev / PostgreSQL prod), Alembic migration verified equal to the ORM in a test.
An analysis runs in three phases - short read (graph), the pipeline (possibly a minute of LLM calls, **no DB transaction held**),
short write (alerts, case, audit entry, analysis, edges in one transaction). SQLite uses `BEGIN IMMEDIATE` and explicit
transaction control so rollbacks inside SAVEPOINTs really roll back (pysqlite quirk, covered by a test).

## 6. Audit chain
`hash_n = SHA-256(hash_{n-1} | canonical({seq, timestamp, actor, action, entity, payload}))`. `verify()` recomputes the chain and
reports the first inconsistent row (modified content, forged-and-rehashed content, gap, reorder). Anchor `GET /audit/head` outside
the database to detect a full-chain rewrite.

## 7. Regimes
`core/regimes.py` encodes threshold, currency, report names and deadline arithmetic (calendar vs working days) for US BSA,
India PMLA and EU AMLD. Amounts are converted through USD with indicative, overridable FX rates.
