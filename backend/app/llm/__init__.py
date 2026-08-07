"""LLM access layer: one OpenAI-compatible client behind a circuit breaker."""

from .breaker import BreakerState, CircuitBreaker
from .client import LLMClient, LLMResult, get_client, reset_client
from .config import LLMConfig, load_config

__all__ = [
    "BreakerState",
    "CircuitBreaker",
    "LLMClient",
    "LLMConfig",
    "LLMResult",
    "get_client",
    "load_config",
    "reset_client",
]
