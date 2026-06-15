# AMD ROCM Installation Guide - Quick Fix

> If you're getting NVIDIA CUDA dependencies instead of AMD ROCM, follow this guide.

---

## ⚠️ The Problem

When you run `pip install -r requirements.txt`, Python defaults to installing **NVIDIA CUDA** PyTorch, not AMD ROCM.

This is because:
- PyTorch CUDA is the default build
- AMD ROCM requires a special PyPI index URL

---

## ✅ The Solution

### Step 1: Install Base Dependencies (Without PyTorch)

```bash
pip install langgraph networkx faiss-cpu sentence-transformers gradio psutil requests pydantic pyyaml python-dotenv
```

### Step 2: Install PyTorch with AMD ROCM Support

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.8
```

### Step 3: (Optional) Install vLLM for AMD ROCM

```bash
pip install vllm[rocm]
```

---

## 🚀 Complete Installation (One Command)

```bash
pip install langgraph networkx faiss-cpu sentence-transformers gradio psutil requests pydantic pyyaml python-dotenv && \
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.8
```

---

## 🧪 Verify Installation

```bash
python scripts/validate.py --full
```

Expected output:
```
✅ Python 3.10+
✅ LangGraph
✅ NetworkX
✅ FAISS
✅ Sentence Transformers
✅ Gradio
✅ PyTorch (ROCM version)
✅ All checks passed!
```

---

## 🆘 If CUDA Dependencies Are Still Being Downloaded

### Option 1: Uninstall and Reinstall

```bash
# Remove CUDA PyTorch
pip uninstall torch torchvision torchaudio -y

# Install ROCM PyTorch
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.8
```

### Option 2: Clear Pip Cache and Reinstall

```bash
pip cache purge
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.8 --no-cache-dir
```

### Option 3: Create Fresh Virtual Environment

```bash
# Remove old environment
rm -rf venv

# Create new one
python -m venv venv
source venv/bin/activate

# Install correctly (AMD ROCM version first)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.8
pip install -r requirements.txt
```

---

## 📋 Key Points

| Scenario | Command | Notes |
|----------|---------|-------|
| AMD ROCM GPU | `--index-url https://download.pytorch.org/whl/rocm5.8` | ✅ Use this |
| NVIDIA CUDA | `--index-url https://download.pytorch.org/whl/cu118` | ❌ Not for you |
| CPU-only | Default (no URL) | For development only |

---

## 🔍 Check What's Installed

```bash
python -c "import torch; print(torch.version.cuda if torch.cuda.is_available() else 'CPU-only')"
```

Expected output for AMD ROCM:
```
False  (ROCM doesn't use CUDA)
```

To specifically check ROCM:
```bash
python -c "import torch; print('ROCM' if 'rocm' in torch.__version__ else 'Unknown PyTorch')"
```

Expected:
```
ROCM
```

---

## 📦 PyTorch ROCM File Size

- Download: ~2GB
- Installed: ~2.5GB
- This is normal and expected

---

## 🎯 Next Steps

After installation:

```bash
# 1. Verify
python scripts/validate.py --full

# 2. Run the application
python src/changeguardian_interactive_demo.py

# 3. Open browser
# http://localhost:7860
```

---

## 💡 Pro Tips

### For Faster Downloads
```bash
pip install --upgrade pip  # Newer pip is faster
pip install -r requirements.txt --upgrade
```

### To Skip Optional Packages
```bash
# Install only essentials (skip vllm, onnxruntime)
pip install langgraph networkx faiss-cpu sentence-transformers gradio
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.8
```

### To Use Older ROCM Version
```bash
# ROCM 5.6
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.6

# ROCM 5.7
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.7
```

---

## ✅ You're All Set!

Once validation passes, you have:
- ✅ AMD ROCM PyTorch (not CUDA)
- ✅ All required dependencies
- ✅ Ready to run ChangeGuardian AI

Next: `python src/changeguardian_interactive_demo.py`

---

**Last Updated**: June 15, 2026  
**Status**: ✅ AMD ROCM Specific Guide
