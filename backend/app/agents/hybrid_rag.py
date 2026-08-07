"""Agent 4 - Hybrid RAG.

Two retrieval strategies over the same change, kept deliberately separate:

    semantic   FAISS over incident write-ups - finds things that resemble this
    exact      the rule engine - finds things that are certainly broken

Fusing them into one score would hide which is which. The report keeps both.
"""

from __future__ import annotations

from ..rag import check_compatibility_rules, search_incidents


def hybrid_rag_agent(state: dict) -> dict:
    params = {
        "service_name": state.get("service_name", ""),
        "old_value": state.get("old_value", ""),
        "new_value": state.get("new_value", ""),
        **state.get("extra_params", {}),
    }

    return {
        **state,
        "similar_incidents": search_incidents(state["change_request"], k=3),
        "rule_violations": check_compatibility_rules(state.get("change_type", ""), params),
    }
