# Production Architecture Sketch

## Current PoC (this repo)

```
Browser -> Streamlit app -> Classifier -> SQLite log -> Claude API (gated)
```

Single-process, single-machine. SQLite resets on redeploy. Adequate for a demo.

## Production target

```
User surfaces (browser ext, IDE plugin, API gateway, chat UI)
    |
    v
Ingress proxy (Portal 26 / Nginx / API Gateway)
    |
    v
Auth layer (OAuth / SSO / JWT validation)
    |
    v
Classification service (stateless, horizontally scaled workers)
    |-- Pattern registry (served from config service, hot-reload)
    |-- Luhn / base64 / semantic classifier
    |-- Per-team policy overrides (Postgres policy table)
    |
    +-- ALLOW: pass request to LLM with governance metadata header
    |
    +-- BLOCK: return 403 + audit record
    |
    v
Structured log -> SIEM (Splunk / Datadog) + Postgres audit store
    |
    v
LLM provider (rate-limited passthrough, 1 connection pool per tenant)
```

## Key production changes from PoC

**Storage.** Swap SQLite for Postgres with connection pooling (PgBouncer). Schema is identical; logger.py swaps the connection string via env var.

**Classifier workers.** Stateless FastAPI workers behind a load balancer. Pattern registry loaded from a config service (Redis or object store) and refreshed on a TTL without restart.

**Policy overrides.** Each team or business unit gets a row in a `policies` table: enabled categories, custom business terms, passthrough threshold. Classification engine reads policy by team_id on each request.

**Semantic detection (Phase 2).** Sentence-transformer model (e.g., `all-MiniLM-L6-v2`) encodes the input and computes cosine similarity against a confidential term corpus. Triggers when similarity exceeds a tuned threshold. Handles the cases regex cannot: paraphrased sensitive concepts, multilingual inputs, novel product names.

**Rate limiting.** Per-user, per-team token budget on LLM passthrough. Prevents exfiltration via high-volume enumeration.

**Observability.** Each request emits a structured log event: team_id, tier, matched patterns, latency, passthrough decision. Feeds a Grafana dashboard and SIEM alert rules (e.g., spike in BLOCKED submissions from a single user).

**Auth.** OIDC token validation at the proxy layer. Classification service trusts the proxy and reads `X-Team-ID` and `X-User-ID` headers to apply the right policy.
