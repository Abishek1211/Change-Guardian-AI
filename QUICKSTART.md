# ChangeGuardian AI — Quick Start Guide

> Get up and running in 5 minutes

---

## ⚡ 5-Minute Setup

### 1. Install Dependencies (2 min)
```bash
cd "d:\intelij projects\AI AMD HACKATHON"

pip install --upgrade pip
pip install langgraph networkx faiss-cpu sentence-transformers gradio psutil requests pydantic
```

### 2. Install & Start Ollama (1 min)
```bash
# Download from https://ollama.com/download
# Then in a new terminal:

ollama pull qwen2.5:3b    # Quick (6GB) OR
ollama pull qwen3:30b-a3b # Better (35GB) OR
ollama pull llama3.1:70b  # Best (60GB)

# Start Ollama
ollama serve
```

### 3. Launch Interactive Demo (2 min)
```bash
# In your project terminal
python changeguardian_interactive_demo.py

# Opens at http://localhost:7860
# Type a change and click "Analyze Risk"
```

---

## 🎯 Three Ways to Use

### Option A: Web Interface (Easiest)
```bash
python changeguardian_interactive_demo.py
# → Open http://localhost:7860
# → Type change request
# → Get risk report in real-time
```

### Option B: Python Script
```python
from changeguardian_enhanced_notebook import workflow

result = workflow.invoke({
    "change_request": "Upgrade payment-service from Spring Boot 2.7 to 3.2"
})

report = result.get("report", {})
print(f"Risk: {report['risk_score']}/100")
print(f"Impact: {report['impact_level']}")
print(f"Action: {report['rollout_plan']}")
```

### Option C: Jupyter Notebook
```bash
jupyter notebook

# New notebook:
from changeguardian_enhanced_notebook import workflow

result = workflow.invoke({"change_request": "Your change"})
# Explore result interactively
```

---

## 📝 Example Scenarios to Try

### Safe Deployment (Score: 15)
```
Upgrade user-service from Spring Boot 3.0 to 3.1
```
→ Expected: LOW RISK, DIRECT ROLLOUT

### Risky Upgrade (Score: 85)
```
Upgrade payment-service from Spring Boot 2.7 to 3.2
```
→ Expected: CRITICAL, DEPLOYMENT BLOCKED

### Memory Danger (Score: 100)
```
Reduce checkout-service memory limit from 2GB to 1GB
```
→ Expected: CRITICAL, DEPLOYMENT BLOCKED

### API Change (Score: 55)
```
Change payment API response field from customer_id to customerId
```
→ Expected: HIGH RISK, STAGED ROLLOUT

### Library Upgrade (Score: 95)
```
Upgrade legacy-auth-client from 1.4.0 to 2.0.0
```
→ Expected: CRITICAL, DEPLOYMENT BLOCKED

---

## 🔧 Troubleshooting

### Problem: "LLM offline"
```bash
# Make sure Ollama is running in another terminal
ollama serve

# Then verify it's reachable
curl http://localhost:11434
```

### Problem: "Out of memory"
```bash
# Use smaller model instead
ollama pull qwen2.5:3b  # Instead of larger models
```

### Problem: "Module not found"
```bash
# Reinstall dependencies
pip install --force-reinstall langgraph networkx faiss-cpu sentence-transformers gradio
```

---

## 📊 What You Get

### Risk Report Includes:
- ✅ **Risk Score** (0-100)
- ✅ **Impact Level** (low / medium / high / critical)
- ✅ **Affected Services** (graph traversal)
- ✅ **Similar Past Incidents** (FAISS vector search)
- ✅ **Rule Violations** (deterministic checks)
- ✅ **Memory Graph Lessons** (prior deployments)
- ✅ **Risk Breakdown** (scoring explanation)
- ✅ **Rollout Plan** (direct / canary / staged / blocked)
- ✅ **LLM Explanation** (AI reasoning)
- ✅ **Remediation Steps** (3 actionable items)

---

## 🚀 Next Steps

1. **Read full docs**: [CHANGEGUARDIAN_README.md](CHANGEGUARDIAN_README.md)
2. **Explore code**: `changeguardian_enhanced_notebook.py`
3. **Customize**: Add your services, incidents, rules
4. **Deploy**: Use in your CI/CD pipeline

---

## 💡 Pro Tips

### Tip 1: Use Larger Models for Better Reasoning
```bash
# For production deployments, use:
ollama pull qwen3:30b-a3b  # or llama3.1:70b
# Auto-detected and used if your hardware supports it
```

### Tip 2: Add Your Own Incidents
Edit `incident_docs` in `changeguardian_enhanced_notebook.py`:
```python
incident_docs.append({
    "id": "INC-007",
    "service": "my-service",
    "severity": "P1",
    "title": "Your incident",
    "root_cause": "What happened",
    "lesson": "What we learned",
    "financial_impact": 100000,
    "duration_minutes": 60
})
```

### Tip 3: Integrate with CI/CD
```bash
# In your pre-deployment hook:
python -c "from changeguardian_enhanced_notebook import workflow; 
result = workflow.invoke({'change_request': sys.argv[1]}); 
score = result['report']['risk_score']; 
exit(1 if score > 75 else 0)"
```

---

## 📞 Help

**Stuck?** Check these files:
- [Full README](CHANGEGUARDIAN_README.md) — Complete documentation
- [Demo Page](DEMO.html) — Visual examples
- [Original Notebook](changeguardian_notebook.ipynb) — Reference implementation

---

**Version**: 2.0 Enhanced  
**Status**: ✅ Production Ready  
**Updated**: 2026-06-14

