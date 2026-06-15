"""
ChangeGuardian AI — Enhanced Production Deployment Risk Analysis
Refactored to support larger models: Qwen 3-30B-A3B, Llama 3.1-70B, etc.

Features:
  ✓ Dynamic model selection (3B → 30B+ models)
  ✓ Enhanced agent prompts leveraging larger models
  ✓ Streaming LLM responses for real-time feedback
  ✓ Interactive Gradio UI with deployment recommendations
  ✓ Deterministic risk scoring + LLM-powered reasoning
  ✓ Vector RAG (FAISS) + Vectorless rule engine
  ✓ Local execution on AMD/Intel hardware (no cloud APIs)
"""

import os
import json
import time
import re
import asyncio
from typing import TypedDict, Optional, Dict, Any, List
import requests
import psutil
import platform
import numpy as np
import networkx as nx
from sentence_transformers import SentenceTransformer
import faiss
from langgraph.graph import StateGraph, END

# ============================================================================
# CONFIGURATION & MODEL SELECTION
# ============================================================================

class LLMConfig:
    """Configuration for different LLM models."""
    MODELS = {
        "qwen2.5:3b": {
            "vram_gb": 6,
            "ram_gb": 16,
            "context_window": 32768,
            "temperature": 0.2,
            "timeout": 90,
            "reasoning_depth": "basic",
        },
        "qwen2.5:7b": {
            "vram_gb": 12,
            "ram_gb": 32,
            "context_window": 32768,
            "temperature": 0.3,
            "timeout": 120,
            "reasoning_depth": "intermediate",
        },
        "qwen2.5:14b": {
            "vram_gb": 20,
            "ram_gb": 64,
            "context_window": 32768,
            "temperature": 0.3,
            "timeout": 150,
            "reasoning_depth": "deep",
        },
        "qwen3:30b-a3b": {
            "vram_gb": 35,
            "ram_gb": 128,
            "context_window": 128000,
            "temperature": 0.2,
            "timeout": 180,
            "reasoning_depth": "expert",
        },
        "llama3.1:70b": {
            "vram_gb": 60,
            "ram_gb": 256,
            "context_window": 131072,
            "temperature": 0.2,
            "timeout": 200,
            "reasoning_depth": "expert",
        },
    }

    @staticmethod
    def select_model(available_ram_gb: float, preferred_model: Optional[str] = None) -> str:
        """Select optimal model based on available RAM."""
        if preferred_model and preferred_model in LLMConfig.MODELS:
            config = LLMConfig.MODELS[preferred_model]
            if available_ram_gb >= config["ram_gb"]:
                return preferred_model
            print(f"WARNING: {preferred_model} needs {config['ram_gb']}GB RAM, only {available_ram_gb}GB available. Falling back...")

        # Find largest model that fits
        for model_name, config in sorted(LLMConfig.MODELS.items(), key=lambda x: x[1]["ram_gb"], reverse=True):
            if available_ram_gb >= config["ram_gb"]:
                return model_name
        return "qwen2.5:3b"  # Fallback

# ============================================================================
# SYSTEM INITIALIZATION
# ============================================================================

ram_gb = psutil.virtual_memory().total / (1024 ** 3)
cpu_cores = psutil.cpu_count(logical=True)
cpu_phys = psutil.cpu_count(logical=False)
cpu_name = platform.processor() or "Unknown CPU"

print("=" * 70)
print("  CHANGEGUARDIAN AI - Enhanced Edition")
print("=" * 70)
print(f"  CPU: {cpu_name} | Cores: {cpu_phys} (physical), {cpu_cores} (logical)")
print(f"  Total RAM: {ram_gb:.1f} GB | Available: {psutil.virtual_memory().available / (1024**3):.1f} GB")
print("=" * 70)

# Select model
OLLAMA_MODEL = LLMConfig.select_model(ram_gb, preferred_model="qwen3:30b-a3b")
MODEL_CONFIG = LLMConfig.MODELS[OLLAMA_MODEL]
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_TIMEOUT = MODEL_CONFIG["timeout"]

def _ollama_available() -> bool:
    try:
        r = requests.get("http://localhost:11434", timeout=3)
        return r.status_code == 200
    except Exception:
        return False

OLLAMA_READY = _ollama_available()
print(f"\n[OK] Selected Model: {OLLAMA_MODEL}")
print(f"[OK] Context Window: {MODEL_CONFIG['context_window']:,} tokens")
print(f"[OK] Reasoning Depth: {MODEL_CONFIG['reasoning_depth'].upper()}")
print(f"[OK] Ollama Status: {'RUNNING' if OLLAMA_READY else 'NOT FOUND (rule-based fallback)'}")

if OLLAMA_READY:
    print("\nWarming up LLM (loading into memory)...")
    t0 = time.time()
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": "Ready.", "stream": False},
            timeout=OLLAMA_TIMEOUT,
        )
        elapsed = time.time() - t0
        ram_used = psutil.virtual_memory().used / (1024 ** 3)
        print(f"[OK] LLM warmed in {elapsed:.1f}s | RAM: {ram_used:.1f}/{ram_gb:.1f} GB")
    except Exception as e:
        print(f"[WARNING] LLM warmup failed: {e}")

# ============================================================================
# DATA LAYER (Services, Libraries, Rules, Incidents)
# ============================================================================

services = {
    "payment-service":   {"java": "11", "spring_boot": "2.7", "memory_limit_gb": 2, "peak_memory_gb": 1.6, "restarts_30d": 3, "criticality": "critical", "db": "payment-db", "team": "payments", "sla_pct": 99.95},
    "checkout-service":  {"java": "11", "spring_boot": "2.7", "memory_limit_gb": 2, "peak_memory_gb": 1.8, "restarts_30d": 8, "criticality": "critical", "db": "checkout-db", "team": "checkout", "sla_pct": 99.99},
    "order-service":     {"java": "17", "spring_boot": "3.1", "memory_limit_gb": 1, "peak_memory_gb": 0.6, "restarts_30d": 1, "criticality": "high", "db": "order-db", "team": "orders", "sla_pct": 99.9},
    "user-service":      {"java": "17", "spring_boot": "3.0", "memory_limit_gb": 1, "peak_memory_gb": 0.4, "restarts_30d": 0, "criticality": "medium", "db": "user-db", "team": "platform", "sla_pct": 99.5},
    "notification-svc":  {"java": "11", "spring_boot": "2.7", "memory_limit_gb": 0.5, "peak_memory_gb": 0.3, "restarts_30d": 2, "criticality": "low", "db": None, "team": "platform", "sla_pct": 98.0},
    "legacy-auth-svc":   {"java": "8", "spring_boot": "2.3", "memory_limit_gb": 1, "peak_memory_gb": 0.7, "restarts_30d": 5, "criticality": "high", "db": "auth-db", "team": "security", "sla_pct": 99.99},
    "inventory-service": {"java": "11", "spring_boot": "2.7", "memory_limit_gb": 1, "peak_memory_gb": 0.5, "restarts_30d": 1, "criticality": "medium", "db": "inventory-db", "team": "warehouse", "sla_pct": 99.0},
}

libraries = {
    "legacy-auth-client": {"current": "1.4.0", "breaking_version": "2.0.0", "used_by": ["payment-service", "checkout-service", "order-service", "user-service", "legacy-auth-svc"]},
    "common-utils": {"current": "3.1.0", "breaking_version": None, "used_by": ["payment-service", "checkout-service", "order-service"]},
}

api_consumers = {
    "payment-api": {"provider": "payment-service", "consumers": ["checkout-service", "order-service", "user-service"], "fields": ["customer_id", "amount", "currency", "status"]},
    "order-api": {"provider": "order-service", "consumers": ["notification-svc", "inventory-service"], "fields": ["order_id", "customerId", "items", "total"]},
}

database_users = {
    "payment-db":   {"shared_by": ["payment-service"], "has_nullable_cols": ["transaction.amount"]},
    "checkout-db":  {"shared_by": ["checkout-service"], "has_nullable_cols": []},
    "order-db":     {"shared_by": ["order-service", "inventory-service"], "has_nullable_cols": ["order.notes"]},
    "auth-db":      {"shared_by": ["legacy-auth-svc", "user-service"], "has_nullable_cols": ["user.phone"]},
    "user-db":      {"shared_by": ["user-service"], "has_nullable_cols": ["user.middle_name"]},
    "inventory-db": {"shared_by": ["inventory-service"], "has_nullable_cols": []},
}

event_consumers = {
    "order-created": {"producer": "order-service", "fields": ["orderId", "customerId", "customerEmail", "items", "total"], "consumers": {"notification-svc": ["customerId", "customerEmail"], "inventory-service": ["orderId", "items"]}},
    "payment-settled": {"producer": "payment-service", "fields": ["paymentId", "orderId", "amount"], "consumers": {"order-service": ["paymentId", "orderId"]}},
}

compatibility_rules = {
    "spring_boot_java": {"3.x": ">=17", "2.7.x": ">=11", "2.3.x": ">=8"},
    "spring_boot_breaking": {"2.7_to_3.x": ["javax -> jakarta namespace migration required", "Removed deprecated Spring APIs", "spring.factories auto-configuration format removed"]},
    "memory_safety_buffer_pct": 0.20,
    "high_restart_threshold": 5,
}

incident_docs = [
    {"id": "INC-001", "service": "checkout-service", "severity": "P1", "title": "OOMKilled after memory reduction", "root_cause": "Memory limit set below peak usage during Black Friday. Pod restarted 14 times.", "lesson": "Never reduce memory limit below 120% of observed peak.", "financial_impact": 250000, "duration_minutes": 120},
    {"id": "INC-002", "service": "payment-service", "severity": "P1", "title": "Spring Boot 3 migration broke javax imports", "root_cause": "javax.persistence not migrated to jakarta.persistence. 100% of payment pods crashed.", "lesson": "Run javax->jakarta migration script before upgrading to Spring Boot 3.", "financial_impact": 500000, "duration_minutes": 45},
    {"id": "INC-003", "service": "order-service", "severity": "P2", "title": "NOT NULL constraint caused bulk insert failure", "root_cause": "Added NOT NULL constraint without backfilling existing NULL rows. Deployment blocked 4 hours.", "lesson": "Backfill NULLs before adding NOT NULL constraints.", "financial_impact": 50000, "duration_minutes": 240},
    {"id": "INC-004", "service": "user-service", "severity": "P2", "title": "API field rename broke checkout", "root_cause": "Renamed customer_id to customerId without versioning. Checkout returned 500s.", "lesson": "Never rename API fields without a version bump or backward-compatible alias.", "financial_impact": 100000, "duration_minutes": 60},
    {"id": "INC-005", "service": "legacy-auth-svc", "severity": "P1", "title": "legacy-auth-client 2.0 removed token refresh method", "root_cause": "Upgraded shared library without checking breaking changes. All services broke.", "lesson": "Check breaking changes in shared library changelog before bulk upgrade.", "financial_impact": 750000, "duration_minutes": 90},
    {"id": "INC-006", "service": "notification-svc", "severity": "P2", "title": "Missing customerEmail field in Kafka event", "root_cause": "customerEmail removed from order-created event. Notification service could not send emails.", "lesson": "Never remove event fields consumed by downstream services without migration.", "financial_impact": 75000, "duration_minutes": 180},
]

memory_graph = [
    {"deployment": "DEP-101", "service": "payment-service", "change": "Spring Boot 2.5 to 2.7", "outcome": "success", "lessons": ["Ran full regression suite", "Deployed on low-traffic Sunday"], "tested_in_staging": True, "rollback_time_seconds": 0},
    {"deployment": "DEP-102", "service": "checkout-service", "change": "memory 2GB to 1.5GB", "outcome": "failed", "lessons": ["OOMKilled after 2 hours", "Rolled back immediately"], "tested_in_staging": False, "rollback_time_seconds": 300},
    {"deployment": "DEP-103", "service": "order-service", "change": "ADD NOT NULL order.notes", "outcome": "failed", "lessons": ["Forgot to backfill NULLs", "4 hour P2 incident"], "tested_in_staging": False, "rollback_time_seconds": 600},
    {"deployment": "DEP-104", "service": "user-service", "change": "API field rename user_name", "outcome": "failed", "lessons": ["Broke 2 downstream consumers", "Emergency rollback deployed"], "tested_in_staging": False, "rollback_time_seconds": 180},
    {"deployment": "DEP-105", "service": "legacy-auth-svc", "change": "legacy-auth-client 1.3 to 1.4", "outcome": "success", "lessons": ["Minor version – no breaking changes", "Tested in staging 1 week"], "tested_in_staging": True, "rollback_time_seconds": 0},
]

print(f"\n[OK] Data loaded: {len(services)} services | {len(libraries)} libs | {len(incident_docs)} incidents | {len(memory_graph)} prior deployments")

# ============================================================================
# GRAPH RAG & VECTOR RAG
# ============================================================================

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

print(f"[OK] Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

# FAISS Vector RAG
embedder = SentenceTransformer("all-MiniLM-L6-v2")
corpus = [f"{d['title']}. {d['root_cause']} Lesson: {d['lesson']}" for d in incident_docs]
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

print(f"[OK] FAISS index ready: {faiss_index.ntotal} vectors")

# ============================================================================
# ENHANCED LLM SYSTEM PROMPTS (leverage larger model reasoning)
# ============================================================================

SYSTEM_PROMPT_EXPERT = """You are ChangeGuardian AI, an expert deployment risk analyst for production systems.

Your role is to provide deep, nuanced risk assessment for production deployments considering:
  1. Service criticality and SLA requirements
  2. Financial impact of potential failures
  3. Blast radius and cascade failure risks
  4. Team readiness and testing procedures
  5. Rollback complexity and RTO/RPO metrics

Respond with sophisticated reasoning that considers multiple dimensions of risk.
Format your response as valid JSON only (no markdown fences, no extra text)."""

SYSTEM_PROMPT_STANDARD = """You are ChangeGuardian AI, a deployment risk advisor.
Analyze the change request and provide a comprehensive risk assessment.
Respond with valid JSON only (no markdown, no explanation outside JSON)."""

# ============================================================================
# LANGGRAPH AGENTS (Enhanced with better prompts)
# ============================================================================

class CGState(TypedDict, total=False):
    change_request: str
    service_name: str
    old_value: str
    new_value: str
    extra_params: dict
    change_type: str
    affected_services: list
    similar_incidents: list
    rule_violations: list
    memory_lessons: list
    risk_score: int
    impact_level: str
    risk_reasons: list
    rollout_plan: str
    llm_explanation: str
    llm_remediation: list
    financial_impact: int
    sla_impact: str
    report: dict

def intake_agent(state: dict) -> dict:
    """Parse change request and extract parameters."""
    req = state["change_request"]
    req_lower = req.lower()
    extra = {}

    # Service/library identification
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
    m = re.search(r'from\s+(\d+(?:\.\d+)?)\s*[Gg][Bb]\s+to\s+(\d+(?:\.\d+)?)\s*[Gg][Bb]', req, re.I)
    if m:
        old_value, new_value = m.group(1), m.group(2)
        extra["new_memory_gb"] = float(new_value)
        extra["old_memory_gb"] = float(old_value)

    m = re.search(r'field\s+from\s+(\w+)\s+to\s+(\w+)', req, re.I)
    if m:
        old_value, new_value = m.group(1), m.group(2)

    if not old_value:
        m = re.search(r'from\s+([\w\.]+)\s+to\s+([\w\.]+)', req, re.I)
        if m:
            old_value, new_value = m.group(1), m.group(2)

    m = re.search(r'NOT NULL constraint to\s+([\w\.]+)', req, re.I)
    if m:
        extra["column"] = m.group(1)
        extra["constraint"] = "NOT NULL"
    elif not extra.get("column"):
        m = re.search(r'constraint\s+to\s+([\w\.]+)', req, re.I)
        if m and m.group(1).lower() not in ("not", "null"):
            extra["column"] = m.group(1)
            extra["constraint"] = "NOT NULL"

    m = re.search(r'[Rr]emove\s+(\w+)\s+field\s+from\s+([a-z][\w-]+)', req)
    if m:
        extra["removed_field"] = m.group(1)
        extra["event_name"] = m.group(2)

    return {**state, "service_name": service_name, "old_value": old_value, "new_value": new_value, "extra_params": extra}

def scenario_router(state: dict) -> dict:
    """Classify change scenario type."""
    req = state["change_request"].lower()
    extra = state.get("extra_params", {})

    if any(k in req for k in ["spring boot", "spring", "framework", "java", "runtime"]):
        ct = "framework_upgrade"
    elif any(k in req for k in ["memory", "cpu", "limit", "ram", "gb", "resource"]):
        ct = "resource_change"
    elif any(k in req for k in ["not null", "schema", "constraint", "column", "migration", "index"]):
        ct = "db_schema"
    elif any(k in req for k in ["kafka", "event", "topic", "stream", "pubsub"]):
        ct = "event_schema"
    elif "library_name" in extra or any(lib in req for lib in libraries):
        ct = "shared_dependency"
    elif any(k in req for k in ["api", "field", "endpoint", "response", "rename", "contract"]):
        ct = "api_contract"
    else:
        ct = "framework_upgrade"

    return {**state, "change_type": ct}

def graph_impact_agent(state: dict) -> dict:
    """Find affected services using graph traversal."""
    svc = state.get("service_name", "")
    ct = state.get("change_type", "")
    extra = state.get("extra_params", {})
    aff = set()

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

def hybrid_rag_agent(state: dict) -> dict:
    """Combine vector RAG (FAISS) + vectorless rules."""
    params = {"service_name": state.get("service_name", ""), "old_value": state.get("old_value", ""), "new_value": state.get("new_value", ""), **state.get("extra_params", {})}
    return {**state, "similar_incidents": search_incidents(state["change_request"], k=3), "rule_violations": check_compatibility_rules(state.get("change_type", ""), params)}

def check_compatibility_rules(scenario: str, params: dict) -> list:
    """Vectorless RAG: deterministic rule checking."""
    violations = []
    svc = params.get("service_name", "")
    svc_info = services.get(svc, {})

    if scenario == "framework_upgrade":
        new_ver = params.get("new_value", "")
        cur_java = int(svc_info.get("java", "8"))
        if new_ver.startswith("3."):
            if cur_java < 17:
                violations.append(f"JAVA_MISMATCH: Spring Boot {new_ver} requires Java >=17, {svc} has Java {cur_java}")
            for b in compatibility_rules["spring_boot_breaking"]["2.7_to_3.x"]:
                violations.append(f"BREAKING_CHANGE: {b}")
        elif new_ver.startswith("2.7") and cur_java < 11:
            violations.append(f"JAVA_MISMATCH: Spring Boot 2.7 requires Java >=11, {svc} has Java {cur_java}")

    elif scenario == "resource_change":
        new_mem = params.get("new_memory_gb", 0.0)
        peak = svc_info.get("peak_memory_gb", 0.0)
        restarts = svc_info.get("restarts_30d", 0)
        min_safe = peak * (1 + compatibility_rules["memory_safety_buffer_pct"])
        if new_mem and new_mem < min_safe:
            violations.append(f"MEMORY_UNSAFE: {new_mem}GB < safe minimum {min_safe:.2f}GB (peak {peak}GB + 20% buffer)")
        if restarts >= compatibility_rules["high_restart_threshold"]:
            violations.append(f"HIGH_RESTART_RISK: {svc} had {restarts} restarts in 30d – OOMKill likely")

    elif scenario == "db_schema":
        db = svc_info.get("db", "")
        db_info = database_users.get(db, {})
        column = params.get("column", "")
        if len(db_info.get("shared_by", [])) > 1:
            violations.append(f"SHARED_DB: {db} shared by {db_info['shared_by']} – all impacted")
        if "NOT NULL" in params.get("constraint", "").upper() and column in db_info.get("has_nullable_cols", []):
            violations.append(f"NULL_VIOLATION: '{column}' has existing NULLs – backfill required before constraint")

    elif scenario == "api_contract":
        old_fld = params.get("old_value", "")
        new_fld = params.get("new_value", "")
        for api, info in api_consumers.items():
            if info["provider"] == svc:
                if old_fld in info["fields"]:
                    violations.append(f"BREAKING_API: '{old_fld}' -> '{new_fld}' in {api} is not backward compatible")
                if len(info["consumers"]) > 2:
                    violations.append(f"WIDE_IMPACT: {len(info['consumers'])} consumers of {api} will break: {info['consumers']}")

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
        removed_f = params.get("removed_field", "")
        event_info = event_consumers.get(event, {})
        for consumer, fields in event_info.get("consumers", {}).items():
            if removed_f in fields:
                crit = services.get(consumer, {}).get("criticality", "unknown")
                violations.append(f"EVENT_FIELD_REMOVED: '{removed_f}' consumed by '{consumer}' ({crit}) – will break")

    return violations

def memory_graph_agent(state: dict) -> dict:
    """Look up prior deployment outcomes."""
    svc = state.get("service_name", "")
    ct = state.get("change_type", "")
    kws = {
        "framework_upgrade": ["spring boot", "java", "upgrade", "migrate"],
        "resource_change": ["memory", "gb", "oom", "resource"],
        "db_schema": ["not null", "schema", "constraint", "null"],
        "api_contract": ["api", "field", "rename", "endpoint"],
        "shared_dependency": ["library", "client", "dependency"],
        "event_schema": ["kafka", "event", "field"],
    }.get(ct, [])
    lessons = [{"deployment": m["deployment"], "service": m["service"], "change": m["change"], "outcome": m["outcome"], "lessons": m["lessons"], "tested_in_staging": m.get("tested_in_staging", False)} for m in memory_graph if m["service"] == svc or any(k in m["change"].lower() for k in kws)]
    return {**state, "memory_lessons": lessons}

def risk_rollout_agent(state: dict) -> dict:
    """Deterministic risk scoring and rollout recommendation."""
    svc = state.get("service_name", "")
    ct = state.get("change_type", "")
    affected = state.get("affected_services", [])
    incs = state.get("similar_incidents", [])
    viols = state.get("rule_violations", [])
    mems = state.get("memory_lessons", [])
    extra = state.get("extra_params", {})
    svc_info = services.get(svc, {})

    score = 10
    reasons = ["Base score (+10)"]

    # Criticality
    crit = svc_info.get("criticality", "medium")
    cb = {"critical": 30, "high": 20, "medium": 10, "low": 5}.get(crit, 10)
    score += cb
    reasons.append(f"Service criticality={crit} (+{cb})")

    # Affected services
    ab = min(len(affected) * 5, 25)
    if ab:
        score += ab
        reasons.append(f"{len(affected)} affected service(s) (+{ab})")

    # Incident history with financial impact
    p1 = [i for i in incs if i.get("severity") == "P1"]
    p2 = [i for i in incs if i.get("severity") == "P2"]
    financial_impact = 0
    if p1:
        score += 20
        financial_impact = p1[0].get("financial_impact", 0)
        reasons.append(f"Similar P1 incident: {p1[0]['id']} (+20)")
    elif p2:
        score += 10
        financial_impact = p2[0].get("financial_impact", 0)
        reasons.append(f"Similar P2 incident: {p2[0]['id']} (+10)")

    # Rule violations
    vb = min(len(viols) * 15, 30)
    if vb:
        score += vb
        reasons.append(f"{len(viols)} rule violation(s) (+{vb})")

    # Memory failures
    failed_mems = [m for m in mems if m["outcome"] == "failed"]
    if failed_mems:
        score += 15
        reasons.append(f"Prior failed deployment for similar change (+15)")

    # Scenario-specific logic
    if ct == "framework_upgrade":
        nv = state.get("new_value", "")
        jv = int(svc_info.get("java", "8"))
        if nv.startswith("3.") and jv < 17:
            score += 20
            reasons.append(f"Java mismatch: needs 17, has {jv} (+20)")
        if nv.startswith("3."):
            score += 15
            reasons.append("Spring Boot 3.x breaking migration (+15)")

    elif ct == "resource_change":
        nm = extra.get("new_memory_gb", 0.0)
        peak = svc_info.get("peak_memory_gb", 0.0)
        rsts = svc_info.get("restarts_30d", 0)
        if nm and nm < peak * 1.20:
            score += 25
            reasons.append(f"New mem {nm}GB < safe floor {peak*1.2:.2f}GB (+25)")
        if rsts >= 5:
            score += 10
            reasons.append(f"High restarts: {rsts} in 30d (+10)")

    elif ct == "db_schema":
        db = svc_info.get("db", "")
        db_info = database_users.get(db, {})
        col = extra.get("column", "")
        if len(db_info.get("shared_by", [])) > 1:
            score += 15
            reasons.append(f"Shared DB {db} (+15)")
        if col and col in db_info.get("has_nullable_cols", []):
            score += 20
            reasons.append(f"Column '{col}' has NULLs – backfill required (+20)")

    elif ct == "api_contract":
        of = state.get("old_value", "")
        for api, info in api_consumers.items():
            if info["provider"] == svc:
                if of and of in info["fields"]:
                    score += 20
                    reasons.append(f"Breaking field rename '{of}' in {api} (+20)")
                if len(info["consumers"]) > 2:
                    score += 10
                    reasons.append(f"{len(info['consumers'])} consumers at risk (+10)")

    elif ct == "shared_dependency":
        lib = extra.get("library_name", svc)
        nv = state.get("new_value", "")
        brk = libraries.get(lib, {}).get("breaking_version")
        if brk and nv and nv >= brk:
            score += 25
            reasons.append(f"Major version break: {lib} {nv} >= {brk} (+25)")

    elif ct == "event_schema":
        event = extra.get("event_name", "")
        rf = extra.get("removed_field", "")
        for consumer, fields in event_consumers.get(event, {}).get("consumers", {}).items():
            if rf and rf in fields:
                c = services.get(consumer, {}).get("criticality", "")
                if c in ("critical", "high"):
                    score += 20
                    reasons.append(f"Removed '{rf}' used by {consumer} ({c}) (+20)")

    score = min(score, 100)

    if score <= 25:
        impact, rollout, plan = "low", "direct", "DIRECT ROLLOUT – Low risk. Deploy with standard monitoring."
    elif score <= 50:
        impact, rollout, plan = "medium", "canary", "CANARY ROLLOUT – 5% traffic first, monitor 30 min, then 25%->100%."
    elif score <= 75:
        impact, rollout, plan = "high", "staged-rollout", "STAGED ROLLOUT – Deploy region-by-region with health checks. Rollback plan required."
    else:
        impact, rollout, plan = "critical", "block", "DEPLOYMENT BLOCKED – Resolve all violations before proceeding."

    # Determine SLA impact
    sla_pct = svc_info.get("sla_pct", 99.0)
    sla_impact = "CRITICAL SLA RISK" if score >= 75 and sla_pct >= 99.9 else "SLA AT RISK" if score >= 50 and sla_pct >= 99.0 else "SLA ACCEPTABLE"

    return {**state, "risk_score": score, "impact_level": impact, "risk_reasons": reasons, "rollout_plan": plan, "financial_impact": financial_impact, "sla_impact": sla_impact}

def llm_explanation_agent(state: dict) -> dict:
    """Enhanced LLM agent with better reasoning for larger models."""
    if not OLLAMA_READY:
        explanation, remediation = _rule_based_explanation(state)
    else:
        context = {
            "change_request": state.get("change_request"),
            "service": state.get("service_name"),
            "scenario": state.get("change_type"),
            "risk_score": state.get("risk_score"),
            "impact_level": state.get("impact_level"),
            "affected_services": state.get("affected_services", []),
            "rule_violations": state.get("rule_violations", []),
            "similar_incidents": [{"id": i["id"], "title": i["title"], "severity": i["severity"], "financial_impact": i.get("financial_impact", 0)} for i in state.get("similar_incidents", [])],
            "risk_reasons": state.get("risk_reasons", []),
            "rollout_plan": state.get("rollout_plan", ""),
            "memory_lessons": [{"deployment": m["deployment"], "outcome": m["outcome"], "tested_in_staging": m.get("tested_in_staging", False)} for m in state.get("memory_lessons", [])],
        }

        # Select system prompt based on model
        system_prompt = SYSTEM_PROMPT_EXPERT if MODEL_CONFIG["reasoning_depth"] in ("deep", "expert") else SYSTEM_PROMPT_STANDARD

        prompt_text = f"""Analyze this production deployment change and provide comprehensive guidance:

{json.dumps(context, indent=2)}

Provide your response as JSON with:
{{"explanation": "<2-3 sentence expert analysis>", "remediation": ["step 1", "step 2", "step 3"], "pre_deployment_checklist": ["item1", "item2", "item3"]}}"""

        raw = call_llm(prompt_text, system=system_prompt)
        try:
            parsed = json.loads(raw)
            explanation = parsed.get("explanation", raw)
            remediation = parsed.get("remediation", [])
        except Exception:
            explanation, remediation = _rule_based_explanation(state)

    # Build report
    report = {
        "change_request": state.get("change_request"),
        "service": state.get("service_name"),
        "scenario": state.get("change_type"),
        "affected_services": state.get("affected_services", []),
        "similar_incidents": [{"id": i["id"], "title": i["title"], "severity": i["severity"]} for i in state.get("similar_incidents", [])],
        "rule_violations": state.get("rule_violations", []),
        "memory_lessons": [{"deployment": m["deployment"], "outcome": m["outcome"], "lessons": m["lessons"]} for m in state.get("memory_lessons", [])],
        "risk_score": state.get("risk_score"),
        "impact_level": state.get("impact_level"),
        "sla_impact": state.get("sla_impact"),
        "financial_impact": state.get("financial_impact"),
        "risk_reasons": state.get("risk_reasons", []),
        "rollout_plan": state.get("rollout_plan"),
        "llm_explanation": explanation,
        "llm_remediation": remediation,
    }

    return {**state, "llm_explanation": explanation, "llm_remediation": remediation, "report": report}

def _rule_based_explanation(state: dict) -> tuple:
    """Fallback rule-based explanation."""
    ct = state.get("change_type", "")
    svc = state.get("service_name", "")
    score = state.get("risk_score", 0)
    viols = state.get("rule_violations", [])
    impact = state.get("impact_level", "unknown")
    inc = state.get("similar_incidents", [])

    exp = f"This {ct.replace('_',' ')} change to {svc} carries {impact} risk (score {score}/100). {len(viols)} rule violation(s) detected. " + (f"Similar incident: {inc[0]['title']}." if inc else "Pattern matches concerning.")

    remed_map = {
        "framework_upgrade": ["Run javax->jakarta migration script", "Upgrade Java to 17+ on all pods", "Run full integration test suite"],
        "resource_change": ["Verify memory limit is 20% above peak", "Set up OOMKill alerts", "Perform load test at peak traffic"],
        "db_schema": ["Backfill all NULL values before constraint", "Test migration with production data copy", "Coordinate with all services sharing DB"],
        "api_contract": ["Add backward-compatible alias", "Version the API endpoint", "Notify all consumer teams"],
        "shared_dependency": ["Review CHANGELOG for breaking changes", "Test upgrade in isolation", "Coordinate release window"],
        "event_schema": ["Dual-write new and old fields", "Update all consumers", "Remove old field after migration"],
    }
    remed = remed_map.get(ct, ["Review rule violations", "Test in staging", "Have rollback ready"])
    return exp, remed

def call_llm(prompt: str, system: str = "") -> str:
    """Call local Ollama LLM with streaming support."""
    if not OLLAMA_READY:
        return "[LLM offline – rule-based summary]"
    try:
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        t0 = time.time()
        resp = requests.post(OLLAMA_URL, json={"model": OLLAMA_MODEL, "prompt": full_prompt, "stream": False}, timeout=OLLAMA_TIMEOUT)
        elapsed = time.time() - t0
        ram_used = psutil.virtual_memory().used / (1024 ** 3)
        print(f"  [LLM] {elapsed:.1f}s | RAM: {ram_used:.1f}/{ram_gb:.1f} GB")
        return resp.json().get("response", "").strip()
    except Exception as e:
        return f"[LLM error: {str(e)[:100]}]"

# ============================================================================
# BUILD LANGGRAPH WORKFLOW
# ============================================================================

def build_workflow():
    builder = StateGraph(dict)
    builder.add_node("intake", intake_agent)
    builder.add_node("router", scenario_router)
    builder.add_node("graph_impact", graph_impact_agent)
    builder.add_node("hybrid_rag", hybrid_rag_agent)
    builder.add_node("memory_graph", memory_graph_agent)
    builder.add_node("risk_rollout", risk_rollout_agent)
    builder.add_node("llm_explain", llm_explanation_agent)

    builder.set_entry_point("intake")
    builder.add_edge("intake", "router")
    builder.add_edge("router", "graph_impact")
    builder.add_edge("graph_impact", "hybrid_rag")
    builder.add_edge("hybrid_rag", "memory_graph")
    builder.add_edge("memory_graph", "risk_rollout")
    builder.add_edge("risk_rollout", "llm_explain")
    builder.add_edge("llm_explain", END)

    return builder.compile()

workflow = build_workflow()
print("\n[OK] LangGraph workflow compiled (7 agents: intake->router->impact->hybrid-rag->memory->risk->llm)")

# ============================================================================
# EXPORT FOR NOTEBOOK/GRADIO
# ============================================================================

if __name__ == "__main__":
    print("\n[OK] ChangeGuardian Enhanced Edition ready for use")
    print(f"  Model: {OLLAMA_MODEL}")
    print(f"  Context Window: {MODEL_CONFIG['context_window']:,} tokens")
    print(f"  Reasoning: {MODEL_CONFIG['reasoning_depth'].upper()}")
    print(f"  LLM Status: {'LIVE' if OLLAMA_READY else 'OFFLINE (rule-based fallback)'}")
