# Feature status and remaining gaps

**Updated:** 2026-09-30  
**Scope:** Current repository and verified local runtime. TILLU is a private, single-owner assistant built by and for Heoster.

## Operational now

- Unified Assistant with professional Markdown-like responses, citations, tool chips, typed widgets, approval cards, and current IST clock context.
- Adaptive Intent → Planning → Execution cycle with cost/latency-aware provider routing, predictive RPM/TPM windows, 429 cooldown, latency thresholds, circuit breakers, and deterministic fallbacks.
- Read tools: current web search, weather, news, trends, document RAG, tasks/calendar/progress, notes, automations, syllabus, calculator, and system context.
- Approval-gated chat writes: task creation, note creation, WhatsApp message proposal, browser click/type, and Gmail draft proposal.
- Playwright isolated browser navigation and page reading with request policy checks and approval-gated interaction.
- Files/PDF validation, bounded parsing, page-aware retrieval, citations, and optional Supabase Storage upload.
- Notes, canvas UI, tasks, calendar, browser reader, research collections, syllabus tracker, Discover, automation CRUD/runs, activity, integration and owner Settings views.
- Persisted settings for timezone, response style, weather coordinates, agent-cycle visibility, freshness search and reminder discovery, plus non-destructive API diagnostics.
- Optional Gmail and official WhatsApp Cloud API adapters. Missing credentials disable them without breaking TILLU.
- Durable Postgres queue migration and worker implementation for production jobs; local development retains explicit fallbacks.
- Owner-only production authentication using `OWNER_USER_ID` or `OWNER_EMAIL`.

## Partially implemented

| Capability | Current state | Required completion |
|---|---|---|
| Production persistence | SQLite is still the primary route repository | Complete repository abstraction and force Postgres in production |
| RAG | Strong lexical/page-aware retrieval | OCR, tables/formulas, embeddings, reranking, ingestion jobs and versioning |
| Conversations | History, search, rename API, pin, archive and deletion | Branch, edit/resend, regenerate, export and complete message metadata persistence |
| Memory | Recent conversation window | User-controlled long-term memory, review/delete controls and summaries |
| Streaming | Whole response returned | SSE event stream, cancellation, reconnect and durable run continuation |
| Browser control | Isolated sessions, navigate/read, approved selectors | Semantic targets, durable sessions, tabs, screenshots in UI and download policy |
| Gmail | Search/read adapter and approved draft foundation | OAuth connection UI, MIME normalization, attachments, send approval and webhook/watch |
| WhatsApp | Official outbound approved text adapter | Webhooks, templates, delivery receipts, contacts, opt-in and conversation UI |
| Automations | CRUD, cron calculation, history, queue migration | Postgres-only claiming, retries, cancellation, dead-letter UI and richer triggers/actions |
| Notifications | Due-reminder discovery | PWA/Android/Windows/email delivery, quiet hours, snooze and receipts |
| Mobile/desktop | Expo and Tauri foundations | Feature parity, secure token storage, native notifications, signing and updates |
| Canvas | Drawing and PNG export | Cloud persistence, pages, shapes/text, PDF backgrounds and version history |

## Highest remaining priorities

1. Move every production repository from SQLite/process globals to owner-scoped Supabase Postgres.
2. Persist complete message metadata: widgets, citations, tools, cycle phases, provider, model and usage.
3. Add SSE streaming, cancellation and durable continuation.
4. Complete conversation management and user-controlled memory.
5. Add production document ingestion jobs with OCR and hybrid pgvector retrieval.
6. Complete notification delivery and automation operations.
7. Replace every static UI metric/status with live API data.
8. Expand the current seven-test baseline with owner rejection, approvals, SSRF, queues, files, RLS and provider-fallback coverage.

## Honesty rules

A configured adapter is not reported as connected until credentials are present. An action is not reported complete until its server-side execution result exists. No router can guarantee zero downtime; deterministic tools remain available when possible, while free-form synthesis requires at least one healthy model.
