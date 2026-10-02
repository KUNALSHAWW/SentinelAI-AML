"""
Sanctions screening
===================

Real list-based screening (replacing the old hard-coded five-string check).

* **Data**: official OFAC SDN CSV files (``sdn.csv`` + ``alt.csv`` + ``add.csv``)
  via :func:`parse_ofac_csv`, a generic JSON format, or the bundled synthetic
  demo list. ``sentinelai sanctions update`` downloads the OFAC files.
* **Matching**: token-aligned Jaro-Winkler + phonetic skeleton + containment
  (see :mod:`sentinelai.engine.names`), with secondary-identifier corroboration
  (country) and short-name guards. Candidate generation uses an inverted index
  so a 19k-entry / ~40k-alias list screens in milliseconds.
* **Decision policy** (calibrated, documented):

  ==========================  =========================================
  Outcome                     Condition
  ==========================  =========================================
  ``MATCH`` (policy floor)    exact name/alias of an entity; or of an
                              individual with >= 3 name tokens or country
                              corroboration (common two-word personal names
                              are not auto-blocked on name alone)
  ``STRONG_POTENTIAL_MATCH``  score >= ``sanctions_match_threshold`` (higher
                              weight when a country corroborates it)
  ``POTENTIAL_MATCH``         score >= ``sanctions_review_threshold``
  ==========================  =========================================

  Fuzzy-only hits never trigger the automatic block floor - they go to an
  analyst - because "Kunal Shaw" vs "Kunal Shah" must not freeze an account.
"""

from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from sentinelai.core.config import settings
from sentinelai.core.jurisdictions import get_jurisdictions
from sentinelai.core.logging import get_logger
from sentinelai.engine import names as nm

logger = get_logger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
EXACT = 0.995
CORROBORATED_STRONG = 0.95


@dataclass
class ListEntry:
    uid: str
    name: str
    entity_type: str = "ENTITY"
    aliases: List[str] = field(default_factory=list)
    programs: List[str] = field(default_factory=list)
    countries: List[str] = field(default_factory=list)
    list_name: str = "UNKNOWN"
    remarks: str = ""

    def all_names(self) -> List[Tuple[str, bool]]:
        return [(self.name, False)] + [(a, True) for a in self.aliases if a]


@dataclass
class ListMatch:
    uid: str
    list_name: str
    listed_name: str
    matched_name: str
    via_alias: bool
    score: float
    level: str                       # MATCH | STRONG_POTENTIAL_MATCH | POTENTIAL_MATCH
    programs: List[str]
    countries: List[str]
    entity_type: str
    corroborated_by: List[str]
    aligned_tokens: List[Tuple[str, str, float]]
    queried_name: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "queried_name": self.queried_name, "listed_name": self.listed_name,
            "matched_name": self.matched_name, "via_alias": self.via_alias,
            "score": round(self.score, 3), "level": self.level, "uid": self.uid,
            "list": self.list_name, "programs": self.programs, "countries": self.countries,
            "entity_type": self.entity_type, "corroborated_by": self.corroborated_by,
            "aligned_tokens": [{"query": a, "listed": b, "similarity": s} for a, b, s in self.aligned_tokens],
        }


class WatchList:
    """Indexed name list with fuzzy search."""

    def __init__(self, entries: Iterable[ListEntry], *, name: str, source: str, as_of: str = "unknown",
                 synthetic: bool = False):
        self.name = name
        self.source = source
        self.as_of = as_of
        self.synthetic = synthetic
        self.entries: List[ListEntry] = list(entries)
        self._variants: List[Tuple[int, str, bool, Tuple[str, ...]]] = []
        self._index: Dict[str, Set[int]] = defaultdict(set)
        self._build()

    def _build(self) -> None:
        for ei, entry in enumerate(self.entries):
            for text, is_alias in entry.all_names():
                toks = nm.tokens(text)
                if not toks:
                    continue
                vid = len(self._variants)
                self._variants.append((ei, text, is_alias, toks))
                for t in toks:
                    for key in self._keys(t):
                        self._index[key].add(vid)

    @staticmethod
    def _keys(token: str) -> Set[str]:
        keys = {f"t:{token[:3]}", f"s:{nm.skeleton(token)[:2]}"} if len(token) >= 3 else {f"t:{token}"}
        return keys

    def __len__(self) -> int:
        return len(self.entries)

    def candidates(self, query_tokens: Iterable[str]) -> Set[int]:
        found: Set[int] = set()
        for t in query_tokens:
            for key in self._keys(t):
                found |= self._index.get(key, set())
        return found

    def search(self, query: str, min_score: float, limit: int = 3) -> List[Tuple[float, int, str, bool, list]]:
        q_tokens = nm.tokens(query)
        if not q_tokens:
            return []
        best_per_entry: Dict[int, Tuple[float, int, str, bool, list]] = {}
        for vid in self.candidates(q_tokens):
            ei, text, is_alias, _ = self._variants[vid]
            score, aligned = nm.name_similarity(query, text)
            if score >= min_score and (ei not in best_per_entry or score > best_per_entry[ei][0]):
                best_per_entry[ei] = (score, ei, text, is_alias, aligned)
        return sorted(best_per_entry.values(), key=lambda r: r[0], reverse=True)[:limit]

    @property
    def info(self) -> Dict[str, Any]:
        return {"name": self.name, "source": self.source, "as_of": self.as_of,
                "entries": len(self.entries), "names_indexed": len(self._variants), "synthetic": self.synthetic}


class SanctionsScreener:
    def __init__(self, watchlist: WatchList, whitelist: Optional[Set[str]] = None):
        self.watchlist = watchlist
        self.whitelist = {nm.normalize(w) for w in (whitelist or set())}

    def screen(self, name: str, countries: Iterable[Optional[str]] = ()) -> List[ListMatch]:
        """Screen one name; ``countries`` are corroborating secondary identifiers."""
        if not name or nm.normalize(name) in self.whitelist:
            return []
        j = get_jurisdictions()
        context = {j.normalize(c) for c in countries if c}
        context.discard("")
        review = settings.risk.sanctions_review_threshold
        strong = settings.risk.sanctions_match_threshold
        matches: List[ListMatch] = []
        for score, ei, text, is_alias, aligned in self.watchlist.search(name, review):
            entry = self.watchlist.entries[ei]
            corroboration = sorted(context & {j.normalize(c) for c in entry.countries})
            n_tokens = len(nm.tokens(name))
            if score >= EXACT and (entry.entity_type != "INDIVIDUAL" or n_tokens >= 3 or corroboration):
                level = "MATCH"
            elif score >= CORROBORATED_STRONG and corroboration and n_tokens >= 2:
                level = "STRONG_POTENTIAL_MATCH"
            elif score >= strong or score >= EXACT:
                level = "STRONG_POTENTIAL_MATCH"
            else:
                level = "POTENTIAL_MATCH"
            matches.append(ListMatch(
                uid=entry.uid, list_name=entry.list_name, listed_name=entry.name, matched_name=text,
                via_alias=is_alias, score=score, level=level, programs=entry.programs,
                countries=entry.countries, entity_type=entry.entity_type, corroborated_by=corroboration,
                aligned_tokens=aligned, queried_name=name,
            ))
        return matches

    @property
    def info(self) -> Dict[str, Any]:
        return self.watchlist.info


# --------------------------------------------------------------------------
# Loaders
# --------------------------------------------------------------------------
def _null(value: str) -> str:
    value = (value or "").strip()
    return "" if value in ("-0-", "-0- ") else value


def _flip_individual(name: str) -> str:
    """OFAC lists individuals as 'LAST, First Middle' - return 'First Middle LAST'."""
    if "," in name:
        last, _, first = name.partition(",")
        return f"{first.strip()} {last.strip()}".strip()
    return name


def parse_ofac_csv(sdn_text: str, alt_text: str = "", add_text: str = "") -> List[ListEntry]:
    """Parse OFAC's legacy delimited SDN files.

    * ``sdn.csv``: ent_num, SDN_Name, SDN_Type, Program, Title, Call_Sign, Vess_type,
      Tonnage, GRT, Vess_flag, Vess_owner, Remarks (no header row)
    * ``alt.csv``: ent_num, alt_num, alt_type, alt_name, alt_remarks
    * ``add.csv``: ent_num, add_num, address, city/state/zip, country, add_remarks
    """
    aliases: Dict[str, List[str]] = defaultdict(list)
    for row in csv.reader(io.StringIO(alt_text)):
        if len(row) >= 4 and _null(row[3]):
            aliases[row[0].strip()].append(_null(row[3]))
    countries: Dict[str, Set[str]] = defaultdict(set)
    j = get_jurisdictions()
    reverse_names = {v.lower(): k for k, v in j.names.items()}
    for row in csv.reader(io.StringIO(add_text)):
        if len(row) >= 5 and _null(row[4]):
            country = _null(row[4])
            countries[row[0].strip()].add(reverse_names.get(country.lower(), country))

    entries: List[ListEntry] = []
    for row in csv.reader(io.StringIO(sdn_text)):
        if len(row) < 4 or not row[0].strip().isdigit():
            continue
        uid, raw_name = row[0].strip(), _null(row[1])
        kind = _null(row[2]).lower()
        entity_type = {"individual": "INDIVIDUAL", "vessel": "VESSEL", "aircraft": "AIRCRAFT"}.get(kind, "ENTITY")
        flip = entity_type == "INDIVIDUAL"
        name = _flip_individual(raw_name) if flip else raw_name
        alts = [_flip_individual(a) if flip else a for a in aliases.get(uid, [])]
        programs = [p.strip("[] ") for p in _null(row[3]).replace("] [", "|").split("|") if p.strip("[] ")]
        entries.append(ListEntry(
            uid=f"OFAC-{uid}", name=name, entity_type=entity_type, aliases=alts, programs=programs,
            countries=sorted(countries.get(uid, set())), list_name="OFAC_SDN",
            remarks=_null(row[11]) if len(row) > 11 else "",
        ))
    return entries


def load_json_list(path: Path) -> WatchList:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    source = raw.get("source", "CUSTOM")
    entries = [
        ListEntry(
            uid=e.get("uid", f"{source}-{i}"), name=e["name"], entity_type=e.get("type", "ENTITY"),
            aliases=e.get("aliases", []), programs=e.get("programs", []), countries=e.get("countries", []),
            list_name=source,
        )
        for i, e in enumerate(raw.get("entries", []))
    ]
    return WatchList(entries, name=raw.get("name", path.stem), source=source,
                     as_of=raw.get("as_of", "unknown"), synthetic=bool(raw.get("synthetic")))


def load_ofac_dir(directory: Path) -> Optional[WatchList]:
    sdn = directory / "sdn.csv"
    if not sdn.exists():
        return None
    read = lambda n: (directory / n).read_text(encoding="utf-8", errors="replace") if (directory / n).exists() else ""
    entries = parse_ofac_csv(sdn.read_text(encoding="utf-8", errors="replace"), read("alt.csv"), read("add.csv"))
    as_of = __import__("datetime").datetime.fromtimestamp(sdn.stat().st_mtime).date().isoformat()
    return WatchList(entries, name="OFAC SDN", source="OFAC_SDN", as_of=as_of)


_default: Optional[SanctionsScreener] = None


def get_screener(reload: bool = False) -> SanctionsScreener:
    """Load, in priority order: explicit file, downloaded OFAC files, bundled demo list."""
    global _default
    if _default is not None and not reload:
        return _default
    watchlist: Optional[WatchList] = None
    if settings.risk.sanctions_list_file:
        watchlist = load_json_list(Path(settings.risk.sanctions_list_file))
    if watchlist is None:
        watchlist = load_ofac_dir(Path(settings.risk.lists_dir) / "ofac")
    if watchlist is None:
        watchlist = load_json_list(_DATA_DIR / "sanctions_demo.json")
        logger.warning("Using the synthetic DEMO sanctions list - run `sentinelai sanctions update` for OFAC data")
    _default = SanctionsScreener(watchlist)
    return _default


OFAC_URLS = {
    "sdn.csv": ["https://sanctionslistservice.ofac.treas.gov/api/download/SDN.CSV",
                "https://www.treasury.gov/ofac/downloads/sdn.csv"],
    "alt.csv": ["https://sanctionslistservice.ofac.treas.gov/api/download/ALT.CSV",
                "https://www.treasury.gov/ofac/downloads/alt.csv"],
    "add.csv": ["https://sanctionslistservice.ofac.treas.gov/api/download/ADD.CSV",
                "https://www.treasury.gov/ofac/downloads/add.csv"],
}


def download_ofac(directory: Optional[Path] = None, client=None) -> Dict[str, int]:
    """Download the official OFAC SDN delimited files; returns {filename: bytes}."""
    import httpx

    target = Path(directory or Path(settings.risk.lists_dir) / "ofac")
    target.mkdir(parents=True, exist_ok=True)
    own = client is None
    client = client or httpx.Client(timeout=60, follow_redirects=True)
    sizes: Dict[str, int] = {}
    try:
        for filename, urls in OFAC_URLS.items():
            last_error: Optional[Exception] = None
            for url in urls:
                try:
                    response = client.get(url)
                    response.raise_for_status()
                    (target / filename).write_bytes(response.content)
                    sizes[filename] = len(response.content)
                    break
                except Exception as exc:  # try the next mirror
                    last_error = exc
            else:
                raise RuntimeError(f"Could not download {filename}: {last_error}")
    finally:
        if own:
            client.close()
    return sizes
