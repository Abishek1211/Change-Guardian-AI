"""Agent 6 - Risk & Rollout.

Fully deterministic, no LLM. Every point added to the score appends a matching
line to `risk_reasons`, so the number is always reconstructable from the audit
trail. That property is the point of this agent - a risk score an engineer
cannot interrogate is one they will not act on.
"""

from __future__ import annotations

from ..data import api_consumers, database_users, event_consumers, libraries, services

BASE_SCORE = 10
CRITICALITY_POINTS = {"critical": 30, "high": 20, "medium": 10, "low": 5}
MAX_AFFECTED_POINTS = 25
MAX_VIOLATION_POINTS = 30

# Score -> (impact level, rollout strategy, operator-facing plan)
THRESHOLDS = (
    (25, "low", "direct", "DIRECT ROLLOUT - Low risk. Deploy with standard monitoring."),
    (50, "medium", "canary", "CANARY ROLLOUT - 5% traffic first, monitor 30 min, then 25%->100%."),
    (75, "high", "staged-rollout",
     "STAGED ROLLOUT - Deploy region-by-region with health checks. Rollback plan required."),
    (100, "critical", "block",
     "DEPLOYMENT BLOCKED - Resolve all violations before proceeding."),
)


def _scenario_points(state: dict, svc_info: dict) -> list[tuple[int, str]]:
    """Scenario-specific risk on top of the generic signals."""
    change_type = state.get("change_type", "")
    extra = state.get("extra_params", {})
    svc = state.get("service_name", "")
    found: list[tuple[int, str]] = []

    if change_type == "framework_upgrade":
        new_value = state.get("new_value", "")
        java = int(svc_info.get("java", "8"))
        if new_value.startswith("3.") and java < 17:
            found.append((20, f"Java mismatch: needs 17, has {java} (+20)"))
        if new_value.startswith("3."):
            found.append((15, "Spring Boot 3.x breaking migration (+15)"))

    elif change_type == "resource_change":
        new_memory = extra.get("new_memory_gb", 0.0)
        peak = svc_info.get("peak_memory_gb", 0.0)
        restarts = svc_info.get("restarts_30d", 0)
        if new_memory and new_memory < peak * 1.20:
            found.append((25, f"New mem {new_memory}GB < safe floor {peak * 1.2:.2f}GB (+25)"))
        if restarts >= 5:
            found.append((10, f"High restarts: {restarts} in 30d (+10)"))

    elif change_type == "db_schema":
        db = svc_info.get("db", "")
        db_info = database_users.get(db, {})
        column = extra.get("column", "")
        if len(db_info.get("shared_by", [])) > 1:
            found.append((15, f"Shared DB {db} (+15)"))
        if column and column in db_info.get("has_nullable_cols", []):
            found.append((20, f"Column '{column}' has NULLs - backfill required (+20)"))

    elif change_type == "api_contract":
        old_field = state.get("old_value", "")
        for api, info in api_consumers.items():
            if info["provider"] != svc:
                continue
            if old_field and old_field in info["fields"]:
                found.append((20, f"Breaking field rename '{old_field}' in {api} (+20)"))
            if len(info["consumers"]) > 2:
                found.append((10, f"{len(info['consumers'])} consumers at risk (+10)"))

    elif change_type == "shared_dependency":
        lib = extra.get("library_name", svc)
        new_value = state.get("new_value", "")
        breaking = libraries.get(lib, {}).get("breaking_version")
        if breaking and new_value and new_value >= breaking:
            found.append((25, f"Major version break: {lib} {new_value} >= {breaking} (+25)"))

    elif change_type == "event_schema":
        event = extra.get("event_name", "")
        removed = extra.get("removed_field", "")
        for consumer, fields in event_consumers.get(event, {}).get("consumers", {}).items():
            if removed and removed in fields:
                crit = services.get(consumer, {}).get("criticality", "")
                if crit in ("critical", "high"):
                    found.append((20, f"Removed '{removed}' used by {consumer} ({crit}) (+20)"))

    return found


def risk_rollout_agent(state: dict) -> dict:
    svc_info = services.get(state.get("service_name", ""), {})
    affected = state.get("affected_services", [])
    incidents = state.get("similar_incidents", [])
    violations = state.get("rule_violations", [])
    lessons = state.get("memory_lessons", [])

    score = BASE_SCORE
    reasons = [f"Base score (+{BASE_SCORE})"]

    criticality = svc_info.get("criticality", "medium")
    points = CRITICALITY_POINTS.get(criticality, 10)
    score += points
    reasons.append(f"Service criticality={criticality} (+{points})")

    points = min(len(affected) * 5, MAX_AFFECTED_POINTS)
    if points:
        score += points
        reasons.append(f"{len(affected)} affected service(s) (+{points})")

    # The closest matching past incident also supplies the financial estimate -
    # "what it cost last time" rather than a model of this specific change.
    p1 = [i for i in incidents if i.get("severity") == "P1"]
    p2 = [i for i in incidents if i.get("severity") == "P2"]
    financial_impact = 0
    if p1:
        score += 20
        financial_impact = p1[0].get("financial_impact", 0)
        reasons.append(f"Similar P1 incident: {p1[0]['id']} (+20)")
    elif p2:
        score += 10
        financial_impact = p2[0].get("financial_impact", 0)
        reasons.append(f"Similar P2 incident: {p2[0]['id']} (+10)")

    points = min(len(violations) * 15, MAX_VIOLATION_POINTS)
    if points:
        score += points
        reasons.append(f"{len(violations)} rule violation(s) (+{points})")

    if any(entry["outcome"] == "failed" for entry in lessons):
        score += 15
        reasons.append("Prior failed deployment for similar change (+15)")

    for points, reason in _scenario_points(state, svc_info):
        score += points
        reasons.append(reason)

    score = min(score, 100)

    for ceiling, impact, _strategy, plan in THRESHOLDS:
        if score <= ceiling:
            break

    return {
        **state,
        "risk_score": score,
        "impact_level": impact,
        "risk_reasons": reasons,
        "rollout_plan": plan,
        "financial_impact": financial_impact,
        "sla_impact": _sla_impact(score, svc_info.get("sla_pct", 99.0)),
    }


def _sla_impact(score: int, sla_pct: float) -> str:
    """A tight SLA turns a risky change into an expensive one - 99.99% allows
    about 4 minutes of downtime a month, so there is no room to absorb a bad
    rollout."""
    if score >= 75 and sla_pct >= 99.9:
        return "CRITICAL SLA RISK"
    if score >= 50 and sla_pct >= 99.0:
        return "SLA AT RISK"
    return "SLA ACCEPTABLE"
