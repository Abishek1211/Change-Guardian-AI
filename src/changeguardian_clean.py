#!/usr/bin/env python
# coding: utf-8

# # ChangeGuardian AI
# ### LangGraph Â· NetworkX Graph RAG Â· FAISS Vector RAG Â· Vectorless Rules Â· Local LLM (Ollama/AMD)
# 
# **Architecture:**
# ```
# Change Request
#      
# [1] Intake Agent           extract service, old/new value, extra params
#     
# [2] Scenario Router      classify: framework_upgrade | resource_change | db_schema |
#                                    api_contract | shared_dependency | event_schema
#     
# [3] Graph Impact Agent     NetworkX: find all affected services/DBs/APIs/Kafka
#      
# [4] Hybrid RAG Agent       FAISS vector search (similar incidents)
#                           + Vectorless rule lookup (exact constraint checks)
#      
# [5] Memory Graph Agent    check prior deployment outcomes for same service
#   
# [6] Risk & Rollout Agent   deterministic scoring (0-100) + rollout decision
#    
# [7] LLM Explanation Agent Local Qwen/Mistral via Ollama (AMD ROCm / CPU RAM)
#                            generates: plain-english explanation + remediation steps
#     
#    Report
# ```
# 
# **Why AMD?** The local LLM loads entirely into system RAM (or AMD GPU via ROCm). No cloud API. No data leaves the machine. Runs on AMD EPYC / Ryzen with large RAM or AMD Radeon GPU.

# Cell 1 — Install dependencies
# numpy 2.x is the resident version on this machine.
# Fix: upgrade pyarrow (16+) and scikit-learn (1.5+) to numpy-2.x compatible builds.


import numpy, pyarrow, sklearn
print(f"numpy        : {numpy.__version__}")
print(f"pyarrow      : {pyarrow.__version__}")
print(f"scikit-learn : {sklearn.__version__}")
print("All dependencies OK — proceed to Cell 2.")

# ── Ollama setup (for local LLM on AMD hardware) ──────────────────────────────
# Download Ollama: https://ollama.com/download  then run in a terminal:
#   ollama pull qwen2.5:3b      (16 GB RAM)
#   ollama pull qwen2.5:7b      (32 GB RAM)
#   ollama pull qwen2.5:14b     (64 GB RAM)
# The notebook works WITHOUT Ollama — rule-based fallback activates automatically.


# Cell 2 â€” AMD System Info + LLM Setup
import psutil, platform, os, requests, json, time

# â”€â”€ System info (AMD RAM / CPU) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
ram_gb      = psutil.virtual_memory().total / (1024 ** 3)
cpu_cores   = psutil.cpu_count(logical=True)
cpu_phys    = psutil.cpu_count(logical=False)
cpu_name    = platform.processor() or "Unknown CPU"

print("=" * 60)
print("  AMD SYSTEM PROFILE")
print("=" * 60)
print(f"  CPU          : {cpu_name}")
print(f"  Physical cores: {cpu_phys}    Logical cores: {cpu_cores}")
print(f"  Total RAM    : {ram_gb:.1f} GB")
print(f"  Available RAM: {psutil.virtual_memory().available / (1024**3):.1f} GB")
print("=" * 60)

# â”€â”€ Recommend model based on available RAM â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
if ram_gb >= 64:
    OLLAMA_MODEL = "qwen2.5:14b"
elif ram_gb >= 32:
    OLLAMA_MODEL = "qwen2.5:7b"
else:
    OLLAMA_MODEL = "qwen2.5:3b"

OLLAMA_URL     = "http://localhost:11434/api/generate"
OLLAMA_TIMEOUT = 120  # seconds

# â”€â”€ Test Ollama connectivity â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _ollama_available() -> bool:
    try:
        r = requests.get("http://localhost:11434", timeout=3)
        return r.status_code == 200
    except Exception:
        return False

OLLAMA_READY = _ollama_available()
print(f"\n  Recommended model : {OLLAMA_MODEL}")
print(f"  Ollama status     : {'RUNNING' if OLLAMA_READY else 'NOT FOUND (rule-based fallback will be used)'}")

# â”€â”€ LLM call wrapper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def call_llm(prompt: str, system: str = "") -> str:
    """
    Call local Ollama LLM. Uses AMD GPU (ROCm) or CPU RAM automatically.
    Falls back to rule-based summary if Ollama is not running.
    """
    if not OLLAMA_READY:
        return "[LLM offline â€” rule-based summary only]"
    try:
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        t0 = time.time()
        resp = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": full_prompt, "stream": False},
            timeout=OLLAMA_TIMEOUT,
        )
        elapsed = time.time() - t0
        data = resp.json()
        ram_used = psutil.virtual_memory().used / (1024 ** 3)
        print(f"  [LLM] {elapsed:.1f}s | RAM in use: {ram_used:.1f}/{ram_gb:.1f} GB")
        return data.get("response", "").strip()
    except Exception as e:
        return f"[LLM error: {e}]"

# Warm up (optional â€” loads model into RAM/VRAM once)
if OLLAMA_READY:
    print("\nWarming up LLM (loads model into AMD RAM)...")
    call_llm("Say 'ready' in one word.")
    print(f"  LLM warm. RAM used: {psutil.virtual_memory().used/(1024**3):.1f} GB")


# Cell 3 â€” Enterprise Data (realistic production inventory)

services = {
    "payment-service":   {"java": "11", "spring_boot": "2.7", "memory_limit_gb": 2,   "peak_memory_gb": 1.6, "restarts_30d": 3,  "criticality": "critical", "db": "payment-db",   "team": "payments"},
    "checkout-service":  {"java": "11", "spring_boot": "2.7", "memory_limit_gb": 2,   "peak_memory_gb": 1.8, "restarts_30d": 8,  "criticality": "critical", "db": "checkout-db",  "team": "checkout"},
    "order-service":     {"java": "17", "spring_boot": "3.1", "memory_limit_gb": 1,   "peak_memory_gb": 0.6, "restarts_30d": 1,  "criticality": "high",     "db": "order-db",    "team": "orders"},
    "user-service":      {"java": "17", "spring_boot": "3.0", "memory_limit_gb": 1,   "peak_memory_gb": 0.4, "restarts_30d": 0,  "criticality": "medium",   "db": "user-db",     "team": "platform"},
    "notification-svc":  {"java": "11", "spring_boot": "2.7", "memory_limit_gb": 0.5, "peak_memory_gb": 0.3, "restarts_30d": 2,  "criticality": "low",      "db": None,          "team": "platform"},
    "legacy-auth-svc":   {"java": "8",  "spring_boot": "2.3", "memory_limit_gb": 1,   "peak_memory_gb": 0.7, "restarts_30d": 5,  "criticality": "high",     "db": "auth-db",     "team": "security"},
    "inventory-service": {"java": "11", "spring_boot": "2.7", "memory_limit_gb": 1,   "peak_memory_gb": 0.5, "restarts_30d": 1,  "criticality": "medium",   "db": "inventory-db","team": "warehouse"},
}

libraries = {
    "legacy-auth-client": {
        "current": "1.4.0", "breaking_version": "2.0.0",
        "used_by": ["payment-service", "checkout-service", "order-service", "user-service", "legacy-auth-svc"],
    },
    "common-utils": {
        "current": "3.1.0", "breaking_version": None,
        "used_by": ["payment-service", "checkout-service", "order-service"],
    },
}

api_consumers = {
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

database_users = {
    "payment-db":   {"shared_by": ["payment-service"],                    "has_nullable_cols": ["transaction.amount"]},
    "checkout-db":  {"shared_by": ["checkout-service"],                   "has_nullable_cols": []},
    "order-db":     {"shared_by": ["order-service", "inventory-service"], "has_nullable_cols": ["order.notes"]},
    "auth-db":      {"shared_by": ["legacy-auth-svc", "user-service"],    "has_nullable_cols": ["user.phone"]},
    "user-db":      {"shared_by": ["user-service"],                       "has_nullable_cols": ["user.middle_name"]},
    "inventory-db": {"shared_by": ["inventory-service"],                  "has_nullable_cols": []},
}

event_consumers = {
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

compatibility_rules = {
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

incident_docs = [
    {"id": "INC-001", "service": "checkout-service", "severity": "P1",
     "title": "OOMKilled after memory reduction",
     "root_cause": "Memory limit set below peak usage during Black Friday. Pod restarted 14 times.",
     "lesson": "Never reduce memory limit below 120% of observed peak."},
    {"id": "INC-002", "service": "payment-service", "severity": "P1",
     "title": "Spring Boot 3 migration broke javax imports",
     "root_cause": "javax.persistence not migrated to jakarta.persistence. 100% of payment pods crashed.",
     "lesson": "Run javax->jakarta migration script before upgrading to Spring Boot 3."},
    {"id": "INC-003", "service": "order-service", "severity": "P2",
     "title": "NOT NULL constraint caused bulk insert failure",
     "root_cause": "Added NOT NULL constraint without backfilling existing NULL rows. Deployment blocked 4 hours.",
     "lesson": "Backfill NULLs before adding NOT NULL constraints."},
    {"id": "INC-004", "service": "user-service", "severity": "P2",
     "title": "API field rename broke checkout",
     "root_cause": "Renamed customer_id to customerId without versioning. Checkout returned 500s.",
     "lesson": "Never rename API fields without a version bump or backward-compatible alias."},
    {"id": "INC-005", "service": "legacy-auth-svc", "severity": "P1",
     "title": "legacy-auth-client 2.0 removed token refresh method",
     "root_cause": "Upgraded shared library without checking breaking changes. All services using old token refresh API broke.",
     "lesson": "Check breaking changes in shared library changelog before bulk upgrade."},
    {"id": "INC-006", "service": "notification-svc", "severity": "P2",
     "title": "Missing customerEmail field in Kafka event",
     "root_cause": "customerEmail removed from order-created event. Notification service could not send emails.",
     "lesson": "Never remove event fields consumed by downstream services without a migration period."},
]

memory_graph = [
    {"deployment": "DEP-101", "service": "payment-service",  "change": "Spring Boot 2.5 to 2.7",        "outcome": "success", "lessons": ["Ran full regression suite", "Deployed on low-traffic Sunday"]},
    {"deployment": "DEP-102", "service": "checkout-service", "change": "memory 2GB to 1.5GB",           "outcome": "failed",  "lessons": ["OOMKilled after 2 hours", "Rolled back immediately"]},
    {"deployment": "DEP-103", "service": "order-service",    "change": "ADD NOT NULL order.notes",      "outcome": "failed",  "lessons": ["Forgot to backfill NULLs", "4 hour P2 incident"]},
    {"deployment": "DEP-104", "service": "user-service",     "change": "API field rename user_name",    "outcome": "failed",  "lessons": ["Broke 2 downstream consumers", "Emergency rollback deployed"]},
    {"deployment": "DEP-105", "service": "legacy-auth-svc",  "change": "legacy-auth-client 1.3 to 1.4","outcome": "success", "lessons": ["Minor version â€” no breaking changes", "Tested in staging 1 week"]},
]

print(f"Data loaded: {len(services)} services | {len(libraries)} libs | {len(incident_docs)} incidents | {len(memory_graph)} past deployments")


# Cell 4 â€” Graph RAG: NetworkX dependency graph
import networkx as nx

G = nx.DiGraph()

for svc, info in services.items():
    G.add_node(svc, node_type="service", criticality=info["criticality"])

for db, info in database_users.items():
    G.add_node(db, node_type="database")
    for svc in info["shared_by"]:
        G.add_edge(svc, db, rel="USES_DB")

for api, info in api_consumers.items():
    G.add_node(api, node_type="api")
    G.add_edge(info["provider"], api, rel="PROVIDES_API")
    for consumer in info["consumers"]:
        G.add_edge(consumer, api, rel="CONSUMES_API")
        G.add_edge(consumer, info["provider"], rel="CALLS")

for event, info in event_consumers.items():
    G.add_node(event, node_type="kafka_event")
    G.add_edge(info["producer"], event, rel="PRODUCES_EVENT")
    for consumer in info["consumers"]:
        G.add_edge(consumer, event, rel="CONSUMES_EVENT")

for lib, info in libraries.items():
    G.add_node(lib, node_type="library")
    for svc in info["used_by"]:
        G.add_edge(svc, lib, rel="DEPENDS_ON")


def get_affected_services(service_name: str) -> list:
    if service_name not in G:
        return []
    affected = set()
    for node in nx.descendants(G, service_name):
        if G.nodes[node].get("node_type") == "service":
            affected.add(node)
    for node in nx.ancestors(G, service_name):
        if G.nodes[node].get("node_type") == "service":
            affected.add(node)
    affected.discard(service_name)
    return sorted(affected)


print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
print(f"payment-service affected: {get_affected_services('payment-service')}")


# Cell 5 â€” Vector RAG: FAISS + SentenceTransformers (runs on AMD CPU via all cores)
import numpy as np, faiss
from sentence_transformers import SentenceTransformer

print(f"Loading embedding model on {cpu_cores} CPU threads...")
# sentence-transformers automatically uses all available CPU cores (AMD benefit)
embedder = SentenceTransformer("all-MiniLM-L6-v2")

corpus = [
    f"{d['title']}. {d['root_cause']} Lesson: {d['lesson']}"
    for d in incident_docs
]

vecs = embedder.encode(corpus, convert_to_numpy=True, show_progress_bar=False).astype("float32")
faiss.normalize_L2(vecs)

faiss_index = faiss.IndexFlatIP(vecs.shape[1])
faiss_index.add(vecs)


def search_incidents(query: str, k: int = 3) -> list:
    qv = embedder.encode([query], convert_to_numpy=True).astype("float32")
    faiss.normalize_L2(qv)
    scores, indices = faiss_index.search(qv, min(k, len(incident_docs)))
    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx >= 0:
            doc = incident_docs[idx].copy()
            doc["sim"] = round(float(score), 3)
            results.append(doc)
    return results


print(f"FAISS index: {faiss_index.ntotal} vectors | dim={vecs.shape[1]}")
print(f"Test: {[r['id'] for r in search_incidents('Spring Boot upgrade Java')]}")


# Cell 6 â€” Vectorless RAG: Exact rule/constraint checker

def check_compatibility_rules(scenario: str, params: dict) -> list:
    violations = []
    svc      = params.get("service_name", "")
    svc_info = services.get(svc, {})

    if scenario == "framework_upgrade":
        new_ver  = params.get("new_value", "")
        cur_java = int(svc_info.get("java", "8"))
        if new_ver.startswith("3."):
            if cur_java < 17:
                violations.append(f"JAVA_MISMATCH: Spring Boot {new_ver} requires Java >=17, {svc} has Java {cur_java}")
            for b in compatibility_rules["spring_boot_breaking"]["2.7_to_3.x"]:
                violations.append(f"BREAKING_CHANGE: {b}")
        elif new_ver.startswith("2.7") and cur_java < 11:
            violations.append(f"JAVA_MISMATCH: Spring Boot 2.7 requires Java >=11, {svc} has Java {cur_java}")

    elif scenario == "resource_change":
        new_mem  = params.get("new_memory_gb", 0.0)
        peak     = svc_info.get("peak_memory_gb", 0.0)
        restarts = svc_info.get("restarts_30d", 0)
        min_safe = peak * (1 + compatibility_rules["memory_safety_buffer_pct"])
        if new_mem and new_mem < min_safe:
            violations.append(f"MEMORY_UNSAFE: {new_mem}GB < safe minimum {min_safe:.2f}GB (peak {peak}GB + 20% buffer)")
        if restarts >= compatibility_rules["high_restart_threshold"]:
            violations.append(f"HIGH_RESTART_RISK: {svc} had {restarts} restarts in 30d â€” OOMKill likely")

    elif scenario == "db_schema":
        db       = svc_info.get("db", "")
        db_info  = database_users.get(db, {})
        column   = params.get("column", "")
        if len(db_info.get("shared_by", [])) > 1:
            violations.append(f"SHARED_DB: {db} shared by {db_info['shared_by']} â€” all impacted")
        if "NOT NULL" in params.get("constraint", "").upper() and column in db_info.get("has_nullable_cols", []):
            violations.append(f"NULL_VIOLATION: '{column}' has existing NULLs â€” backfill required before constraint")

    elif scenario == "api_contract":
        old_fld  = params.get("old_value", "")
        new_fld  = params.get("new_value", "")
        for api, info in api_consumers.items():
            if info["provider"] == svc:
                if old_fld in info["fields"]:
                    violations.append(f"BREAKING_API: '{old_fld}' -> '{new_fld}' in {api} is not backward compatible")
                if len(info["consumers"]) > 2:
                    violations.append(f"WIDE_IMPACT: {len(info['consumers'])} consumers of {api} will break: {info['consumers']}")

    elif scenario == "shared_dependency":
        lib      = params.get("library_name", "")
        new_ver  = params.get("new_value", "")
        lib_info = libraries.get(lib, {})
        breaking = lib_info.get("breaking_version")
        users    = lib_info.get("used_by", [])
        if breaking and new_ver >= breaking:
            violations.append(f"BREAKING_LIB: {lib} {new_ver} >= breaking version {breaking}")
        if len(users) > 3:
            violations.append(f"BULK_RISK: {len(users)} services use {lib}: {users}")

    elif scenario == "event_schema":
        event      = params.get("event_name", "")
        removed_f  = params.get("removed_field", "")
        event_info = event_consumers.get(event, {})
        for consumer, fields in event_info.get("consumers", {}).items():
            if removed_f in fields:
                crit = services.get(consumer, {}).get("criticality", "unknown")
                violations.append(f"EVENT_FIELD_REMOVED: '{removed_f}' consumed by '{consumer}' ({crit}) â€” will break")

    return violations


print("Vectorless RAG ready")
print(check_compatibility_rules("framework_upgrade", {"service_name": "payment-service", "new_value": "3.2"}))


# Cell 7 â€” LangGraph State
from typing import TypedDict

class CGState(TypedDict, total=False):
    change_request:   str
    service_name:     str
    old_value:        str
    new_value:        str
    extra_params:     dict
    change_type:      str    # framework_upgrade|resource_change|db_schema|api_contract|shared_dependency|event_schema
    affected_services: list
    similar_incidents: list
    rule_violations:  list
    memory_lessons:   list
    risk_score:       int    # 0-100
    impact_level:     str    # low|medium|high|critical
    risk_reasons:     list
    rollout_plan:     str
    llm_explanation:  str    # plain-English explanation from local LLM
    llm_remediation:  list   # remediation steps from local LLM
    report:           dict

print("CGState defined")


# Cell 8 â€” Seven Agent Functions
import re

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# AGENT 1: Intake
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def intake_agent(state: dict) -> dict:
    req       = state["change_request"]
    req_lower = req.lower()
    extra     = {}

    # Identify service/library
    service_name = "unknown"
    for lib in sorted(libraries, key=len, reverse=True):
        if lib in req_lower:
            service_name = lib
            extra["library_name"] = lib
            break
    if service_name == "unknown":
        for svc in sorted(services, key=len, reverse=True):
            if svc in req_lower:
                service_name = svc
                break

    old_value, new_value = "", ""

    # Memory: "from 2GB to 1GB"
    m = re.search(r'from\s+(\d+(?:\.\d+)?)\s*[Gg][Bb]\s+to\s+(\d+(?:\.\d+)?)\s*[Gg][Bb]', req, re.I)
    if m:
        old_value, new_value = m.group(1), m.group(2)
        extra["new_memory_gb"] = float(new_value)
        extra["old_memory_gb"] = float(old_value)

    # API field: "field from X to Y"
    m = re.search(r'field\s+from\s+(\w+)\s+to\s+(\w+)', req, re.I)
    if m:
        old_value, new_value = m.group(1), m.group(2)

    # Generic version: "from X to Y"
    if not old_value:
        m = re.search(r'from\s+([\w\.]+)\s+to\s+([\w\.]+)', req, re.I)
        if m:
            old_value, new_value = m.group(1), m.group(2)

    # DB NOT NULL column
    m = re.search(r'NOT NULL constraint to\s+([\w\.]+)', req, re.I)
    if m:
        extra["column"] = m.group(1)
        extra["constraint"] = "NOT NULL"
    elif not extra.get("column"):
        m = re.search(r'constraint\s+to\s+([\w\.]+)', req, re.I)
        if m and m.group(1).lower() not in ("not", "null"):
            extra["column"] = m.group(1)
            extra["constraint"] = "NOT NULL"

    # Kafka remove field
    m = re.search(r'[Rr]emove\s+(\w+)\s+field\s+from\s+([a-z][\w-]+)', req)
    if m:
        extra["removed_field"] = m.group(1)
        extra["event_name"]    = m.group(2)

    return {**state, "service_name": service_name, "old_value": old_value,
            "new_value": new_value, "extra_params": extra}


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# AGENT 2: Scenario Router
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def scenario_router(state: dict) -> dict:
    req   = state["change_request"].lower()
    extra = state.get("extra_params", {})

    if any(k in req for k in ["spring boot", "spring", "framework"]):
        ct = "framework_upgrade"
    elif any(k in req for k in ["memory", "cpu", "limit", "ram", "gb"]):
        ct = "resource_change"
    elif any(k in req for k in ["not null", "schema", "constraint", "column", "migration"]):
        ct = "db_schema"
    elif any(k in req for k in ["kafka", "event", "topic", "stream"]):
        ct = "event_schema"
    elif "library_name" in extra or any(lib in req for lib in libraries):
        ct = "shared_dependency"
    elif any(k in req for k in ["api", "field", "endpoint", "response", "rename"]):
        ct = "api_contract"
    else:
        ct = "framework_upgrade"

    return {**state, "change_type": ct}


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# AGENT 3: Graph Impact
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def graph_impact_agent(state: dict) -> dict:
    svc   = state.get("service_name", "")
    ct    = state.get("change_type", "")
    extra = state.get("extra_params", {})
    aff   = set()

    if svc in G:
        aff.update(get_affected_services(svc))

    if ct == "shared_dependency":
        lib = extra.get("library_name", svc)
        aff.update(libraries.get(lib, {}).get("used_by", []))

    if ct == "event_schema":
        event = extra.get("event_name", "")
        aff.update(event_consumers.get(event, {}).get("consumers", {}).keys())

    if ct == "api_contract":
        for api, info in api_consumers.items():
            if info["provider"] == svc:
                aff.update(info["consumers"])

    if ct == "db_schema":
        db = services.get(svc, {}).get("db", "")
        aff.update(database_users.get(db, {}).get("shared_by", []))

    aff.discard(svc)
    aff = {s for s in aff if s in services}
    return {**state, "affected_services": sorted(aff)}


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# AGENT 4: Hybrid RAG
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def hybrid_rag_agent(state: dict) -> dict:
    params = {
        "service_name": state.get("service_name", ""),
        "old_value":    state.get("old_value", ""),
        "new_value":    state.get("new_value", ""),
        **state.get("extra_params", {}),
    }
    return {
        **state,
        "similar_incidents": search_incidents(state["change_request"], k=3),
        "rule_violations":   check_compatibility_rules(state.get("change_type", ""), params),
    }


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# AGENT 5: Memory Graph
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def memory_graph_agent(state: dict) -> dict:
    svc   = state.get("service_name", "")
    ct    = state.get("change_type", "")
    kws   = {
        "framework_upgrade": ["spring boot", "java", "upgrade", "migrate"],
        "resource_change":   ["memory", "gb", "oom", "resource"],
        "db_schema":         ["not null", "schema", "constraint", "null"],
        "api_contract":      ["api", "field", "rename", "endpoint"],
        "shared_dependency": ["library", "client", "dependency"],
        "event_schema":      ["kafka", "event", "field"],
    }.get(ct, [])
    lessons = [
        {"deployment": m["deployment"], "service": m["service"],
         "change": m["change"], "outcome": m["outcome"], "lessons": m["lessons"]}
        for m in memory_graph
        if m["service"] == svc or any(k in m["change"].lower() for k in kws)
    ]
    return {**state, "memory_lessons": lessons}


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# AGENT 6: Risk & Rollout (deterministic â€” no LLM, fully auditable)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def risk_rollout_agent(state: dict) -> dict:
    svc      = state.get("service_name", "")
    ct       = state.get("change_type", "")
    affected = state.get("affected_services", [])
    incs     = state.get("similar_incidents", [])
    viols    = state.get("rule_violations", [])
    mems     = state.get("memory_lessons", [])
    extra    = state.get("extra_params", {})
    svc_info = services.get(svc, {})

    score   = 10
    reasons = ["Base score (+10)"]

    # Criticality
    crit = svc_info.get("criticality", "medium")
    cb   = {"critical": 30, "high": 20, "medium": 10, "low": 5}.get(crit, 10)
    score += cb; reasons.append(f"Service criticality={crit} (+{cb})")

    # Affected services
    ab = min(len(affected) * 5, 25)
    if ab: score += ab; reasons.append(f"{len(affected)} affected service(s) (+{ab})")

    # Incident history
    p1 = [i for i in incs if i.get("severity") == "P1"]
    p2 = [i for i in incs if i.get("severity") == "P2"]
    if p1:   score += 20; reasons.append(f"Similar P1 incident: {p1[0]['id']} (+20)")
    elif p2: score += 10; reasons.append(f"Similar P2 incident: {p2[0]['id']} (+10)")

    # Rule violations
    vb = min(len(viols) * 15, 30)
    if vb: score += vb; reasons.append(f"{len(viols)} rule violation(s) (+{vb})")

    # Memory failures
    if any(m["outcome"] == "failed" for m in mems):
        score += 15; reasons.append("Prior failed deployment for similar change (+15)")

    # Scenario-specific bonuses
    if ct == "framework_upgrade":
        nv = state.get("new_value", "")
        jv = int(svc_info.get("java", "8"))
        if nv.startswith("3.") and jv < 17: score += 20; reasons.append(f"Java mismatch: needs 17, has {jv} (+20)")
        if nv.startswith("3."):             score += 15; reasons.append("Spring Boot 3.x breaking migration (+15)")

    elif ct == "resource_change":
        nm   = extra.get("new_memory_gb", 0.0)
        peak = svc_info.get("peak_memory_gb", 0.0)
        rsts = svc_info.get("restarts_30d", 0)
        if nm and nm < peak * 1.20: score += 25; reasons.append(f"New mem {nm}GB < safe floor {peak*1.2:.2f}GB (+25)")
        if rsts >= 5:                score += 10; reasons.append(f"High restarts: {rsts} in 30d (+10)")

    elif ct == "db_schema":
        db      = svc_info.get("db", "")
        db_info = database_users.get(db, {})
        col     = extra.get("column", "")
        if len(db_info.get("shared_by", [])) > 1: score += 15; reasons.append(f"Shared DB {db} (+15)")
        if col and col in db_info.get("has_nullable_cols", []): score += 20; reasons.append(f"Column '{col}' has NULLs â€” backfill required (+20)")

    elif ct == "api_contract":
        of = state.get("old_value", "")
        for api, info in api_consumers.items():
            if info["provider"] == svc:
                if of and of in info["fields"]: score += 20; reasons.append(f"Breaking field rename '{of}' in {api} (+20)")
                if len(info["consumers"]) > 2:  score += 10; reasons.append(f"{len(info['consumers'])} consumers at risk (+10)")

    elif ct == "shared_dependency":
        lib  = extra.get("library_name", svc)
        nv   = state.get("new_value", "")
        brk  = libraries.get(lib, {}).get("breaking_version")
        if brk and nv and nv >= brk: score += 25; reasons.append(f"Major version break: {lib} {nv} >= {brk} (+25)")

    elif ct == "event_schema":
        event = extra.get("event_name", "")
        rf    = extra.get("removed_field", "")
        for consumer, fields in event_consumers.get(event, {}).get("consumers", {}).items():
            if rf and rf in fields:
                c = services.get(consumer, {}).get("criticality", "")
                if c in ("critical", "high"): score += 20; reasons.append(f"Removed '{rf}' used by {consumer} ({c}) (+20)")

    score = min(score, 100)

    if   score <= 25: impact, rollout, plan = "low",      "direct",         "DIRECT ROLLOUT â€” Low risk. Deploy with standard monitoring."
    elif score <= 50: impact, rollout, plan = "medium",   "canary",         "CANARY ROLLOUT â€” 5% traffic first, monitor 30 min, then 25%->100%."
    elif score <= 75: impact, rollout, plan = "high",     "staged-rollout", "STAGED ROLLOUT â€” Deploy region-by-region with health checks. Rollback plan required."
    else:             impact, rollout, plan = "critical",  "block",          "DEPLOYMENT BLOCKED â€” Resolve all violations before proceeding."

    return {
        **state,
        "risk_score":   score,
        "impact_level": impact,
        "risk_reasons": reasons,
        "rollout_plan": plan,
    }


# AGENT 7: LLM Explanation (Local Qwen/Mistral via Ollama on AMD hardware)
_LLM_SYSTEM = """You are ChangeGuardian AI, a production deployment risk advisor.
You will receive a structured risk analysis. Your job is to:
1. Write a plain-English explanation (3 sentences) of WHY this change is risky.
2. List exactly 3 concrete remediation steps an engineer should take BEFORE deploying.

Respond in this exact JSON format (no markdown fences):
{"explanation": "<3 sentence explanation>", "remediation": ["step 1", "step 2", "step 3"]}"""

def _rule_based_explanation(state: dict) -> tuple:
    """Fallback when LLM is offline â€” generate explanation from rules."""
    ct      = state.get("change_type", "")
    svc     = state.get("service_name", "")
    score   = state.get("risk_score", 0)
    viols   = state.get("rule_violations", [])
    impact  = state.get("impact_level", "unknown")
    inc     = state.get("similar_incidents", [])

    exp = (f"This {ct.replace('_',' ')} change to {svc} carries {impact} risk (score {score}/100). "
           f"{len(viols)} rule violation(s) were detected that must be resolved before deployment. "
           + (f"A similar change previously caused: {inc[0]['title']}." if inc else "No identical past incident found but pattern matches are concerning."))

    remed_map = {
        "framework_upgrade":  ["Run javax->jakarta migration script on entire codebase", "Upgrade Java to 17+ on all pods before deploying", "Run full integration test suite against new Spring Boot version"],
        "resource_change":    ["Verify new memory limit is at least 20% above observed peak usage", "Set up OOMKill alerts before reducing limits", "Perform load test at peak traffic levels first"],
        "db_schema":          ["Backfill all NULL values in the target column before adding constraint", "Run migration in staging with production data copy first", "Coordinate deployment with all services sharing the database"],
        "api_contract":       ["Add backward-compatible alias alongside new field name", "Version the API endpoint (/v2/) before renaming fields", "Notify all consumer teams and agree migration timeline"],
        "shared_dependency":  ["Review CHANGELOG for all breaking changes between old and new version", "Test upgrade in isolation for each consuming service", "Coordinate a single release window across all affected teams"],
        "event_schema":       ["Add new field alongside old field (dual-write) during migration period", "Update all consumers to handle both old and new field names", "Remove old field only after all consumers confirm migration"],
    }
    remed = remed_map.get(ct, ["Review all rule violations", "Test in staging first", "Have rollback plan ready"])
    return exp, remed


def llm_explanation_agent(state: dict) -> dict:
    """
    Calls local Ollama LLM (Qwen2.5/Mistral) running on AMD hardware.
    The LLM receives the full deterministic risk analysis and generates:
      - Plain-English explanation (3 sentences)
      - 3 concrete remediation steps
    Falls back to rule-based text if Ollama is not running.
    """
    if not OLLAMA_READY:
        explanation, remediation = _rule_based_explanation(state)
    else:
        prompt = json.dumps({
            "change_request":   state.get("change_request"),
            "service":          state.get("service_name"),
            "scenario":         state.get("change_type"),
            "risk_score":       state.get("risk_score"),
            "impact_level":     state.get("impact_level"),
            "affected_services":state.get("affected_services", []),
            "rule_violations":  state.get("rule_violations", []),
            "similar_incidents":[{"id":i["id"],"title":i["title"],"severity":i["severity"]} for i in state.get("similar_incidents",[])],
            "risk_reasons":     state.get("risk_reasons", []),
            "rollout_plan":     state.get("rollout_plan", ""),
        }, indent=2)
        raw = call_llm(prompt, system=_LLM_SYSTEM)
        try:
            parsed      = json.loads(raw)
            explanation = parsed.get("explanation", raw)
            remediation = parsed.get("remediation", [])
        except Exception:
            explanation, remediation = _rule_based_explanation(state)

    report = {
        "change_request":   state.get("change_request"),
        "service":          state.get("service_name"),
        "scenario":         state.get("change_type"),
        "affected_services":state.get("affected_services", []),
        "similar_incidents":[{"id":i["id"],"title":i["title"],"severity":i["severity"]} for i in state.get("similar_incidents",[])],
        "rule_violations":  state.get("rule_violations", []),
        "memory_lessons":   [{"deployment":m["deployment"],"outcome":m["outcome"],"lessons":m["lessons"]} for m in state.get("memory_lessons",[])],
        "risk_score":       state.get("risk_score"),
        "impact_level":     state.get("impact_level"),
        "risk_reasons":     state.get("risk_reasons", []),
        "rollout_plan":     state.get("rollout_plan"),
        "llm_explanation":  explanation,
        "llm_remediation":  remediation,
    }

    return {
        **state,
        "llm_explanation": explanation,
        "llm_remediation": remediation,
        "report":          report,
    }


print("All 7 agent functions defined")


# Cell 9 â€” Build LangGraph Workflow (7 nodes)
from langgraph.graph import StateGraph, END

def build_workflow():
    builder = StateGraph(dict)

    builder.add_node("intake",       intake_agent)
    builder.add_node("router",       scenario_router)
    builder.add_node("graph_impact", graph_impact_agent)
    builder.add_node("hybrid_rag",   hybrid_rag_agent)
    builder.add_node("memory_graph", memory_graph_agent)
    builder.add_node("risk_rollout", risk_rollout_agent)
    builder.add_node("llm_explain",  llm_explanation_agent)  

    builder.set_entry_point("intake")
    builder.add_edge("intake",       "router")
    builder.add_edge("router",       "graph_impact")
    builder.add_edge("graph_impact", "hybrid_rag")
    builder.add_edge("hybrid_rag",   "memory_graph")
    builder.add_edge("memory_graph", "risk_rollout")
    builder.add_edge("risk_rollout", "llm_explain")
    builder.add_edge("llm_explain",  END)

    return builder.compile()


workflow = build_workflow()
print("LangGraph workflow compiled")
print("intake -> router -> graph_impact -> hybrid_rag -> memory_graph -> risk_rollout -> llm_explain -> END")


# Cell 10 â€” Run 6 Demo Scenarios

ICONS = {"low": "", "medium": "", "high": " ", "critical": ""}

def print_report(result: dict):
    r      = result.get("report", {})
    impact = r.get("impact_level", "unknown")
    score  = r.get("risk_score", 0)
    icon   = ICONS.get(impact, "âšª")

    print("=" * 72)
    print(f"  CHANGE   : {r.get('change_request')}")
    print(f"  SCENARIO : {r.get('scenario','').replace('_',' ').upper()}")
    print(f"  SERVICE  : {r.get('service')}")
    print("-" * 72)
    aff = r.get("affected_services", [])
    print(f"  AFFECTED ({len(aff)}): {', '.join(aff) or 'None'}")

    print("\n  SIMILAR INCIDENTS (Vector RAG):")
    for i in r.get("similar_incidents", []):
        print(f"    [{i['severity']}] {i['id']}: {i['title']}")

    print("\n  RULE VIOLATIONS (Vectorless RAG):")
    for v in r.get("rule_violations", []) or ["  None"]:
        print(f"    ! {v}")

    print("\n  MEMORY GRAPH:")
    for m in r.get("memory_lessons", []) or [{"outcome":"none","deployment":"-","lessons":["No prior data"]}]:
        tag = "FAILED" if m["outcome"] == "failed" else "SUCCESS" if m["outcome"] == "success" else "-"
        print(f"    [{m['deployment']}][{tag}] {' | '.join(m['lessons'])}")

    print("\n  RISK BREAKDOWN:")
    for rr in r.get("risk_reasons", []):
        print(f"    + {rr}")

    print(f"\n  {icon} RISK SCORE: {score}/100  |  IMPACT: {impact.upper()}")
    print(f"  ROLLOUT: {r.get('rollout_plan')}")

    print("\n  LLM EXPLANATION (AMD Local LLM):")
    print(f"    {r.get('llm_explanation','')}")

    print("\n  LLM REMEDIATION STEPS:")
    for j, step in enumerate(r.get("llm_remediation", []), 1):
        print(f"    {j}. {step}")

    print("=" * 72)
    print()


scenarios = [
    "Upgrade payment-service from Spring Boot 2.7 to 3.2",
    "Reduce checkout-service memory limit from 2GB to 1GB",
    "Add NOT NULL constraint to transaction.amount in payment-db",
    "Change payment API response field from customer_id to customerId",
    "Upgrade legacy-auth-client from 1.4.0 to 2.0.0 across all services",
    "Remove customerEmail field from order-created Kafka event",
]

ram_before = psutil.virtual_memory().used / (1024 ** 3)
print(f"RAM before run: {ram_before:.1f} GB used / {ram_gb:.1f} GB total\n")

all_results = []
for i, sc in enumerate(scenarios, 1):
    print(f"[{i}/6] Running: {sc}")
    t0 = time.time()
    result = workflow.invoke({"change_request": sc})
    elapsed = time.time() - t0
    all_results.append(result)
    print_report(result)
    print(f"  (pipeline took {elapsed:.1f}s | RAM: {psutil.virtual_memory().used/(1024**3):.1f} GB)\n")

print("\n" + "=" * 72)
print("  SUMMARY TABLE")
print("=" * 72)
print(f"{'#':<3} {'Score':>5} {'Impact':<10} {'Scenario':<30} {'Rollout'}")
print("-" * 72)
for i, r in enumerate(all_results, 1):
    rpt = r.get("report", {})
    icon = ICONS.get(rpt.get("impact_level",""),"")
    print(f"{i:<3} {rpt.get('risk_score',0):>5}  {icon}{rpt.get('impact_level',''):<9} {rpt.get('scenario',''):<30} {rpt.get('rollout_plan','')[:35]}")
print("=" * 72)


import gradio as gr

def analyze_change(change_request: str) -> str:
    if not change_request.strip():
        return "Please enter a change request."

    t0     = time.time()
    result = workflow.invoke({"change_request": change_request.strip()})
    elapsed = time.time() - t0
    ram_now = psutil.virtual_memory().used / (1024**3)
    r      = result.get("report", {})

    impact = r.get("impact_level", "unknown")
    score  = r.get("risk_score", 0)
    icon   = ICONS.get(impact)

    aff_md   = ", ".join(f"`{s}`" for s in r.get("affected_services",[])) or "_None_"
    viols_md = "\n".join(f"- `{v}`" for v in r.get("rule_violations",[])) or "_No violations_"
    incs_md  = "\n".join(f"- **[{i['severity']}]** `{i['id']}`: {i['title']}" for i in r.get("similar_incidents",[])) or "_None_"
    mems_md  = "\n".join(
        f"- {'**FAILED**' if m['outcome']=='failed' else '**SUCCESS**'} `{m['deployment']}`: {' | '.join(m['lessons'])}"
        for m in r.get("memory_lessons",[])
    ) or "_No prior deployments_"
    reasons_md = "\n".join(f"- {rr}" for rr in r.get("risk_reasons",[])) or "_None_"
    remed_md   = "\n".join(f"{j}. {s}" for j,s in enumerate(r.get("llm_remediation",[]),1)) or "_None_"

    return f"""## {icon} ChangeGuardian AI  Risk Report

| | |
|---|---|
| **Change** | {r.get('change_request')} |
| **Scenario** | `{r.get('scenario','').replace('_',' ').upper()}` |
| **Service** | `{r.get('service')}` |
| **Risk Score** | **{score} / 100** |
| **Impact** | {icon} **{impact.upper()}** |
| **Rollout** | {r.get('rollout_plan')} |
| **Pipeline time** | {elapsed:.1f}s \| AMD RAM in use: {ram_now:.1f}/{ram_gb:.1f} GB |

---

###  Affected Services
{aff_md}

###  Rule Violations (Vectorless RAG)
{viols_md}

###  Similar Past Incidents (Vector RAG  FAISS)
{incs_md}

###  Memory Graph
{mems_md}

###  Risk Score Breakdown
{reasons_md}

---

###  LLM Explanation  *(Local {OLLAMA_MODEL} ” {'AMD GPU/ROCm' if OLLAMA_READY else 'rule-based fallback'})*
{r.get('llm_explanation','')}

###  Remediation Steps
{remed_md}
"""


demo = gr.Interface(
    fn=analyze_change,
    inputs=gr.Textbox(
        label="Describe your production change",
        placeholder="e.g. Upgrade payment-service from Spring Boot 2.7 to 3.2",
        lines=3,
    ),
    outputs=gr.Markdown(label="Risk Analysis Report"),
    title="ChangeGuardian AI",
    description=(
        f"Pre-deployment production risk analysis \n"
        f"Running on AMD hardware . RAM: {ram_gb:.0f} GB · CPU: {cpu_cores} threads · "
        f"LLM: {OLLAMA_MODEL} ({'LIVE' if OLLAMA_READY else 'offline-fallback'})"
    ),
    examples=[
        ["Upgrade payment-service from Spring Boot 2.7 to 3.2"],
        ["Reduce checkout-service memory limit from 2GB to 1GB"],
        ["Add NOT NULL constraint to transaction.amount in payment-db"],
        ["Change payment API response field from customer_id to customerId"],
        ["Upgrade legacy-auth-client from 1.4.0 to 2.0.0 across all services"],
        ["Remove customerEmail field from order-created Kafka event"],
    ],
    theme=gr.themes.Soft(),
)

demo.launch(share=False)

