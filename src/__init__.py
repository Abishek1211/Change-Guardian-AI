"""
ChangeGuardian AI - Production Deployment Risk Analysis Platform

A comprehensive system for analyzing deployment risks using:
- LangGraph orchestration (7-agent pipeline)
- Vector RAG (FAISS) for similarity search
- Vectorless RAG (rule engine) for constraint checking
- Local LLMs (Ollama/vLLM) for reasoning
- NetworkX graphs for service dependency analysis

Optimized for AMD ROCM and CPU environments.
"""

__version__ = "2.0.0"
__author__ = "ChangeGuardian Team"
__description__ = "Production Deployment Risk Analysis Platform"

# Core imports for easy access
try:
    from .changeguardian_enhanced import (
        workflow,
        LLMConfig,
        search_incidents,
        get_affected_services,
        check_compatibility_rules,
    )
    __all__ = [
        'workflow',
        'LLMConfig',
        'search_incidents',
        'get_affected_services',
        'check_compatibility_rules',
    ]
except ImportError as e:
    print(f"Warning: Could not import core modules: {e}")
    __all__ = []
