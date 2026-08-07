"""Per-IP rate limiting.

The deployed instance is public and unauthenticated, and every analysis costs a
Groq call against a shared free-tier quota. Without a limit here, one script
would exhaust the day's requests for everyone.

Behind Traefik the client IP arrives in X-Forwarded-For; slowapi's default
`get_remote_address` would otherwise bucket every visitor under the proxy's IP
and rate-limit the whole internet as one user.
"""

from __future__ import annotations

import os

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

# Only trust the forwarded header when something is actually in front of us.
TRUST_PROXY = os.getenv("TRUST_PROXY_HEADERS", "true").strip().lower() in ("1", "true", "yes")


def client_identifier(request: Request) -> str:
    if TRUST_PROXY:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            # Left-most entry is the original client; the rest are proxy hops.
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("x-real-ip", "")
        if real_ip:
            return real_ip.strip()
    return get_remote_address(request)


limiter = Limiter(key_func=client_identifier)
