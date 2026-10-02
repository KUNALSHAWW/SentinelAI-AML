"""Dependency-free evaluation metrics."""

from __future__ import annotations

import random
from typing import Callable, Dict, List, Sequence, Tuple


def confusion(scores: Sequence[float], labels: Sequence[int], threshold: float) -> Dict[str, int]:
    tp = fp = tn = fn = 0
    for s, y in zip(scores, labels):
        pred = s >= threshold
        if pred and y:
            tp += 1
        elif pred and not y:
            fp += 1
        elif not pred and y:
            fn += 1
        else:
            tn += 1
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn}


def prf(c: Dict[str, int]) -> Dict[str, float]:
    p = c["tp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else 0.0
    r = c["tp"] / (c["tp"] + c["fn"]) if c["tp"] + c["fn"] else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    fpr = c["fp"] / (c["fp"] + c["tn"]) if c["fp"] + c["tn"] else 0.0
    return {"precision": p, "recall": r, "f1": f1, "fpr": fpr}


def roc_auc(scores: Sequence[float], labels: Sequence[int]) -> float:
    """Mann-Whitney U formulation with average ranks for ties."""
    pairs = sorted(zip(scores, labels))
    ranks, i = {}, 0
    n = len(pairs)
    rank_of = [0.0] * n
    while i < n:
        j = i
        while j + 1 < n and pairs[j + 1][0] == pairs[i][0]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            rank_of[k] = avg
        i = j + 1
    pos = sum(1 for _, y in pairs if y)
    neg = n - pos
    if not pos or not neg:
        return float("nan")
    rank_sum = sum(r for r, (_, y) in zip(rank_of, pairs) if y)
    return (rank_sum - pos * (pos + 1) / 2) / (pos * neg)


def average_precision(scores: Sequence[float], labels: Sequence[int]) -> float:
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    tp = 0
    ap = 0.0
    total_pos = sum(labels)
    for rank, i in enumerate(order, 1):
        if labels[i]:
            tp += 1
            ap += tp / rank
    return ap / total_pos if total_pos else float("nan")


def bootstrap_ci(fn: Callable[[Sequence[float], Sequence[int]], float], scores: Sequence[float], labels: Sequence[int],
                 n: int = 200, seed: int = 1, alpha: float = 0.05) -> Tuple[float, float]:
    r = random.Random(seed)
    idx = list(range(len(scores)))
    vals: List[float] = []
    for _ in range(n):
        sample = [r.choice(idx) for _ in idx]
        v = fn([scores[i] for i in sample], [labels[i] for i in sample])
        if v == v:
            vals.append(v)
    vals.sort()
    if not vals:
        return float("nan"), float("nan")
    return vals[int(alpha / 2 * len(vals))], vals[min(len(vals) - 1, int((1 - alpha / 2) * len(vals)))]


def calibration(scores: Sequence[float], labels: Sequence[int], edges=(0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 101)) -> List[Dict]:
    rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        bucket = [y for s, y in zip(scores, labels) if lo <= s < hi]
        rows.append({"range": f"{lo}-{min(hi - 1, 100)}", "n": len(bucket),
                     "suspicious_rate": (sum(bucket) / len(bucket)) if bucket else None})
    return rows
