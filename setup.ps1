# ChangeGuardian AI - AMD ROCM vLLM Setup Script (Windows)
# Usage: .\setup.ps1 -SetupType rocm
#        .\setup.ps1 -SetupType cpu
# Example: .\setup.ps1 -SetupType rocm   # For AMD GPU with ROCM
#          .\setup.ps1 -SetupType cpu    # For CPU-only inference

param(
    [ValidateSet('cpu', 'rocm')]
    [string]$SetupType = 'cpu'
)

# Color output
function Write-Success { Write-Host $args -ForegroundColor Green }
function Write-Warning { Write-Host $args -ForegroundColor Yellow }
function Write-Error-Custom { Write-Host $args -ForegroundColor Red }

Write-Host "═════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  ChangeGuardian AI - AMD ROCM vLLM Setup (Windows)" -ForegroundColor Cyan
Write-Host "═════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "Setup Type : $SetupType"

# Check Python
$pythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pythonPath) {
    Write-Error-Custom "❌ ERROR: Python not found. Please install Python 3.10+"
    exit 1
}

$pythonVersion = python --version 2>&1
Write-Host "Python     : $pythonVersion"
Write-Host "═════════════════════════════════════════════════════════════════" -ForegroundColor Cyan

# Create virtual environment
if (-not (Test-Path "venv")) {
    Write-Host "📦 Creating virtual environment..."
    python -m venv venv
    Write-Success "✅ Virtual environment created"
} else {
    Write-Success "✅ Virtual environment already exists"
}

# Activate venv
& ".\venv\Scripts\Activate.ps1"
Write-Success "✅ Virtual environment activated"

# Upgrade pip
Write-Host "📦 Upgrading pip..."
python -m pip install --upgrade pip setuptools wheel -q 2>$null

# Install base requirements
Write-Host "📦 Installing base dependencies..."
pip install -r requirements.txt -q

# Install PyTorch
Write-Host "📦 Installing PyTorch..."
if ($SetupType -eq 'rocm') {
    Write-Host "  → Installing PyTorch with AMD ROCM 5.8 support"
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.8 -q

    Write-Host "  → Installing ONNX Runtime for ROCM (optional)"
    pip install onnxruntime-rocm -q 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "  ⚠️  ONNX Runtime ROCM not available (non-critical)"
    }
} else {
    Write-Host "  → Installing PyTorch CPU-only"
    pip install torch torchvision torchaudio -q
}

# Download embedding model
Write-Host "📦 Downloading sentence-transformers model..."
python << 'PYTHON_SCRIPT'
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
Write-Host ""
Write-Host "📋 Verifying installation..."
python << 'PYTHON_SCRIPT'
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

if not all_ok:
    print("\n⚠️  Some packages are missing. Run: pip install -r requirements.txt")
    sys.exit(1)
PYTHON_SCRIPT

Write-Host ""
Write-Host "═════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Success "  ✅ Setup Complete!"
Write-Host "═════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:"
Write-Host ""
if ($SetupType -eq 'rocm') {
    Write-Host "1. (Optional) Download vLLM-compatible model:"
    Write-Host "   python -m vllm.entrypoints.openai.api_server --model meta-llama/Llama-2-7b-hf --tensor-parallel-size 2"
    Write-Host ""
}

Write-Host "2. Start the application:"
Write-Host "   python src/changeguardian_interactive_demo.py"
Write-Host ""
Write-Host "3. Open browser to:"
Write-Host "   http://localhost:7860"
Write-Host ""
Write-Host "4. Or use CLI:"
Write-Host "   python -c `"from src.changeguardian_enhanced import workflow; result = workflow.invoke({'change_request': 'Upgrade payment-service Spring Boot 2.7 to 3.2'}); print(result)`""
Write-Host ""
Write-Host "5. For Jupyter notebook:"
Write-Host "   jupyter notebook"
Write-Host ""
Write-Host "═════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
