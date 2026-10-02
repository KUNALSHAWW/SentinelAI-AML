"""Graph motifs as pure functions over edge lists."""

from datetime import timedelta

from sentinelai.engine import graph as g
from sentinelai.engine.types import Edge
from tests.conftest import NOW


def e(a, b, amt, hours_ago):
    return Edge(a, b, amt, NOW - timedelta(hours=hours_ago))


def test_fan_in_needs_enough_distinct_senders_in_window():
    edges = [e(f"s{i}", "hub", 1000, i * 3) for i in range(6)]
    assert g.find_fans(edges, {"hub"})[0]["type"] == "fan_in"
    assert g.find_fans(edges[:3], {"hub"}) == []
    spread = [e(f"s{i}", "hub", 1000, i * 100) for i in range(6)]         # same senders, but over weeks
    assert g.find_fans(spread, {"hub"}) == []
    same_sender = [e("s0", "hub", 1000, i) for i in range(8)]
    assert g.find_fans(same_sender, {"hub"}) == []


def test_fan_out():
    edges = [e("hub", f"r{i}", 500, i) for i in range(7)]
    assert g.find_fans(edges, {"hub"})[0]["type"] == "fan_out"


def test_pass_through_requires_high_ratio_and_short_delay():
    assert g.find_pass_through([e("a", "mid", 10_000, 10), e("mid", "b", 9_600, 6)], {"mid"})
    assert not g.find_pass_through([e("a", "mid", 10_000, 10), e("mid", "b", 3_000, 6)], {"mid"})
    assert not g.find_pass_through([e("a", "mid", 10_000, 200), e("mid", "b", 9_900, 6)], {"mid"})


def test_two_hop_cycle():
    cycles = g.find_cycles([e("a", "b", 100_000, 50), e("b", "a", 98_000, 20)], {"a"})
    assert len(cycles) == 1 and cycles[0]["length"] == 2


def test_long_cycle_and_time_ordering():
    ring = [e("a", "b", 100, 60), e("b", "c", 98, 40), e("c", "d", 97, 30), e("d", "e", 96, 20), e("e", "a", 95, 10)]
    assert g.find_cycles(ring, {"a"})[0]["length"] == 5
    backwards = [e("e", "a", 95, 60), e("d", "e", 96, 50), e("c", "d", 97, 40), e("b", "c", 98, 30), e("a", "b", 100, 20)]
    assert g.find_cycles(backwards, {"a"}) == []                          # money cannot return before it leaves


def test_cycle_requires_comparable_amounts():
    assert g.find_cycles([e("a", "b", 100_000, 50), e("b", "a", 5_000, 20)], {"a"}) == []


def test_dense_graph_search_is_bounded():
    nodes = [f"n{i}" for i in range(30)]
    edges = [e(a, b, 100, 1) for a in nodes for b in nodes if a != b]
    g.find_cycles(edges, {"n0"})            # must terminate quickly (search budget)


def test_analyze_produces_graph_payload_and_flags_edges(make_ctx):
    ctx = make_ctx(tx={"parties": ["Hub Co"], "sender_account": "Hub Co", "receiver_account": "Off Shore", "amount": 9000},
                   customer={"name": "Hub Co", "customer_id": "Hub Co", "transaction_history": [
                       {"amount": 1500, "counterparty": f"payer-{i}", "direction": "IN", "timestamp": (NOW - timedelta(hours=2 + i)).isoformat()} for i in range(7)]})
    f = g.analyze(ctx)
    assert {s.code for s in f.signals} >= {"NET_FAN_IN"}
    assert f.nodes and f.edges and any(x["flagged"] for x in f.edges) and any(x["current"] for x in f.edges)
