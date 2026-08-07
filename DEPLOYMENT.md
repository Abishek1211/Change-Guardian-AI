# Deployment

Target: an Oracle `VM.Standard.A1.Flex` instance (4 ARM OCPU, 24 GB, no GPU)
already running Dokploy behind Traefik, shared with other applications. Ports
22, 80, and 443 only.

Everything builds for `linux/arm64`, **on the server** rather than cross-built
from a dev machine.

## 1. Get a Groq key

`console.groq.com/keys` — free, no card. The key is account-wide; the model is
chosen by configuration, not at key creation.

Free-tier limits on `llama-3.1-8b-instant` at time of writing: 30 req/min,
14,400 req/day, **6,000 tokens/min**, 500,000 tokens/day.

Tokens per minute is the real ceiling, not requests. One analysis costs roughly
635 tokens (~500 prompt, ~135 completion), so the quota supports about **9
analyses per minute across all visitors combined**. The per-IP rate limit is
lower than that on purpose, and the circuit breaker covers the case where
several visitors arrive at once. Verify current limits at
`console.groq.com/docs/rate-limits` — they change.

## 2. Create the Dokploy application

1. **New Application** → source: GitHub → `Abishek1211/Change-Guardian-AI`
2. Build type: **Dockerfile**
3. Branch: `main`

## 3. Environment

Set these in Dokploy's **Environment** tab. They are never committed — `.env` is
gitignored and `.dockerignore` excludes it from the build context so a key
cannot end up in an image layer.

```
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.1-8b-instant
LLM_API_KEY=gsk_...
LLM_TIMEOUT_SECONDS=20
RATE_LIMIT_PER_MINUTE=5
TRUST_PROXY_HEADERS=true
```

`TRUST_PROXY_HEADERS` matters. Behind Traefik every request arrives from the
proxy's address, so without reading `X-Forwarded-For` the rate limiter would
bucket the entire internet as one client and lock everyone out after five
requests.

Omitting `LLM_API_KEY` is valid — the pipeline runs fully and agent 7 serves the
deterministic explanation.

## 4. Domain

Add `changeguardian.abishekrajavelu.in` in the Domains tab, port `8000`. Traefik
issues the certificate automatically. Point the DNS A record at the instance
first, or the ACME challenge fails.

## 5. Resource limits

The box is shared. Set these so a traffic spike here cannot degrade the other
applications:

| Setting | Value |
|---|---|
| CPU limit | `2.0` (of 4) |
| Memory limit | `1G` |
| Memory reservation | `256M` |

Steady-state usage is far below this — the container holds one ONNX session and
serves a six-row corpus. The limit is a blast wall, not a sizing estimate.

## 6. Healthcheck

Path `/health`, port `8000`.

It returns 200 whenever the process is serving, **including when the LLM
provider is down**. Provider state is reported in the body instead. Failing the
healthcheck on an LLM outage would restart a container that is working
correctly — the deterministic pipeline does not need the model.

```json
{ "status": "ok",
  "llm": { "provider": "llama-3.1-8b-instant @ api.groq.com",
           "breaker": { "state": "closed", "consecutive_failures": 0 } },
  "retrieval": "faiss (fastembed)" }
```

## Local parity

```bash
docker compose up --build
```

Reads `.env`, exposes `http://localhost:8000`. Same image the server builds.

## Build notes

- The build compiles the frontend in a Node stage and copies only the output
  into the Python runtime — no Node in the final image.
- `prebuild_index.py` runs during the build to download the ONNX model and embed
  the corpus, so the running container never reaches HuggingFace and the first
  request does not pay a 90 MB download.
- The corpus vector cache is fingerprinted by corpus text plus model name. Edit
  the incidents in `backend/app/data/` and the cache is ignored and recomputed
  rather than silently serving stale vectors.
- Expect a slow first build on 4 OCPUs — mostly `npm ci` and the ONNX download.
  Rebuilds reuse cached layers unless dependencies change.

## Rollback

Dokploy keeps previous deployments; redeploy an earlier one from the
Deployments tab. Tagged releases correspond to `main` commits, so
`git checkout v2.0.0` reproduces a known-good tree.
