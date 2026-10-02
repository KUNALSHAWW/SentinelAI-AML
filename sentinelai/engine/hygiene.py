"""
Input hygiene
=============

Free-text fields (party names, notes, document titles) are attacker-controlled
and end up in LLM prompts. This module detects instruction-like content aimed
at an automated reviewer. A hit is both *sanitised* before any LLM sees it and
*reported as a risk signal* - someone trying to talk the screener out of
flagging a transaction is itself suspicious.
"""

from __future__ import annotations

import re
from typing import Dict, List

_PATTERNS = [
    r"ignore (?:all |any |the )?(?:previous|prior|above|earlier) (?:instructions?|prompts?|rules?)",
    r"disregard (?:all |any |the )?(?:previous|prior|above|earlier)",
    r"(?:you are|act as|pretend to be) (?:now )?(?:a |an )?(?:different|new|helpful|unrestricted|system)",
    r"(?:system|assistant|developer)\s*(?:prompt|message|instruction)",
    r"\bnew instructions?\b",
    r"(?:mark|rate|score|classify|set)\b.{0,40}\b(?:as|to)\b.{0,15}\b(?:low risk|safe|clean|no risk|risk score\s*(?:of|=|:)?\s*0)",
    r"do not (?:flag|report|escalate|screen)",
    r"(?:approve|clear|whitelist)\s+(?:this|the)\s+(?:transaction|customer|party)",
    r"</?\s*(?:system|instructions?|untrusted_data|tool|assistant)\s*>",
    r"reveal (?:your|the) (?:system )?prompt",
]
_COMPILED = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in _PATTERNS]
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f​-‏‪-‮⁦-⁩]")
_TAG = re.compile(r"</?\s*[a-z_]+\s*>", re.IGNORECASE)


def detect_injection(texts: List[str]) -> List[Dict[str, str]]:
    hits = []
    for text in texts:
        for pattern in _COMPILED:
            m = pattern.search(text or "")
            if m:
                hits.append({"pattern": pattern.pattern[:60], "excerpt": text[max(0, m.start() - 20): m.end() + 20][:160]})
                break
    return hits


def sanitize(text: str, max_len: int = 300) -> str:
    """Neutralise control/bidi characters and pseudo-tags, bound the length."""
    cleaned = _CONTROL.sub("", text or "")
    cleaned = _TAG.sub("", cleaned)
    return cleaned.strip()[:max_len]
