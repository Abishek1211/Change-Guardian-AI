"""REST + SSE endpoints."""

from __future__ import annotations

import json
import os
from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from ..data import SCENARIOS, example_requests, services
from ..graph import graph_payload
from ..llm import get_client
from ..pipeline import run_analysis, stream_analysis
from ..rag import get_retriever
from .limiter import limiter

router = APIRouter()

RATE_LIMIT = f"{os.getenv('RATE_LIMIT_PER_MINUTE', '5')}/minute"

MAX_REQUEST_CHARS = 500


class AnalyzeRequest(BaseModel):
    change_request: str = Field(
        ...,
        min_length=3,
        max_length=MAX_REQUEST_CHARS,
        description="Plain-English description of the change, e.g. "
        "'Upgrade payment-service from Spring Boot 2.7 to 3.2'",
    )


class AnalyzeResponse(BaseModel):
    report: dict[str, Any]


@router.post("/api/analyze", response_model=AnalyzeResponse)
@limiter.limit(RATE_LIMIT)
async def analyze(request: Request, body: AnalyzeRequest) -> AnalyzeResponse:
    """Run all 7 agents and return the finished report."""
    import asyncio

    report = await asyncio.to_thread(run_analysis, body.change_request)
    return AnalyzeResponse(report=report)


@router.get("/api/analyze/stream")
@limiter.limit(RATE_LIMIT)
async def analyze_stream(
    request: Request,
    change_request: str = Query(..., min_length=3, max_length=MAX_REQUEST_CHARS),
) -> EventSourceResponse:
    """Server-sent events - one per agent as it completes.

    This is the endpoint that makes the pipeline legible: a visitor who has
    never heard of LangGraph watches seven steps fill in with their actual
    intermediate output.
    """

    async def event_source():
        # Do not poll request.is_disconnected() here. EventSourceResponse runs
        # its own disconnect listener on the ASGI receive channel, and a second
        # consumer steals the message it waits for - the check then reports a
        # disconnect on the first iteration and the stream closes empty. Client
        # departure is handled by sse_starlette cancelling this generator.
        async for event in stream_analysis(change_request):
            yield {"event": event["event"], "data": json.dumps(event, default=str)}

    return EventSourceResponse(event_source())


@router.get("/api/services")
async def get_services() -> dict[str, Any]:
    """The dependency graph as {nodes, edges} for React Flow."""
    payload = graph_payload()
    payload["service_count"] = len(services)
    return payload


@router.get("/api/examples")
async def get_examples() -> dict[str, Any]:
    """Canned change requests, one per scenario, for the demo UI."""
    return {"examples": example_requests, "scenarios": list(SCENARIOS)}


@router.get("/health")
async def health() -> dict[str, Any]:
    """Dokploy healthcheck target.

    Always 200 while the process is serving. The LLM provider being down is
    reported in the body, not the status code - the pipeline still produces
    complete reports without it, so failing the healthcheck would restart a
    container that is working fine.
    """
    client = get_client()
    return {
        "status": "ok",
        "llm": client.status(),
        "retrieval": get_retriever().backend,
        "services_indexed": len(services),
    }
