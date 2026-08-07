"""Agent 7 - LLM Explanation.

The only agent that talks to a model, and the only one allowed to fail. Agents
1-6 have already produced the score, the blast radius, and the violations; this
one turns that into prose an on-call engineer can read at 3am.

If the provider is down, rate-limited, or simply not configured, the rule-based
explanation below is used instead and the report is otherwise identical. The
public demo has no auth, so this path is load-bearing rather than theoretical.
"""

from __future__ import annotations

import json
from typing import Any

from ..llm import LLMResult, get_client

SYSTEM_PROMPT = """You are ChangeGuardian AI, a production deployment risk advisor.
You will receive a completed risk analysis. The score and findings are already
correct - do not recompute or dispute them. Your job is to:
1. Write a plain-English explanation (3 sentences) of WHY this change is risky.
2. List exactly 3 concrete remediation steps an engineer should take BEFORE deploying.

Respond in this exact JSON format (no markdown fences):
{"explanation": "<3 sentence explanation>", "remediation": ["step 1", "step 2", "step 3"]}"""

_REMEDIATION_BY_SCENARIO: dict[str, list[str]] = {
    "framework_upgrade": [
        "Run javax->jakarta migration script on entire codebase",
        "Upgrade Java to 17+ on all pods before deploying",
        "Run full integration test suite against new Spring Boot version",
    ],
    "resource_change": [
        "Verify new memory limit is at least 20% above observed peak usage",
        "Set up OOMKill alerts before reducing limits",
        "Perform load test at peak traffic levels first",
    ],
    "db_schema": [
        "Backfill all NULL values in the target column before adding constraint",
        "Run migration in staging with production data copy first",
        "Coordinate deployment with all services sharing the database",
    ],
    "api_contract": [
        "Add backward-compatible alias alongside new field name",
        "Version the API endpoint (/v2/) before renaming fields",
        "Notify all consumer teams and agree migration timeline",
    ],
    "shared_dependency": [
        "Review CHANGELOG for all breaking changes between old and new version",
        "Test upgrade in isolation for each consuming service",
        "Coordinate a single release window across all affected teams",
    ],
    "event_schema": [
        "Add new field alongside old field (dual-write) during migration period",
        "Update all consumers to handle both old and new field names",
        "Remove old field only after all consumers confirm migration",
    ],
}

_FALLBACK_REMEDIATION = [
    "Review all rule violations",
    "Test in staging first",
    "Have rollback plan ready",
]


def rule_based_explanation(state: dict) -> tuple[str, list[str]]:
    """Deterministic prose, assembled from what agents 1-6 already established."""
    change_type = state.get("change_type", "")
    svc = state.get("service_name", "")
    score = state.get("risk_score", 0)
    violations = state.get("rule_violations", [])
    impact = state.get("impact_level", "unknown")
    incidents = state.get("similar_incidents", [])

    explanation = (
        f"This {change_type.replace('_', ' ')} change to {svc} carries {impact} risk "
        f"(score {score}/100). {len(violations)} rule violation(s) were detected that "
        "must be resolved before deployment. "
        + (
            f"A similar change previously caused: {incidents[0]['title']}."
            if incidents
            else "No identical past incident found but pattern matches are concerning."
        )
    )

    return explanation, _REMEDIATION_BY_SCENARIO.get(change_type, _FALLBACK_REMEDIATION)


def build_prompt(state: dict) -> str:
    return json.dumps(
        {
            "change_request": state.get("change_request"),
            "service": state.get("service_name"),
            "scenario": state.get("change_type"),
            "risk_score": state.get("risk_score"),
            "impact_level": state.get("impact_level"),
            "affected_services": state.get("affected_services", []),
            "rule_violations": state.get("rule_violations", []),
            "similar_incidents": [
                {"id": i["id"], "title": i["title"], "severity": i["severity"]}
                for i in state.get("similar_incidents", [])
            ],
            "risk_reasons": state.get("risk_reasons", []),
            "rollout_plan": state.get("rollout_plan", ""),
        },
        indent=2,
    )


def _parse(result: LLMResult, state: dict) -> tuple[str, list[str], str]:
    """Returns (explanation, remediation, source)."""
    if not result.ok:
        explanation, remediation = rule_based_explanation(state)
        return explanation, remediation, "rule-based"

    try:
        parsed = json.loads(result.text)
        explanation = parsed["explanation"]
        remediation = parsed.get("remediation", [])
    except (json.JSONDecodeError, KeyError, TypeError):
        # A model that returned prose instead of JSON is not a model outage, but
        # the report needs structure - fall back rather than show raw output.
        explanation, remediation = rule_based_explanation(state)
        return explanation, remediation, "rule-based"

    if not isinstance(remediation, list) or not remediation:
        _, remediation = rule_based_explanation(state)
    return explanation, [str(step) for step in remediation], "llm"


def build_report(state: dict, explanation: str, remediation: list[str], source: str) -> dict[str, Any]:
    return {
        "change_request": state.get("change_request"),
        "service": state.get("service_name"),
        "scenario": state.get("change_type"),
        "affected_services": state.get("affected_services", []),
        "similar_incidents": [
            {
                "id": i["id"],
                "title": i["title"],
                "severity": i["severity"],
                "financial_impact": i.get("financial_impact", 0),
            }
            for i in state.get("similar_incidents", [])
        ],
        "rule_violations": state.get("rule_violations", []),
        "memory_lessons": [
            {"deployment": m["deployment"], "outcome": m["outcome"], "lessons": m["lessons"]}
            for m in state.get("memory_lessons", [])
        ],
        "risk_score": state.get("risk_score"),
        "impact_level": state.get("impact_level"),
        "sla_impact": state.get("sla_impact"),
        "financial_impact": state.get("financial_impact", 0),
        "risk_reasons": state.get("risk_reasons", []),
        "rollout_plan": state.get("rollout_plan"),
        "llm_explanation": explanation,
        "llm_remediation": remediation,
        "llm_source": source,
    }


def _finish(state: dict, explanation: str, remediation: list[str], source: str) -> dict:
    return {
        **state,
        "llm_explanation": explanation,
        "llm_remediation": remediation,
        "llm_source": source,
        "report": build_report(state, explanation, remediation, source),
    }


def llm_explanation_agent(state: dict) -> dict:
    result = get_client().complete(build_prompt(state), SYSTEM_PROMPT, json_mode=True)
    return _finish(state, *_parse(result, state))


async def allm_explanation_agent(state: dict) -> dict:
    result = await get_client().acomplete(build_prompt(state), SYSTEM_PROMPT, json_mode=True)
    return _finish(state, *_parse(result, state))
