"""Bundled demo scenarios with timestamps resolved relative to *now* (so demos never go stale)."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from sentinelai.core.time import utcnow

_FILE = Path(__file__).resolve().parent.parent / "data" / "scenarios.json"


def _resolve(node: Any, now: datetime) -> Any:
    if isinstance(node, dict):
        out = {k: _resolve(v, now) for k, v in node.items() if k != "ts_offset_hours"}
        if "ts_offset_hours" in node:
            out["timestamp"] = (now + timedelta(hours=float(node["ts_offset_hours"]))).isoformat()
        return out
    if isinstance(node, list):
        return [_resolve(x, now) for x in node]
    return node


def load_scenarios(now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    now = now or utcnow()
    raw = json.loads(_FILE.read_text(encoding="utf-8"))
    return [_resolve(copy.deepcopy(s), now) for s in raw["scenarios"]]


def scenario_request(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """Shape a scenario as an ``AnalysisRequest`` payload."""
    req: Dict[str, Any] = {"transaction": scenario["transaction"], "customer": scenario["customer"]}
    if scenario.get("network_transactions"):
        req["network_transactions"] = scenario["network_transactions"]
    if scenario.get("regime"):
        req["regime"] = scenario["regime"]
    return req
