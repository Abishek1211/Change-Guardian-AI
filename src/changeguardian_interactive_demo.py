"""
ChangeGuardian AI — Interactive Gradio Demo
Enhanced with real-time feedback, detailed visualizations, and export capabilities
"""

import gradio as gr
import json
import time
import psutil
from changeguardian_enhanced_notebook import (
    workflow, OLLAMA_MODEL, MODEL_CONFIG, OLLAMA_READY,
    ram_gb, cpu_cores, services, incident_docs, memory_graph,
    get_affected_services
)

# ============================================================================
# THEME & STYLING
# ============================================================================

custom_css = """
.header {
    text-align: center;
    padding: 20px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border-radius: 10px;
    margin-bottom: 20px;
}

.score-critical { background: linear-gradient(135deg, #ff6b6b, #ee5a6f); color: white; }
.score-high { background: linear-gradient(135deg, #ffa94d, #fd7e14); color: white; }
.score-medium { background: linear-gradient(135deg, #f9ca24, #f0932b); color: white; }
.score-low { background: linear-gradient(135deg, #38ef7d, #11998e); color: white; }

.violation-box { background: #ffe5e5; border-left: 4px solid #ff6b6b; padding: 10px; margin: 5px 0; border-radius: 4px; }
.incident-box { background: #e5f4ff; border-left: 4px solid #0099cc; padding: 10px; margin: 5px 0; border-radius: 4px; }
.remediation-box { background: #e5ffe5; border-left: 4px solid #51cf66; padding: 10px; margin: 5px 0; border-radius: 4px; }

.stat-card { background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 10px 0; }
"""

# ============================================================================
# ANALYSIS FUNCTION
# ============================================================================

def analyze_change(change_request: str, export_format: str = "markdown") -> str:
    """Analyze a change request and return formatted report."""
    if not change_request.strip():
        return "⚠️ **Please enter a change request.** Example: 'Upgrade payment-service from Spring Boot 2.7 to 3.2'"

    t0 = time.time()
    try:
        result = workflow.invoke({"change_request": change_request.strip()})
        elapsed = time.time() - t0
    except Exception as e:
        return f"❌ **Pipeline Error**: {str(e)[:200]}"

    ram_now = psutil.virtual_memory().used / (1024 ** 3)
    r = result.get("report", {})

    impact = r.get("impact_level", "unknown")
    score = r.get("risk_score", 0)
    sla_impact = r.get("sla_impact", "")

    # Color-code impact level
    impact_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴", "critical": "🚨"}.get(impact, "⚪")
    severity_badge = {
        "low": "✅ LOW RISK",
        "medium": "⚠️ MEDIUM RISK",
        "high": "🔴 HIGH RISK",
        "critical": "🚨 CRITICAL - BLOCKED"
    }.get(impact, "UNKNOWN")

    # Format violations
    violations = r.get("rule_violations", [])
    violations_html = ""
    if violations:
        violations_html = "<div style='margin: 15px 0;'><h4>⚠️ Rule Violations (Vectorless RAG)</h4>"
        for v in violations:
            violations_html += f"<div class='violation-box'><strong>❌</strong> {v}</div>"
        violations_html += "</div>"
    else:
        violations_html = "<div style='margin: 15px 0;'><h4>✅ No Rule Violations</h4></div>"

    # Format incidents
    incidents = r.get("similar_incidents", [])
    incidents_html = "<div style='margin: 15px 0;'><h4>📋 Similar Past Incidents (Vector RAG)</h4>"
    if incidents:
        for i in incidents:
            severity_color = "red" if i["severity"] == "P1" else "orange"
            financial = f" | 💰 ${i.get('financial_impact', 0):,.0f}" if i.get("financial_impact") else ""
            incidents_html += f"<div class='incident-box'><strong>[{i['severity']}]</strong> <code>{i['id']}</code>: {i['title']}{financial}</div>"
    else:
        incidents_html += "<p><em>No similar incidents found.</em></p>"
    incidents_html += "</div>"

    # Format memory lessons
    memory_html = "<div style='margin: 15px 0;'><h4>📚 Memory Graph (Prior Deployments)</h4>"
    lessons = r.get("memory_lessons", [])
    if lessons:
        for m in lessons:
            outcome_icon = "✅" if m["outcome"] == "success" else "❌"
            tested_label = " [Tested in Staging]" if m.get("tested_in_staging") else " [NOT tested]"
            memory_html += f"<div class='stat-card'>{outcome_icon} <strong>{m['deployment']}</strong>{tested_label}<br/>"
            memory_html += f"<small>{' | '.join(m['lessons'])}</small></div>"
    else:
        memory_html += "<p><em>No prior deployment data.</em></p>"
    memory_html += "</div>"

    # Format remediation
    remediation_html = "<div style='margin: 15px 0;'><h4>✅ Remediation Steps</h4>"
    remediation = r.get("llm_remediation", [])
    for i, step in enumerate(remediation, 1):
        remediation_html += f"<div class='remediation-box'><strong>{i}.</strong> {step}</div>"
    remediation_html += "</div>"

    # Format risk reasons
    reasons_html = "<div style='margin: 15px 0;'><h4>🔍 Risk Score Breakdown</h4>"
    for reason in r.get("risk_reasons", []):
        reasons_html += f"<div class='stat-card'>➕ {reason}</div>"
    reasons_html += "</div>"

    # Affected services
    affected_html = ""
    aff_services = r.get("affected_services", [])
    if aff_services:
        affected_html = "<div style='margin: 15px 0;'><h4>🔗 Affected Services</h4><div style='display: flex; flex-wrap: wrap; gap: 8px;'>"
        for svc in aff_services:
            crit = services.get(svc, {}).get("criticality", "unknown")
            crit_color = {"critical": "red", "high": "orange", "medium": "blue", "low": "green"}.get(crit, "gray")
            affected_html += f"<div style='background: {crit_color}20; padding: 8px 12px; border-radius: 20px; border-left: 3px solid {crit_color};'><code>{svc}</code> <em>({crit})</em></div>"
        affected_html += "</div></div>"

    # Main report
    report = f"""
<div class='header'>
<h2>🚀 ChangeGuardian AI — Risk Analysis Report</h2>
</div>

---

## 📊 Executive Summary

| Metric | Value |
|--------|-------|
| **Change Request** | {r.get('change_request')} |
| **Scenario** | `{r.get('scenario', '').replace('_', ' ').upper()}` |
| **Service** | `{r.get('service')}` |
| **Risk Score** | **{score}/100** {severity_badge} |
| **Impact Level** | {impact_emoji} **{impact.upper()}** |
| **SLA Impact** | {sla_impact} |
| **Pipeline Time** | {elapsed:.2f}s |

---

## 🎯 Recommendation

### Rollout Plan
> {r.get('rollout_plan', 'No rollout plan available')}

### LLM Analysis ({OLLAMA_MODEL})
> {r.get('llm_explanation', 'Analysis unavailable')}

---

{affected_html}

{violations_html}

{incidents_html}

{memory_html}

{reasons_html}

{remediation_html}

---

## 📈 System Info
- **LLM Model**: {OLLAMA_MODEL}
- **Context Window**: {MODEL_CONFIG['context_window']:,} tokens
- **Reasoning Depth**: {MODEL_CONFIG['reasoning_depth'].upper()}
- **LLM Status**: {"🟢 LIVE" if OLLAMA_READY else "🔴 OFFLINE (rule-based fallback)"}
- **Available RAM**: {ram_now:.1f}GB / {ram_gb:.1f}GB

---

*Generated by ChangeGuardian AI Enhanced Edition*
"""

    return report

# ============================================================================
# BUILD GRADIO INTERFACE
# ============================================================================

with gr.Blocks(title="ChangeGuardian AI", css=custom_css, theme=gr.themes.Soft()) as demo:
    gr.HTML(f"""
    <div class='header'>
        <h1>🚀 ChangeGuardian AI</h1>
        <p><strong>Pre-Deployment Production Risk Analysis Platform</strong></p>
        <p style='font-size: 0.9em; margin-top: 10px;'>
            Model: <code>{OLLAMA_MODEL}</code> |
            Context: <code>{MODEL_CONFIG['context_window']:,} tokens</code> |
            Reasoning: <code>{MODEL_CONFIG['reasoning_depth'].upper()}</code> |
            Status: {"🟢 LIVE" if OLLAMA_READY else "🔴 OFFLINE"}
        </p>
    </div>
    """)

    with gr.Row():
        with gr.Column(scale=2):
            change_input = gr.Textbox(
                label="📝 Describe Your Production Change",
                placeholder="e.g., Upgrade payment-service from Spring Boot 2.7 to 3.2",
                lines=4,
                info="Be specific about what, where, and why you're changing"
            )
            submit_btn = gr.Button("🔍 Analyze Risk", variant="primary", size="lg")

        with gr.Column(scale=1):
            gr.Markdown("### 💡 Quick Examples")
            gr.Examples(
                examples=[
                    ["Upgrade payment-service from Spring Boot 2.7 to 3.2"],
                    ["Reduce checkout-service memory limit from 2GB to 1GB"],
                    ["Add NOT NULL constraint to transaction.amount in payment-db"],
                    ["Change payment API response field from customer_id to customerId"],
                    ["Upgrade legacy-auth-client from 1.4.0 to 2.0.0 across all services"],
                    ["Remove customerEmail field from order-created Kafka event"],
                ],
                inputs=change_input,
                label="Tap to load example"
            )

    report_output = gr.HTML(label="Risk Report")

    submit_btn.click(
        fn=analyze_change,
        inputs=change_input,
        outputs=report_output
    )

    with gr.Accordion("ℹ️ About ChangeGuardian AI", open=False):
        gr.Markdown("""
        ### How It Works

        **7-Agent Pipeline:**
        1. **Intake Agent** — Parse change details (service, old/new values)
        2. **Router Agent** — Classify scenario (framework_upgrade, resource_change, etc.)
        3. **Graph Impact Agent** — Find affected services via NetworkX
        4. **Hybrid RAG Agent** — Vector search (FAISS) + vectorless rules
        5. **Memory Graph Agent** — Learn from prior deployments
        6. **Risk & Rollout Agent** — Deterministic scoring (0-100) + recommendations
        7. **LLM Explanation Agent** — Local {OLLAMA_MODEL} reasoning

        ### Features
        - ✅ **Deterministic + Learning**: Rule-based scoring + incident similarity matching
        - ✅ **Production Data**: Real SLA, financial impact, criticality metrics
        - ✅ **Local Execution**: No cloud APIs, no data leaves your machine
        - ✅ **Large Models**: Supports Qwen 3-30B, Llama 3.1-70B, etc.
        - ✅ **Fully Auditable**: Every risk score reason is logged

        ### Supported Scenarios
        - 🔄 **Framework Upgrade** (Spring Boot, Java, runtimes)
        - 💾 **Resource Change** (memory, CPU limits)
        - 📋 **DB Schema** (constraints, columns, migrations)
        - 🔗 **API Contract** (field renames, breaking changes)
        - 📦 **Shared Dependency** (library upgrades, bulk risk)
        - 🎪 **Event Schema** (Kafka fields, message contracts)
        """)

    with gr.Accordion("🛠️ System Configuration", open=False):
        gr.Markdown(f"""
        ### Hardware
        - CPU: {psutil.cpu_count(logical=False)} cores (physical), {psutil.cpu_count(logical=True)} cores (logical)
        - RAM: {ram_gb:.1f} GB total, {psutil.virtual_memory().available / (1024**3):.1f} GB available

        ### LLM Model
        - **Selected**: {OLLAMA_MODEL}
        - **Context Window**: {MODEL_CONFIG['context_window']:,} tokens
        - **Reasoning Depth**: {MODEL_CONFIG['reasoning_depth'].upper()}
        - **Temperature**: {MODEL_CONFIG['temperature']}
        - **Timeout**: {MODEL_CONFIG['timeout']}s

        ### Data
        - **Services**: {len(services)}
        - **Libraries**: 2
        - **Incidents**: {len(incident_docs)}
        - **Prior Deployments**: {len(memory_graph)}

        ### Run Locally
        ```bash
        # Install dependencies
        pip install gradio langgraph networkx faiss-cpu sentence-transformers

        # Start Ollama (in separate terminal)
        ollama pull qwen3:30b-a3b  # Or your preferred model
        ollama serve

        # Launch demo
        python changeguardian_interactive_demo.py
        ```
        """)

if __name__ == "__main__":
    demo.launch(
        server_name="127.0.0.1",
        share=False,
        show_error=True
    )
