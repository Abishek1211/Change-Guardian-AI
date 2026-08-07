"""Agent 2 - Scenario Router.

Keyword classification into one of six scenarios. Order matters: the checks run
most-specific first, because "Reduce checkout-service memory from 2GB to 1GB"
contains both a resource keyword and, via "service", nothing that should route
it to a framework upgrade.
"""

from __future__ import annotations

from ..data import libraries

_FRAMEWORK = ("spring boot", "spring", "framework")
_RESOURCE = ("memory", "cpu", "limit", "ram", "gb")
_DB_SCHEMA = ("not null", "schema", "constraint", "column", "migration")
_EVENT = ("kafka", "event", "topic", "stream")
_API = ("api", "field", "endpoint", "response", "rename")


def scenario_router(state: dict) -> dict:
    request = state["change_request"].lower()
    extra = state.get("extra_params", {})

    if any(k in request for k in _FRAMEWORK):
        change_type = "framework_upgrade"
    elif any(k in request for k in _RESOURCE):
        change_type = "resource_change"
    elif any(k in request for k in _DB_SCHEMA):
        change_type = "db_schema"
    elif any(k in request for k in _EVENT):
        change_type = "event_schema"
    elif "library_name" in extra or any(lib in request for lib in libraries):
        change_type = "shared_dependency"
    elif any(k in request for k in _API):
        change_type = "api_contract"
    else:
        change_type = "framework_upgrade"

    return {**state, "change_type": change_type}
