#!/usr/bin/env python3
"""
ChangeGuardian AI - Streamlit Web Application
Interactive deployment risk analysis with vLLM integration
"""

import streamlit as st
import sys
import os
from pathlib import Path
import time
import requests
import psutil
import json

# Add src to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from changeguardian_enhanced import (
    workflow,
    OLLAMA_MODEL,
    MODEL_CONFIG,
    OLLAMA_READY,
    ram_gb,
    cpu_cores,
    services,
    incident_docs,
    get_affected_services,
)

# ============================================================================
# PAGE CONFIG
# ============================================================================

st.set_page_config(
    page_title="ChangeGuardian AI",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        margin: 10px 0;
    }
    .risk-low { background: linear-gradient(135deg, #38ef7d, #11998e); color: white; }
    .risk-medium { background: linear-gradient(135deg, #f9ca24, #f0932b); color: white; }
    .risk-high { background: linear-gradient(135deg, #ffa94d, #fd7e14); color: white; }
    .risk-critical { background: linear-gradient(135deg, #ff6b6b, #ee5a6f); color: white; }
    .stat-box {
        background: #f0f2f6;
        padding: 15px;
        border-radius: 8px;
        border-left: 4px solid #667eea;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# SIDEBAR - SYSTEM INFO & SETTINGS
# ============================================================================

with st.sidebar:
    st.markdown("## 🔧 System Configuration")

    st.markdown("### Hardware")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("CPU Cores", f"{cpu_cores}")
    with col2:
        st.metric("RAM", f"{ram_gb:.1f} GB")

    st.markdown("### LLM Model")
    st.markdown(f"**Selected:** `{OLLAMA_MODEL}`")
    st.markdown(f"**Context:** `{MODEL_CONFIG['context_window']:,}` tokens")
    st.markdown(f"**Reasoning:** `{MODEL_CONFIG['reasoning_depth'].upper()}`")

    # Status indicator
    status_color = "🟢" if OLLAMA_READY else "🔴"
    st.markdown(f"{status_color} **vLLM Status:** {'RUNNING' if OLLAMA_READY else 'OFFLINE (Rule-based)'}")

    if not OLLAMA_READY:
        st.warning("⚠️ vLLM not detected on port 8000. Using rule-based analysis.")

    st.divider()

    # Quick examples
    st.markdown("### 📚 Quick Examples")
    examples = [
        "Upgrade payment-service from Spring Boot 2.7 to 3.2",
        "Reduce checkout-service memory limit from 2GB to 1GB",
        "Add NOT NULL constraint to transaction.amount",
        "Change payment API field from customer_id to customerId",
        "Upgrade legacy-auth-client to 2.0.0",
        "Remove customerEmail from order-created event",
    ]

    if st.button("📋 Load Example"):
        st.session_state.example_change = st.selectbox(
            "Choose an example:",
            examples,
            key="example_select"
        )

# ============================================================================
# MAIN CONTENT
# ============================================================================

st.markdown("""
<div style="text-align: center; margin-bottom: 30px;">
    <h1>🚀 ChangeGuardian AI</h1>
    <p><strong>Pre-Deployment Production Risk Analysis Platform</strong></p>
    <p style="font-size: 0.9em; color: #666;">
        LangGraph · NetworkX Graph RAG · FAISS Vector RAG · Vectorless Rules · vLLM/AMD
    </p>
</div>
""", unsafe_allow_html=True)

# Input section
st.markdown("## 📝 Analyze Your Deployment Change")

col1, col2 = st.columns([3, 1])

with col1:
    change_request = st.text_area(
        "Describe your production change:",
        placeholder="e.g., Upgrade payment-service from Spring Boot 2.7 to 3.2",
        height=100,
        label_visibility="collapsed"
    )

with col2:
    analyze_button = st.button("🔍 Analyze Risk", type="primary", use_container_width=True)

# ============================================================================
# ANALYSIS LOGIC
# ============================================================================

if analyze_button and change_request:
    with st.spinner("🔄 Analyzing change... (this may take a moment)"):
        try:
            t0 = time.time()
            result = workflow.invoke({"change_request": change_request})
            elapsed = time.time() - t0

            report = result.get("report", {})

            # Extract key metrics
            risk_score = report.get("risk_score", 0)
            impact_level = report.get("impact_level", "unknown")
            affected = report.get("affected_services", [])
            violations = report.get("rule_violations", [])
            incidents = report.get("similar_incidents", [])
            remediation = report.get("llm_remediation", [])

            # Display results
            st.success("✅ Analysis Complete")

            # ================================================================
            # EXECUTIVE SUMMARY
            # ================================================================

            st.markdown("## 📊 Executive Summary")

            # Risk score card with color coding
            impact_colors = {
                "low": "🟢",
                "medium": "🟡",
                "high": "🔴",
                "critical": "🚨",
            }
            impact_emoji = impact_colors.get(impact_level, "⚪")

            col1, col2, col3, col4, col5 = st.columns(5)

            with col1:
                st.metric(
                    "Risk Score",
                    f"{risk_score}/100",
                    delta=f"{impact_level.upper()}",
                )

            with col2:
                st.metric("Impact Level", f"{impact_emoji} {impact_level.upper()}")

            with col3:
                st.metric("Affected Services", len(affected))

            with col4:
                st.metric("Rule Violations", len(violations))

            with col5:
                st.metric("Pipeline Time", f"{elapsed:.2f}s")

            # ================================================================
            # DETAILS TABS
            # ================================================================

            tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
                "📋 Overview",
                "🔗 Affected Services",
                "⚠️ Violations",
                "📚 Similar Incidents",
                "💊 Remediation",
                "🧠 LLM Analysis",
            ])

            # Tab 1: Overview
            with tab1:
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("### Change Details")
                    st.markdown(f"**Request:** {change_request}")
                    st.markdown(f"**Service:** `{report.get('service', 'unknown')}`")
                    st.markdown(f"**Scenario:** `{report.get('scenario', '').replace('_', ' ').upper()}`")

                with col2:
                    st.markdown("### Risk Assessment")
                    st.markdown(f"**Rollout Plan:** {report.get('rollout_plan', 'N/A')}")
                    st.markdown(f"**SLA Impact:** {report.get('sla_impact', 'N/A')}")
                    st.markdown(f"**Financial Impact:** ${report.get('financial_impact', 0):,.0f}")

                st.divider()

                st.markdown("### Risk Score Breakdown")
                for reason in report.get("risk_reasons", []):
                    st.text(f"• {reason}")

            # Tab 2: Affected Services
            with tab2:
                if affected:
                    st.markdown(f"### 🔗 {len(affected)} Service(s) Impacted")
                    cols = st.columns(min(3, len(affected)))
                    for idx, svc in enumerate(affected):
                        with cols[idx % 3]:
                            svc_info = services.get(svc, {})
                            criticality = svc_info.get("criticality", "unknown")
                            crit_emoji = {
                                "critical": "🚨",
                                "high": "🔴",
                                "medium": "🟡",
                                "low": "🟢",
                            }.get(criticality, "⚪")

                            st.markdown(f"""
                            <div class='stat-box'>
                                <strong>{crit_emoji} {svc}</strong><br>
                                Criticality: {criticality}
                            </div>
                            """, unsafe_allow_html=True)
                else:
                    st.info("No other services affected by this change.")

            # Tab 3: Violations
            with tab3:
                if violations:
                    st.markdown(f"### ⚠️ {len(violations)} Violation(s) Detected")
                    for violation in violations:
                        st.error(f"❌ {violation}")
                else:
                    st.success("✅ No rule violations detected!")

            # Tab 4: Similar Incidents
            with tab4:
                if incidents:
                    st.markdown(f"### 📋 {len(incidents)} Similar Incident(s) Found")
                    for inc in incidents:
                        severity_emoji = "🔴" if inc["severity"] == "P1" else "🟡"
                        with st.expander(f"{severity_emoji} {inc['id']}: {inc['title']}"):
                            st.markdown(f"**Severity:** {inc['severity']}")
                            st.markdown(f"**Financial Impact:** ${inc.get('financial_impact', 0):,.0f}")
                else:
                    st.info("No similar past incidents found.")

            # Tab 5: Remediation
            with tab5:
                st.markdown("### 💊 Recommended Remediation Steps")
                if remediation:
                    for i, step in enumerate(remediation, 1):
                        st.markdown(f"{i}. **{step}**")
                else:
                    st.info("No specific remediation steps recommended.")

            # Tab 6: LLM Analysis
            with tab6:
                st.markdown(f"### 🧠 LLM Analysis ({OLLAMA_MODEL})")

                if OLLAMA_READY:
                    st.markdown("#### Explanation")
                    st.info(report.get("llm_explanation", "LLM analysis unavailable"))
                else:
                    st.warning("LLM is offline. Showing rule-based analysis instead.")
                    st.info(report.get("llm_explanation", "Using rule-based fallback."))

            # ================================================================
            # EXPORT SECTION
            # ================================================================

            st.divider()
            st.markdown("## 📥 Export Report")

            col1, col2 = st.columns(2)

            with col1:
                # JSON export
                json_report = json.dumps(report, indent=2)
                st.download_button(
                    label="📄 Download as JSON",
                    data=json_report,
                    file_name=f"changeguardian_report_{int(time.time())}.json",
                    mime="application/json",
                )

            with col2:
                # Markdown export
                markdown_report = f"""
# ChangeGuardian AI Risk Report

## Executive Summary
- **Risk Score:** {risk_score}/100
- **Impact Level:** {impact_level.upper()}
- **Affected Services:** {len(affected)}
- **Rule Violations:** {len(violations)}

## Change Details
- **Request:** {change_request}
- **Service:** {report.get('service', 'unknown')}
- **Scenario:** {report.get('scenario', '').replace('_', ' ').upper()}

## Rollout Plan
{report.get('rollout_plan', 'N/A')}

## Remediation Steps
{chr(10).join([f'{i}. {step}' for i, step in enumerate(remediation, 1)])}

---
Generated by ChangeGuardian AI
"""
                st.download_button(
                    label="📋 Download as Markdown",
                    data=markdown_report,
                    file_name=f"changeguardian_report_{int(time.time())}.md",
                    mime="text/markdown",
                )

        except Exception as e:
            st.error(f"❌ Analysis failed: {str(e)}")
            st.info("Check that the workflow is properly initialized and vLLM is running.")

elif analyze_button and not change_request:
    st.warning("⚠️ Please enter a change request to analyze.")

# ================================================================
# FOOTER
# ================================================================

st.divider()
st.markdown("""
<div style="text-align: center; color: #666; font-size: 0.9em;">
    <p>ChangeGuardian AI v1.0 | <a href="https://github.com/Abishek1211/Change-Guardian-AI">GitHub</a></p>
    <p>Powered by LangGraph · NetworkX · FAISS · vLLM/AMD</p>
</div>
""", unsafe_allow_html=True)
