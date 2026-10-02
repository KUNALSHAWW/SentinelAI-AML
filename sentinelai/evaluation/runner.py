"""Run the benchmark: engine vs ablations vs baselines, plus sanctions-matcher variant tests."""

from __future__ import annotations

import random
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

from sentinelai.core.config import settings
from sentinelai.core.fx import to_usd
from sentinelai.core.jurisdictions import get_jurisdictions
from sentinelai.engine import DetectionEngine, build_input
from sentinelai.engine.sanctions import SanctionsScreener, get_screener
from sentinelai.engine.scoring import combine
from sentinelai.engine.types import Signal
from sentinelai.evaluation import metrics as M
from sentinelai.evaluation.generator import FIRST, LAST, Sample, make_dataset
from sentinelai.evaluation.variants import VARIANTS, make_variant

CATEGORIES = ["SANCTIONS", "PEP", "GEOGRAPHIC", "BEHAVIORAL", "NETWORK", "CRYPTO", "TRADE", "CUSTOMER", "INTEGRITY"]


def naive_threshold_baseline(request: Dict[str, Any]) -> float:
    """What a legacy rule engine does: flag any >= USD 10k or any high-risk-country leg. Returns 0/100."""
    tx = request["transaction"]
    usd = to_usd(float(tx.get("amount", 0)), tx.get("currency", "USD"))
    j = get_jurisdictions()
    countries = [tx.get("origin_country"), tx.get("destination_country"), *tx.get("intermediate_countries", [])]
    risky = any(j.categories(c) for c in countries if c)
    return 100.0 if (usd >= 10_000 or risky) else 0.0


def additive_score(signals: List[Signal]) -> float:
    """The old scoring idea: add weights (x100) and clamp at 100."""
    return min(100.0, sum(s.weight * 100 for s in signals))


def _metrics_block(scores: List[float], labels: List[int], threshold: float) -> Dict[str, Any]:
    c = M.confusion(scores, labels, threshold)
    out = {**c, **M.prf(c), "threshold": threshold}
    return out


def run_benchmark(n: int = 1000, seed: int = 7, regime: str = "US_BSA", suspicious_ratio: float = 0.2,
                  threshold: Optional[float] = None) -> Dict[str, Any]:
    threshold = threshold or settings.risk.high_risk_threshold
    dataset = make_dataset(n, seed, suspicious_ratio, regime)
    engine = DetectionEngine()
    started = time.perf_counter()
    results = []
    for s in dataset:
        req = s.request
        ctx = build_input(req["transaction"], req["customer"], req.get("network_transactions"), regime=req.get("regime"))
        results.append((s, engine.run(ctx)))
    elapsed = time.perf_counter() - started

    labels = [s.label for s, _ in results]
    scores = [r.score.score for _, r in results]

    summary: Dict[str, Any] = {
        "config": {"n": n, "seed": seed, "regime": regime, "suspicious_ratio": suspicious_ratio, "threshold": threshold,
                   "engine_seconds": round(elapsed, 2), "ms_per_transaction": round(1000 * elapsed / n, 2),
                   "sanctions_list": get_screener().info},
        "engine": {**_metrics_block(scores, labels, threshold),
                   "roc_auc": M.roc_auc(scores, labels), "average_precision": M.average_precision(scores, labels),
                   "f1_ci95": M.bootstrap_ci(lambda s, y: M.prf(M.confusion(s, y, threshold))["f1"], scores, labels),
                   "auc_ci95": M.bootstrap_ci(M.roc_auc, scores, labels)},
        "calibration": M.calibration(scores, labels),
    }

    # threshold sweep
    review_t = settings.risk.medium_risk_threshold
    summary["review_point"] = {**_metrics_block(scores, labels, review_t), "roc_auc": summary["engine"]["roc_auc"]}
    summary["threshold_sweep"] = [{"threshold": t, **_metrics_block(scores, labels, t)} for t in (30, 40, 50, 60, 70, 80)]

    # baselines on identical data
    naive = [naive_threshold_baseline(s.request) for s, _ in results]
    additive = [additive_score(r.signals) for _, r in results]
    summary["baselines"] = {
        "naive_threshold_rules": {**_metrics_block(naive, labels, 50), "roc_auc": M.roc_auc(naive, labels)},
        "additive_clamp_scoring": {**_metrics_block(additive, labels, threshold), "roc_auc": M.roc_auc(additive, labels),
                                   "average_precision": M.average_precision(additive, labels)},
        "additive_clamp_review": {**_metrics_block(additive, labels, settings.risk.medium_risk_threshold),
                                  "roc_auc": M.roc_auc(additive, labels), "average_precision": M.average_precision(additive, labels)},
    }

    # ablation: remove each detector category and re-fuse the remaining signals
    ablation = {}
    for cat in CATEGORIES:
        abl_scores = [combine([sg for sg in r.signals if sg.category != cat], with_counterfactuals=False).score for _, r in results]
        block = _metrics_block(abl_scores, labels, threshold)
        ablation[cat] = {**block, "roc_auc": M.roc_auc(abl_scores, labels),
                         "delta_recall": block["recall"] - summary["engine"]["recall"],
                         "delta_fpr": block["fpr"] - summary["engine"]["fpr"]}
    summary["ablation"] = ablation

    # per-typology recall and hard-negative false-positive rate
    by_typ: Dict[str, List[int]] = defaultdict(list)
    for (s, r) in results:
        if s.label:
            by_typ[s.typology or "?"].append(1 if r.score.score >= threshold else 0)
    summary["per_typology_recall"] = {k: {"n": len(v), "recall": sum(v) / len(v)} for k, v in sorted(by_typ.items())}
    hard = [(r.score.score >= threshold) for s, r in results if s.hard_negative]
    easy = [(r.score.score >= threshold) for s, r in results if not s.label and not s.hard_negative]
    summary["false_positive_rate"] = {
        "hard_negatives": {"n": len(hard), "fpr": sum(hard) / len(hard) if hard else None},
        "ordinary_benign": {"n": len(easy), "fpr": sum(easy) / len(easy) if easy else None}}
    worst = sorted(((r.score.score, s.id, [sg.code for sg in r.signals]) for s, r in results if not s.label), reverse=True)[:5]
    summary["top_false_positives"] = [{"score": a, "id": b, "signals": c} for a, b, c in worst]
    missed = sorted(((r.score.score, s.id, s.typology, [sg.code for sg in r.signals]) for s, r in results if s.label), )[:5]
    summary["lowest_scored_suspicious"] = [{"score": a, "id": b, "typology": c, "signals": d} for a, b, c, d in missed]
    return summary


def run_sanctions_matcher_eval(seed: int = 11, n_random_names: int = 3000, screener: Optional[SanctionsScreener] = None) -> Dict[str, Any]:
    """Synthetic variant testing: per-class recall and false-positive rate on random benign names."""
    screener = screener or get_screener()
    r = random.Random(seed)
    entries = screener.watchlist.entries
    classes: Dict[str, Dict[str, Any]] = {}
    for kind in VARIANTS:
        total = review_hit = strong_hit = 0
        for e in entries:
            if kind == "drop_token" and len(e.name.split()) < 3:
                continue
            q = make_variant(e.name, kind, r)
            total += 1
            matches = [m for m in screener.screen(q) if m.uid == e.uid]
            if matches:
                review_hit += 1
                if matches[0].level in ("MATCH", "STRONG_POTENTIAL_MATCH"):
                    strong_hit += 1
        if total:
            classes[kind] = {"n": total, "recall_any_hit": review_hit / total, "recall_strong_or_match": strong_hit / total}

    fp = 0
    for _ in range(n_random_names):
        name = f"{r.choice(FIRST)} {r.choice(LAST)}" if r.random() < .6 else f"{r.choice(['Apex', 'Summit', 'Orion', 'Cobalt', 'Pioneer'])} {r.choice(['Logistics', 'Foods', 'Textiles', 'Software'])}"
        if screener.screen(name):
            fp += 1
    return {"entries": len(entries), "variant_recall": classes,
            "false_positive_rate_random_names": {"n": n_random_names, "false_positives": fp, "rate": fp / n_random_names},
            "thresholds": {"review": settings.risk.sanctions_review_threshold, "strong": settings.risk.sanctions_match_threshold}}
