"""
SentinelAI command line
=======================

    sentinelai serve [--host H --port P --reload]
    sentinelai analyze [FILE] [--no-llm] [--regime IN_PMLA] [-o out.json]
    sentinelai screen "Name" [--country RU]          # sanctions / PEP screening
    sentinelai sanctions update | info                # load / inspect the OFAC list
    sentinelai evaluate [--n 1500 --seed 7 --markdown FILE]
    sentinelai audit verify
    sentinelai scenarios
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from sentinelai.core.config import settings
from sentinelai.core.logging import setup_logging


def _print_result(label: str, d: Dict[str, Any]) -> None:
    ra = d["risk_assessment"]
    print(f"\n{'=' * 72}\n{label}\n{'=' * 72}")
    print(f"Risk {ra['risk_score']}/100 ({ra['risk_level']})  ->  {d['recommended_action']}   "
          f"[mode={d['mode']}, llm={d['llm_status']}]")
    if d.get("explanation"):
        print("Why (points):")
        for c in d["explanation"]["contributions"][:6]:
            print(f"  +{c['points']:>2}  {c['description']}")
        for cf in d["explanation"]["counterfactuals"][:1]:
            print(f"  Counterfactual: without '{cf['without']}' -> {cf['score_without']} ({cf['level_without']})")
    if d.get("typologies"):
        print("Typologies: " + ", ".join(t["name"] for t in d["typologies"]))
    for w in d.get("warnings", []):
        print(f"  ! {w}")
    if d.get("sar_required"):
        r = d.get("report") or {}
        print(f"{r.get('report_type', 'SAR')} required - deadline {d.get('sar_deadline')}")


def cmd_serve(args) -> None:
    import uvicorn
    if args.host:
        settings.api.host = args.host
    if args.port:
        settings.api.port = args.port
    reload = args.reload or settings.api.reload
    print(f"SentinelAI {settings.app_version} on http://{settings.api.host}:{settings.api.port}  "
          f"(env={settings.environment}, regime={settings.risk.regime}, llm_configured={settings.llm.api_key_configured})")
    uvicorn.run("sentinelai.api.app:app", host=settings.api.host, port=settings.api.port, reload=reload,
                workers=1 if reload else settings.api.workers, log_level=settings.monitoring.log_level.lower())


def cmd_analyze(args) -> None:
    from sentinelai.db.session import configure_engine, dispose_engine, init_db
    from sentinelai.models.schemas import AnalysisRequest
    from sentinelai.services.analysis import AnalysisService
    from sentinelai.services.scenarios import load_scenarios, scenario_request

    if args.file:
        raw = json.loads(Path(args.file).read_text())
        scenarios = raw["scenarios"] if isinstance(raw, dict) and "scenarios" in raw else raw
        items = [(s.get("scenario") or s.get("id") or f"case-{i}", scenario_request(s) if "request" not in s else s["request"])
                 for i, s in enumerate(scenarios, 1)]
    else:
        items = [(f"{s['scenario']}", scenario_request(s)) for s in load_scenarios()]

    async def run():
        configure_engine("sqlite+aiosqlite:///:memory:" if not args.persist else None)
        await init_db()
        service = AnalysisService()
        out = []
        for label, payload in items:
            payload = {**payload, "enable_llm_analysis": not args.no_llm, "persist": True}
            if args.regime:
                payload["regime"] = args.regime
            resp = await service.analyze_transaction(AnalysisRequest.model_validate(payload))
            d = json.loads(resp.model_dump_json())
            _print_result(label, d)
            out.append({"scenario": label, **{k: d[k] for k in ("risk_assessment", "recommended_action", "sar_required", "mode", "typologies", "explanation")}})
        await dispose_engine()
        return out

    results = asyncio.run(run())
    if args.output:
        Path(args.output).write_text(json.dumps(results, indent=2, default=str))
        print(f"\nResults written to {args.output}")
    high = sum(1 for r in results if r["risk_assessment"]["risk_level"] in ("HIGH", "CRITICAL"))
    print(f"\n{len(results)} cases, {high} high/critical, avg score "
          f"{sum(r['risk_assessment']['risk_score'] for r in results) / max(1, len(results)):.1f}")


def cmd_screen(args) -> None:
    from sentinelai.engine.pep import get_pep_screener
    from sentinelai.engine.sanctions import get_screener
    s = get_screener()
    print(f"List: {s.info['name']} ({s.info['entries']} entries, as of {s.info['as_of']}{', SYNTHETIC' if s.info['synthetic'] else ''})")
    matches = s.screen(args.name, [args.country] if args.country else [])
    if not matches:
        print("Sanctions: no hits")
    for m in matches:
        print(f"Sanctions: {m.level:24} {m.score:.3f}  '{args.name}' ~ '{m.listed_name}' [{', '.join(m.programs)}]"
              f"{'  corroborated by ' + ','.join(m.corroborated_by) if m.corroborated_by else ''}")
    pep = get_pep_screener().screen(args.name, args.occupation or "")
    for m in pep.list_matches:
        print(f"PEP list:  {m['score']:.3f}  '{m['listed_name']}' ({m['position']}, {m['country']})")
    for r in pep.role_indicators:
        print(f"PEP role indicator: {r['role']} ('{r['matched_text']}')")
    if not pep.is_pep_candidate:
        print("PEP: no indication")


def cmd_sanctions(args) -> None:
    from sentinelai.engine.sanctions import download_ofac, get_screener
    if args.action == "update":
        sizes = download_ofac()
        print("Downloaded: " + ", ".join(f"{k} ({v:,} bytes)" for k, v in sizes.items()))
        info = get_screener(reload=True).info
        print(f"Loaded {info['entries']:,} entries / {info['names_indexed']:,} names from {info['source']}")
    else:
        print(json.dumps(get_screener().info, indent=2))


def cmd_evaluate(args) -> None:
    from sentinelai.evaluation.report import render_markdown
    from sentinelai.evaluation.runner import run_benchmark, run_sanctions_matcher_eval
    bench = run_benchmark(args.n, args.seed, args.regime)
    matcher = run_sanctions_matcher_eval(seed=args.seed)
    md = render_markdown(bench, matcher)
    if args.markdown:
        Path(args.markdown).write_text(md)
        print(f"Report written to {args.markdown}")
    e = bench["engine"]
    print(f"n={args.n} seed={args.seed}: ROC-AUC {e['roc_auc']:.3f}, AP {e['average_precision']:.3f}, "
          f"@{e['threshold']}: P {e['precision']:.2f} R {e['recall']:.2f} FPR {e['fpr']:.3f}")
    if not args.markdown:
        print(md)


def cmd_audit(args) -> None:
    from sentinelai.db.session import init_db, session_scope
    from sentinelai.services.audit import audit

    async def run():
        await init_db()
        async with session_scope() as s:
            return await audit.verify(s)
    result = asyncio.run(run())
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 2)


def cmd_scenarios(_args) -> None:
    from sentinelai.services.scenarios import load_scenarios
    for s in load_scenarios():
        print(f"{s['id']:20} {s['scenario']}")


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(prog="sentinelai", description="SentinelAI - explainable AML intelligence")
    parser.add_argument("--version", action="version", version=f"SentinelAI {settings.app_version}")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("serve", help="Run the API server")
    p.add_argument("--host"), p.add_argument("--port", type=int)
    p.add_argument("--reload", action="store_true")
    p.set_defaults(fn=cmd_serve)

    p = sub.add_parser("analyze", help="Analyse scenarios (default: bundled demo scenarios)")
    p.add_argument("file", nargs="?", help="JSON file of scenarios/requests")
    p.add_argument("--no-llm", action="store_true", help="Deterministic engine only")
    p.add_argument("--regime", choices=["US_BSA", "IN_PMLA", "EU_AMLD"])
    p.add_argument("--persist", action="store_true", help="Write to the configured database (default: in-memory)")
    p.add_argument("-o", "--output")
    p.set_defaults(fn=cmd_analyze)

    p = sub.add_parser("screen", help="Screen a name against sanctions and PEP lists")
    p.add_argument("name"), p.add_argument("--country"), p.add_argument("--occupation")
    p.set_defaults(fn=cmd_screen)

    p = sub.add_parser("sanctions", help="Manage the sanctions list")
    p.add_argument("action", choices=["update", "info"])
    p.set_defaults(fn=cmd_sanctions)

    p = sub.add_parser("evaluate", help="Run the synthetic benchmark")
    p.add_argument("--n", type=int, default=1500), p.add_argument("--seed", type=int, default=7)
    p.add_argument("--regime", default="US_BSA", choices=["US_BSA", "IN_PMLA", "EU_AMLD"])
    p.add_argument("--markdown", help="Write the report to this file")
    p.set_defaults(fn=cmd_evaluate)

    p = sub.add_parser("audit", help="Audit trail tools")
    p.add_argument("action", choices=["verify"])
    p.set_defaults(fn=cmd_audit)

    p = sub.add_parser("scenarios", help="List bundled demo scenarios")
    p.set_defaults(fn=cmd_scenarios)

    args = parser.parse_args(argv)
    if not getattr(args, "fn", None):
        parser.print_help()
        return
    setup_logging(settings.monitoring.log_level if args.command == "serve" else "WARNING", "text")
    args.fn(args)


if __name__ == "__main__":
    main()
