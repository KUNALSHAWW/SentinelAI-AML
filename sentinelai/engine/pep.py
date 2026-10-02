"""
PEP screening
=============

Two independent channels:

1. **List match** - fuzzy name match against a PEP list (bundled synthetic demo
   data, or any dataset in the same JSON shape).
2. **Role indicator** - whole-word/phrase patterns in the customer's name or
   occupation. The previous implementation used raw substrings, so "Kingston",
   "Viking" or a "General Manager" were flagged as PEPs. Patterns here are
   anchored to government context and tested against those false positives.

A role indicator is weaker evidence than a list match and is reported as such.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from sentinelai.core.config import settings
from sentinelai.engine import names as nm
from sentinelai.engine.sanctions import ListEntry, WatchList

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_ROLE_PATTERNS = [
    (r"\bminister\b", "Government minister"),
    (r"\b(?:senator|member of parliament|parliamentarian|lok sabha|rajya sabha)\b", "Legislator"),
    (r"\b(?:mp|mla|mlc)\b(?=[\s,.)]|$)", "Legislator (MP/MLA)"),
    (r"\bambassador\b", "Ambassador"),
    (r"\b(?:governor|lieutenant governor)\b(?!['\u2019]s)", "Governor"),
    (r"\bmayor\b", "Mayor"),
    (r"\b(?:supreme court|high court|constitutional court) (?:judge|justice)\b", "Senior judge"),
    (r"\b(?:head of state|head of government|prime minister|chief minister)\b", "Head of state/government"),
    (r"\bpresident of (?:the )?(?:republic|nation|country|senate|state|united states)\b", "Head of state"),
    (r"\b(?:army|air force|naval|navy) (?:general|chief|commander)\b", "Senior military officer"),
    (r"\b(?:lieutenant general|brigadier general|major general|field marshal|air marshal|admiral)\b", "Senior military officer"),
    (r"\b(?:cabinet secretary|secretary of state|home secretary|foreign secretary)\b", "Senior official"),
    (r"\b(?:crown prince|royal highness|hrh)\b", "Royal family"),
    (r"\b(?:central bank (?:governor|deputy governor)|deputy governor)\b", "Central bank official"),
    (r"\b(?:state[- ]owned (?:enterprise|company) (?:chairman|ceo|director))\b", "State-owned enterprise executive"),
    (r"\bconsul[- ]general\b", "Diplomat"),
]
_COMPILED = [(re.compile(p, re.IGNORECASE), label) for p, label in _ROLE_PATTERNS]


@dataclass
class PEPResult:
    list_matches: List[Dict[str, Any]]
    role_indicators: List[Dict[str, str]]

    @property
    def is_pep_candidate(self) -> bool:
        return bool(self.list_matches or self.role_indicators)


def role_indicators(*texts: Optional[str]) -> List[Dict[str, str]]:
    found: List[Dict[str, str]] = []
    seen = set()
    for text in texts:
        if not text:
            continue
        for pattern, label in _COMPILED:
            match = pattern.search(text)
            if match and (label, match.group(0).lower()) not in seen:
                seen.add((label, match.group(0).lower()))
                found.append({"role": label, "matched_text": match.group(0), "source_text": text[:120]})
    return found


class PEPScreener:
    def __init__(self, watchlist: WatchList, meta: Dict[str, Dict[str, Any]]):
        self.watchlist = watchlist
        self.meta = meta

    def screen(self, name: str, occupation: str = "") -> PEPResult:
        matches: List[Dict[str, Any]] = []
        threshold = settings.risk.pep_match_threshold
        for score, ei, text, is_alias, aligned in self.watchlist.search(name, threshold):
            entry = self.watchlist.entries[ei]
            info = self.meta.get(entry.uid, {})
            matches.append({
                "listed_name": entry.name, "matched_name": text, "score": round(score, 3), "uid": entry.uid,
                "position": info.get("position"), "country": info.get("country"),
                "category": info.get("category", "PEP"), "level": info.get("level"),
                "list": entry.list_name,
            })
        return PEPResult(list_matches=matches, role_indicators=role_indicators(name, occupation))


def load_pep_json(path: Path) -> PEPScreener:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    source = raw.get("source", "CUSTOM")
    entries, meta = [], {}
    for i, e in enumerate(raw.get("entries", [])):
        uid = e.get("uid", f"{source}-{i}")
        entries.append(ListEntry(uid=uid, name=e["name"], entity_type="INDIVIDUAL", aliases=e.get("aliases", []),
                                 countries=[e["country"]] if e.get("country") else [], list_name=source))
        meta[uid] = e
    wl = WatchList(entries, name=raw.get("name", path.stem), source=source, synthetic=bool(raw.get("synthetic")))
    return PEPScreener(wl, meta)


_default: Optional[PEPScreener] = None


def get_pep_screener(reload: bool = False) -> PEPScreener:
    global _default
    if _default is None or reload:
        custom = Path(settings.risk.lists_dir) / "pep.json"
        _default = load_pep_json(custom if custom.exists() else _DATA_DIR / "pep_demo.json")
    return _default
