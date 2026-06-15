#!/usr/bin/env python3
"""
ChangeGuardian AI - Command-Line Usage Example

Run this script to analyze deployment changes from the command line.

Usage:
  python examples/cli_example.py "Upgrade payment-service Spring Boot 2.7 to 3.2"
  python examples/cli_example.py --scenario framework_upgrade
  python examples/cli_example.py --batch examples/changes.txt
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def format_report(report: Dict[str, Any]) -> str:
    """Format risk analysis report for terminal output."""

    output = []
    output.append("\n" + "═" * 80)
    output.append("  DEPLOYMENT RISK ANALYSIS REPORT")
    output.append("═" * 80)

    # Basic info
    output.append(f"\n📝 CHANGE REQUEST:")
    output.append(f"   {report.get('change_request', 'N/A')}")

    output.append(f"\n🎯 SCENARIO:")
    output.append(f"   {report.get('scenario', 'unknown').upper()}")

    # Risk score
    risk_score = report.get('risk_score', 0)
    impact_level = report.get('impact_level', 'unknown').upper()

    risk_color = "🔴" if risk_score > 75 else "🟡" if risk_score > 50 else "🟢"
    output.append(f"\n{risk_color} RISK ASSESSMENT:")
    output.append(f"   Score: {risk_score}/100")
    output.append(f"   Level: {impact_level}")
    output.append(f"   Plan: {report.get('rollout_plan', 'N/A')}")

    # SLA Impact
    sla_impact = report.get('sla_impact', 'NONE')
    if 'CRITICAL' in sla_impact:
        output.append(f"\n⚠️  SLA IMPACT: {sla_impact}")
    elif 'RISK' in sla_impact:
        output.append(f"\n⚠️  SLA IMPACT: {sla_impact}")

    # Financial impact
    financial_impact = report.get('financial_impact', 0)
    if financial_impact > 0:
        output.append(f"\n💰 FINANCIAL IMPACT (if fails):")
        output.append(f"   ${financial_impact:,}")

    # Affected services
    affected = report.get('affected_services', [])
    if affected:
        output.append(f"\n📊 AFFECTED SERVICES ({len(affected)}):")
        for service in affected[:10]:  # Limit to first 10
            output.append(f"   • {service}")
        if len(affected) > 10:
            output.append(f"   ... and {len(affected) - 10} more")

    # Similar incidents
    incidents = report.get('similar_incidents', [])
    if incidents:
        output.append(f"\n📋 SIMILAR PAST INCIDENTS:")
        for incident in incidents[:5]:
            output.append(f"   • {incident.get('id')}: {incident.get('title')}")
            output.append(f"     Severity: {incident.get('severity')} | Impact: ${incident.get('financial_impact', 0):,}")

    # Rule violations
    violations = report.get('rule_violations', [])
    if violations:
        output.append(f"\n⚠️  RULE VIOLATIONS ({len(violations)}):")
        for violation in violations[:5]:
            output.append(f"   • {violation}")
        if len(violations) > 5:
            output.append(f"   ... and {len(violations) - 5} more")

    # Risk breakdown
    reasons = report.get('risk_reasons', [])
    if reasons:
        output.append(f"\n📈 RISK SCORE BREAKDOWN:")
        for reason in reasons[:10]:
            output.append(f"   • {reason}")

    # LLM Explanation
    explanation = report.get('llm_explanation', '')
    if explanation:
        output.append(f"\n💭 LLM ANALYSIS:")
        # Wrap text at 76 chars
        lines = explanation.split('\n')
        for line in lines[:10]:  # First 10 lines
            if len(line) > 76:
                words = line.split()
                current_line = ""
                for word in words:
                    if len(current_line) + len(word) + 1 > 76:
                        output.append(f"   {current_line}")
                        current_line = word
                    else:
                        current_line += " " + word if current_line else word
                if current_line:
                    output.append(f"   {current_line}")
            else:
                output.append(f"   {line}")

    # Remediation steps
    remediation = report.get('llm_remediation', [])
    if remediation:
        output.append(f"\n✅ REMEDIATION STEPS:")
        for i, step in enumerate(remediation, 1):
            output.append(f"   {i}. {step}")

    output.append("\n" + "═" * 80 + "\n")

    return "\n".join(output)

def analyze_change(change_request: str) -> Dict[str, Any]:
    """Analyze a deployment change."""
    try:
        from src.changeguardian_enhanced import workflow

        print(f"🔍 Analyzing: {change_request}")
        print("⏳ Processing (this may take 5-30 seconds)...")

        result = workflow.invoke({"change_request": change_request})
        return result.get("report", {})

    except ImportError as e:
        print(f"❌ Error: Could not import ChangeGuardian: {e}")
        print("   Run: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="ChangeGuardian AI - Deployment Risk Analysis CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python examples/cli_example.py "Upgrade payment-service Spring Boot 2.7 to 3.2"
  python examples/cli_example.py --file changes.txt
  python examples/cli_example.py --json "Reduce checkout-service memory to 1GB"

Output Formats:
  --text     : Human-readable report (default)
  --json     : JSON format (for integration)
  --csv      : CSV format (for spreadsheets)
        """
    )

    parser.add_argument('change_request', nargs='?', help='Deployment change to analyze')
    parser.add_argument('--file', '-f', help='Read changes from file (one per line)')
    parser.add_argument('--batch', '-b', help='Batch mode: analyze multiple changes')
    parser.add_argument('--output', '-o', help='Output file (default: stdout)')
    parser.add_argument('--format', '-fmt', default='text', choices=['text', 'json', 'csv'],
                        help='Output format')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')

    args = parser.parse_args()

    # Validate input
    if not args.change_request and not args.file and not args.batch:
        parser.print_help()
        sys.exit(1)

    results = []

    # Single change
    if args.change_request:
        report = analyze_change(args.change_request)
        results.append(report)

    # File input
    elif args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"❌ File not found: {args.file}")
            sys.exit(1)

        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    print(f"📌 Processing: {line}")
                    report = analyze_change(line)
                    results.append(report)

    # Format output
    output_lines = []

    if args.format == 'text':
        for report in results:
            output_lines.append(format_report(report))

    elif args.format == 'json':
        output_lines.append(json.dumps(results, indent=2))

    elif args.format == 'csv':
        import csv
        import io

        csv_buffer = io.StringIO()
        if results:
            fieldnames = ['change_request', 'scenario', 'risk_score', 'impact_level', 'rollout_plan']
            writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
            writer.writeheader()
            for report in results:
                writer.writerow({k: report.get(k, '') for k in fieldnames})

        output_lines.append(csv_buffer.getvalue())

    # Output
    output_text = "\n".join(output_lines)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(output_text)
        print(f"\n✅ Results saved to {args.output}")
    else:
        print(output_text)

if __name__ == "__main__":
    main()
