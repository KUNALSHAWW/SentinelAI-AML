import pytest

from sentinelai.engine import names as nm


@pytest.mark.parametrize("a,b,minimum", [
    ("Muammar Gaddafi", "Muammar Qadhafi", 0.92),
    ("Moammar Khadafy", "Muammar Gaddafi", 0.90),
    ("Mohammed Al-Rashid", "Muhammad Rashid", 0.92),
    ("Smith John", "John Smith", 0.99),
    ("Viktor Petrov", "Wiktor Petrow", 0.90),
    ("Acme Trading LLC", "ACME TRADING LTD", 0.99),
    ("sanctioned_russian_bank", "Sanctioned Russian Bank", 0.99),
])
def test_variants_score_high(a, b, minimum):
    assert nm.name_similarity(a, b)[0] >= minimum


@pytest.mark.parametrize("a,b,maximum", [
    ("Ivan Ivanov", "Ivan Petrov", 0.6),
    ("John Smith", "Jane Doe", 0.5),
    ("Li Wei", "Wang Fang", 0.5),
])
def test_different_names_score_low(a, b, maximum):
    assert nm.name_similarity(a, b)[0] <= maximum


def test_short_names_are_capped():
    assert nm.name_similarity("Al Li", "Ali Lu")[0] <= 0.75


def test_containment_of_listed_name_in_longer_party():
    assert nm.name_similarity("Sanctioned Russian Bank Moscow Branch", "Sanctioned Russian Bank")[0] >= 0.88


def test_skeleton_folds_voicing_and_digraphs():
    assert nm.skeleton("gaddafi") == nm.skeleton("qadhafi") == nm.skeleton("khadafy")
    assert nm.skeleton("mohammed") == nm.skeleton("muhammad")


def test_jaro_winkler_reference_values():
    assert nm.jaro_winkler("MARTHA", "MARHTA") == pytest.approx(0.9611, abs=1e-3)
    assert nm.jaro_winkler("DIXON", "DICKSONX") == pytest.approx(0.8133, abs=1e-3)
    assert nm.jaro_winkler("abc", "abc") == 1.0 and nm.jaro_winkler("abc", "xyz") == 0.0
