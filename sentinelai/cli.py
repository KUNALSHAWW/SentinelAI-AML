"""
SentinelAI CLI Entry Point
==========================

Command-line interface for running the SentinelAI platform.
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from sentinelai.core.config import settings
from sentinelai.core.logging import get_logger, setup_logging

logger = get_logger(__name__)


def print_banner():
    """Print SentinelAI ASCII banner"""
    banner = """
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║   ███████╗███████╗███╗   ██╗████████╗██╗███╗   ██╗███████╗██╗                ║
║   ██╔════╝██╔════╝████╗  ██║╚══██╔══╝██║████╗  ██║██╔════╝██║                ║
║   ███████╗█████╗  ██╔██╗ ██║   ██║   ██║██╔██╗ ██║█████╗  ██║                ║
║   ╚════██║██╔══╝  ██║╚██╗██║   ██║   ██║██║╚██╗██║██╔══╝  ██║                ║
║   ███████║███████╗██║ ╚████║   ██║   ██║██║ ╚████║███████╗███████╗           ║
║   ╚══════╝╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚═╝╚═╝  ╚═══╝╚══════╝╚══════╝           ║
║                              █████╗ ██╗                                       ║
║                             ██╔══██╗██║                                       ║
║                             ███████║██║                                       ║
║                             ██╔══██║██║                                       ║
║                             ██║  ██║██║                                       ║
║                             ╚═╝  ╚═╝╚═╝                                       ║
║                                                                               ║
║   🛡️  Financial Crime Intelligence Platform v1.0.0                            ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
    """
    print(banner)


def run_server():
    """Run the FastAPI server"""
    import uvicorn
    
    print_banner()
    print(f"\n🚀 Starting SentinelAI API Server...")
    print(f"   Environment: {settings.environment}")
    print(f"   Host: {settings.api.host}")
    print(f"   Port: {settings.api.port}")
    print(f"   LLM Provider: {settings.llm.provider}")
    print(f"\n📚 API Documentation: http://{settings.api.host}:{settings.api.port}/docs")
    print()
    
    uvicorn.run(
        "sentinelai.api.app:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.api.reload,
        workers=settings.api.workers if not settings.api.reload else 1,
        log_level=settings.monitoring.log_level.lower(),
    )


def run_analysis(file_path: str, output_path: str = None):
    """Run analysis on a JSON file of cases"""
    from sentinelai.agents.orchestrator import AMLOrchestrator
    
    print_banner()
    print(f"\n🔍 Running AML Analysis...")
    print(f"   Input: {file_path}")
    
    # Load cases
    with open(file_path, "r") as f:
        cases = json.load(f)
    
    print(f"   Cases to analyze: {len(cases)}")
    print()
    
    # Initialize orchestrator
    orchestrator = AMLOrchestrator()
    
    results = []
    
    async def analyze_all():
        for i, case in enumerate(cases, 1):
            print(f"\n{'='*60}")
            print(f"Case {i}/{len(cases)}: {case.get('scenario', 'Unknown')}")
            print('='*60)
            
            # Parse timestamps
            tx = case["transaction"]
            if "timestamp" in tx and isinstance(tx["timestamp"], str):
                tx["timestamp"] = datetime.fromisoformat(tx["timestamp"])
            
            customer = case["customer"]
            for htx in customer.get("transaction_history", []):
                if isinstance(htx.get("timestamp"), str):
                    htx["timestamp"] = datetime.fromisoformat(htx["timestamp"])
            
            # Run analysis
            result = await orchestrator.analyze(tx, customer)
            
            # Print results
            print(f"\n📊 Risk Score: {result['risk_score']}/100")
            print(f"🎯 Risk Level: {result['risk_level']}")
            print(f"📋 Decision Path: {' → '.join(result['decision_path'])}")
            
            if result.get("alerts"):
                print(f"\n🚨 Alerts ({len(result['alerts'])}):")
                for alert in result["alerts"][:5]:
                    print(f"   • {alert}")
            
            if result.get("risk_factors"):
                print(f"\n⚠️ Risk Factors ({len(result['risk_factors'])}):")
                for factor in result["risk_factors"][:5]:
                    print(f"   • {factor}")
            
            if result.get("sar_required"):
                print(f"\n📄 SAR Required: Yes")
                if result.get("case_id"):
                    print(f"   Case ID: {result['case_id']}")
            
            results.append({
                "scenario": case.get("scenario"),
                "risk_score": result["risk_score"],
                "risk_level": result["risk_level"],
                "sar_required": result.get("sar_required", False),
                "alerts": result.get("alerts", []),
                "decision_path": result.get("decision_path", [])
            })
    
    asyncio.run(analyze_all())
    
    # Save results
    if output_path:
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n✅ Results saved to: {output_path}")
    
    print(f"\n{'='*60}")
    print("Analysis Complete!")
    print(f"{'='*60}")
    
    # Summary
    high_risk = sum(1 for r in results if r["risk_level"] in ["HIGH", "CRITICAL"])
    sars = sum(1 for r in results if r["sar_required"])
    avg_score = sum(r["risk_score"] for r in results) / len(results) if results else 0
    
    print(f"\n📈 Summary:")
    print(f"   Total Cases: {len(results)}")
    print(f"   High/Critical Risk: {high_risk}")
    print(f"   SAR Required: {sars}")
    print(f"   Average Risk Score: {avg_score:.1f}")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="SentinelAI - Financial Crime Intelligence Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  sentinelai serve                    Start the API server
  sentinelai analyze cases.json       Analyze cases from JSON file
  sentinelai analyze cases.json -o results.json
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Serve command
    serve_parser = subparsers.add_parser("serve", help="Start the API server")
    serve_parser.add_argument(
        "--host", default=None,
        help=f"Host to bind (default: {settings.api.host})"
    )
    serve_parser.add_argument(
        "--port", type=int, default=None,
        help=f"Port to bind (default: {settings.api.port})"
    )
    serve_parser.add_argument(
        "--reload", action="store_true",
        help="Enable auto-reload for development"
    )
    
    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze transactions")
    analyze_parser.add_argument(
        "input", help="Input JSON file with cases"
    )
    analyze_parser.add_argument(
        "-o", "--output", help="Output JSON file for results"
    )
    
    # Version
    parser.add_argument(
        "--version", action="version",
        version=f"SentinelAI v{settings.app_version}"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(
        log_level=settings.monitoring.log_level,
        log_format="text"  # Use colored text for CLI
    )
    
    if args.command == "serve":
        if args.host:
            settings.api.host = args.host
        if args.port:
            settings.api.port = args.port
        if args.reload:
            settings.api.reload = True
        run_server()
    
    elif args.command == "analyze":
        if not Path(args.input).exists():
            print(f"Error: File not found: {args.input}")
            sys.exit(1)
        run_analysis(args.input, args.output)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
