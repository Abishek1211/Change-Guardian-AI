"""A small circuit breaker for the LLM call.

The deployed instance is a public URL with no auth. If the free-tier quota is
exhausted or the provider goes slow, every request would otherwise pay the full
timeout before falling back. The breaker makes that failure cheap: after a few
consecutive failures it stops trying for a cooldown period and lets agent 7 use
the deterministic explanation immediately.

States:

    CLOSED     normal - calls go through
    OPEN       short-circuit - fail instantly, no network call
    HALF_OPEN  cooldown elapsed - let exactly one probe through

Cooldown doubles on each successive failed probe, up to max_cooldown_seconds,
so a provider that is down for an hour is polled a handful of times rather than
once a minute.
"""

from __future__ import annotations

import threading
import time
from enum import Enum


class BreakerState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 3,
        cooldown_seconds: float = 60.0,
        max_cooldown_seconds: float = 600.0,
    ) -> None:
        self._failure_threshold = max(1, failure_threshold)
        self._base_cooldown = cooldown_seconds if cooldown_seconds > 0 else 60.0
        self._max_cooldown = max(self._base_cooldown, max_cooldown_seconds)

        self._lock = threading.Lock()
        self._failures = 0
        self._opened_at = 0.0
        self._cooldown = self._base_cooldown
        self._probe_in_flight = False

        # Observability - surfaced on /health so the demo can show provider state.
        self.total_calls = 0
        self.total_failures = 0
        self.total_short_circuits = 0
        self.last_error: str | None = None

    @property
    def state(self) -> BreakerState:
        with self._lock:
            return self._state_locked()

    def _state_locked(self) -> BreakerState:
        if self._failures < self._failure_threshold:
            return BreakerState.CLOSED
        if time.monotonic() - self._opened_at >= self._cooldown:
            return BreakerState.HALF_OPEN
        return BreakerState.OPEN

    def allow(self) -> bool:
        """Reserve an attempt. False means short-circuit without calling out."""
        with self._lock:
            state = self._state_locked()
            if state is BreakerState.CLOSED:
                self.total_calls += 1
                return True
            if state is BreakerState.HALF_OPEN and not self._probe_in_flight:
                self._probe_in_flight = True
                self.total_calls += 1
                return True
            self.total_short_circuits += 1
            return False

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._cooldown = self._base_cooldown
            self._probe_in_flight = False
            self.last_error = None

    def record_failure(self, error: str, *, permanent: bool = False) -> None:
        """`permanent` is for errors retrying cannot fix - a bad key, a model
        name the provider does not recognise. Those trip the breaker on the
        first occurrence instead of after `failure_threshold` attempts."""
        with self._lock:
            was_probe = self._probe_in_flight
            self._probe_in_flight = False
            self.total_failures += 1
            self.last_error = error

            already_open = self._failures >= self._failure_threshold

            if permanent:
                self._failures = self._failure_threshold
            else:
                self._failures += 1

            if was_probe or (permanent and not already_open):
                # A failed probe means the provider is still down: back off harder.
                self._cooldown = min(self._cooldown * 2, self._max_cooldown)

            if self._failures >= self._failure_threshold:
                self._opened_at = time.monotonic()

    def snapshot(self) -> dict:
        with self._lock:
            state = self._state_locked()
            retry_in = 0.0
            if state is BreakerState.OPEN:
                retry_in = max(0.0, self._cooldown - (time.monotonic() - self._opened_at))
            return {
                "state": state.value,
                "consecutive_failures": self._failures,
                "retry_in_seconds": round(retry_in, 1),
                "total_calls": self.total_calls,
                "total_failures": self.total_failures,
                "total_short_circuits": self.total_short_circuits,
                "last_error": self.last_error,
            }

    def reset(self) -> None:
        with self._lock:
            self._failures = 0
            self._cooldown = self._base_cooldown
            self._probe_in_flight = False
            self.last_error = None
