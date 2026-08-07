"""The seven agents, in pipeline order.

`AGENTS` is the single source of truth for the sequence. Both the LangGraph
builder and the SSE streamer read from it, so adding an agent in one place
cannot silently desynchronise the other.

`emits` names the state keys each agent is responsible for producing - the SSE
stream uses it to send only that agent's contribution rather than the whole
state on every step.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .explain import allm_explanation_agent, llm_explanation_agent, rule_based_explanation
from .graph_impact import graph_impact_agent
from .hybrid_rag import hybrid_rag_agent
from .intake import intake_agent
from .memory import memory_graph_agent
from .risk import risk_rollout_agent
from .router import scenario_router
from .state import CGState


@dataclass(frozen=True)
class AgentSpec:
    key: str
    label: str
    description: str
    run: Callable[[dict], dict]
    emits: tuple[str, ...]
    # Agent 7 has an async variant because it makes a network call; the rest are
    # pure CPU and would gain nothing from being coroutines.
    arun: Callable[[dict], Any] | None = None


AGENTS: tuple[AgentSpec, ...] = (
    AgentSpec(
        key="intake",
        label="Intake",
        description="Parse the change request into service, old value, new value",
        run=intake_agent,
        emits=("service_name", "old_value", "new_value", "extra_params"),
    ),
    AgentSpec(
        key="router",
        label="Scenario Router",
        description="Classify into one of six change scenarios",
        run=scenario_router,
        emits=("change_type",),
    ),
    AgentSpec(
        key="graph_impact",
        label="Graph Impact",
        description="Traverse the dependency graph for the blast radius",
        run=graph_impact_agent,
        emits=("affected_services",),
    ),
    AgentSpec(
        key="hybrid_rag",
        label="Hybrid RAG",
        description="Vector search over incidents plus deterministic rule checks",
        run=hybrid_rag_agent,
        emits=("similar_incidents", "rule_violations"),
    ),
    AgentSpec(
        key="memory_graph",
        label="Memory Graph",
        description="Look up how this change went last time",
        run=memory_graph_agent,
        emits=("memory_lessons",),
    ),
    AgentSpec(
        key="risk_rollout",
        label="Risk & Rollout",
        description="Deterministic 0-100 score and rollout strategy",
        run=risk_rollout_agent,
        emits=("risk_score", "impact_level", "risk_reasons", "rollout_plan",
               "financial_impact", "sla_impact"),
    ),
    AgentSpec(
        key="llm_explain",
        label="LLM Explanation",
        description="Plain-English reasoning and 3 remediation steps",
        run=llm_explanation_agent,
        arun=allm_explanation_agent,
        emits=("llm_explanation", "llm_remediation", "llm_source"),
    ),
)

AGENT_KEYS = tuple(spec.key for spec in AGENTS)

__all__ = [
    "AGENTS",
    "AGENT_KEYS",
    "AgentSpec",
    "CGState",
    "allm_explanation_agent",
    "graph_impact_agent",
    "hybrid_rag_agent",
    "intake_agent",
    "llm_explanation_agent",
    "memory_graph_agent",
    "risk_rollout_agent",
    "rule_based_explanation",
    "scenario_router",
]
