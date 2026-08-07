"""Shared pipeline state.

Every agent takes the state dict and returns a new one with its own keys added.
Nothing mutates in place, so the SSE stream can snapshot after each step.
"""

from __future__ import annotations

from typing import Any, TypedDict


class CGState(TypedDict, total=False):
    # Agent 1 - intake
    change_request: str
    service_name: str
    old_value: str
    new_value: str
    extra_params: dict[str, Any]

    # Agent 2 - scenario router
    change_type: str

    # Agent 3 - graph impact
    affected_services: list[str]

    # Agent 4 - hybrid RAG
    similar_incidents: list[dict[str, Any]]
    rule_violations: list[str]

    # Agent 5 - memory graph
    memory_lessons: list[dict[str, Any]]

    # Agent 6 - risk & rollout
    risk_score: int
    impact_level: str
    risk_reasons: list[str]
    rollout_plan: str
    financial_impact: int  # USD, from the closest matching past incident
    sla_impact: str

    # Agent 7 - LLM explanation
    llm_explanation: str
    llm_remediation: list[str]
    llm_source: str  # "llm" | "rule-based"

    report: dict[str, Any]
