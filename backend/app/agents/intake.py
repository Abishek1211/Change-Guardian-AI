"""Agent 1 - Intake.

Regex parse of the change request into `service_name`, `old_value`,
`new_value`, plus scenario-specific extras. Deliberately not an LLM call: the
input vocabulary is small and closed, and a regex that fails is debuggable in a
way a hallucinated service name is not.
"""

from __future__ import annotations

import re

from ..data import api_consumers, event_consumers, libraries, services

# Ordered longest-first so "legacy-auth-client" is not shadowed by a shorter
# name that happens to be a substring of it.
_LIBRARY_NAMES = sorted(libraries, key=len, reverse=True)
_SERVICE_NAMES = sorted(services, key=len, reverse=True)

# APIs and Kafka events are owned by a service. A request phrased against the
# interface ("the payment API") still has to resolve to the service that
# provides it, or agents 3 and 6 have nothing to key their scenario logic on.
_API_OWNERS = {name: info["provider"] for name, info in api_consumers.items()}
_EVENT_OWNERS = {name: info["producer"] for name, info in event_consumers.items()}


def _loose(text: str) -> str:
    """Collapse the hyphen/space distinction: people write "payment API" for
    "payment-api" and "order service" for "order-service"."""
    return text.replace("-", " ")


def _resolve_owner(lowered: str, candidates: dict[str, str]) -> tuple[str, str] | None:
    """Find the longest matching name and return (matched_name, owning_service)."""
    loose_haystack = _loose(lowered)
    for name in sorted(candidates, key=len, reverse=True):
        if name in lowered or _loose(name) in loose_haystack:
            return name, candidates[name]
    return None

_MEMORY_RE = re.compile(r"from\s+(\d+(?:\.\d+)?)\s*GB\s+to\s+(\d+(?:\.\d+)?)\s*GB", re.I)
_API_FIELD_RE = re.compile(r"field\s+from\s+(\w+)\s+to\s+(\w+)", re.I)
# "from Spring Boot 2.7 to 3.2" - the version is not the first token after
# "from", so skip any product name in between and anchor on a digit. Without
# this the flagship example extracts nothing and the Java/jakarta violations
# never fire.
_VERSION_RE = re.compile(r"from\s+(?:[\w.\- ]*?\s)?(\d[\w.]*)\s+to\s+(\d[\w.]*)", re.I)
_GENERIC_RE = re.compile(r"from\s+([\w.]+)\s+to\s+([\w.]+)", re.I)
_NOT_NULL_RE = re.compile(r"NOT NULL constraint to\s+([\w.]+)", re.I)
_CONSTRAINT_RE = re.compile(r"constraint\s+to\s+([\w.]+)", re.I)
# Not case-insensitive by design: the trailing [a-z] anchors on a lowercase
# event name ("order-created") so a sentence-initial word cannot be captured.
_KAFKA_RE = re.compile(r"[Rr]emove\s+(\w+)\s+field\s+from\s+([a-z][\w-]+)")


def intake_agent(state: dict) -> dict:
    request = state["change_request"]
    lowered = request.lower()
    extra: dict = {}

    service_name = "unknown"
    for lib in _LIBRARY_NAMES:
        if lib in lowered:
            service_name = lib
            extra["library_name"] = lib
            break
    if service_name == "unknown":
        for svc in _SERVICE_NAMES:
            if svc in lowered:
                service_name = svc
                break

    # Fall back to the interface the request names, then to its owner. Exact
    # service names are tried first above so this never overrides a direct hit.
    if service_name == "unknown":
        match = _resolve_owner(lowered, _API_OWNERS)
        if match:
            extra["api_name"], service_name = match

    if service_name == "unknown":
        match = _resolve_owner(lowered, _EVENT_OWNERS)
        if match:
            extra["event_name"], service_name = match

    old_value = new_value = ""

    match = _MEMORY_RE.search(request)
    if match:
        old_value, new_value = match.group(1), match.group(2)
        extra["old_memory_gb"] = float(old_value)
        extra["new_memory_gb"] = float(new_value)

    match = _API_FIELD_RE.search(request)
    if match:
        old_value, new_value = match.group(1), match.group(2)

    if not old_value:
        match = _VERSION_RE.search(request) or _GENERIC_RE.search(request)
        if match:
            old_value, new_value = match.group(1), match.group(2)

    match = _NOT_NULL_RE.search(request)
    if match:
        extra["column"] = match.group(1)
        extra["constraint"] = "NOT NULL"
    else:
        match = _CONSTRAINT_RE.search(request)
        # "constraint to not null" would otherwise capture the keyword itself.
        if match and match.group(1).lower() not in ("not", "null"):
            extra["column"] = match.group(1)
            extra["constraint"] = "NOT NULL"

    match = _KAFKA_RE.search(request)
    if match:
        extra["removed_field"] = match.group(1)
        extra["event_name"] = match.group(2)

    return {
        **state,
        "service_name": service_name,
        "old_value": old_value,
        "new_value": new_value,
        "extra_params": extra,
    }
