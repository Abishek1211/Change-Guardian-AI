#!/bin/bash
# ChangeGuardian AI - AMD ROCM vLLM Setup Script
# Usage: bash setup.sh [rocm|cpu]
# Example: bash setup.sh rocm     # For AMD GPU with ROCM
#          bash setup.sh cpu      # For CPU-only inference

set -e  # Exit on error

SETUP_TYPE="${1:-cpu}"  # Default to CPU
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)

echo "═══════════════════════════════════════════════════════════════"
echo "  ChangeGuardian AI - AMD ROCM vLLM Setup"
echo "═══════════════════════════════════════════════════════════════"
echo "Setup Type : $SETUP_TYPE"
echo "Python     : $PYTHON_VERSION"
echo "═══════════════════════════════════════════════════════════════"

# Check Python version
if [ "$PYTHON_VERSION" \< "3.10" ]; then
    echo "❌ ERROR: Python 3.10+ required. Found $PYTHON_VERSION"
    exit 1
fi

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
else
    echo "✅ Virtual environment already exists"
fi

# Activate venv
source venv/bin/activate
echo "✅ Virtual environment activated"

# Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip setuptools wheel > /dev/null

# Install base requirements
echo "📦 Installing base dependencies..."
pip install -r requirements.txt -q

# Install PyTorch with ROCM or CPU backend
echo "📦 Installing PyTorch..."
if [ "$SETUP_TYPE" = "rocm" ]; then
    echo "  → Installing PyTorch with AMD ROCM 5.8 support"
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.8 -q

    # Optional: ONNX Runtime with ROCM
    echo "  → Installing ONNX Runtime for ROCM (optional)"
    pip install onnxruntime-rocm -q 2>/dev/null || echo "  ⚠️  ONNX Runtime ROCM not available (non-critical)"

elif [ "$SETUP_TYPE" = "cpu" ]; then
    echo "  → Installing PyTorch CPU-only"
    pip install torch torchvision torchaudio -q
fi

# Download embedding model
echo "📦 Downloading sentence-transformers model..."
python3 << 'PYTHON_SCRIPT'
import os
from sentence_transformers import SentenceTransformer

model_name = "all-MiniLM-L6-v2"
cache_dir = os.path.expanduser("~/.cache/sentence-transformers")
print(f"  → Model cache: {cache_dir}")

try:
    model = SentenceTransformer(model_name)
    print(f"  ✅ Model loaded: {model_name}")
except Exception as e:
    print(f"  ⚠️  Could not download model: {e}")
    print("     Model will be downloaded on first run")
PYTHON_SCRIPT

# Verify installation
echo ""
echo "📋 Verifying installation..."
python3 << 'PYTHON_SCRIPT'
import sys
packages = {
    'langgraph': 'LangGraph',
    'vllm': 'vLLM',
    'networkx': 'NetworkX',
    'faiss': 'FAISS',
    'sentence_transformers': 'Sentence Transformers',
    'gradio': 'Gradio',
    'torch': 'PyTorch'
}

all_ok = True
for pkg, name in packages.items():
    try:
        mod = __import__(pkg)
        version = getattr(mod, '__version__', 'unknown')
        print(f"  ✅ {name:25s} {version}")
    except ImportError:
        print(f"  ❌ {name:25s} NOT INSTALLED")
        all_ok = False

if all_ok:
    print("\n✅ All dependencies installed successfully!")
else:
    print("\n⚠️  Some packages are missing. Run: pip install -r requirements.txt")
    sys.exit(1)
PYTHON_SCRIPT

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  ✅ Setup Complete!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "Next steps:"
echo ""
if [ "$SETUP_TYPE" = "rocm" ]; then
    echo "1. (Optional) Download vLLM-compatible model:"
    echo "   python3 -m vllm.entrypoints.openai.api_server --model meta-llama/Llama-2-7b-hf --tensor-parallel-size 2"
    echo ""
fi

echo "2. Start the application:"
echo "   python3 src/changeguardian_interactive_demo.py"
echo ""
echo "3. Open browser to:"
echo "   http://localhost:7860"
echo ""
echo "4. Or use CLI:"
echo "   python3 -c \"from src.changeguardian_enhanced import workflow; result = workflow.invoke({'change_request': 'Upgrade payment-service Spring Boot 2.7 to 3.2'}); print(result)\""
echo ""
echo "5. For Jupyter notebook:"
echo "   jupyter notebook"
echo ""
echo "═══════════════════════════════════════════════════════════════"
