"""Pipeline execution - batch and streaming.

Both paths derive their sequence from `agents.AGENTS`, so they cannot drift:

    run_analysis()    compiles the LangGraph workflow and invokes it
    stream_analysis() steps the same agents one at a time, yielding an event
                      after each so the UI can show the pipeline working

The streaming path deliberately does not use LangGraph's own stream. We want an
event per agent carrying that agent's specific contribution and its elapsed
time, which means owning the loop.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncIterator

from langgraph.graph import END, StateGraph

from .agents import AGENTS, AgentSpec


def build_workflow():
    """Compile the 7-node LangGraph."""
    builder = StateGraph(dict)

    for spec in AGENTS:
        builder.add_node(spec.key, spec.run)

    builder.set_entry_point(AGENTS[0].key)
    for current, following in zip(AGENTS, AGENTS[1:]):
        builder.add_edge(current.key, following.key)
    builder.add_edge(AGENTS[-1].key, END)

    return builder.compile()


_workflow = None


def get_workflow():
    global _workflow
    if _workflow is None:
        _workflow = build_workflow()
    return _workflow


def run_analysis(change_request: str) -> dict[str, Any]:
    """Run the full pipeline and return the report dict."""
    started = time.monotonic()
    state = get_workflow().invoke({"change_request": change_request})
    report = dict(state.get("report", {}))
    report["elapsed_ms"] = int((time.monotonic() - started) * 1000)
    return report


async def _run_agent(spec: AgentSpec, state: dict) -> dict:
    if spec.arun is not None:
        return await spec.arun(state)
    # The deterministic agents are fast but not instant; a thread keeps the
    # event loop free to flush SSE frames while they run.
    return await asyncio.to_thread(spec.run, state)


def _emitted(spec: AgentSpec, state: dict) -> dict[str, Any]:
    return {key: state[key] for key in spec.emits if key in state}


async def stream_analysis(change_request: str) -> AsyncIterator[dict[str, Any]]:
    """Yield one event per agent, then a final `complete` event with the report.

    Event shapes:
        {"event": "start",    "agents": [...]}
        {"event": "agent",    "agent": "...", "index": 1, "status": "complete",
         "output": {...}, "elapsed_ms": 42}
        {"event": "agent",    "status": "error", "error": "..."}
        {"event": "complete", "report": {...}, "elapsed_ms": 1234}
    """
    yield {
        "event": "start",
        "agents": [
            {"key": s.key, "label": s.label, "description": s.description, "index": i}
            for i, s in enumerate(AGENTS, start=1)
        ],
    }

    state: dict[str, Any] = {"change_request": change_request}
    pipeline_started = time.monotonic()

    for index, spec in enumerate(AGENTS, start=1):
        agent_started = time.monotonic()
        try:
            state = await _run_agent(spec, state)
        except Exception as exc:  # noqa: BLE001
            # Agent 7 handles its own failures; anything reaching here is a bug
            # in a deterministic agent. Report it rather than dropping the stream.
            yield {
                "event": "agent",
                "agent": spec.key,
                "label": spec.label,
                "index": index,
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
                "elapsed_ms": int((time.monotonic() - agent_started) * 1000),
            }
            return

        yield {
            "event": "agent",
            "agent": spec.key,
            "label": spec.label,
            "index": index,
            "status": "complete",
            "output": _emitted(spec, state),
            "elapsed_ms": int((time.monotonic() - agent_started) * 1000),
        }

    report = dict(state.get("report", {}))
    elapsed = int((time.monotonic() - pipeline_started) * 1000)
    report["elapsed_ms"] = elapsed
    yield {"event": "complete", "report": report, "elapsed_ms": elapsed}
