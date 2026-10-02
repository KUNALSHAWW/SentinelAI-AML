import math

import pytest

from sentinelai.core.config import settings
from sentinelai.engine.scoring import combine, combine_with_ai, decide, level_for
from sentinelai.engine.types import Signal


def sig(code, w, cat="BEHAVIORAL", **kw):
    return Signal(code=code, category=cat, weight=w, description=code, subject=code, **kw)


def test_empty_is_zero_low():
    r = combine([])
    assert r.score == 0 and r.level == "LOW" and r.contributions == []


def test_contributions_sum_exactly_to_score():
    signals = [sig("A", .35, "GEOGRAPHIC"), sig("B", .15, "GEOGRAPHIC"), sig("C", .3), sig("D", .5, "NETWORK"), sig("E", .08, "CRYPTO")]
    r = combine(signals)
    assert sum(c["points"] for c in r.contributions) == r.score


def test_monotone_in_evidence():
    base = [sig("A", .3), sig("B", .2, "GEOGRAPHIC")]
    assert combine(base + [sig("C", .1, "CRYPTO")]).score >= combine(base).score
    assert combine([sig("A", .6)]).score > combine([sig("A", .3)]).score


def test_saturates_instead_of_summing():
    """Ten 30%-signals in different categories are ~97, not 300 clamped to 100; one 90% signal stays below 100."""
    many = combine([sig(f"S{i}", .3, f"CAT{i}") for i in range(10)]).score
    assert 95 <= many <= 98
    assert combine([sig("X", .9, "SANCTIONS")]).score == 90


def test_correlated_signals_in_one_category_are_discounted():
    same = combine([sig("A", .3, "GEOGRAPHIC"), sig("B", .3, "GEOGRAPHIC"), sig("C", .3, "GEOGRAPHIC")]).score
    diff = combine([sig("A", .3, "GEOGRAPHIC"), sig("B", .3, "NETWORK"), sig("C", .3, "CRYPTO")]).score
    assert same < diff


def test_dedupe_keeps_strongest_per_code_and_subject():
    a = Signal("X", "GEOGRAPHIC", .2, "d", subject="s1")
    b = Signal("X", "GEOGRAPHIC", .4, "d", subject="s1")
    assert combine([a, b]).score == combine([b]).score


def test_floor_is_applied_and_shown_as_own_waterfall_entry():
    r = combine([sig("S", .97, "SANCTIONS", floor=95), sig("G", .1, "GEOGRAPHIC")])
    assert r.score >= 95
    assert sum(c["points"] for c in r.contributions) == r.score
    weak = combine([Signal("S", "SANCTIONS", .2, "x", floor=90)])
    assert weak.score == 90 and weak.floor_applied == "S"
    assert any(c["code"] == "POLICY_FLOOR" for c in weak.contributions)


def test_levels_follow_configured_thresholds():
    cfg = settings.risk
    assert level_for(cfg.medium_risk_threshold - 1) == "LOW"
    assert level_for(cfg.medium_risk_threshold) == "MEDIUM"
    assert level_for(cfg.high_risk_threshold) == "HIGH"
    assert level_for(cfg.critical_risk_threshold) == "CRITICAL"


def test_counterfactual_identifies_level_changing_signal():
    r = combine([sig("BIG", .75, "NETWORK"), sig("small", .05, "CRYPTO")])
    top = r.counterfactuals[0]
    assert top["without"] == "BIG" and top["changes_level"] and top["score_without"] < r.score


def test_ai_can_only_raise_and_is_capped():
    det = [sig("A", .3), sig("B", .2, "GEOGRAPHIC")]
    base = combine(det).score
    ai = [Signal("AI_X", "AI_RESEARCH", .9, "ai", subject="x", verified=False)]
    boosted = combine_with_ai(det, ai, max_uplift=10).score
    assert base < boosted <= base + 10
    assert combine_with_ai(det, ai, max_uplift=0).score == base
    assert combine_with_ai(det, [], max_uplift=10).score == base


def test_ai_waterfall_still_sums_to_score_after_capping():
    det = [sig("A", .3)]
    ai = [Signal("AI_X", "AI_RESEARCH", .9, "ai", subject="x"), Signal("AI_Y", "AI_RESEARCH", .8, "ai", subject="y")]
    r = combine_with_ai(det, ai, max_uplift=12)
    assert sum(c["points"] for c in r.contributions) == r.score


def test_ai_zero_or_negative_evidence_cannot_lower_score():
    det = [sig("A", .5)]
    r = combine_with_ai(det, [Signal("AI_X", "AI_RESEARCH", 0.0, "says it is fine", subject="x")], max_uplift=15)
    assert r.score == combine(det).score


def test_decide_sanctions_requires_verified_match():
    unverified = [Signal("SANCTIONS_MATCH", "SANCTIONS", .97, "x", floor=95, verified=False)]
    assert decide(combine(unverified), unverified)["sanctions_confirmed"] is False
    verified = [Signal("SANCTIONS_MATCH", "SANCTIONS", .97, "x", floor=95)]
    d = decide(combine(verified), verified)
    assert d["sanctions_confirmed"] and d["recommended_action"] == "BLOCK" and d["report_required"]


def test_decide_actions_by_level():
    cfg = settings.risk
    s = lambda w: [sig("A", w)]
    assert decide(combine(s(.05)), s(.05))["recommended_action"] == "APPROVE"
    assert decide(combine(s(.4)), s(.4))["recommended_action"] == "REVIEW"
    assert decide(combine(s(.7)), s(.7))["recommended_action"] == "ESCALATE"
    assert decide(combine(s(.95)), s(.95))["recommended_action"] == "BLOCK"


def test_pep_requires_report_at_medium():
    sg = [Signal("PEP_MATCH", "PEP", .4, "pep", subject="p")]
    assert decide(combine(sg), sg)["report_required"] is True
