"""Prometheus metrics (previously configured in prometheus.yml but never exposed)."""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

registry = CollectorRegistry()

ANALYSES = Counter("sentinelai_analyses_total", "Analyses completed", ["risk_level", "mode"], registry=registry)
ANALYSIS_LATENCY = Histogram(
    "sentinelai_analysis_seconds", "End-to-end analysis latency", ["mode"], registry=registry,
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120),
)
SIGNALS = Counter("sentinelai_signals_total", "Detection signals fired", ["code"], registry=registry)
SANCTIONS_HITS = Counter("sentinelai_sanctions_hits_total", "Sanctions screening hits", ["level"], registry=registry)
REPORTS_REQUIRED = Counter("sentinelai_reports_required_total", "Analyses requiring a SAR/STR", registry=registry)
CASES_CREATED = Counter("sentinelai_cases_created_total", "Cases created", registry=registry)
LLM_CALLS = Counter("sentinelai_llm_agent_runs_total", "LLM research-agent runs", ["agent", "outcome"], registry=registry)
SEARCH_QUERIES = Counter("sentinelai_web_search_queries_total", "Guarded web-search queries", ["outcome"], registry=registry)
HTTP_REQUESTS = Counter("sentinelai_http_requests_total", "HTTP requests", ["method", "route", "status"], registry=registry)
HTTP_LATENCY = Histogram("sentinelai_http_request_seconds", "HTTP latency", ["route"], registry=registry)
AUDIT_ENTRIES = Gauge("sentinelai_audit_entries", "Audit chain length (updated on verify/head)", registry=registry)


def render() -> tuple[bytes, str]:
    return generate_latest(registry), CONTENT_TYPE_LATEST
