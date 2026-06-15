# ChangeGuardian AI - Setup Script (Windows)
param([ValidateSet('cpu', 'rocm')][string]$SetupType = 'cpu')

function Write-Success { Write-Host $args -ForegroundColor Green }
function Write-Warning { Write-Host $args -ForegroundColor Yellow }

Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "  ChangeGuardian AI Setup" -ForegroundColor Cyan
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "Setup Type : $SetupType"

# Check Python
$pythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pythonPath) {
    Write-Host "ERROR: Python not found. Please install Python 3.10+" -ForegroundColor Red
    exit 1
}

$pythonVersion = python --version 2>&1
Write-Host "Python     : $pythonVersion"
Write-Host "=====================================================================" -ForegroundColor Cyan

# Create virtual environment
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv venv
    Write-Success "Virtual environment created"
} else {
    Write-Success "Virtual environment already exists"
}

# Activate venv
& ".\venv\Scripts\Activate.ps1"
Write-Success "Virtual environment activated"

# Upgrade pip
Write-Host "Upgrading pip..."
python -m pip install --upgrade pip setuptools wheel -q 2>$null

# Install base requirements
Write-Host "Installing base dependencies..."
pip install -r requirements.txt -q

# Install PyTorch
Write-Host "Installing PyTorch..."
if ($SetupType -eq 'rocm') {
    Write-Host "  Installing PyTorch with AMD ROCM 5.8 support"
    Write-Host "  (This may take 2-5 minutes, ~2GB download)"
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.8 -q
    Write-Success "  PyTorch ROCM installed"
    Write-Host "  Installing ONNX Runtime for ROCM (optional)"
    pip install onnxruntime-rocm -q 2>$null
} else {
    Write-Host "  Installing PyTorch CPU-only"
    Write-Host "  (This may take 2-5 minutes, ~1GB download)"
    pip install torch torchvision torchaudio -q
    Write-Success "  PyTorch CPU installed"
}

# Download embedding model
Write-Host "Downloading sentence-transformers model..."
python -c "from sentence_transformers import SentenceTransformer; model = SentenceTransformer('all-MiniLM-L6-v2'); print('  Model loaded successfully')" 2>$null

# Verify installation
Write-Host ""
Write-Host "Verifying installation..."

$verifyScript = @"
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
        print(f'  OK {name:25s} {version}')
    except ImportError:
        print(f'  FAIL {name:25s} NOT INSTALLED')
        all_ok = False

if not all_ok:
    print('\nWARNING: Some packages are missing. Run: pip install -r requirements.txt')
    sys.exit(1)
"@

python -c $verifyScript

Write-Host ""
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Success "Setup Complete!"
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:"
Write-Host ""
Write-Host "1. Start the application:"
Write-Host "   python src/changeguardian_interactive_demo.py"
Write-Host ""
Write-Host "2. Open browser to:"
Write-Host "   http://localhost:7860"
Write-Host ""
Write-Host "3. Or validate setup:"
Write-Host "   python scripts/validate.py --full"
Write-Host ""
