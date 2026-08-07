"""End-to-end pipeline tests.

Runs offline by default: LLM_API_KEY is cleared so agent 7 takes the
rule-based path and no network call happens. The deterministic assertions
below are the contract - if a refactor changes a risk score, this catches it.

    python backend/tests/test_pipeline.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Must be set before the LLM client reads configuration.
os.environ["LLM_API_KEY"] = ""
os.environ["LLM_BASE_URL"] = "https://api.groq.com/openai/v1"

from app.agents import AGENT_KEYS  # noqa: E402
from app.graph import get_affected_services, graph_payload  # noqa: E402
from app.pipeline import run_analysis, stream_analysis  # noqa: E402

# (request, expected scenario, expected service, minimum score)
CASES = [
    ("Upgrade payment-service from Spring Boot 2.7 to 3.2",
     "framework_upgrade", "payment-service", 75),
    ("Reduce checkout-service memory from 2GB to 1GB",
     "resource_change", "checkout-service", 75),
    ("Add NOT NULL constraint to order.notes in order-service",
     "db_schema", "order-service", 50),
    ("Change payment API response field from customer_id to customerId",
     "api_contract", "payment-service", 50),
    ("Upgrade legacy-auth-client from 1.4.0 to 2.0.0",
     "shared_dependency", "legacy-auth-client", 50),
    ("Remove customerEmail field from order-created Kafka event",
     "event_schema", "order-service", 25),
]

REQUIRED_REPORT_KEYS = {
    "change_request", "service", "scenario", "affected_services",
    "similar_incidents", "rule_violations", "memory_lessons", "risk_score",
    "impact_level", "sla_impact", "financial_impact", "risk_reasons",
    "rollout_plan", "llm_explanation", "llm_remediation",
}


def test_all_scenarios_classify_and_score():
    for request, scenario, service, min_score in CASES:
        report = run_analysis(request)
        assert report["scenario"] == scenario, \
            f"{request!r} -> {report['scenario']}, expected {scenario}"
        assert report["service"] == service, \
            f"{request!r} -> {report['service']}, expected {service}"
        assert report["risk_score"] >= min_score, \
            f"{request!r} scored {report['risk_score']}, expected >= {min_score}"


def test_versions_extract_from_product_name_phrasing():
    """Regression: "from Spring Boot 2.7 to 3.2" puts a product name between
    "from" and the version. The original regex anchored on the first token and
    silently extracted nothing, which disabled every version-dependent rule -
    the flagship example scored 85 instead of 100 with no violations listed."""
    report = run_analysis("Upgrade payment-service from Spring Boot 2.7 to 3.2")

    violations = " | ".join(report["rule_violations"])
    assert "JAVA_MISMATCH" in violations, \
        f"Java 11 vs Spring Boot 3 must be flagged, got: {report['rule_violations']}"
    assert "jakarta" in violations, "javax->jakarta migration must be flagged"

    reasons = " | ".join(report["risk_reasons"])
    assert "Java mismatch" in reasons
    assert "Spring Boot 3.x breaking migration" in reasons


def test_scenario_specific_rules_actually_fire():
    """Every scenario must produce at least one violation on its demo request.
    A scenario that silently scores generic risk looks fine and is useless."""
    for request, scenario, *_ in CASES:
        report = run_analysis(request)
        assert report["rule_violations"], \
            f"{scenario} produced no rule violations for {request!r}"


def test_report_has_full_contract():
    report = run_analysis(CASES[0][0])
    missing = REQUIRED_REPORT_KEYS - set(report)
    assert not missing, f"report missing keys: {sorted(missing)}"


def test_score_is_reconstructable_from_reasons():
    """The audit trail is the feature - every point must be accounted for."""
    report = run_analysis(CASES[0][0])
    total = 0
    for reason in report["risk_reasons"]:
        assert "(+" in reason, f"reason carries no points: {reason!r}"
        total += int(reason.rsplit("(+", 1)[1].rstrip(")"))
    # Scores cap at 100, so the reasons may legitimately sum higher.
    assert min(total, 100) == report["risk_score"], \
        f"reasons sum to {total}, score is {report['risk_score']}"


def test_score_is_bounded():
    for request, *_ in CASES:
        score = run_analysis(request)["risk_score"]
        assert 0 <= score <= 100, f"{request!r} scored {score}"


def test_rollout_matches_threshold():
    bands = [(25, "low"), (50, "medium"), (75, "high"), (100, "critical")]
    for request, *_ in CASES:
        report = run_analysis(request)
        expected = next(level for ceiling, level in bands if report["risk_score"] <= ceiling)
        assert report["impact_level"] == expected, \
            f"score {report['risk_score']} -> {report['impact_level']}, expected {expected}"


def test_falls_back_to_rule_based_without_key():
    report = run_analysis(CASES[0][0])
    assert report["llm_source"] == "rule-based"
    assert report["llm_explanation"], "fallback must still produce prose"
    assert len(report["llm_remediation"]) == 3, "fallback must give 3 steps"


def test_blast_radius_is_bidirectional():
    affected = get_affected_services("payment-service")
    assert "checkout-service" in affected, "consumers of payment-api must be included"
    assert "payment-service" not in affected, "a service is not in its own blast radius"


def test_unknown_service_degrades_gracefully():
    report = run_analysis("Upgrade some-service-that-does-not-exist to version 9")
    assert report["service"] == "unknown"
    assert report["affected_services"] == []
    assert report["risk_score"] > 0, "an unknown service should still score, not crash"


def test_graph_payload_shape():
    payload = graph_payload()
    assert payload["nodes"] and payload["edges"]
    node_ids = {n["id"] for n in payload["nodes"]}
    for edge in payload["edges"]:
        assert edge["source"] in node_ids and edge["target"] in node_ids, \
            f"dangling edge: {edge}"
    assert {"service", "database", "api", "kafka_event", "library"} <= {
        n["type"] for n in payload["nodes"]
    }


def test_stream_emits_every_agent_in_order():
    async def collect():
        return [event async for event in stream_analysis(CASES[0][0])]

    events = asyncio.run(collect())

    assert events[0]["event"] == "start"
    assert len(events[0]["agents"]) == 7

    agent_events = [e for e in events if e["event"] == "agent"]
    assert [e["agent"] for e in agent_events] == list(AGENT_KEYS)
    assert all(e["status"] == "complete" for e in agent_events)
    assert [e["index"] for e in agent_events] == list(range(1, 8))

    final = events[-1]
    assert final["event"] == "complete"
    assert final["report"]["risk_score"] == run_analysis(CASES[0][0])["risk_score"], \
        "streaming and batch paths must agree"


def test_stream_output_is_json_serialisable():
    import json

    async def collect():
        return [event async for event in stream_analysis(CASES[2][0])]

    for event in asyncio.run(collect()):
        json.dumps(event, default=str)


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failures = []
    for test in tests:
        try:
            test()
            print(f"  PASS  {test.__name__}")
        except Exception as exc:  # noqa: BLE001
            failures.append(test.__name__)
            print(f"  FAIL  {test.__name__}: {type(exc).__name__}: {exc}")

    print(f"\n{len(tests) - len(failures)}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
