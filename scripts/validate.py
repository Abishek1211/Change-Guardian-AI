#!/usr/bin/env python3
"""
ChangeGuardian AI - Setup Validation Script

Verifies that all dependencies are installed and the environment is properly configured.
Run this after setup.sh or setup.ps1 to ensure everything is working correctly.

Usage:
  python scripts/validate.py
  python scripts/validate.py --full    # Extended checks including LLM
"""

import sys
import os
import argparse
from pathlib import Path

# Color output
class Color:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def success(msg): print(f"{Color.GREEN}[OK] {msg}{Color.RESET}")
def error(msg): print(f"{Color.RED}[FAIL] {msg}{Color.RESET}")
def warning(msg): print(f"{Color.YELLOW}[WARN] {msg}{Color.RESET}")
def info(msg): print(f"{Color.CYAN}[INFO] {msg}{Color.RESET}")

def check_python():
    """Check Python version."""
    print(f"\n{Color.BOLD}[PYTHON] Configuration{Color.RESET}")

    version_info = sys.version_info
    version_str = f"{version_info.major}.{version_info.minor}.{version_info.micro}"

    if version_info >= (3, 10):
        success(f"Python {version_str}")
        return True
    else:
        error(f"Python {version_str} (need 3.10+)")
        return False

def check_package(package_name, display_name=None):
    """Check if a package is installed."""
    display_name = display_name or package_name
    try:
        mod = __import__(package_name)
        version = getattr(mod, '__version__', 'unknown')
        success(f"{display_name:30s} {version}")
        return True
    except ImportError:
        error(f"{display_name:30s} NOT INSTALLED")
        return False

def check_core_packages():
    """Check all core dependencies."""
    print(f"\n{Color.BOLD}[DEPS] Core Dependencies{Color.RESET}")

    packages = [
        ('langgraph', 'LangGraph'),
        ('networkx', 'NetworkX'),
        ('numpy', 'NumPy'),
        ('scipy', 'SciPy'),
        ('faiss', 'FAISS'),
        ('sentence_transformers', 'Sentence Transformers'),
        ('gradio', 'Gradio'),
        ('psutil', 'psutil'),
        ('requests', 'Requests'),
        ('pydantic', 'Pydantic'),
    ]

    results = []
    for pkg, display in packages:
        results.append(check_package(pkg, display))

    return all(results)

def check_pytorch():
    """Check PyTorch installation and ROCM support."""
    print(f"\n{Color.BOLD}[TORCH] PyTorch & GPU Support{Color.RESET}")

    try:
        import torch
        success(f"PyTorch {torch.__version__}")

        # Check CUDA (for NVIDIA) or ROCM (for AMD)
        try:
            if torch.cuda.is_available():
                device_count = torch.cuda.device_count()
                device_name = torch.cuda.get_device_name(0)
                success(f"CUDA/ROCM available ({device_count} device(s): {device_name})")
                return True
            else:
                warning("CUDA/ROCM not detected (CPU fallback will be used)")
                return True
        except Exception as e:
            warning(f"GPU check failed: {e} (CPU fallback will be used)")
            return True

    except ImportError:
        error("PyTorch NOT INSTALLED")
        return False

def check_vllm():
    """Check vLLM installation."""
    print(f"\n{Color.BOLD}[VLLM] vLLM (Optional){Color.RESET}")

    try:
        import vllm
        success(f"vLLM {vllm.__version__}")
        return True
    except ImportError:
        warning("vLLM not installed (Ollama fallback will be used)")
        return True

def check_file_structure():
    """Check that project files are in the right place."""
    print(f"\n{Color.BOLD}[FILES] File Structure{Color.RESET}")

    required_files = {
        'src/changeguardian_enhanced.py': 'Core module',
        'src/changeguardian_interactive_demo.py': 'Web UI',
        'requirements.txt': 'Dependencies',
        'README_ROCM_VLLM.md': 'Documentation',
    }

    project_root = Path(__file__).parent.parent
    results = []

    for file_path, description in required_files.items():
        full_path = project_root / file_path
        if full_path.exists():
            success(f"{description:30s} ({file_path})")
            results.append(True)
        else:
            error(f"{description:30s} NOT FOUND ({file_path})")
            results.append(False)

    return all(results)

def check_embedding_model():
    """Check if embedding model is cached."""
    print(f"\n{Color.BOLD}[MODEL] Embedding Model{Color.RESET}")

    try:
        import os
        cache_dir = os.path.expanduser("~/.cache/sentence-transformers")
        model_name = "all-MiniLM-L6-v2"

        if os.path.exists(cache_dir):
            info(f"Cache directory: {cache_dir}")
            if os.listdir(cache_dir):
                success("Embedding model cached (will be used on first run)")
                return True
            else:
                warning("Cache directory empty (model will be downloaded on first run)")
                return True
        else:
            warning("Cache not initialized (model will be downloaded on first run)")
            return True
    except Exception as e:
        warning(f"Could not check cache: {e}")
        return True

def check_llm_connectivity():
    """Check if Ollama is running."""
    print(f"\n{Color.BOLD}[LLM] LLM Service{Color.RESET}")

    try:
        import requests
        response = requests.get("http://localhost:11434", timeout=3)
        if response.status_code == 200:
            success("Ollama is running on localhost:11434")
            return True
    except Exception:
        pass

    warning("Ollama not detected on localhost:11434 (can be started later)")
    return True

def check_vllm_connectivity():
    """Check if vLLM is running."""
    try:
        import requests
        response = requests.get("http://localhost:8000/v1/models", timeout=3)
        if response.status_code == 200:
            success("vLLM is running on localhost:8000")
            return True
    except Exception:
        pass

    return False

def run_import_test():
    """Test importing the main module."""
    print(f"\n{Color.BOLD}[TEST] Import Test{Color.RESET}")

    try:
        # Add project to path
        project_root = Path(__file__).parent.parent
        sys.path.insert(0, str(project_root))

        from src.changeguardian_enhanced import (
            workflow,
            LLMConfig,
            search_incidents,
            get_affected_services,
        )

        success("Core module imports successful")
        success(f"LLMConfig available ({len(LLMConfig.MODELS)} models)")
        info("Sample models: " + ", ".join(list(LLMConfig.MODELS.keys())[:3]))
        return True

    except ImportError as e:
        error(f"Import failed: {e}")
        return False
    except Exception as e:
        error(f"Unexpected error: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(
        description='Validate ChangeGuardian AI setup',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/validate.py              # Quick check
  python scripts/validate.py --full       # Extended checks
  python scripts/validate.py --rocm       # Check ROCM specifically
        """
    )
    parser.add_argument('--full', action='store_true', help='Run extended checks')
    parser.add_argument('--rocm', action='store_true', help='Check ROCM support')

    args = parser.parse_args()

    print(f"{Color.BOLD}{Color.CYAN}")
    print("=" * 70)
    print("  ChangeGuardian AI - Setup Validation")
    print("=" * 70)
    print(f"{Color.RESET}")

    checks = []

    # Basic checks
    checks.append(("Python", check_python()))
    checks.append(("Core Dependencies", check_core_packages()))
    checks.append(("PyTorch", check_pytorch()))
    checks.append(("File Structure", check_file_structure()))

    # Extended checks
    if args.full or args.rocm:
        checks.append(("vLLM", check_vllm()))
        checks.append(("Embedding Model", check_embedding_model()))

    # LLM connectivity checks
    if args.full:
        checks.append(("Ollama Connectivity", check_llm_connectivity()))
        vllm_ok = check_vllm_connectivity()
        if vllm_ok:
            checks.append(("vLLM Connectivity", vllm_ok))

    # Import test
    checks.append(("Import Test", run_import_test()))

    # Summary
    print(f"\n{Color.BOLD}{Color.CYAN}")
    print("=" * 70)
    print("  Validation Summary")
    print("=" * 70)
    print(f"{Color.RESET}")

    passed = sum(1 for _, result in checks if result)
    total = len(checks)

    for name, result in checks:
        status = f"{Color.GREEN}PASS{Color.RESET}" if result else f"{Color.RED}FAIL{Color.RESET}"
        print(f"  {name:30s} {status}")

    print(f"\n  Result: {passed}/{total} checks passed")

    if passed == total:
        success("All checks passed!")
        print(f"\n{Color.BOLD}Next steps:{Color.RESET}")
        print("  1. python src/changeguardian_interactive_demo.py")
        print("  2. Open http://localhost:7860 in browser")
        return 0
    else:
        failed = total - passed
        error(f"{failed} check(s) failed")
        print(f"\n{Color.BOLD}Fix these issues then run validation again:{Color.RESET}")
        print("  pip install -r requirements.txt --upgrade")
        print("  python scripts/validate.py")
        return 1

if __name__ == "__main__":
    sys.exit(main())
