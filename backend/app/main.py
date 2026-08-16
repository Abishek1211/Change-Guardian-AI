"""FastAPI entrypoint.

Single container: FastAPI serves the API under /api and the built React bundle
at /. One origin means no CORS, one Traefik route, and one thing to debug.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Load .env before anything reads configuration at import time.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from slowapi.errors import RateLimitExceeded  # noqa: E402
from slowapi.middleware import SlowAPIMiddleware  # noqa: E402

from .api import limiter, router  # noqa: E402
from .llm import get_client  # noqa: E402
from .rag import get_retriever  # noqa: E402

logger = logging.getLogger("changeguardian")

# Written by the Docker build; absent during local backend-only development.
FRONTEND_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("LLM provider: %s", get_client().config.describe())
    # Build the FAISS index now so the first visitor does not wait for the
    # embedding model to load.
    try:
        logger.info("Retrieval backend: %s", get_retriever().warmup())
    except ImportError as exc:
        logger.warning("Retrieval unavailable: %s", exc)
    yield


app = FastAPI(
    title="ChangeGuardian AI",
    description="Autonomous deployment risk analysis - 7-agent LangGraph pipeline",
    version="2.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# The page is entirely self-contained - its own bundle, no external fonts,
# scripts, or images - so a strict CSP costs nothing here. 'unsafe-inline' is
# needed for style only, because React Flow sets element styles inline.
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data:",
        "font-src 'self'",
        # The API and SSE stream are same-origin; nothing else should be reachable.
        "connect-src 'self'",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'none'",
    ]
)

SECURITY_HEADERS = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    # Traefik terminates TLS and only serves this over HTTPS.
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    for header, value in SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    return response


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limited",
            "detail": (
                "This demo runs on a free-tier LLM quota shared by everyone. "
                f"Limit is {os.getenv('RATE_LIMIT_PER_MINUTE', '5')} analyses per minute."
            ),
        },
    )


app.include_router(router)


if FRONTEND_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

    # HEAD as well as GET: uptime monitors and link scrapers commonly send HEAD,
    # and FastAPI does not derive it from a GET route - the bare / would answer
    # 405 and a monitor would report the site as down.
    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def serve_spa(full_path: str) -> FileResponse:
        """Serve the SPA, letting client-side routing own every non-API path."""
        candidate = (FRONTEND_DIR / full_path).resolve()
        # Guard against ../ traversal escaping the static directory.
        if candidate.is_file() and candidate.is_relative_to(FRONTEND_DIR.resolve()):
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIR / "index.html")

else:

    @app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
    async def no_frontend() -> JSONResponse:
        return JSONResponse(
            {
                "service": "ChangeGuardian AI",
                "note": "Frontend not built. API is live - see /docs.",
                "endpoints": ["/api/analyze", "/api/analyze/stream", "/api/services",
                              "/api/examples", "/health"],
            }
        )
