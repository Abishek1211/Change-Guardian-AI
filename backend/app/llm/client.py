"""OpenAI-compatible LLM client with a circuit breaker.

Agent 7 (LLM Explanation) is the only part of ChangeGuardian that talks to a
model. Agents 1-6 are fully deterministic, so a model outage degrades the
report's prose - not its risk score, blast radius, or rule violations.

This client therefore never raises. It returns an `LLMResult` whose `ok` flag
tells the caller whether to use `text` or fall back to the rule-based
explanation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .breaker import CircuitBreaker
from .config import LLMConfig, load_config


@dataclass
class LLMResult:
    ok: bool
    text: str = ""
    elapsed_ms: int = 0
    model: str = ""
    error: str | None = None
    # Why the call did not happen / did not succeed. One of:
    # "disabled" | "circuit_open" | "timeout" | "rate_limited" | "auth" | "error"
    reason: str | None = None
    usage: dict[str, int] = field(default_factory=dict)

    @property
    def used_fallback(self) -> bool:
        return not self.ok


# Exception name -> (reason, permanent). Matching on names rather than importing
# the exception classes keeps this module importable when `openai` is absent,
# which is the case for anyone running the deterministic pipeline offline.
_ERROR_MAP: dict[str, tuple[str, bool]] = {
    "APITimeoutError": ("timeout", False),
    "APIConnectionError": ("connection", False),
    "RateLimitError": ("rate_limited", False),
    "InternalServerError": ("error", False),
    "AuthenticationError": ("auth", True),
    "PermissionDeniedError": ("auth", True),
    "NotFoundError": ("bad_model", True),
    "BadRequestError": ("bad_request", True),
}


def _classify(exc: Exception) -> tuple[str, bool]:
    name = type(exc).__name__
    if name in _ERROR_MAP:
        return _ERROR_MAP[name]

    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        if status == 429:
            return "rate_limited", False
        if status in (401, 403):
            return "auth", True
        if status == 404:
            return "bad_model", True
        if 400 <= status < 500:
            return "bad_request", True
        return "error", False

    if isinstance(exc, TimeoutError):
        return "timeout", False
    return "error", False


class LLMClient:
    """Wraps one OpenAI-compatible endpoint. Safe to share across requests."""

    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or load_config()
        self.breaker = CircuitBreaker(
            failure_threshold=self.config.failure_threshold,
            cooldown_seconds=self.config.cooldown_seconds,
            max_cooldown_seconds=self.config.max_cooldown_seconds,
        )
        self._sync_client: Any = None
        self._async_client: Any = None
        self._import_error: str | None = None

    # ---------------------------------------------------------------- clients

    def _kwargs(self) -> dict:
        return {
            "base_url": self.config.base_url,
            "api_key": self.config.api_key,
            "timeout": self.config.timeout_seconds,
            # The breaker handles retries; the SDK's own retries would multiply
            # the wall-clock cost of an outage by 3.
            "max_retries": 0,
        }

    def _get_sync(self) -> Any:
        if self._sync_client is None:
            from openai import OpenAI  # imported lazily - optional dependency

            self._sync_client = OpenAI(**self._kwargs())
        return self._sync_client

    def _get_async(self) -> Any:
        if self._async_client is None:
            from openai import AsyncOpenAI

            self._async_client = AsyncOpenAI(**self._kwargs())
        return self._async_client

    # ------------------------------------------------------------- preflight

    def _payload(self, prompt: str, system: str, json_mode: bool) -> dict:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if json_mode:
            # Supported by Groq, Gemini's OpenAI shim, and recent Ollama. If a
            # provider rejects it we retry once without it (see _complete).
            payload["response_format"] = {"type": "json_object"}
        return payload

    def _precheck(self) -> LLMResult | None:
        """Returns a short-circuit result, or None to proceed with the call."""
        if not self.config.enabled:
            return LLMResult(ok=False, reason="disabled", model=self.config.model,
                             error="LLM not configured")
        if self._import_error:
            return LLMResult(ok=False, reason="disabled", model=self.config.model,
                             error=self._import_error)
        if not self.breaker.allow():
            snap = self.breaker.snapshot()
            return LLMResult(
                ok=False, reason="circuit_open", model=self.config.model,
                error=f"circuit open, retrying in {snap['retry_in_seconds']}s",
            )
        return None

    @staticmethod
    def _extract(response: Any, started: float, model: str) -> LLMResult:
        text = (response.choices[0].message.content or "").strip()
        usage = {}
        if getattr(response, "usage", None):
            usage = {
                "prompt_tokens": response.usage.prompt_tokens or 0,
                "completion_tokens": response.usage.completion_tokens or 0,
            }
        return LLMResult(
            ok=bool(text),
            text=text,
            elapsed_ms=int((time.monotonic() - started) * 1000),
            model=model,
            usage=usage,
            reason=None if text else "empty_response",
        )

    def _handle_import_failure(self, exc: ImportError) -> LLMResult:
        self._import_error = (
            f"the 'openai' package is not installed ({exc}); "
            "run 'pip install openai' to enable LLM explanations"
        )
        # Not the provider's fault - do not let it trip the breaker.
        self.breaker.record_success()
        return LLMResult(ok=False, reason="disabled", model=self.config.model,
                         error=self._import_error)

    def _settle(self, result: LLMResult) -> LLMResult:
        """Report a completed call to the breaker. An empty completion counts as
        a failure - it is useless to agent 7 either way."""
        if result.ok:
            self.breaker.record_success()
        else:
            self.breaker.record_failure("empty response")
        return result

    def _handle_failure(self, exc: Exception, started: float) -> LLMResult:
        reason, permanent = _classify(exc)
        message = f"{type(exc).__name__}: {exc}"
        self.breaker.record_failure(message, permanent=permanent)
        return LLMResult(
            ok=False,
            elapsed_ms=int((time.monotonic() - started) * 1000),
            model=self.config.model,
            error=message,
            reason=reason,
        )

    # ------------------------------------------------------------ public API

    def complete(self, prompt: str, system: str = "", *, json_mode: bool = False) -> LLMResult:
        short_circuit = self._precheck()
        if short_circuit is not None:
            return short_circuit

        started = time.monotonic()
        try:
            client = self._get_sync()
        except ImportError as exc:
            return self._handle_import_failure(exc)

        payload = self._payload(prompt, system, json_mode)
        try:
            response = client.chat.completions.create(**payload)
        except Exception as exc:  # noqa: BLE001 - deliberately total
            if json_mode and _is_json_mode_rejection(exc):
                return self._retry_without_json_mode_sync(client, prompt, system, started)
            return self._handle_failure(exc, started)

        return self._settle(result=self._extract(response, started, self.config.model))

    async def acomplete(self, prompt: str, system: str = "", *, json_mode: bool = False) -> LLMResult:
        short_circuit = self._precheck()
        if short_circuit is not None:
            return short_circuit

        started = time.monotonic()
        try:
            client = self._get_async()
        except ImportError as exc:
            return self._handle_import_failure(exc)

        payload = self._payload(prompt, system, json_mode)
        try:
            response = await client.chat.completions.create(**payload)
        except Exception as exc:  # noqa: BLE001
            if json_mode and _is_json_mode_rejection(exc):
                payload.pop("response_format", None)
                try:
                    response = await client.chat.completions.create(**payload)
                except Exception as retry_exc:  # noqa: BLE001
                    return self._handle_failure(retry_exc, started)
            else:
                return self._handle_failure(exc, started)

        return self._settle(result=self._extract(response, started, self.config.model))

    def _retry_without_json_mode_sync(
        self, client: Any, prompt: str, system: str, started: float
    ) -> LLMResult:
        payload = self._payload(prompt, system, json_mode=False)
        try:
            response = client.chat.completions.create(**payload)
        except Exception as exc:  # noqa: BLE001
            return self._handle_failure(exc, started)
        return self._settle(result=self._extract(response, started, self.config.model))

    def status(self) -> dict:
        return {
            "provider": self.config.describe(),
            "model": self.config.model,
            "enabled": self.config.enabled,
            "breaker": self.breaker.snapshot(),
        }


def _is_json_mode_rejection(exc: Exception) -> bool:
    """Some OpenAI-compatible endpoints 400 on `response_format`. Worth one
    retry without it before declaring the provider unhealthy."""
    if type(exc).__name__ != "BadRequestError":
        return False
    return "response_format" in str(exc).lower()


# A process-wide default, mirroring how the notebook used a single module-level
# `call_llm`. Tests and the FastAPI app can construct their own instances.
_default_client: LLMClient | None = None


def get_client() -> LLMClient:
    global _default_client
    if _default_client is None:
        _default_client = LLMClient()
    return _default_client


def reset_client() -> None:
    """Drop the cached client so a later get_client() re-reads the environment."""
    global _default_client
    _default_client = None
