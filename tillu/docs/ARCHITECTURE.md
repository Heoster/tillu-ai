# TILLU implemented architecture — built by and for Heoster

TILLU is a private, single-owner assistant. Authentication excludes everyone except Heoster; owner scoping remains defense in depth.

```text
React PWA / Tauri / Expo
          │ HTTPS
          ▼
      FastAPI API
          │
          ├── Owner authentication + policy + approvals
          ├── Adaptive LangGraph cycle
          │     Intent model → Planning model → validated tools → Execution model
          ├── Authoritative read-tool registry
          ├── Typed write/external action proposals
          ├── Provider router and quota/health state
          ├── Playwright controlled browser
          ├── File/PDF/RAG pipeline
          └── Repositories and queue
                ├── SQLite local development/current route repository
                └── Supabase Postgres/Auth/Storage + durable queue migration
```

## Adaptive agent cycle

1. **Intent:** a low-cost fast model returns constrained JSON. Deterministic rules are the fallback.
2. **Planning:** a reasoning-capable model selects only registered read tools. The server validates names, arguments and call count.
3. **Execution:** server tools run against validated arguments.
4. **Evidence evaluation:** a reasoning model or deterministic policy checks missing, stale, contradictory and failed evidence.
5. **Bounded revision:** when necessary, the graph revises registered read-tool calls and retries at most twice.
6. **Response and verification:** an execution model synthesizes verified context and a deterministic citation pass removes invalid markers. Writes and external effects become persisted approval proposals instead of direct tool calls.

The gateway filters models by phase/capability, predicted RPM and TPM headroom, 429 cooldown and circuit state. It ranks remaining candidates by relative cost, latency EWMA, failures and reasoning suitability.

## Tool and action boundary

Read tools include web, weather, news, trends, document retrieval, workspace context, notes, automations, syllabus, calculator and system context. Typed approval actions currently cover tasks, notes, browser interactions, Gmail draft creation and WhatsApp outbound text. Models cannot register tools, bypass approval or mark an action successful.

## Response contract

Chat returns professional text plus typed widgets, citations, tool activity, cycle phases, provider/model identity, run/conversation IDs, IST generation time and visible errors. The frontend renders data, but authority remains with server results.

## Browser architecture

Safe reader mode retrieves bounded HTML without scripts. Controlled browser mode uses isolated Playwright contexts, request interception and public-network validation. Navigation/read are immediate; click/type/keypress produce expiring approval proposals. Current sessions are process-local and therefore not durable.

## Data and jobs

Local development uses SQLite. Migration `005_execution_hardening.sql` adds Postgres job leases, `SKIP LOCKED` claiming, idempotency, automation occurrences and usage accounting. The worker claims durable production jobs. Core route repositories have not all moved to Postgres, which remains the primary reliability blocker.

## Knowledge pipeline

PDFs are size/signature/structure/page bounded, quarantined, fingerprinted and indexed into page/heading-aware overlapping chunks. Retrieval uses BM25-style scoring, phrase boosts and page diversity. OCR, hybrid embeddings/pgvector, table/formula extraction, parser versioning and asynchronous ingestion remain incomplete.

## Deployment

- Vercel: web/PWA
- Render Docker web service: FastAPI plus Playwright runtime
- Render worker: durable job consumer
- Supabase: owner auth, intended Postgres source of truth and Storage
- GitHub Actions: protected scheduled refresh and due-automation enqueueing

See `FEATURE_STATUS.md` for the current implementation boundary and `ARCHITECTURE_AUDIT.md` for security findings.
