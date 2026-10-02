"""
Transaction-graph analytics
===========================

Money-laundering structure is relational, so this module reasons over a directed
multigraph of money flows rather than isolated rows. It implements the standard
AML graph motifs from the literature (AMLSim / AMLgentex / GARG-AML):

* **fan-in**  - many distinct senders -> one account (mule collection)
* **fan-out** - one account -> many distinct receivers (dispersion)
* **pass-through** - receive then forward >= 80 % within hours (funnel / layering)
* **cycles** - money returning to its origin through 2-5 hops (round-tripping)

Edges come from the customer's counterparty-tagged history, from any
``network_transactions`` supplied by the caller, and - in the service layer -
from edges persisted by earlier analyses, so the graph accumulates over time.
All detectors are pure functions over an edge list (easy to test and benchmark).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from sentinelai.engine.context import entity_key
from sentinelai.engine.types import NETWORK, Edge, EngineInput, Signal

FAN_MIN_COUNTERPARTIES = 5
FAN_WINDOW = timedelta(hours=72)
PASS_THROUGH_RATIO = 0.80
PASS_THROUGH_WINDOW = timedelta(hours=48)
CYCLE_MAX_LEN = 5
CYCLE_WINDOW = timedelta(days=30)
CYCLE_AMOUNT_TOLERANCE = 0.6      # smallest hop must be >= 60% of the largest


@dataclass
class GraphFindings:
    nodes: List[Dict[str, Any]] = field(default_factory=list)
    edges: List[Dict[str, Any]] = field(default_factory=list)
    highlights: List[Dict[str, Any]] = field(default_factory=list)
    signals: List[Signal] = field(default_factory=list)


def edges_from_input(ctx: EngineInput) -> List[Edge]:
    """Edges implied by the current transaction and the customer's tagged history."""
    me = entity_key(ctx.customer_id)
    edges = [Edge(ctx.sender, ctx.receiver, ctx.amount_usd, ctx.timestamp, "current")]
    for h in ctx.history:
        if not h.counterparty:
            continue
        other = entity_key(h.counterparty)
        if h.direction == "IN":
            edges.append(Edge(other, me, h.amount_usd, h.timestamp))
        else:
            edges.append(Edge(me, other, h.amount_usd, h.timestamp))
    edges += ctx.network_edges
    return _unique(edges)


def _unique(edges: Iterable[Edge]) -> List[Edge]:
    seen, out = set(), []
    for e in edges:
        if e.source == e.target:
            continue
        k = e.key()
        if k not in seen:
            seen.add(k)
            out.append(e)
    return out


def _window_groups(items: List[Tuple[Any, Edge]], window: timedelta) -> List[List[Tuple[Any, Edge]]]:
    """Slide a window over time-ordered edges; return the densest group."""
    items = sorted(items, key=lambda it: it[1].timestamp)
    best: List[Tuple[Any, Edge]] = []
    lo = 0
    for hi in range(len(items)):
        while items[hi][1].timestamp - items[lo][1].timestamp > window:
            lo += 1
        group = items[lo: hi + 1]
        if len({k for k, _ in group}) > len({k for k, _ in best}):
            best = group
    return [best] if best else []


def find_fans(edges: List[Edge], focus: Set[str]) -> List[Dict[str, Any]]:
    incoming: Dict[str, List[Tuple[str, Edge]]] = defaultdict(list)
    outgoing: Dict[str, List[Tuple[str, Edge]]] = defaultdict(list)
    for e in edges:
        incoming[e.target].append((e.source, e))
        outgoing[e.source].append((e.target, e))
    found = []
    for node in focus:
        for kind, table in (("fan_in", incoming), ("fan_out", outgoing)):
            for group in _window_groups(table.get(node, []), FAN_WINDOW):
                peers = {k for k, _ in group}
                if len(peers) >= FAN_MIN_COUNTERPARTIES:
                    found.append({
                        "type": kind, "node": node, "peers": sorted(peers),
                        "total_usd": round(sum(e.amount_usd for _, e in group), 2),
                        "edge_keys": [e.key() for _, e in group],
                    })
    return found


def find_pass_through(edges: List[Edge], focus: Set[str]) -> List[Dict[str, Any]]:
    inbound: Dict[str, List[Edge]] = defaultdict(list)
    outbound: Dict[str, List[Edge]] = defaultdict(list)
    for e in edges:
        inbound[e.target].append(e)
        outbound[e.source].append(e)
    found = []
    for node in focus:
        for incoming in inbound.get(node, []):
            forwarded = [o for o in outbound.get(node, [])
                         if timedelta(0) <= o.timestamp - incoming.timestamp <= PASS_THROUGH_WINDOW]
            total_out = sum(o.amount_usd for o in forwarded)
            if incoming.amount_usd > 0 and total_out >= PASS_THROUGH_RATIO * incoming.amount_usd and forwarded:
                hours = (max(o.timestamp for o in forwarded) - incoming.timestamp).total_seconds() / 3600
                found.append({
                    "type": "pass_through", "node": node, "received_usd": round(incoming.amount_usd, 2),
                    "forwarded_usd": round(total_out, 2), "hours": round(hours, 1),
                    "from": incoming.source, "to": sorted({o.target for o in forwarded}),
                    "edge_keys": [incoming.key()] + [o.key() for o in forwarded],
                })
                break
    return found


def find_cycles(edges: List[Edge], focus: Set[str], max_len: int = CYCLE_MAX_LEN) -> List[Dict[str, Any]]:
    """Time-ordered simple cycles (length 2..max_len) through any ``focus`` node."""
    out_edges: Dict[str, List[Edge]] = defaultdict(list)
    for e in edges:
        out_edges[e.source].append(e)
    cycles, seen_signatures = [], set()
    budget = [20_000]                       # bound the search on dense graphs

    def dfs(start: str, node: str, path: List[Edge], visited: Set[str]) -> None:
        budget[0] -= 1
        if len(path) >= max_len or budget[0] < 0:
            return
        for e in out_edges.get(node, []):
            if path and e.timestamp < path[-1].timestamp:
                continue                                   # money must move forward in time
            if path and e.timestamp - path[0].timestamp > CYCLE_WINDOW:
                continue
            if e.target == start and path:
                cycle = path + [e]
                amounts = [c.amount_usd for c in cycle]
                if min(amounts) >= CYCLE_AMOUNT_TOLERANCE * max(amounts):
                    sig = frozenset((c.source, c.target) for c in cycle)
                    if sig not in seen_signatures:
                        seen_signatures.add(sig)
                        cycles.append({
                            "type": "cycle", "nodes": [c.source for c in cycle],
                            "length": len(cycle), "amount_usd": round(min(amounts), 2),
                            "span_hours": round((cycle[-1].timestamp - cycle[0].timestamp).total_seconds() / 3600, 1),
                            "edge_keys": [c.key() for c in cycle],
                        })
            elif e.target not in visited and e.target != start:
                dfs(start, e.target, path + [e], visited | {e.target})

    for start in focus:
        dfs(start, start, [], {start})
    return cycles


def analyze(ctx: EngineInput, extra_edges: Optional[List[Edge]] = None) -> GraphFindings:
    edges = _unique(edges_from_input(ctx) + list(extra_edges or []))
    focus = {ctx.sender, ctx.receiver, entity_key(ctx.customer_id)} - {""}
    findings = GraphFindings()
    highlights: List[Dict[str, Any]] = []

    highlights += find_fans(edges, focus)
    highlights += find_pass_through(edges, focus)
    highlights += find_cycles(edges, focus)

    for h in highlights:
        if h["type"] == "fan_in":
            findings.signals.append(Signal(
                code="NET_FAN_IN", category=NETWORK, weight=0.46, subject=h["node"], typology="FAN_IN",
                description=f"{len(h['peers'])} distinct senders paid '{h['node']}' within 72h (USD {h['total_usd']:,.0f})",
                evidence=h, alert_type="NETWORK_ANOMALY"))
        elif h["type"] == "fan_out":
            findings.signals.append(Signal(
                code="NET_FAN_OUT", category=NETWORK, weight=0.46, subject=h["node"], typology="FAN_OUT",
                description=f"'{h['node']}' paid {len(h['peers'])} distinct receivers within 72h (USD {h['total_usd']:,.0f})",
                evidence=h, alert_type="NETWORK_ANOMALY"))
        elif h["type"] == "pass_through":
            findings.signals.append(Signal(
                code="NET_PASS_THROUGH", category=NETWORK, weight=0.50, subject=h["node"], typology="PASS_THROUGH",
                description=f"'{h['node']}' forwarded {h['forwarded_usd'] / max(h['received_usd'], 1):.0%} of USD "
                            f"{h['received_usd']:,.0f} within {h['hours']}h",
                evidence=h, alert_type="NETWORK_ANOMALY"))
        elif h["type"] == "cycle":
            findings.signals.append(Signal(
                code="NET_ROUND_TRIP", category=NETWORK, weight=0.70 if h["length"] <= 3 else 0.60,
                subject="->".join(sorted(h["nodes"])), typology="ROUND_TRIPPING",
                description=f"Funds returned to origin via {h['length']}-hop cycle ({' -> '.join(h['nodes'])} -> {h['nodes'][0]})",
                evidence=h, alert_type="NETWORK_ANOMALY"))

    highlighted_edges = {k for h in highlights for k in h.get("edge_keys", [])}
    degree: Dict[str, int] = defaultdict(int)
    for e in edges:
        degree[e.source] += 1
        degree[e.target] += 1
    findings.nodes = [
        {"id": n, "degree": d, "focus": n in focus, "customer": n == entity_key(ctx.customer_id)}
        for n, d in sorted(degree.items(), key=lambda kv: -kv[1])
    ][:60]
    keep = {n["id"] for n in findings.nodes}
    findings.edges = [
        {"source": e.source, "target": e.target, "amount_usd": round(e.amount_usd, 2),
         "timestamp": e.timestamp.isoformat(), "flagged": e.key() in highlighted_edges, "current": e.ref == "current"}
        for e in sorted(edges, key=lambda e: e.timestamp) if e.source in keep and e.target in keep
    ][:200]
    findings.highlights = [{k: v for k, v in h.items() if k != "edge_keys"} for h in highlights]
    return findings
