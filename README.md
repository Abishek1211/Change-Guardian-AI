# ChangeGuardian AI

Autonomous deployment risk analysis. Describe a change in plain English and get
back a 0–100 risk score, the blast radius, the rules it violates, what happened
last time someone tried it, and a rollout strategy — before it reaches
production.

```
> Upgrade payment-service from Spring Boot 2.7 to 3.2

  RISK 85/100  CRITICAL          DEPLOYMENT BLOCKED
  Blast radius   5 services      checkout, order, user, inventory, notification
  SLA            CRITICAL RISK   99.95% leaves ~22 min/month of error budget
  Comparable     INC-002         $500,000, 45 min
```

## How it works

Seven agents in a LangGraph pipeline. Six are fully deterministic; only the last
one calls a model.

| # | Agent | What it does |
|---|---|---|
| 1 | Intake | Regex parse into service, old value, new value |
| 2 | Scenario Router | Classify into one of six change scenarios |
| 3 | Graph Impact | NetworkX traversal for the blast radius |
| 4 | Hybrid RAG | FAISS over past incidents **plus** a deterministic rule engine |
| 5 | Memory Graph | Prior deployment outcomes for this service and change type |
| 6 | Risk & Rollout | 0–100 score and rollout strategy |
| 7 | LLM Explanation | Plain-English reasoning and 3 remediation steps |

**The score is never produced by a model.** Agent 6 is arithmetic, and every
point it adds appends a matching line to `risk_reasons`:

```
Base score (+10)
Service criticality=critical (+30)
5 affected service(s) (+25)
Similar P1 incident: INC-002 (+20)
2 rule violation(s) (+30)
Java mismatch: needs 17, has 11 (+20)
Spring Boot 3.x breaking migration (+15)
```

That trail reconstructs the number exactly — a test asserts it. A risk score an
engineer cannot interrogate is one they will not act on.

Agent 4 keeps its two retrieval strategies separate rather than fusing them.
Vector search finds incidents that *resemble* this change; the rule engine finds
constraints that are *certainly* violated. Spring Boot 3 on Java 11 will fail —
that is not a similarity judgement, and it should not be scored like one.

**Scenarios:** `framework_upgrade` · `resource_change` · `db_schema` ·
`api_contract` · `shared_dependency` · `event_schema`

**Rollout thresholds:** ≤25 DIRECT · 26–50 CANARY · 51–75 STAGED · >75 BLOCKED

## Inference is pluggable

Agent 7 talks to any OpenAI-compatible endpoint. Provider is entirely a matter
of environment:

| Setup | `LLM_BASE_URL` | `LLM_MODEL` |
|---|---|---|
| Groq (deployed default) | `https://api.groq.com/openai/v1` | `llama-3.1-8b-instant` |
| Google AI Studio | `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-2.0-flash-lite` |
| Fully local | `http://localhost:11434/v1` | `qwen2.5:3b` |

**Running with no key at all is a supported mode, not a degraded one.** All seven
agents execute, the score and blast radius are unchanged, and agent 7 uses a
deterministic explanation. Nothing leaves the machine.

The hosted demo is a public URL with no auth, so a free-tier quota is a matter
of when rather than if. A circuit breaker short-circuits after consecutive
failures and serves the rule-based explanation immediately instead of paying the
timeout on every request. Rate limits and connection errors are treated as
transient; a bad key trips it on the first call, because retrying will not fix
that.

## Run it

```bash
pip install -r backend/requirements.txt
```

```bash
cp .env.example .env    # optional: add LLM_API_KEY for LLM explanations
```

```bash
uvicorn app.main:app --reload --app-dir backend
```

Then `http://localhost:8000/docs`.

| Endpoint | Purpose |
|---|---|
| `POST /api/analyze` | Run the pipeline, return the report |
| `GET /api/analyze/stream` | SSE — one event per agent as it completes |
| `GET /api/services` | Dependency graph as `{nodes, edges}` |
| `GET /api/examples` | Canned requests, one per scenario |
| `GET /health` | Status, including live circuit-breaker state |

```bash
curl -N "http://localhost:8000/api/analyze/stream?change_request=Reduce%20checkout-service%20memory%20from%202GB%20to%201GB"
```

## Tests

```bash
python backend/tests/test_llm_client.py && python backend/tests/test_pipeline.py
```

Both run fully offline — no key, no network. The pipeline suite pins the score
for all six scenarios, so a refactor that changes risk arithmetic fails loudly.

## The dataset is synthetic

The seven services, six incidents, and five past deployments in
`backend/app/data/` are **invented** — modelled on a mid-size e-commerce estate,
but not derived from any real system. The financial impacts are illustrative.
They exist to exercise the six scenarios, not to claim production provenance.

## Deployment

Single container: a multi-stage build compiles the React frontend and FastAPI
serves it alongside the API. One origin, no CORS, one route.

Targets `linux/arm64` — an Oracle Ampere instance behind Traefik. See
[ARCHITECTURE.md](ARCHITECTURE.md).
