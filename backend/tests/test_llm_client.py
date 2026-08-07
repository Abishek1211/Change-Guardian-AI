"""Tests for the LLM client and its circuit breaker.

Runs offline - no provider, no API key, no `openai` package required. The
transport is faked by assigning to `client._sync_client`, which is exactly the
seam the lazy import creates.

    python backend/tests/test_llm_client.py      (or: pytest backend/tests)
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.llm.breaker import BreakerState, CircuitBreaker  # noqa: E402
from app.llm.client import LLMClient, _classify  # noqa: E402
from app.llm.config import LLMConfig, load_config  # noqa: E402


# --------------------------------------------------------------------- fakes

class APITimeoutError(Exception):
    """Mimics openai.APITimeoutError by name - that is what _classify keys on."""


class RateLimitError(Exception):
    pass


class AuthenticationError(Exception):
    pass


class BadRequestError(Exception):
    pass


class _Message:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Message(content)


class _Usage:
    prompt_tokens = 120
    completion_tokens = 80


class _Response:
    def __init__(self, content):
        self.choices = [_Choice(content)]
        self.usage = _Usage()


class FakeTransport:
    """Stands in for `openai.OpenAI`. Replays a scripted list of outcomes."""

    def __init__(self, outcomes):
        self._outcomes = list(outcomes)
        self.calls: list[dict] = []
        self.chat = self  # so `client.chat.completions.create(...)` resolves
        self.completions = self

    def create(self, **payload):
        self.calls.append(payload)
        outcome = self._outcomes.pop(0) if self._outcomes else self._outcomes
        if isinstance(outcome, Exception):
            raise outcome
        return _Response(outcome)


def make_client(outcomes, **overrides) -> tuple[LLMClient, FakeTransport]:
    config = LLMConfig(
        base_url="https://api.groq.com/openai/v1",
        model="llama-3.1-8b-instant",
        api_key="test-key",
        timeout_seconds=5.0,
        **overrides,
    )
    client = LLMClient(config)
    transport = FakeTransport(outcomes)
    client._sync_client = transport
    return client, transport


# -------------------------------------------------------------------- config

def test_hosted_provider_without_key_is_disabled():
    config = LLMConfig(base_url="https://api.groq.com/openai/v1")
    assert not config.has_key
    assert config.requires_key
    assert not config.enabled, "hosted provider with no key must not be attempted"


def test_local_ollama_needs_no_key():
    config = LLMConfig(base_url="http://localhost:11434/v1", model="qwen2.5:3b")
    assert config.is_local
    assert config.enabled, "Ollama accepts any token - local mode must stay usable"


def test_config_reads_environment():
    os.environ["LLM_MODEL"] = "gemini-2.0-flash-lite"
    os.environ["LLM_TIMEOUT_SECONDS"] = "9.5"
    os.environ["LLM_API_KEY"] = "abc123"
    try:
        config = load_config()
        assert config.model == "gemini-2.0-flash-lite"
        assert config.timeout_seconds == 9.5
        assert config.enabled
    finally:
        for key in ("LLM_MODEL", "LLM_TIMEOUT_SECONDS", "LLM_API_KEY"):
            os.environ.pop(key, None)


def test_malformed_numeric_env_falls_back_to_default():
    os.environ["LLM_TIMEOUT_SECONDS"] = "twenty"
    try:
        assert load_config().timeout_seconds == 20.0
    finally:
        os.environ.pop("LLM_TIMEOUT_SECONDS", None)


# ------------------------------------------------------------------- breaker

def test_breaker_opens_after_threshold():
    breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=60)
    for _ in range(2):
        assert breaker.allow()
        breaker.record_failure("boom")
    assert breaker.state is BreakerState.CLOSED, "must tolerate failures below threshold"

    assert breaker.allow()
    breaker.record_failure("boom")
    assert breaker.state is BreakerState.OPEN
    assert not breaker.allow(), "open breaker must short-circuit"


def test_breaker_half_opens_after_cooldown_then_closes_on_success():
    breaker = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.05)
    breaker.allow()
    breaker.record_failure("boom")
    assert breaker.state is BreakerState.OPEN

    time.sleep(0.06)
    assert breaker.state is BreakerState.HALF_OPEN
    assert breaker.allow(), "half-open must admit one probe"
    assert not breaker.allow(), "and only one"

    breaker.record_success()
    assert breaker.state is BreakerState.CLOSED
    assert breaker.allow()


def test_cooldown_backs_off_when_probe_fails():
    breaker = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.05, max_cooldown_seconds=10)
    breaker.allow()
    breaker.record_failure("boom")

    time.sleep(0.06)
    assert breaker.allow()
    breaker.record_failure("still down")

    assert breaker.snapshot()["retry_in_seconds"] > 0.05, "failed probe must widen the window"


def test_permanent_error_trips_breaker_immediately():
    breaker = CircuitBreaker(failure_threshold=5, cooldown_seconds=60)
    breaker.allow()
    breaker.record_failure("bad key", permanent=True)
    assert breaker.state is BreakerState.OPEN, "a bad key will not fix itself in 4 more calls"


# ------------------------------------------------------ error classification

def test_error_classification():
    assert _classify(APITimeoutError("slow")) == ("timeout", False)
    assert _classify(RateLimitError("429")) == ("rate_limited", False)
    assert _classify(AuthenticationError("401")) == ("auth", True)

    unknown = Exception("something")
    unknown.status_code = 503
    assert _classify(unknown) == ("error", False)


# -------------------------------------------------------------------- client

def test_successful_completion():
    client, transport = make_client(['{"explanation": "fine", "remediation": []}'])
    result = client.complete("prompt", "system", json_mode=True)

    assert result.ok
    assert "fine" in result.text
    assert result.usage["completion_tokens"] == 80
    assert transport.calls[0]["response_format"] == {"type": "json_object"}
    assert transport.calls[0]["messages"][0]["role"] == "system"


def test_disabled_client_never_calls_provider():
    client = LLMClient(LLMConfig(base_url="https://api.groq.com/openai/v1", api_key=""))
    transport = FakeTransport(["should not be reached"])
    client._sync_client = transport

    result = client.complete("prompt")
    assert not result.ok
    assert result.reason == "disabled"
    assert transport.calls == [], "no key means no network call at all"


def test_failures_trip_breaker_then_short_circuit():
    client, transport = make_client(
        [APITimeoutError("t1"), APITimeoutError("t2"), APITimeoutError("t3"), "unreachable"],
        failure_threshold=3,
        cooldown_seconds=60,
    )

    for _ in range(3):
        result = client.complete("prompt")
        assert not result.ok
        assert result.reason == "timeout"

    result = client.complete("prompt")
    assert result.reason == "circuit_open"
    assert len(transport.calls) == 3, "open breaker must not reach the transport"


def test_rate_limit_is_transient_not_permanent():
    client, _ = make_client([RateLimitError("429 quota"), "recovered"], failure_threshold=3)

    assert client.complete("p").reason == "rate_limited"
    assert client.breaker.state is BreakerState.CLOSED, "one 429 must not disable the demo"
    assert client.complete("p").ok


def test_bad_key_trips_on_first_call():
    client, transport = make_client(
        [AuthenticationError("invalid api key"), "unreachable"], failure_threshold=3
    )

    assert client.complete("p").reason == "auth"
    assert client.complete("p").reason == "circuit_open"
    assert len(transport.calls) == 1


def test_json_mode_rejection_retries_without_it():
    client, transport = make_client(
        [BadRequestError("response_format is not supported"), '{"explanation": "ok"}']
    )

    result = client.complete("prompt", json_mode=True)
    assert result.ok, "a provider that lacks JSON mode should still produce text"
    assert "response_format" in transport.calls[0]
    assert "response_format" not in transport.calls[1]
    assert client.breaker.state is BreakerState.CLOSED


def test_empty_completion_counts_as_failure():
    client, _ = make_client(["   "])
    result = client.complete("prompt")
    assert not result.ok
    assert result.reason == "empty_response"
    assert client.breaker.total_failures == 1


def test_status_is_json_serialisable():
    import json

    client, _ = make_client(["ok"])
    client.complete("p")
    payload = json.dumps(client.status())
    assert "llama-3.1-8b-instant" in payload


# ---------------------------------------------------------------------- main

def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failures = []
    for test in tests:
        try:
            test()
            print(f"  PASS  {test.__name__}")
        except Exception as exc:  # noqa: BLE001
            failures.append((test.__name__, exc))
            print(f"  FAIL  {test.__name__}: {type(exc).__name__}: {exc}")

    print(f"\n{len(tests) - len(failures)}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
