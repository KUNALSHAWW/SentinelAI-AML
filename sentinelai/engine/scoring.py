"""
Explainable risk scoring
========================

Evidence signals are fused with a **noisy-OR**: if each signal alone indicates
illicit activity with probability ``p_i``, the combined probability is
``1 - prod(1 - p_i)``. Compared with the old "add up weights and clamp" scheme
this is:

* **monotone** - more evidence never lowers risk;
* **saturating** - ten weak signals cannot silently outweigh one strong one,
  and the score is never an arbitrary clamp at 100;
* **exactly decomposable** - with ``w_i = -ln(1 - p_i)`` the score is
  ``1 - exp(-sum w_i)``, so every signal's share of the score is
  ``w_i / sum(w)``. The waterfall shown to analysts sums to the final score.

Signals in the same category are correlated (three geography flags are not
three independent facts), so within a category the i-th strongest signal is
discounted by ``CORRELATION_DISCOUNT ** i``.

Policy *floors* (e.g. a verified sanctions match => score >= 95) are applied
last and shown explicitly as their own waterfall entry.

The LLM layer can only **add** bounded points (:func:`combine_with_ai`); it can
never reduce a deterministic score, so a prompt-injected "this is fine" cannot
launder a risky transaction.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from sentinelai.core.config import settings
from sentinelai.engine.types import AI_RESEARCH, LEVELS, Signal

CORRELATION_DISCOUNT = 0.6
_MAX_P = 0.995


@dataclass
class ScoreResult:
    score: int
    level: str
    raw_score: float
    contributions: List[Dict[str, Any]] = field(default_factory=list)
    floor_applied: Optional[str] = None
    counterfactuals: List[Dict[str, Any]] = field(default_factory=list)
    category_scores: Dict[str, int] = field(default_factory=dict)


def level_for(score: float) -> str:
    cfg = settings.risk
    if score >= cfg.critical_risk_threshold:
        return "CRITICAL"
    if score >= cfg.high_risk_threshold:
        return "HIGH"
    if score >= cfg.medium_risk_threshold:
        return "MEDIUM"
    return "LOW"


def dedupe(signals: Sequence[Signal]) -> List[Signal]:
    """Keep the strongest signal per (code, subject)."""
    best: Dict[tuple, Signal] = {}
    for s in signals:
        key = (s.code, s.subject)
        if key not in best or s.weight > best[key].weight:
            best[key] = s
    return list(best.values())


def _effective_weights(signals: Sequence[Signal]) -> List[tuple]:
    """Return [(signal, w_eff)] after category-correlation discounting."""
    by_cat: Dict[str, List[Signal]] = defaultdict(list)
    for s in signals:
        by_cat[s.category].append(s)
    out = []
    for group in by_cat.values():
        group.sort(key=lambda s: s.weight, reverse=True)
        for rank, s in enumerate(group):
            p = min(max(s.weight, 0.0), _MAX_P)
            out.append((s, -math.log(1.0 - p) * (CORRELATION_DISCOUNT ** rank)))
    return out


def _raw(signals: Sequence[Signal]) -> float:
    total = sum(w for _, w in _effective_weights(signals))
    return 100.0 * (1.0 - math.exp(-total))


def _floor(signals: Sequence[Signal]) -> Optional[Signal]:
    floored = [s for s in signals if s.floor]
    return max(floored, key=lambda s: s.floor) if floored else None


def _final_score(signals: Sequence[Signal]) -> int:
    score = int(round(_raw(signals)))
    floor_signal = _floor(signals)
    if floor_signal:
        score = max(score, int(floor_signal.floor))
    return min(100, score)


def _allocate(shares: List[float], total_points: int) -> List[int]:
    """Largest-remainder rounding so integer points sum exactly to total_points."""
    if not shares or total_points <= 0:
        return [0] * len(shares)
    scale = total_points / sum(shares)
    exact = [s * scale for s in shares]
    floors = [int(math.floor(e)) for e in exact]
    remainder = total_points - sum(floors)
    order = sorted(range(len(exact)), key=lambda i: exact[i] - floors[i], reverse=True)
    for i in order[:remainder]:
        floors[i] += 1
    return floors


def combine(signals: Sequence[Signal], with_counterfactuals: bool = True) -> ScoreResult:
    signals = dedupe(signals)
    weighted = _effective_weights(signals)
    raw = _raw(signals)
    raw_points = int(round(raw))
    final = _final_score(signals)

    shares = [w for _, w in weighted]
    points = _allocate(shares, raw_points)
    contributions = [
        {
            "code": s.code,
            "category": s.category,
            "points": pts,
            "description": s.description,
            "severity": s.severity,
            "typology": s.typology,
        }
        for (s, _), pts in zip(weighted, points)
    ]
    floor_signal = _floor(signals)
    floor_applied = None
    if floor_signal and final > raw_points:
        floor_applied = floor_signal.code
        contributions.append({
            "code": "POLICY_FLOOR",
            "category": floor_signal.category,
            "points": final - raw_points,
            "description": f"Policy floor: {floor_signal.description}",
            "severity": "CRITICAL",
            "typology": floor_signal.typology,
        })
    contributions = [c for c in contributions if c["points"] > 0]
    contributions.sort(key=lambda c: c["points"], reverse=True)

    cat_totals: Dict[str, float] = defaultdict(float)
    for (s, w) in weighted:
        cat_totals[s.category] += w
    category_scores = {c: int(round(100 * (1 - math.exp(-t)))) for c, t in cat_totals.items()}

    result = ScoreResult(
        score=final,
        level=level_for(final),
        raw_score=round(raw, 2),
        contributions=contributions,
        floor_applied=floor_applied,
        category_scores=category_scores,
    )
    if with_counterfactuals and signals:
        result.counterfactuals = _counterfactuals(signals, result)
    return result


def _counterfactuals(signals: List[Signal], base: ScoreResult, limit: int = 3) -> List[Dict[str, Any]]:
    """'If this signal were absent, the score would be X' - for the top drivers."""
    out = []
    for s in signals:
        rest = [x for x in signals if x is not s]
        new_score = _final_score(rest)
        delta = base.score - new_score
        if delta <= 0:
            continue
        new_level = level_for(new_score)
        out.append({
            "without": s.code,
            "description": s.description,
            "score_without": new_score,
            "level_without": new_level,
            "delta": delta,
            "changes_level": new_level != base.level,
        })
    out.sort(key=lambda c: (c["changes_level"], c["delta"]), reverse=True)
    return out[:limit]


def combine_with_ai(
    deterministic: Sequence[Signal], ai: Sequence[Signal], max_uplift: Optional[int] = None
) -> ScoreResult:
    """Fuse AI-research signals, adding at most ``max_uplift`` points.

    AI evidence is *scaled down* (not truncated) when it would exceed the cap,
    so the waterfall still sums exactly to the final score.
    """
    cap = settings.llm.max_uplift if max_uplift is None else max_uplift
    base = combine(deterministic, with_counterfactuals=False)
    if not ai or cap <= 0:
        return combine(deterministic)

    ai_list = [s for s in ai if s.weight > 0]
    target_ceiling = min(100, base.score + cap)
    full = _final_score(list(deterministic) + ai_list)
    if full <= target_ceiling:
        return combine(list(deterministic) + ai_list)

    lo, hi = 0.0, 1.0
    for _ in range(30):
        mid = (lo + hi) / 2
        scaled = [_scaled(s, mid) for s in ai_list]
        if _final_score(list(deterministic) + scaled) <= target_ceiling:
            lo = mid
        else:
            hi = mid
    scaled = [_scaled(s, lo) for s in ai_list]
    return combine(list(deterministic) + scaled)


def _scaled(signal: Signal, factor: float) -> Signal:
    p = 1.0 - (1.0 - min(signal.weight, _MAX_P)) ** factor  # scales w = -ln(1-p) by factor
    clone = Signal(**{**signal.__dict__, "weight": p})
    clone.evidence = {**signal.evidence, "capped_by_policy": factor < 0.999}
    return clone


def decide(result: ScoreResult, signals: Sequence[Signal]) -> Dict[str, Any]:
    """Map a score to a disposition. Sanctions can only be *confirmed* by a verified list match."""
    cfg = settings.risk
    sanctions_confirmed = any(s.code == "SANCTIONS_MATCH" and s.verified for s in signals)
    has_pep = any(s.category == "PEP" for s in signals)

    if sanctions_confirmed or result.level == "CRITICAL":
        action = "BLOCK"
    elif result.level == "HIGH":
        action = "ESCALATE"
    elif result.level == "MEDIUM":
        action = "REVIEW"
    else:
        action = "APPROVE"

    report_required = bool(
        result.score >= cfg.sar_score_threshold
        or sanctions_confirmed
        or (has_pep and result.score >= cfg.medium_risk_threshold)
    )
    return {
        "recommended_action": action,
        "report_required": report_required,
        "sanctions_confirmed": sanctions_confirmed,
    }


__all__ = ["ScoreResult", "combine", "combine_with_ai", "decide", "level_for", "dedupe", "LEVELS", "AI_RESEARCH"]
