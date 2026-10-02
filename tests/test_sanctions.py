import httpx
import pytest

from sentinelai.engine import sanctions as sx
from sentinelai.engine.sanctions import ListEntry, SanctionsScreener, WatchList, get_screener, parse_ofac_csv

SDN = '''36,"AEROCARIBBEAN AIRLINES","-0- ","CUBA","-0- ","-0- ","-0- ","-0- ","-0- ","-0- ","-0- ","Website www.example.test; alt"
173,"ABDUL, Karim Hassan","individual","SDGT] [IFSR","-0- ","-0- ","-0- ","-0- ","-0- ","-0- ","-0- ","DOB 01 Jan 1970"
200,"OCEAN QUEEN","vessel","IRAN","-0- ","-0- ","Tanker","-0- ","-0- ","Panama","-0- ","-0- "
'''
ALT = '''36,1,"aka","AERO-CARIBBEAN","-0- "
173,2,"aka","ABDUL, Kareem H.","-0- "
'''
ADD = '''36,1,"Calle 23","Havana","Cuba","-0- "
173,2,"-0- ","Beirut","Lebanon","-0- "
'''


@pytest.fixture
def screener():
    return get_screener()


def test_demo_list_is_flagged_synthetic(screener):
    assert screener.info["synthetic"] is True and screener.info["entries"] >= 15


def test_exact_entity_match_is_a_policy_match(screener):
    m = screener.screen("Sanctioned Russian Bank")[0]
    assert m.level == "MATCH" and m.score >= 0.995


def test_alias_match(screener):
    m = screener.screen("Cartel XYZ")[0]
    assert m.via_alias and m.level == "MATCH"


def test_listed_name_inside_longer_string_is_only_potential(screener):
    m = screener.screen("Sanctioned Russian Bank Moscow Branch")[0]
    assert m.level == "POTENTIAL_MATCH"


def test_two_token_individual_name_alone_is_not_auto_match():
    """'John Smith'-style exact name on a common 2-token personal name must not block without corroboration."""
    wl = WatchList([ListEntry("X1", "Maria Garcia", "INDIVIDUAL", countries=["MX"], list_name="T")], name="t", source="T")
    s = SanctionsScreener(wl)
    assert s.screen("Maria Garcia")[0].level == "STRONG_POTENTIAL_MATCH"
    assert s.screen("Maria Garcia", countries=["MX"])[0].level == "MATCH"        # country corroborates


def test_fuzzy_hit_never_gets_automatic_floor_without_exactness(screener):
    m = screener.screen("Karim Al-Dazharri", countries=["SY"])[0]
    assert m.level in ("STRONG_POTENTIAL_MATCH", "POTENTIAL_MATCH")


def test_unrelated_and_common_names_do_not_match(screener):
    for name in ("Kunal Shaw", "Acme Manufacturing Inc", "Sarah Johnson", "Delta Freight Services", "moscow_trading_llc"):
        assert screener.screen(name) == [], name


def test_whitelist_suppresses_reviewed_false_positive():
    wl = WatchList([ListEntry("X1", "Acme Holdings", list_name="T")], name="t", source="T")
    assert SanctionsScreener(wl).screen("Acme Holdings")
    assert SanctionsScreener(wl, whitelist={"Acme Holdings"}).screen("Acme Holdings") == []


def test_parse_ofac_csv_individuals_aliases_programs_countries():
    entries = {e.uid: e for e in parse_ofac_csv(SDN, ALT, ADD)}
    assert len(entries) == 3
    person = entries["OFAC-173"]
    assert person.name == "Karim Hassan ABDUL" and person.entity_type == "INDIVIDUAL"
    assert person.aliases == ["Kareem H. ABDUL"] and person.programs == ["SDGT", "IFSR"]
    assert person.countries == ["LB"]
    assert entries["OFAC-36"].aliases == ["AERO-CARIBBEAN"] and entries["OFAC-36"].programs == ["CUBA"]
    assert entries["OFAC-200"].entity_type == "VESSEL"


def test_ofac_entries_are_searchable():
    wl = WatchList(parse_ofac_csv(SDN, ALT, ADD), name="OFAC", source="OFAC_SDN")
    m = SanctionsScreener(wl).screen("Aerocaribbean Airlines")[0]
    assert m.level == "MATCH" and m.list_name == "OFAC_SDN"


def test_download_ofac_uses_fallback_mirror(tmp_path):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if "sanctionslistservice" in str(request.url):
            return httpx.Response(503)
        return httpx.Response(200, content=b"1,x\n")

    sizes = sx.download_ofac(tmp_path, client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert set(sizes) == {"sdn.csv", "alt.csv", "add.csv"} and (tmp_path / "sdn.csv").exists()
    assert any("treasury.gov" in c for c in calls)


def test_download_failure_raises(tmp_path):
    with pytest.raises(RuntimeError):
        sx.download_ofac(tmp_path, client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500))))
