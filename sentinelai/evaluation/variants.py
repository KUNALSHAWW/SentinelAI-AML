"""Name-variant generators for sanctions-matcher evaluation (OFAC: 'test routinely')."""

from __future__ import annotations

import random
import re
from typing import Callable, Dict

_TRANSLIT = [("ou", "u"), ("u", "ou"), ("kh", "h"), ("h", "kh"), ("q", "k"), ("k", "q"), ("ph", "f"), ("y", "i"), ("i", "y"),
             ("ee", "i"), ("oo", "u"), ("ck", "k"), ("w", "v"), ("v", "w"), ("z", "s"), ("ai", "ay")]


def _pick_token(name: str, r: random.Random) -> int:
    toks = name.split()
    longest = [i for i, t in enumerate(toks) if len(t) >= 5] or list(range(len(toks)))
    return r.choice(longest)


def typo(name: str, r: random.Random) -> str:
    toks = name.split()
    i = _pick_token(name, r)
    t = toks[i]
    if len(t) < 4:
        return name
    pos = r.randrange(1, len(t) - 1)
    op = r.choice(["delete", "replace", "insert"])
    if op == "delete":
        t = t[:pos] + t[pos + 1:]
    elif op == "replace":
        t = t[:pos] + r.choice("aeiounrstl") + t[pos + 1:]
    else:
        t = t[:pos] + r.choice("aeiou") + t[pos:]
    toks[i] = t
    return " ".join(toks)


def transposition(name: str, r: random.Random) -> str:
    toks = name.split()
    i = _pick_token(name, r)
    t = toks[i]
    if len(t) < 4:
        return name
    pos = r.randrange(1, len(t) - 2)
    toks[i] = t[:pos] + t[pos + 1] + t[pos] + t[pos + 2:]
    return " ".join(toks)


def reorder(name: str, r: random.Random) -> str:
    toks = name.split()
    if len(toks) < 2:
        return name
    r.shuffle(toks)
    return " ".join(toks) if toks != name.split() else " ".join(reversed(toks))


def translit(name: str, r: random.Random) -> str:
    options = [(a, b) for a, b in _TRANSLIT if a in name.lower()]
    if not options:
        return typo(name, r)
    a, b = r.choice(options)
    return re.sub(a, b, name, count=1, flags=re.IGNORECASE)


def case_punct(name: str, r: random.Random) -> str:
    return r.choice([name.upper(), name.lower(), name.replace(" ", "_"), name.replace(" ", "-"), f"{name}."])


def extra_token(name: str, r: random.Random) -> str:
    return f"{name} {r.choice(['Ltd', 'International', 'Group', 'Co'])}"


def drop_token(name: str, r: random.Random) -> str:
    toks = name.split()
    if len(toks) < 3:
        return name
    toks.pop(r.randrange(len(toks)))
    return " ".join(toks)


VARIANTS: Dict[str, Callable[[str, random.Random], str]] = {
    "typo": typo, "transposition": transposition, "reorder": reorder, "translit": translit,
    "case_punct": case_punct, "extra_token": extra_token, "drop_token": drop_token,
}


def make_variant(name: str, kind: str, r: random.Random) -> str:
    return VARIANTS[kind](name, r)
