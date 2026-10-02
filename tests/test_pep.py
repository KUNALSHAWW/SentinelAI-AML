import pytest

from sentinelai.engine.pep import get_pep_screener, role_indicators


@pytest.mark.parametrize("text", ["Kingston Freight Co", "Viking Logistics", "General Manager", "Vice President of Sales",
                                  "Director of Operations", "Governor's Bakery Ltd", "Kingsley Brown"])
def test_substring_false_positives_are_gone(text):
    assert role_indicators(text) == []


@pytest.mark.parametrize("text,role", [
    ("Deputy Minister of Mining", "Government minister"), ("Member of Parliament", "Legislator"),
    ("Rahul Sharma MLA", "Legislator (MP/MLA)"), ("Ambassador to the UN", "Ambassador"),
    ("Brigadier General", "Senior military officer"), ("Prime Minister", "Head of state/government"),
    ("Deputy Governor, Central Bank", "Central bank official"),
])
def test_role_patterns_match(text, role):
    assert role in {r["role"] for r in role_indicators(text)}


def test_list_match_and_fuzzy_variant():
    s = get_pep_screener()
    assert s.screen("Adebayo Okonkwo").list_matches
    assert s.screen("Adebayo Okonkow").list_matches        # typo still matches
    assert not s.screen("Jane Doe").is_pep_candidate


def test_role_in_occupation_field():
    assert get_pep_screener().screen("Jane Doe", "Senator for Ohio").role_indicators
