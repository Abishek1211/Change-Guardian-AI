"""Deterministic constraint checking (agent 4, "vectorless" half).

Vector search finds incidents that *look* similar. This finds violations that
*are* certain - a Spring Boot 3 upgrade on Java 11 will fail, no retrieval
confidence needed. Keeping the two separate is what makes the risk score
auditable rather than a vibe.
"""

from __future__ import annotations

from typing import Any

from ..data import (
    api_consumers,
    compatibility_rules,
    database_users,
    event_consumers,
    libraries,
    services,
)


def check_compatibility_rules(scenario: str, params: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    svc = params.get("service_name", "")
    svc_info = services.get(svc, {})

    if scenario == "framework_upgrade":
        new_ver = params.get("new_value", "")
        current_java = int(svc_info.get("java", "8"))
        if new_ver.startswith("3."):
            if current_java < 17:
                violations.append(
                    f"JAVA_MISMATCH: Spring Boot {new_ver} requires Java >=17, "
                    f"{svc} has Java {current_java}"
                )
            for breaking in compatibility_rules["spring_boot_breaking"]["2.7_to_3.x"]:
                violations.append(f"BREAKING_CHANGE: {breaking}")
        elif new_ver.startswith("2.7") and current_java < 11:
            violations.append(
                f"JAVA_MISMATCH: Spring Boot 2.7 requires Java >=11, "
                f"{svc} has Java {current_java}"
            )

    elif scenario == "resource_change":
        new_memory = params.get("new_memory_gb", 0.0)
        peak = svc_info.get("peak_memory_gb", 0.0)
        restarts = svc_info.get("restarts_30d", 0)
        min_safe = peak * (1 + compatibility_rules["memory_safety_buffer_pct"])
        if new_memory and new_memory < min_safe:
            violations.append(
                f"MEMORY_UNSAFE: {new_memory}GB < safe minimum {min_safe:.2f}GB "
                f"(peak {peak}GB + 20% buffer)"
            )
        if restarts >= compatibility_rules["high_restart_threshold"]:
            violations.append(
                f"HIGH_RESTART_RISK: {svc} had {restarts} restarts in 30d - OOMKill likely"
            )

    elif scenario == "db_schema":
        db = svc_info.get("db", "")
        db_info = database_users.get(db, {})
        column = params.get("column", "")
        if len(db_info.get("shared_by", [])) > 1:
            violations.append(
                f"SHARED_DB: {db} shared by {db_info['shared_by']} - all impacted"
            )
        if "NOT NULL" in params.get("constraint", "").upper() and column in db_info.get(
            "has_nullable_cols", []
        ):
            violations.append(
                f"NULL_VIOLATION: '{column}' has existing NULLs - backfill required "
                "before constraint"
            )

    elif scenario == "api_contract":
        old_field = params.get("old_value", "")
        new_field = params.get("new_value", "")
        for api, info in api_consumers.items():
            if info["provider"] != svc:
                continue
            if old_field in info["fields"]:
                violations.append(
                    f"BREAKING_API: '{old_field}' -> '{new_field}' in {api} "
                    "is not backward compatible"
                )
            if len(info["consumers"]) > 2:
                violations.append(
                    f"WIDE_IMPACT: {len(info['consumers'])} consumers of {api} "
                    f"will break: {info['consumers']}"
                )

    elif scenario == "shared_dependency":
        lib = params.get("library_name", "")
        new_ver = params.get("new_value", "")
        lib_info = libraries.get(lib, {})
        breaking = lib_info.get("breaking_version")
        users = lib_info.get("used_by", [])
        if breaking and new_ver >= breaking:
            violations.append(f"BREAKING_LIB: {lib} {new_ver} >= breaking version {breaking}")
        if len(users) > 3:
            violations.append(f"BULK_RISK: {len(users)} services use {lib}: {users}")

    elif scenario == "event_schema":
        event = params.get("event_name", "")
        removed_field = params.get("removed_field", "")
        event_info = event_consumers.get(event, {})
        for consumer, fields in event_info.get("consumers", {}).items():
            if removed_field in fields:
                crit = services.get(consumer, {}).get("criticality", "unknown")
                violations.append(
                    f"EVENT_FIELD_REMOVED: '{removed_field}' consumed by "
                    f"'{consumer}' ({crit}) - will break"
                )

    return violations
