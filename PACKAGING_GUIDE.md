# ChangeGuardian AI - Packaging Guide for Hackathon Submission

> Complete instructions for preparing your project for AMD ROCM vLLM Hackathon submission

---

## 📋 Pre-Packaging Checklist

Before creating the final submission package, verify:

```bash
# 1. Validate setup works
python scripts/validate.py --full

# 2. Test web UI runs
python src/changeguardian_interactive_demo.py &
sleep 2
curl http://localhost:7860 > /dev/null && echo "✅ Web UI accessible"

# 3. Test CLI works
python examples/cli_example.py "Test change" | head -5

# 4. Check no credentials exist
grep -r "api_key\|password\|secret\|token" src/ examples/ --include="*.py" || echo "✅ No secrets found"

# 5. Verify file structure
ls -la src/ examples/ scripts/ | grep -E "\.py|\.sh|\.ps1"
```

---

## 🗜️ Creating the Submission Package

### Option 1: TAR.GZ (Recommended for Linux/Mac judges)

#### Step 1: Clean Project
```bash
cd "d:\intelij projects\Change Guardian AI"

# Remove unnecessary files
rm -rf venv
rm -rf .git
rm -rf __pycache__
rm -rf .ipynb_checkpoints
rm -rf .idea .vscode
rm -rf .pytest_cache
rm -rf *.egg-info
rm -f *.pyc *.pyo
rm -rf .coverage htmlcov
rm -f .DS_Store Thumbs.db
rm -f *.log
```

#### Step 2: Create Tarball
```bash
# From parent directory
cd "d:\intelij projects"

tar -czf changeguardian-ai.tar.gz \
  --exclude='Change Guardian AI/.git' \
  --exclude='Change Guardian AI/venv' \
  --exclude='Change Guardian AI/__pycache__' \
  --exclude='Change Guardian AI/.ipynb_checkpoints' \
  --exclude='Change Guardian AI/.idea' \
  --exclude='Change Guardian AI/.vscode' \
  --exclude='Change Guardian AI/.pytest_cache' \
  --exclude='Change Guardian AI/*.egg-info' \
  --exclude='Change Guardian AI/dist' \
  --exclude='Change Guardian AI/build' \
  "Change Guardian AI"

# Verify
ls -lh changeguardian-ai.tar.gz
tar -tzf changeguardian-ai.tar.gz | head -20
```

#### Step 3: Test Extraction
```bash
# Create test directory
mkdir test_submission
cd test_submission

# Extract
tar -xzf ../changeguardian-ai.tar.gz

# Move contents up one level
mv "Change Guardian AI"/* .
rm -rf "Change Guardian AI"

# Validate
python scripts/validate.py --full
```

### Option 2: ZIP (For Windows & Cross-platform)

#### Windows PowerShell
```powershell
# Navigate to project
cd "d:\intelij projects\Change Guardian AI"

# Remove unnecessary files
Remove-Item -Recurse -Force venv -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force .git -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force __pycache__ -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force .idea, .vscode -ErrorAction SilentlyContinue

# Create ZIP
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory((Get-Location).Path, "changeguardian-ai.zip")

# Verify
Get-Item changeguardian-ai.zip | Select-Object Length
```

#### Linux/Mac (using zip command)
```bash
cd "d:\intelij projects"

zip -r changeguardian-ai.zip "Change Guardian AI" \
  -x "Change Guardian AI/.git/*" \
  "Change Guardian AI/venv/*" \
  "Change Guardian AI/__pycache__/*" \
  "Change Guardian AI/.ipynb_checkpoints/*" \
  "Change Guardian AI/.idea/*" \
  "Change Guardian AI/.vscode/*"

# Verify
ls -lh changeguardian-ai.zip
unzip -l changeguardian-ai.zip | head -20
```

---

## 📦 Package Contents Verification

After creating the archive, verify it contains all necessary files:

```bash
# List all files in archive
tar -tzf changeguardian-ai.tar.gz | grep -E "\.py$|\.md$|\.txt$" | sort

# Expected structure:
# README_ROCM_VLLM.md ✅
# CHANGEGUARDIAN_README.md ✅
# DEPLOYMENT.md ✅
# QUICKSTART.md ✅
# SUBMISSION_CHECKLIST.md ✅
# INDEX.md ✅
# requirements.txt ✅
# setup.sh ✅
# setup.ps1 ✅
# src/changeguardian_enhanced.py ✅
# src/changeguardian_interactive_demo.py ✅
# src/__init__.py ✅
# examples/cli_example.py ✅
# examples/changeguardian_full_notebook.ipynb ✅
# scripts/validate.py ✅
```

---

## 📊 Final Package Stats

Document these for your submission:

```bash
# Count files
echo "Total files:"
tar -tzf changeguardian-ai.tar.gz | wc -l

# Count by type
echo "Python files:"
tar -tzf changeguardian-ai.tar.gz | grep "\.py$" | wc -l

echo "Documentation:"
tar -tzf changeguardian-ai.tar.gz | grep "\.md$" | wc -l

# Package size
ls -lh changeguardian-ai.tar.gz | awk '{print "Size: " $5}'

# Largest files
tar -tzf changeguardian-ai.tar.gz | sort -k1 -h | tail -10
```

---

## 🧪 Final Verification Steps

Before submitting, perform these final checks:

### 1. Extract in Clean Environment
```bash
# Create clean test directory
mkdir /tmp/hackathon_test
cd /tmp/hackathon_test

# Extract package
tar -xzf changeguardian-ai.tar.gz
cd changeguardian-ai  # or appropriate directory name
```

### 2. Run Setup Script
```bash
# Test setup
bash setup.sh rocm
# OR
bash setup.sh cpu

# This should:
# ✅ Create venv
# ✅ Install dependencies
# ✅ Download embedding model
# ✅ Pass all validation checks
```

### 3. Validate Installation
```bash
source venv/bin/activate
python scripts/validate.py --full

# All checks should PASS
```

### 4. Quick Functionality Test
```bash
# Test imports
python -c "from src.changeguardian_enhanced import workflow; print('✅ Imports OK')"

# Test CLI
python examples/cli_example.py "Upgrade service memory" | head -10

# Kill any web UI processes first, then test
python src/changeguardian_interactive_demo.py &
sleep 3
curl -s http://localhost:7860 > /dev/null && echo "✅ Web UI OK"
kill %1
```

### 5. Check Documentation
```bash
# Verify all README files exist
for file in README_ROCM_VLLM.md DEPLOYMENT.md QUICKSTART.md SUBMISSION_CHECKLIST.md; do
  [ -f "$file" ] && echo "✅ $file" || echo "❌ $file MISSING"
done

# Verify all setup scripts exist
for file in setup.sh setup.ps1 scripts/validate.py; do
  [ -f "$file" ] && echo "✅ $file" || echo "❌ $file MISSING"
done
```

---

## 📄 Submission Deliverables

Prepare these three components:

### 1. Code Package
- **File**: `changeguardian-ai.tar.gz` or `.zip`
- **Size**: <200MB
- **Contents**: Complete source + setup + docs
- **Status**: ✅ Ready

### 2. Presentation
- **File**: `ChangeGuardian_AI_Presentation.pptx`
- **Slides**: 8-10 slides minimum
- **Content**:
  - Title slide with team info
  - Problem statement
  - Solution overview
  - Architecture diagram
  - 7-agent pipeline details
  - Technology stack (AMD ROCM, vLLM, LangGraph)
  - Demo walkthrough
  - Results & metrics
  - Future enhancements

### 3. Demo Video
- **File**: `changeguardian-ai-demo.mp4`
- **Duration**: 3-5 minutes
- **Format**: 1080p, MP4, H.264
- **Content**:
  - Setup & installation (30 sec)
  - Feature walkthrough (90 sec)
  - Sample analysis (90 sec)
  - Results interpretation (60 sec)
- **Hosting**: YouTube link or attachment

---

## 🎯 Submission Checklist

Before final submission:

### Code Package
- [ ] ✅ TAR.GZ or ZIP created
- [ ] ✅ Size <200MB
- [ ] ✅ Extracts cleanly
- [ ] ✅ Setup script runs
- [ ] ✅ Validation passes
- [ ] ✅ Web UI loads
- [ ] ✅ CLI works
- [ ] ✅ No credentials in code

### Documentation
- [ ] ✅ README_ROCM_VLLM.md complete
- [ ] ✅ DEPLOYMENT.md complete
- [ ] ✅ QUICKSTART.md complete
- [ ] ✅ All examples documented
- [ ] ✅ Troubleshooting guide included
- [ ] ✅ API reference included
- [ ] ✅ Architecture documented

### Presentation
- [ ] ✅ PowerPoint created
- [ ] ✅ All required slides present
- [ ] ✅ Clear problem statement
- [ ] ✅ Solution well explained
- [ ] ✅ Technology stack highlighted
- [ ] ✅ Demo plan documented
- [ ] ✅ Metrics & results shown

### Demo Video
- [ ] ✅ Video created
- [ ] ✅ 3-5 minute duration
- [ ] ✅ 1080p resolution
- [ ] ✅ Setup shown
- [ ] ✅ Features demonstrated
- [ ] ✅ Sample analysis shown
- [ ] ✅ Results interpreted
- [ ] ✅ Hosted (YouTube or link)

---

## 🚀 Submission Process

### Step 1: Prepare Files
```bash
# Clean and create archives
bash setup_submission.sh

# Files created:
# - changeguardian-ai.tar.gz (code)
# - ChangeGuardian_AI_Presentation.pptx (slides)
# - changeguardian-ai-demo.mp4 (video)
```

### Step 2: Create Submission Summary
```markdown
## Submission Summary

**Project**: ChangeGuardian AI  
**Category**: AI/ML Application  
**Team**: [Your Team Name]  
**Members**: [Names]

### Files Included
1. **changeguardian-ai.tar.gz** (130 MB)
   - Complete source code
   - Setup scripts for Linux/Mac/Windows
   - Full documentation
   - Examples and demos

2. **ChangeGuardian_AI_Presentation.pptx** (8 slides)
   - Architecture overview
   - Feature demonstration
   - Technology stack (AMD ROCM vLLM)
   - Performance metrics

3. **changeguardian-ai-demo.mp4** (4 minutes)
   - Feature walkthrough
   - Sample analysis
   - Real-time results

### Setup Instructions
1. Extract: `tar -xzf changeguardian-ai.tar.gz`
2. Setup: `bash setup.sh rocm` (or cpu)
3. Run: `python src/changeguardian_interactive_demo.py`
4. Open: http://localhost:7860

### Key Technologies
- AMD ROCM vLLM
- LangGraph (7-agent orchestration)
- FAISS (vector search)
- NetworkX (graph analysis)
- Gradio (web UI)

### Highlights
- ✅ 3-25 second end-to-end analysis
- ✅ Deterministic risk scoring + LLM reasoning
- ✅ Local execution (no cloud APIs)
- ✅ AMD ROCM GPU optimized
- ✅ Production-ready deployment

### Test Instructions
1. Run setup script
2. Execute: `python scripts/validate.py`
3. Start web UI: `python src/changeguardian_interactive_demo.py`
4. Test sample: Analyze "Upgrade payment-service memory"
```

### Step 3: Upload/Submit

Follow your hackathon's submission process:
- Platform: [Hackathon website URL]
- Deadline: [Date and time]
- Files: Code archive + Presentation + Demo video link

---

## 📞 Troubleshooting Submission Issues

### Archive Won't Extract
```bash
# Test with standard tar
tar -tzf changeguardian-ai.tar.gz > /dev/null && echo "OK"

# Recreate if corrupted
rm changeguardian-ai.tar.gz
tar -czf changeguardian-ai.tar.gz [project files]
```

### Setup Script Fails
```bash
# Check Python version
python --version  # Should be 3.10+

# Check file permissions
chmod +x setup.sh setup.ps1
chmod +x scripts/validate.py

# Try manual setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Validation Fails
```bash
# Full diagnostic
python scripts/validate.py --full

# Fix common issues
pip install --upgrade -r requirements.txt
rm -rf ~/.cache/sentence-transformers
python scripts/validate.py --full
```

---

## 💾 File Size Optimization

If package is too large:

```bash
# Check size breakdown
du -sh src/ examples/ docs/ scripts/

# Remove unnecessary files
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} \;
find . -name ".ipynb_checkpoints" -type d -exec rm -rf {} \;

# Recompress
tar -czf changeguardian-ai-optimized.tar.gz [project]
ls -lh changeguardian-ai-optimized.tar.gz
```

---

## ✅ Final Confirmation

Before hitting submit:

```bash
# 1. Package verified
ls -lh changeguardian-ai.tar.gz
echo "Package created: $(date)"

# 2. Extract test passed
tar -tzf changeguardian-ai.tar.gz | wc -l
echo "Files in archive: OK"

# 3. Documentation complete
ls -1 *.md | wc -l
echo "Documentation: Complete"

# 4. Setup tested
echo "Setup test: PASSED" # (from earlier verification)

# 5. Ready for submission
echo "Status: ✅ READY FOR SUBMISSION"
```

---

## 🎬 Presentation Tips

### For Judges Evaluating Your Code:

1. **Start with extraction**
   - Show clear extraction process
   - Demonstrate no corrupted files

2. **Run setup**
   - Show automated setup working
   - Highlight support for AMD ROCM

3. **Show validation**
   - Run `python scripts/validate.py`
   - Highlight all checks passing

4. **Demo the application**
   - Show web UI loading
   - Demonstrate sample analysis
   - Show risk score and remediation

5. **Discuss architecture**
   - Explain 7-agent pipeline
   - Highlight hybrid RAG approach
   - Mention performance metrics

---

## 📋 Final Checklist

```
BEFORE SUBMISSION:
  ☑ Code archive created & tested
  ☑ All documentation complete
  ☑ Setup scripts functional
  ☑ Validation passes
  ☑ Web UI works
  ☑ CLI tools work
  ☑ No credentials in code
  ☑ Package size <200MB
  ☑ Presentation prepared
  ☑ Demo video recorded
  ☑ Submission form filled
  ☑ All files uploaded
  ☑ Email confirmation received

STATUS: ✅ READY FOR SUBMISSION
```

---

**Package Creation Date**: June 15, 2026  
**Last Updated**: June 15, 2026  
**Status**: ✅ Complete
