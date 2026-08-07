"""Agent 3 - Graph Impact.

Blast radius. Starts from the graph's structural reachability, then adds
scenario-specific edges the generic traversal would miss - a library upgrade
affects every consumer of the library, not just services adjacent to it.
"""

from __future__ import annotations

from ..data import api_consumers, database_users, event_consumers, libraries, services
from ..graph import G, get_affected_services


def graph_impact_agent(state: dict) -> dict:
    svc = state.get("service_name", "")
    change_type = state.get("change_type", "")
    extra = state.get("extra_params", {})

    affected: set[str] = set()

    if svc in G:
        affected.update(get_affected_services(svc))

    if change_type == "shared_dependency":
        lib = extra.get("library_name", svc)
        affected.update(libraries.get(lib, {}).get("used_by", []))

    elif change_type == "event_schema":
        event = extra.get("event_name", "")
        affected.update(event_consumers.get(event, {}).get("consumers", {}))

    elif change_type == "api_contract":
        for info in api_consumers.values():
            if info["provider"] == svc:
                affected.update(info["consumers"])

    elif change_type == "db_schema":
        db = services.get(svc, {}).get("db", "")
        affected.update(database_users.get(db, {}).get("shared_by", []))

    affected.discard(svc)
    # Databases, APIs, and events are graph nodes but not deployable units -
    # the blast radius is the set of services someone has to page.
    affected &= set(services)

    return {**state, "affected_services": sorted(affected)}
