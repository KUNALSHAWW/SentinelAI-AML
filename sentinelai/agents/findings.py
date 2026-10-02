"""
Structured research findings
============================

Replaces regex score-scraping. Agents must finish with a JSON block; this
module parses it robustly, validates ranges, and falls back to a *narrow*
regex only when JSON is missing. If nothing parses, ``risk_score`` is ``None``
and the finding is excluded from scoring - an unparsable answer is never
silently treated as a score of 0 (the old behaviour).

Regression cases from the original bug report that now parse correctly:
``"Confidence score 0.85. Risk score: 70"`` -> 70, ``"**Risk Score:** 85"`` -> 85,
``"confidence score 0-1, risk score 80"`` -> 80.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from sentinelai.engine.types import AI_RESEARCH, Signal

_FENCED = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)
_RISK_SCORE = re.compile(r"risk[\s_*-]*score[\s*:=\-]{0,8}(\d{1,3})(?!\.\d)(?:\s*/\s*100)?", re.IGNORECASE)
_OUT_OF_100 = re.compile(r"\b(\d{1,3})\s*/\s*100\b")
_CONFIDENCE = re.compile(r"confidence(?:\s+score)?[\s*:=\-]{0,8}(\d{1,3}(?:\.\d+)?|\.\d+)\s*(%?)", re.IGNORECASE)

# Verdicts that mean "no concern" - the numeric score is ignored when they contradict it.
_NEGATIVE_VERDICTS = {"NO_MATCH", "NOT_PEP", "NONE", "NO_CONCERN", "CLEAR"}


class AgentFinding(BaseModel):
    agent: str
    verdict: str = "UNKNOWN"
    risk_score: Optional[int] = Field(default=None, ge=0, le=100)
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    red_flags: List[str] = Field(default_factory=list)
    summary: str = ""
    sources: List[str] = Field(default_factory=list)
    parse_status: str = "unparsed"          # json | regex | unparsed | error | timeout
    raw: str = ""

    @field_validator("verdict", mode="before")
    @classmethod
    def _verdict(cls, v):
        return re.sub(r"[\s-]+", "_", str(v or "UNKNOWN").strip().upper())[:40]

    @property
    def usable(self) -> bool:
        return self.risk_score is not None and self.parse_status in ("json", "regex")

    def public(self) -> Dict[str, Any]:
        d = self.model_dump(exclude={"raw"})
        d["raw_excerpt"] = self.raw[:400]
        return d


def _clamp_conf(value: Any) -> Optional[float]:
    try:
        conf = float(value)
    except (TypeError, ValueError):
        return None
    if conf > 100:
        return 1.0
    if conf > 1:                      # tolerate percentages ("85" or "85%")
        conf /= 100.0
    return min(1.0, max(0.0, conf))


def _from_json(agent: str, text: str) -> Optional[AgentFinding]:
    blocks = _FENCED.findall(text)
    candidates = blocks[::-1]
    # Also try the last brace-balanced object that mentions risk_score.
    start = text.rfind("{", 0, text.rfind("risk_score") if "risk_score" in text else -1)
    if start != -1:
        candidates.append(text[start: text.rfind("}") + 1])
    for blob in candidates:
        try:
            data = json.loads(blob)
        except (ValueError, TypeError):
            continue
        if not isinstance(data, dict):
            continue
        score = data.get("risk_score")
        try:
            score = None if score is None else min(100, max(0, int(round(float(score)))))
        except (TypeError, ValueError):
            score = None
        flags = data.get("red_flags") or []
        sources = data.get("sources") or []
        return AgentFinding(
            agent=agent, verdict=data.get("verdict", "UNKNOWN"), risk_score=score,
            confidence=_clamp_conf(data.get("confidence")),
            red_flags=[str(f)[:200] for f in flags][:10] if isinstance(flags, list) else [],
            summary=str(data.get("summary", ""))[:600],
            sources=[str(s)[:300] for s in sources][:10] if isinstance(sources, list) else [],
            parse_status="json", raw=text[:4000],
        )
    return None


def parse_finding(agent: str, text: str) -> AgentFinding:
    text = text or ""
    found = _from_json(agent, text)
    if found:
        return found
    score_match = _RISK_SCORE.search(text) or _OUT_OF_100.search(text)
    conf_match = _CONFIDENCE.search(text)
    if score_match:
        conf = None
        if conf_match:
            conf = _clamp_conf(conf_match.group(1) if not conf_match.group(2) else float(conf_match.group(1)) / 100)
        return AgentFinding(
            agent=agent, risk_score=min(100, int(score_match.group(1))), confidence=conf,
            summary=text.strip()[:400], parse_status="regex", raw=text[:4000],
        )
    return AgentFinding(agent=agent, summary=text.strip()[:400], parse_status="unparsed", raw=text[:4000])


def findings_to_signals(findings: List[AgentFinding]) -> List[Signal]:
    """Translate usable findings into *unverified, advisory* AI signals.

    A finding whose verdict says "no concern" contributes nothing even if its
    number is high (self-contradictory output is not trusted).
    """
    signals: List[Signal] = []
    for f in findings:
        if not f.usable or f.verdict in _NEGATIVE_VERDICTS or f.risk_score < 30:
            continue
        confidence = f.confidence if f.confidence is not None else 0.5
        weight = min(0.6, 0.6 * (f.risk_score / 100.0) * (0.5 + 0.5 * confidence))
        code = "AI_SANCTIONS_RESEARCH_HIT" if f.agent == "sanctions" else f"AI_{f.agent.upper()}_CONCERN"
        signals.append(Signal(
            code=code, category=AI_RESEARCH, weight=weight, subject=f.agent, verified=False,
            description=f"AI research ({f.agent}): {f.summary[:160] or f.verdict} [unverified]",
            evidence={"verdict": f.verdict, "risk_score": f.risk_score, "confidence": f.confidence,
                      "sources": f.sources[:3]},
        ))
    return signals
