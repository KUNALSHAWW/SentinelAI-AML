"""
Name normalisation and similarity
=================================

Building blocks for sanctions/PEP screening:

* Unicode folding, punctuation/underscore stripping, corporate-suffix and title removal
* Jaro-Winkler token similarity (prefix-sensitive, good for transliteration drift)
* A voicing-folded consonant skeleton as a *secondary* phonetic channel so that
  Gaddafi / Qadhafi / Kadhafi or Mohammed / Muhammad still align even when the
  first letter differs (where Jaro-Winkler's prefix bonus would otherwise hurt)
* One-to-one token alignment scored with a length-weighted F1, so reordering
  ("Smith John" vs "John Smith") is free but dropped/extra tokens are penalised
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import List, Sequence, Tuple

CORPORATE_SUFFIXES = {
    "llc", "ltd", "limited", "inc", "incorporated", "corp", "corporation", "co", "company", "gmbh", "ag",
    "sa", "sarl", "srl", "spa", "bv", "nv", "plc", "llp", "lp", "pjsc", "ooo", "oao", "zao", "jsc", "ojsc",
    "fze", "fzco", "fzc", "pvt", "pte", "sdn", "bhd", "as", "ab", "oy", "kk", "ltda", "lda",
}
TITLES = {"mr", "mrs", "ms", "miss", "dr", "prof", "sir", "shri", "smt", "sri", "hon", "haji", "hajji", "sheikh", "sheik"}
STOPWORDS = {"the", "of", "and", "de", "al", "el", "bin", "ibn", "van", "von"}


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


@lru_cache(maxsize=65536)
def tokens(name: str) -> Tuple[str, ...]:
    """Normalised comparison tokens for a name."""
    text = _strip_accents(name or "").lower().replace("&", " and ")
    raw = [t for t in re.split(r"[^a-z0-9]+", text) if t]
    kept = [t for t in raw if t not in CORPORATE_SUFFIXES and t not in TITLES and t not in STOPWORDS]
    return tuple(kept or raw)


def normalize(name: str) -> str:
    return " ".join(tokens(name))


# --- phonetic skeleton ------------------------------------------------------
_DIGRAPHS = [("ph", "f"), ("kh", "k"), ("gh", "g"), ("dh", "d"), ("th", "t"), ("sh", "s"), ("ck", "k"), ("ts", "s")]
_VOICING = str.maketrans({"p": "b", "t": "d", "k": "g", "q": "g", "c": "g", "z": "s", "v": "f", "w": "f", "j": "y"})


@lru_cache(maxsize=65536)
def skeleton(token: str) -> str:
    """Voicing-folded consonant skeleton ('gaddafi' == 'qadhafi' == 'gdf')."""
    s = token.lower()
    for a, b in _DIGRAPHS:
        s = s.replace(a, b)
    s = s.translate(_VOICING)
    s = re.sub(r"(.)\1+", r"\1", s)
    # keep the first letter even if it is a vowel; drop later vowels
    out = s[:1] + re.sub(r"[aeiouy]", "", s[1:])
    return re.sub(r"(.)\1+", r"\1", out)


# --- similarity -------------------------------------------------------------
def jaro(a: str, b: str) -> float:
    if a == b:
        return 1.0
    la, lb = len(a), len(b)
    if not la or not lb:
        return 0.0
    window = max(max(la, lb) // 2 - 1, 0)
    a_match = [False] * la
    b_match = [False] * lb
    matches = 0
    for i, ca in enumerate(a):
        lo, hi = max(0, i - window), min(lb, i + window + 1)
        for j in range(lo, hi):
            if not b_match[j] and b[j] == ca:
                a_match[i] = b_match[j] = True
                matches += 1
                break
    if not matches:
        return 0.0
    k = transpositions = 0
    for i in range(la):
        if a_match[i]:
            while not b_match[k]:
                k += 1
            if a[i] != b[k]:
                transpositions += 1
            k += 1
    t = transpositions / 2
    return (matches / la + matches / lb + (matches - t) / matches) / 3


def jaro_winkler(a: str, b: str, prefix_scale: float = 0.1) -> float:
    j = jaro(a, b)
    if j <= 0.7:
        return j
    prefix = 0
    for ca, cb in zip(a[:4], b[:4]):
        if ca != cb:
            break
        prefix += 1
    return j + prefix * prefix_scale * (1 - j)


def token_similarity(a: str, b: str) -> float:
    """Similarity of two single tokens in [0, 1]."""
    if a == b:
        return 1.0
    if len(a) == 1 or len(b) == 1:                       # initial vs full name ("j" ~ "john")
        return 0.8 if a[:1] == b[:1] else 0.0
    best = jaro_winkler(a, b)
    sa, sb = skeleton(a), skeleton(b)
    if len(sa) >= 3 and len(sb) >= 3 and abs(len(a) - len(b)) <= 3:
        best = max(best, 0.95 * jaro_winkler(sa, sb))    # phonetic channel is capped below 'exact'
    return best


def align_score(query: Sequence[str], candidate: Sequence[str]) -> Tuple[float, List[Tuple[str, str, float]]]:
    """Order-insensitive, length-weighted token alignment score and the aligned pairs.

    Tokens are paired one-to-one greedily by descending similarity; precision is
    the length-weighted similarity covered on the query side, recall on the
    candidate side, and the score is their F1.
    """
    if not query or not candidate:
        return 0.0, []
    pairs = sorted(
        ((token_similarity(q, c), qi, ci) for qi, q in enumerate(query) for ci, c in enumerate(candidate)),
        reverse=True,
    )
    used_q, used_c = set(), set()
    aligned: List[Tuple[str, str, float]] = []
    q_got = c_got = 0.0
    for sim, qi, ci in pairs:
        if qi in used_q or ci in used_c or sim < 0.6:
            continue
        used_q.add(qi)
        used_c.add(ci)
        aligned.append((query[qi], candidate[ci], round(sim, 3)))
        q_got += len(query[qi]) * sim
        c_got += len(candidate[ci]) * sim
    precision = q_got / sum(len(t) for t in query)
    recall = c_got / sum(len(t) for t in candidate)
    if precision + recall == 0:
        return 0.0, aligned
    return 2 * precision * recall / (precision + recall), aligned


def _covered(small: Sequence[str], large: Sequence[str]) -> bool:
    """True when every token of ``small`` has a near-exact partner in ``large``."""
    return all(any(token_similarity(a, b) >= 0.92 for b in large) for a in small)


def name_similarity(query: str, candidate: str) -> Tuple[float, List[Tuple[str, str, float]]]:
    """Overall similarity of two names with false-positive guards."""
    q, c = tokens(query), tokens(candidate)
    if not q or not c:
        return 0.0, []
    if q == c or sorted(q) == sorted(c):
        return 1.0, [(t, t, 1.0) for t in q]
    score, aligned = align_score(q, c)
    # Containment: a listed name embedded in a longer party string
    # ("sanctioned russian bank moscow branch") is a hit worth reviewing.
    if len(c) >= 2 and len(q) > len(c) and _covered(c, q):
        score = max(score, 0.90)
    elif len(q) >= 2 and len(c) > len(q) and _covered(q, c):
        score = max(score, 0.86)
    # Short names produce coincidental matches: cap unless identical.
    if min(len("".join(q)), len("".join(c))) < 5:
        score = min(score, 0.75)
    return score, aligned
