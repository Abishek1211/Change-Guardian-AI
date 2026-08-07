"""Live check against the configured LLM provider.

    pip install openai python-dotenv
    # put LLM_API_KEY=... in .env, then:
    python backend/scripts/smoke_llm.py

Sends agent 7's real prompt shape - a finished deterministic risk report - and
verifies the model returns parseable JSON with an explanation and remediation
steps. Exercises the same client the pipeline uses, so a pass here means agent 7
will work.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:
    pass

from app.llm import get_client  # noqa: E402

SYSTEM = (
    "You are a senior SRE reviewing a deployment risk report. The analysis is "
    "already complete and correct - do not recompute the risk score. Explain it "
    "to an on-call engineer in at most 3 sentences, then give exactly 3 concrete "
    "remediation steps.\n"
    'Respond with JSON only: {"explanation": "...", "remediation": ["...", "...", "..."]}'
)

# A real agent-6 output for the canonical demo request.
REPORT = {
    "change_request": "Upgrade payment-service from Spring Boot 2.7 to 3.2",
    "service": "payment-service",
    "scenario": "framework_upgrade",
    "risk_score": 82,
    "impact_level": "critical",
    "affected_services": ["checkout-service", "order-service", "notification-svc"],
    "rule_violations": [
        "JAVA_VERSION: Spring Boot 3.x requires Java 17+, payment-service runs Java 11",
        "NAMESPACE_MIGRATION: javax.* -> jakarta.* is a breaking change",
    ],
    "similar_incidents": [
        {"id": "INC-201", "title": "Spring Boot 3 upgrade caused startup failure", "severity": "SEV1"}
    ],
    "risk_reasons": [
        "Critical service (+25)",
        "3 downstream services affected (+15)",
        "2 rule violations (+30)",
        "Matching SEV1 incident in history (+12)",
    ],
    "rollout_plan": "BLOCKED - resolve Java version and namespace migration first",
}


def main() -> int:
    client = get_client()
    print(f"provider : {client.config.describe()}")
    print(f"timeout  : {client.config.timeout_seconds}s\n")

    if not client.config.enabled:
        print("LLM is not configured. Set LLM_API_KEY in .env to run this check.")
        print("(The pipeline still works - agent 7 uses rule-based explanations.)")
        return 1

    result = client.complete(json.dumps(REPORT, indent=2), SYSTEM, json_mode=True)

    if not result.ok:
        print(f"FAILED  reason={result.reason}")
        print(f"        {result.error}")
        print(f"\nbreaker: {json.dumps(client.breaker.snapshot(), indent=2)}")
        return 1

    print(f"OK      {result.elapsed_ms} ms   "
          f"{result.usage.get('completion_tokens', '?')} completion tokens\n")

    try:
        parsed = json.loads(result.text)
    except json.JSONDecodeError as exc:
        print(f"WARNING model returned non-JSON ({exc}); agent 7 would fall back.\n")
        print(result.text)
        return 1

    print(f"explanation:\n  {parsed.get('explanation', '<missing>')}\n")
    print("remediation:")
    for i, step in enumerate(parsed.get("remediation", []), 1):
        print(f"  {i}. {step}")

    steps = parsed.get("remediation", [])
    if len(steps) != 3:
        print(f"\nWARNING expected 3 remediation steps, got {len(steps)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
