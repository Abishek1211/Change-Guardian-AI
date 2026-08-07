# Architecture

## The shape of it

```
                       ┌──────────── one container ────────────┐
  browser ──▶ Traefik ─┤  FastAPI ──▶ 7-agent LangGraph        │──▶ Groq
              (TLS)    │     │                                 │   (agent 7 only)
                       │     └──▶ static/  (React build)       │
                       └───────────────────────────────────────┘
```

One origin serves the API and the UI. That is not a packaging shortcut — it
removes CORS, one Traefik route, and an entire class of "works locally, breaks
deployed" problems.

## Why six of seven agents avoid the model

The score, the blast radius, the rule violations, and the rollout decision are
produced by arithmetic and graph traversal. Only the closing explanation is
generated.

This is the central design decision. A risk score that comes out of a language
model cannot be audited, cannot be regression-tested, and cannot be defended in
a change-review meeting. Agent 6 appends a line to `risk_reasons` for every
point it adds, and a test asserts the reasons sum back to the score. The model's
job is narrower and honest: turn a finished analysis into prose.

The practical consequence is that a model outage degrades wording, not
findings. Running with no API key at all is a supported mode.

### Pipeline

| # | Agent | Input → Output | Model? |
|---|---|---|---|
| 1 | Intake | request → service, old, new, extras | no |
| 2 | Scenario Router | request → one of six scenarios | no |
| 3 | Graph Impact | service → affected services | no |
| 4 | Hybrid RAG | request → incidents + violations | no |
| 5 | Memory Graph | service, scenario → past outcomes | no |
| 6 | Risk & Rollout | everything → score, plan, reasons | no |
| 7 | LLM Explanation | report → prose + remediation | yes |

`agents.AGENTS` is the single ordering source. Both the compiled LangGraph
(`POST /api/analyze`) and the hand-stepped loop (`GET /api/analyze/stream`)
derive their sequence from it, and a test asserts the two paths produce the same
score. Streaming owns its loop rather than using LangGraph's, because the UI
needs one event per agent carrying that agent's specific contribution and
elapsed time.

## Hybrid retrieval, kept separate

Agent 4 runs two strategies and does **not** fuse them:

- **Semantic** — FAISS over six incident write-ups, `all-MiniLM-L6-v2`.
  Answers "what does this resemble?"
- **Exact** — a rule engine over the service inventory. Answers "what is
  certainly broken?"

Spring Boot 3 on Java 11 will fail. That is not a similarity judgement and
scoring it like one would be wrong. The report shows both, labelled.

At six documents, FAISS `IndexFlatIP` and a numpy dot product are the same
computation; the retriever supports both and falls back automatically.

## Inference

One `AsyncOpenAI` client with `base_url` from the environment. Groq, Google AI
Studio, and Ollama all speak the OpenAI protocol, so there is no provider
abstraction layer — swapping providers is two environment variables.

### The circuit breaker

The deployed URL is public and unauthenticated against a shared free-tier quota,
so exhaustion is a matter of when. Without a breaker every request would pay the
full timeout before falling back.

```
CLOSED ──(N consecutive failures)──▶ OPEN ──(cooldown)──▶ HALF_OPEN
   ▲                                                          │
   └──────────────(probe succeeds)────────────────────────────┘
                     (probe fails → OPEN, cooldown doubles)
```

Rate limits, timeouts, and connection errors are transient and count toward the
threshold. Authentication and unknown-model errors trip on the first occurrence,
because retrying will not fix a bad key. Live state is exposed on `/health`.

## Runtime shape on the target box

Oracle VM.Standard.A1.Flex — 4 ARM OCPU, 24 GB, no GPU, shared with other
applications behind the same Dokploy/Traefik.

Inference runs off-box at Groq, so a request costs this machine only the
deterministic pipeline: a graph traversal, one 384-dimension embedding, a
six-row dot product, and integer arithmetic. Measured end-to-end at ~470 ms,
almost all of it waiting on the network.

Self-hosting even a 1.5B model was considered and rejected — roughly 8–15 tok/s
on four ARM cores means 20–40 s per explanation with every core pinned, which
would starve the co-tenant applications.

| Constraint | Consequence |
|---|---|
| aarch64, no GPU | `fastembed` (ONNX) not `sentence-transformers` (PyTorch): ~400 MB image, not ~2.5 GB |
| Shared CPU | `OMP_NUM_THREADS=2`, single uvicorn worker, container CPU limits |
| Free-tier quota | Circuit breaker, per-IP rate limit keyed on `X-Forwarded-For` |
| Cold start | Model and corpus vectors baked in at build time |

## Data

`backend/app/data/` — seven services, two shared libraries, two APIs, two Kafka
events, six databases, six incidents, five past deployments.

**Synthetic.** Modelled on a mid-size e-commerce estate, not drawn from any real
system, and the financial figures are illustrative. It exists to exercise the
six scenarios. Importing the module has no side effects.
