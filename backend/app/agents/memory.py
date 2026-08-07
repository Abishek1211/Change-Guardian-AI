"""Agent 5 - Memory Graph.

Prior deployment outcomes for this service, or for this kind of change on any
service. "We tried this before and it went badly" is the highest-signal input
the pipeline has, so a match here is worth more than a semantic incident hit.
"""

from __future__ import annotations

from ..data import memory_graph

_SCENARIO_KEYWORDS = {
    "framework_upgrade": ("spring boot", "java", "upgrade", "migrate"),
    "resource_change": ("memory", "gb", "oom", "resource"),
    "db_schema": ("not null", "schema", "constraint", "null"),
    "api_contract": ("api", "field", "rename", "endpoint"),
    "shared_dependency": ("library", "client", "dependency"),
    "event_schema": ("kafka", "event", "field"),
}


def memory_graph_agent(state: dict) -> dict:
    svc = state.get("service_name", "")
    keywords = _SCENARIO_KEYWORDS.get(state.get("change_type", ""), ())

    lessons = [
        {
            "deployment": entry["deployment"],
            "service": entry["service"],
            "change": entry["change"],
            "outcome": entry["outcome"],
            "lessons": entry["lessons"],
        }
        for entry in memory_graph
        if entry["service"] == svc
        or any(k in entry["change"].lower() for k in keywords)
    ]

    return {**state, "memory_lessons": lessons}
