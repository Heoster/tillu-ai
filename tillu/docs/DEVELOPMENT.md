# Development guide

## Repository layout

```text
apps/api/app/      FastAPI, LangGraph orchestration, tools, providers, repositories
apps/api/tests/    baseline policy/planner/RAG/manifest tests
apps/web/src/      React PWA and responsive product UI
apps/mobile/       Expo Android foundation
apps/desktop/      Tauri Windows shell
packages/          contracts and API client
supabase/          SQL migrations and RLS
docs/              architecture, operations and user documentation
```

Key modules:

- `orchestrator.py` — Intent → Planning → Execution LangGraph and tool registry.
- `providers.py` — phase-aware model registry, RPM/TPM windows, health, cost and fallback.
- `persona.py` — centralized Heoster/TILLU identity, time and response policy.
- `database.py` — current SQLite development/core repository; production replacement remains required.
- `browser_control.py`, `webreader.py`, `netpolicy.py` — controlled browser and network policy.
- `communications.py` — optional Gmail and WhatsApp adapters.
- `automation_runtime.py`, `worker.py` — automations and durable worker.
- `rag.py`, `fileguard.py` — bounded PDF ingestion and retrieval.

## Rules

1. Do not let models execute arbitrary functions or database writes.
2. Register read tools with a typed handler and risk level.
3. Implement writes as typed approval proposals with ownership, expiry and idempotency.
4. Never report provider, integration or action success without a real result.
5. Keep optional integrations optional and backend-only.
6. Inject authoritative current time; use live sources for changing facts.
7. Update `FEATURE_STATUS.md` and API docs with every capability change.

## Checks

```bash
cd apps/api
python -m compileall app
PYTHONPATH=. pytest tests -q

cd ../web
npm install
npm run build
```

For new work, add tests covering success, owner rejection, invalid payloads, replay, provider failure and deterministic fallback. Five current tests are insufficient for release confidence.

## Adding a model

Define phase support, capabilities, relative cost, RPM and TPM in `providers.py`; implement the adapter; ensure 429s raise `HTTPStatusError`; never hard-code credentials. Verify intent, planning and execution independently.

## Adding a chat tool

Add a bounded async handler and `ToolSpec`, expose only necessary arguments, add deterministic routing where useful, create a typed widget, and test provider-free fallback. External effects belong in action proposals, not the read registry.
