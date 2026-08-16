"""The demo inventory ChangeGuardian reasons over.

This is a **synthetic dataset** modelled on a mid-size e-commerce microservice
estate. It is not derived from any real production system. Every service,
incident, and past deployment below is invented to exercise the six scenarios
the pipeline classifies.

Pure data - importing this module has no side effects.
"""

from __future__ import annotations

from typing import Any

Service = dict[str, Any]

services: dict[str, Service] = {
    "payment-service":   {"java": "11", "spring_boot": "2.7", "memory_limit_gb": 2,   "peak_memory_gb": 1.6, "restarts_30d": 3, "criticality": "critical", "db": "payment-db",   "team": "payments",  "sla_pct": 99.95},
    "checkout-service":  {"java": "11", "spring_boot": "2.7", "memory_limit_gb": 2,   "peak_memory_gb": 1.8, "restarts_30d": 8, "criticality": "critical", "db": "checkout-db",  "team": "checkout",  "sla_pct": 99.99},
    "order-service":     {"java": "17", "spring_boot": "3.1", "memory_limit_gb": 1,   "peak_memory_gb": 0.6, "restarts_30d": 1, "criticality": "high",     "db": "order-db",     "team": "orders",    "sla_pct": 99.9},
    "user-service":      {"java": "17", "spring_boot": "3.0", "memory_limit_gb": 1,   "peak_memory_gb": 0.4, "restarts_30d": 0, "criticality": "medium",   "db": "user-db",      "team": "platform",  "sla_pct": 99.5},
    "notification-svc":  {"java": "11", "spring_boot": "2.7", "memory_limit_gb": 0.5, "peak_memory_gb": 0.3, "restarts_30d": 2, "criticality": "low",      "db": None,           "team": "platform",  "sla_pct": 98.0},
    "legacy-auth-svc":   {"java": "8",  "spring_boot": "2.3", "memory_limit_gb": 1,   "peak_memory_gb": 0.7, "restarts_30d": 5, "criticality": "high",     "db": "auth-db",      "team": "security",  "sla_pct": 99.99},
    "inventory-service": {"java": "11", "spring_boot": "2.7", "memory_limit_gb": 1,   "peak_memory_gb": 0.5, "restarts_30d": 1, "criticality": "medium",   "db": "inventory-db", "team": "warehouse", "sla_pct": 99.0},
}

libraries: dict[str, dict[str, Any]] = {
    "legacy-auth-client": {
        "current": "1.4.0",
        "breaking_version": "2.0.0",
        "used_by": ["payment-service", "checkout-service", "order-service", "user-service", "legacy-auth-svc"],
    },
    "common-utils": {
        "current": "3.1.0",
        "breaking_version": None,
        "used_by": ["payment-service", "checkout-service", "order-service"],
    },
}

api_consumers: dict[str, dict[str, Any]] = {
    "payment-api": {
        "provider": "payment-service",
        "consumers": ["checkout-service", "order-service", "user-service"],
        "fields": ["customer_id", "amount", "currency", "status"],
    },
    "order-api": {
        "provider": "order-service",
        "consumers": ["notification-svc", "inventory-service"],
        "fields": ["order_id", "customerId", "items", "total"],
    },
}

database_users: dict[str, dict[str, Any]] = {
    "payment-db":   {"shared_by": ["payment-service"],                    "has_nullable_cols": ["transaction.amount"]},
    "checkout-db":  {"shared_by": ["checkout-service"],                   "has_nullable_cols": []},
    "order-db":     {"shared_by": ["order-service", "inventory-service"], "has_nullable_cols": ["order.notes"]},
    "auth-db":      {"shared_by": ["legacy-auth-svc", "user-service"],    "has_nullable_cols": ["user.phone"]},
    "user-db":      {"shared_by": ["user-service"],                       "has_nullable_cols": ["user.middle_name"]},
    "inventory-db": {"shared_by": ["inventory-service"],                  "has_nullable_cols": []},
}

event_consumers: dict[str, dict[str, Any]] = {
    "order-created": {
        "producer": "order-service",
        "fields": ["orderId", "customerId", "customerEmail", "items", "total"],
        "consumers": {
            "notification-svc":  ["customerId", "customerEmail"],
            "inventory-service": ["orderId", "items"],
        },
    },
    "payment-settled": {
        "producer": "payment-service",
        "fields": ["paymentId", "orderId", "amount"],
        "consumers": {"order-service": ["paymentId", "orderId"]},
    },
}

compatibility_rules: dict[str, Any] = {
    "spring_boot_java": {"3.x": ">=17", "2.7.x": ">=11", "2.3.x": ">=8"},
    "spring_boot_breaking": {
        "2.7_to_3.x": [
            "javax -> jakarta namespace migration required",
            "Removed deprecated Spring APIs",
            "spring.factories auto-configuration format removed",
        ]
    },
    "memory_safety_buffer_pct": 0.20,
    "high_restart_threshold": 5,
}

incident_docs: list[dict[str, Any]] = [
    {"id": "INC-001", "service": "checkout-service", "severity": "P1",
     "title": "OOMKilled after memory reduction",
     "root_cause": "Memory limit set below peak usage during Black Friday. Pod restarted 14 times.",
     "lesson": "Never reduce memory limit below 120% of observed peak.",
     "financial_impact": 250_000, "duration_minutes": 120},
    {"id": "INC-002", "service": "payment-service", "severity": "P1",
     "title": "Spring Boot 3 migration broke javax imports",
     "root_cause": "javax.persistence not migrated to jakarta.persistence. 100% of payment pods crashed.",
     "lesson": "Run javax->jakarta migration script before upgrading to Spring Boot 3.",
     "financial_impact": 500_000, "duration_minutes": 45},
    {"id": "INC-003", "service": "order-service", "severity": "P2",
     "title": "NOT NULL constraint caused bulk insert failure",
     "root_cause": "Added NOT NULL constraint without backfilling existing NULL rows. Deployment blocked 4 hours.",
     "lesson": "Backfill NULLs before adding NOT NULL constraints.",
     "financial_impact": 50_000, "duration_minutes": 240},
    {"id": "INC-004", "service": "user-service", "severity": "P2",
     "title": "API field rename broke checkout",
     "root_cause": "Renamed customer_id to customerId without versioning. Checkout returned 500s.",
     "lesson": "Never rename API fields without a version bump or backward-compatible alias.",
     "financial_impact": 100_000, "duration_minutes": 60},
    {"id": "INC-005", "service": "legacy-auth-svc", "severity": "P1",
     "title": "legacy-auth-client 2.0 removed token refresh method",
     "root_cause": "Upgraded shared library without checking breaking changes. All services using old token refresh API broke.",
     "lesson": "Check breaking changes in shared library changelog before bulk upgrade.",
     "financial_impact": 750_000, "duration_minutes": 90},
    {"id": "INC-006", "service": "notification-svc", "severity": "P2",
     "title": "Missing customerEmail field in Kafka event",
     "root_cause": "customerEmail removed from order-created event. Notification service could not send emails.",
     "lesson": "Never remove event fields consumed by downstream services without a migration period.",
     "financial_impact": 75_000, "duration_minutes": 180},
]

memory_graph: list[dict[str, Any]] = [
    {"deployment": "DEP-101", "service": "payment-service",  "change": "Spring Boot 2.5 to 2.7",         "outcome": "success", "lessons": ["Ran full regression suite", "Deployed on low-traffic Sunday"]},
    {"deployment": "DEP-102", "service": "checkout-service", "change": "memory 2GB to 1.5GB",            "outcome": "failed",  "lessons": ["OOMKilled after 2 hours", "Rolled back immediately"]},
    {"deployment": "DEP-103", "service": "order-service",    "change": "ADD NOT NULL order.notes",       "outcome": "failed",  "lessons": ["Forgot to backfill NULLs", "4 hour P2 incident"]},
    {"deployment": "DEP-104", "service": "user-service",     "change": "API field rename user_name",     "outcome": "failed",  "lessons": ["Broke 2 downstream consumers", "Emergency rollback deployed"]},
    {"deployment": "DEP-105", "service": "legacy-auth-svc",  "change": "legacy-auth-client 1.3 to 1.4",  "outcome": "success", "lessons": ["Minor version - no breaking changes", "Tested in staging 1 week"]},
]

# Shown in the UI so a first-time visitor has something to click. One per scenario.
example_requests: list[dict[str, str]] = [
    {"scenario": "framework_upgrade", "label": "Spring Boot major upgrade",
     "request": "Upgrade payment-service from Spring Boot 2.7 to 3.2"},
    {"scenario": "resource_change", "label": "Memory limit reduction",
     "request": "Reduce checkout-service memory from 2GB to 1GB"},
    {"scenario": "db_schema", "label": "Non-null constraint",
     "request": "Add NOT NULL constraint to order.notes in order-service"},
    {"scenario": "api_contract", "label": "Breaking field rename",
     "request": "Change payment API response field from customer_id to customerId"},
    {"scenario": "shared_dependency", "label": "Shared library major bump",
     "request": "Upgrade legacy-auth-client from 1.4.0 to 2.0.0"},
    {"scenario": "event_schema", "label": "Kafka field removal",
     "request": "Remove customerEmail field from order-created Kafka event"},
]

def known_vocabulary() -> dict[str, list[str]]:
    """Everything intake can resolve.

    The input box accepts free text but understands a closed set. Surfacing that
    set is what stops a visitor typing a service that does not exist and getting
    a confident, meaningless score back.
    """
    return {
        "services": sorted(services),
        "libraries": sorted(libraries),
        "apis": sorted(api_consumers),
        "events": sorted(event_consumers),
    }


SCENARIOS = (
    "framework_upgrade",
    "resource_change",
    "db_schema",
    "api_contract",
    "shared_dependency",
    "event_schema",
)

__all__ = [
    "SCENARIOS",
    "known_vocabulary",
    "api_consumers",
    "compatibility_rules",
    "database_users",
    "event_consumers",
    "example_requests",
    "incident_docs",
    "libraries",
    "memory_graph",
    "services",
]
