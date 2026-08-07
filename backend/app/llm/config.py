"""Environment-driven LLM configuration.

One code path serves three deployments:

    Groq (hosted demo)   LLM_BASE_URL=https://api.groq.com/openai/v1
                         LLM_MODEL=llama-3.1-8b-instant
    Gemini (alternative) LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
                         LLM_MODEL=gemini-2.0-flash-lite
    Ollama (fully local) LLM_BASE_URL=http://localhost:11434/v1
                         LLM_MODEL=qwen2.5:3b

All three speak the OpenAI chat-completions protocol, so the only thing that
changes between them is environment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "llama-3.1-8b-instant"

# Ollama accepts any non-empty bearer token. Sending this rather than an empty
# string keeps the local path working without special-casing it in the client.
PLACEHOLDER_API_KEY = "not-needed"


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    return int(_env_float(name, default))


@dataclass(frozen=True)
class LLMConfig:
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    api_key: str = PLACEHOLDER_API_KEY
    timeout_seconds: float = 20.0
    max_tokens: int = 700
    temperature: float = 0.2

    # Circuit breaker tuning.
    failure_threshold: int = 3
    cooldown_seconds: float = 60.0
    max_cooldown_seconds: float = 600.0

    @property
    def is_local(self) -> bool:
        return any(h in self.base_url for h in ("localhost", "127.0.0.1", "host.docker.internal"))

    @property
    def requires_key(self) -> bool:
        """Hosted providers reject unauthenticated calls; Ollama does not care."""
        return not self.is_local

    @property
    def has_key(self) -> bool:
        return bool(self.api_key) and self.api_key != PLACEHOLDER_API_KEY

    @property
    def enabled(self) -> bool:
        """False means: do not even attempt a call, go straight to rule-based text.

        This is the "someone cloned the repo and ran it without a key" path. It
        is a normal, supported way to run ChangeGuardian, not an error.
        """
        if not self.base_url or not self.model:
            return False
        return self.has_key or not self.requires_key

    def describe(self) -> str:
        if not self.enabled:
            return "disabled (no LLM_API_KEY set - rule-based explanations only)"
        host = self.base_url.split("//", 1)[-1].split("/", 1)[0]
        return f"{self.model} @ {host}"


def load_config() -> LLMConfig:
    return LLMConfig(
        base_url=os.getenv("LLM_BASE_URL", DEFAULT_BASE_URL).strip().rstrip("/"),
        model=os.getenv("LLM_MODEL", DEFAULT_MODEL).strip(),
        api_key=os.getenv("LLM_API_KEY", PLACEHOLDER_API_KEY).strip() or PLACEHOLDER_API_KEY,
        timeout_seconds=_env_float("LLM_TIMEOUT_SECONDS", 20.0),
        max_tokens=_env_int("LLM_MAX_TOKENS", 700),
        temperature=_env_float("LLM_TEMPERATURE", 0.2),
        failure_threshold=_env_int("LLM_FAILURE_THRESHOLD", 3),
        cooldown_seconds=_env_float("LLM_COOLDOWN_SECONDS", 60.0),
        max_cooldown_seconds=_env_float("LLM_MAX_COOLDOWN_SECONDS", 600.0),
    )
