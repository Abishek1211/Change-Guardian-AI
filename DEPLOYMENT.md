# ChangeGuardian AI - Hackathon Submission Package

> **Complete, ready-to-run deployment risk analyzer** for AMD ROCM vLLM environments

---

## 📦 What's Included

This package contains everything needed to run ChangeGuardian AI:

✅ **Source Code**
- 7-agent LangGraph pipeline
- FAISS vector RAG + rule-based RAG
- NetworkX service dependency analysis
- Local LLM integration (Ollama/vLLM)
- Interactive Gradio web interface

✅ **Automated Setup**
- `setup.sh` (Linux/MacOS)
- `setup.ps1` (Windows)
- Virtual environment + dependency installation
- Model caching

✅ **Documentation**
- `README_ROCM_VLLM.md` - Complete setup guide
- `CHANGEGUARDIAN_README.md` - Feature documentation
- `QUICKSTART.md` - Quick reference
- Architecture and API docs

✅ **Examples**
- CLI usage examples
- Jupyter notebooks
- Web UI demo

✅ **Validation**
- `scripts/validate.py` - Verify setup is correct

---

## 🚀 Quick Start (3 Steps)

### Step 1: Extract Package
```bash
tar -xzf changeguardian-ai.tar.gz
cd changeguardian-ai
```

### Step 2: Run Setup
```bash
# For AMD GPU with ROCM:
bash setup.sh rocm

# For CPU-only:
bash setup.sh cpu
```

### Step 3: Run Application
```bash
# Activate virtual environment
source venv/bin/activate  # Linux/Mac
# OR
.\venv\Scripts\Activate.ps1  # Windows

# Start web interface
python src/changeguardian_interactive_demo.py

# Open: http://localhost:7860
```

That's it! ✨

---

## 📁 Directory Structure

```
changeguardian-ai/
├── src/                              ← Main code
│   ├── changeguardian_enhanced.py   ← Core 7-agent pipeline
│   ├── changeguardian_interactive_demo.py  ← Web UI
│   └── __init__.py                   ← Package initialization
│
├── examples/                         ← Usage examples
│   ├── cli_example.py               ← Command-line usage
│   └── changeguardian_full_notebook.ipynb  ← Jupyter
│
├── scripts/                          ← Utilities
│   ├── validate.py                  ← Verify setup
│   ├── setup.sh                     ← Linux/Mac setup
│   └── setup.ps1                    ← Windows setup
│
├── docs/                            ← Documentation
│   ├── ARCHITECTURE.md              ← System design
│   └── API_REFERENCE.md             ← API docs
│
├── requirements.txt                 ← Dependencies (AMD ROCM optimized)
├── README_ROCM_VLLM.md             ← Setup & deployment guide
├── CHANGEGUARDIAN_README.md        ← Feature documentation
├── DEPLOYMENT.md                   ← This file
└── .gitignore                      ← Git ignore rules
```

---

## ⚙️ System Requirements

### Minimum (CPU-Only)
- **CPU**: Any modern processor (2+ cores)
- **RAM**: 16GB
- **Disk**: 20GB free
- **Python**: 3.10+
- **OS**: Linux, MacOS, Windows 10+

### Recommended (AMD GPU)
- **GPU**: AMD Radeon Pro or EPYC MI series
- **VRAM**: 8GB+ (for 7B), 24GB+ (for 30B)
- **System RAM**: 32GB+
- **Disk**: 30GB+ (models + dependencies)
- **Python**: 3.10+
- **OS**: Linux (Ubuntu 20.04+)

---

## 🔧 Installation Options

### Option A: Automated (Recommended)

#### Linux/MacOS
```bash
bash setup.sh rocm    # AMD GPU
# or
bash setup.sh cpu     # CPU-only
```

#### Windows
```powershell
.\setup.ps1 -SetupType rocm
# or
.\setup.ps1 -SetupType cpu
```

### Option B: Manual

```bash
# Create virtual environment
python3.10 -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\Activate.ps1  # Windows

# Install dependencies
pip install -r requirements.txt

# (Optional) Install PyTorch with ROCM
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.8

# Verify
python scripts/validate.py
```

---

## 🎯 Usage

### 1. Web Interface (Recommended)

```bash
python src/changeguardian_interactive_demo.py

# Open browser: http://localhost:7860
```

Features:
- Interactive input form
- Real-time analysis results
- Risk score visualization
- Remediation recommendations
- JSON export

### 2. Command-Line

```bash
python examples/cli_example.py "Upgrade payment-service Spring Boot 2.7 to 3.2"

# Or batch processing:
python examples/cli_example.py --file changes.txt --output report.json
```

### 3. Python API

```python
from src.changeguardian_enhanced import workflow

result = workflow.invoke({
    "change_request": "Upgrade payment-service from Spring Boot 2.7 to 3.2"
})

report = result.get("report", {})
print(f"Risk: {report['risk_score']}/100")
print(f"Impact: {report['impact_level']}")
print(f"Recommendation: {report['rollout_plan']}")
```

### 4. Jupyter Notebook

```bash
jupyter notebook examples/changeguardian_full_notebook.ipynb
```

---

## ✅ Verification

After installation, verify everything works:

```bash
# Quick validation
python scripts/validate.py

# Full validation (with LLM checks)
python scripts/validate.py --full

# ROCM-specific checks
python scripts/validate.py --rocm
```

Expected output:
```
✅ Python 3.10.x
✅ Core Dependencies
✅ PyTorch [with CUDA/ROCM]
✅ File Structure
✅ Import Test

Result: 5/5 checks passed
```

---

## 🚀 Performance

Typical analysis times on AMD Ryzen 5950X (64GB RAM):

| Scenario | Time | Notes |
|----------|------|-------|
| Input parsing | ~50ms | Regex-based |
| Graph analysis | ~100ms | NetworkX traversal |
| RAG search | ~200ms | FAISS vector search |
| Risk scoring | ~50ms | Deterministic rules |
| LLM explanation | 2-20s | Model-dependent |
| **Total** | **3-25s** | Depends on model size |

---

## 🔥 AMD ROCM vLLM Integration

### Using vLLM (Recommended)

```bash
# Install vLLM with ROCM support
pip install vllm[rocm]

# Start vLLM server
python -m vllm.entrypoints.openai.api_server \
    --model meta-llama/Llama-2-7b-hf \
    --tensor-parallel-size 1 \
    --port 8000

# Application will auto-detect and use vLLM
```

### Using Ollama (Alternative)

```bash
# Install Ollama from https://ollama.com/download

# Start Ollama
ollama serve

# In another terminal, pull model
ollama pull qwen2.5:7b
```

---

## 🐛 Troubleshooting

### Setup Issues

**Error: Python not found**
- Install Python 3.10+ from [python.org](https://python.org)
- Ensure it's in PATH: `python --version`

**Error: venv already exists**
- Remove it: `rm -rf venv` (or `rmdir venv /s` on Windows)
- Re-run setup: `bash setup.sh rocm`

**Error: ModuleNotFoundError**
- Reinstall dependencies: `pip install -r requirements.txt --upgrade`
- Try `pip install --no-cache-dir -r requirements.txt`

### Runtime Issues

**Error: Ollama connection refused**
- Start Ollama: `ollama serve` (in separate terminal)
- Verify: `curl http://localhost:11434`
- The app will use rule-based fallback if Ollama is unavailable

**Error: ROCM not detected**
- Check installation: `rocm-smi`
- Verify PyTorch: `python -c "import torch; print(torch.cuda.is_available())"`
- Update drivers: Follow [AMD ROCM guide](https://rocmdocs.amd.com)

**Error: Out of Memory (OOM)**
- Use smaller model: `bash setup.sh cpu`
- Or reduce batch size in code
- Or use quantization: `--quantization int8`

### Performance Issues

**Analysis taking >30 seconds**
- Switch to smaller model (qwen2.5:3b instead of 7b)
- Use CPU fallback (faster for small models)
- Check system resources: `htop` / Task Manager

---

## 📊 Features

### ✨ Core Capabilities

- **Dynamic Model Selection**: Auto-selects best model based on available RAM
- **7-Agent Pipeline**: Specialized agents for each analysis step
- **Vector RAG**: FAISS-based similarity search for incident matching
- **Rule Engine**: Deterministic checking for Java versions, memory safety, etc.
- **Graph Analysis**: NetworkX for service dependency mapping
- **Risk Scoring**: 0-100 scale with detailed breakdowns
- **LLM Reasoning**: Local models (Ollama/vLLM) for explanations
- **SLA Tracking**: Identifies critical service risks
- **Financial Impact**: Estimates cost of potential failures

### 🎯 Scenarios

1. **Framework Upgrade** — Spring Boot, Java runtime migrations
2. **Resource Change** — Memory/CPU limit adjustments
3. **Database Schema** — Column changes, migrations
4. **API Contract** — Field renames, breaking changes
5. **Shared Dependency** — Library upgrades across services
6. **Event Schema** — Kafka message contract changes

---

## 📚 Documentation

- **[README_ROCM_VLLM.md](README_ROCM_VLLM.md)** — Complete setup guide for AMD ROCM
- **[CHANGEGUARDIAN_README.md](CHANGEGUARDIAN_README.md)** — Feature details and examples
- **[QUICKSTART.md](QUICKSTART.md)** — Quick reference guide
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — System design (if available)
- **[docs/API_REFERENCE.md](docs/API_REFERENCE.md)** — API documentation (if available)

---

## 🎓 Example Scenarios

### Example 1: High-Risk Framework Upgrade
```
INPUT: Upgrade payment-service from Spring Boot 2.7 to 3.2

OUTPUT:
  Risk Score: 85/100 (CRITICAL)
  Affected: 5 services
  Violations: Java mismatch, breaking API changes
  Similar Incident: INC-002 (Spring Boot 3 migration, $500K impact)
  Recommendation: DEPLOYMENT BLOCKED - Resolve violations first
  
  Remediation:
  1. Upgrade Java to 17+
  2. Run javax→jakarta migration
  3. Run full integration tests
```

### Example 2: Memory Reduction (Dangerous)
```
INPUT: Reduce checkout-service memory from 2GB to 1GB

OUTPUT:
  Risk Score: 100/100 (CRITICAL)
  Peak Memory: 1.8GB (safe floor: 2.16GB)
  Violations: Memory unsafe, high restart risk
  Similar Incident: INC-001 (OOMKilled, $250K impact)
  Recommendation: DEPLOYMENT BLOCKED - Will fail
```

### Example 3: API Field Rename (Medium Risk)
```
INPUT: Change API response field from customer_id to customerId

OUTPUT:
  Risk Score: 55/100 (HIGH)
  Affected: 3 services
  Violations: Breaking API change
  Similar Incident: INC-004 (API rename broke checkout, P2)
  Recommendation: STAGED ROLLOUT - Deploy region-by-region
  
  Remediation:
  1. Add backward-compatible alias
  2. Version API endpoint (/v2/)
  3. Notify consumer teams + migration timeline
```

---

## 🎯 Submission Checklist

Before submitting to hackathon:

- [ ] ✅ Setup script runs without errors
- [ ] ✅ `python scripts/validate.py` passes all checks
- [ ] ✅ Web UI loads at `http://localhost:7860`
- [ ] ✅ Sample analysis completes in <30s
- [ ] ✅ Risk score is accurate and justified
- [ ] ✅ README is clear and comprehensive
- [ ] ✅ No API keys or credentials in code
- [ ] ✅ Project packaged: `tar -czf changeguardian-ai.tar.gz .`
- [ ] ✅ File size is reasonable (<200MB)
- [ ] ✅ Demo video prepared (walkthrough of features)
- [ ] ✅ PowerPoint presentation created

---

## 📞 Support

For issues:
1. Check [Troubleshooting](#troubleshooting) section
2. Run `python scripts/validate.py --full`
3. Check logs in `logs/` directory
4. Review README_ROCM_VLLM.md for detailed setup

---

## 📄 License

Internal Hackathon Project — Not for external distribution

---

## 🙏 Credits

Built by ChangeGuardian Team for AMD ROCM vLLM Hackathon 2026

**Last Updated**: June 15, 2026  
**Status**: ✅ Ready for Submission  

---

**You're all set!** 🚀

Run `python src/changeguardian_interactive_demo.py` and open http://localhost:7860
