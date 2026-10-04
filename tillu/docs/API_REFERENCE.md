# API reference

Base path: `/api`. Cloud mode requires `Authorization: Bearer <Supabase access token>` and accepts only Heoster’s configured owner identity. Development mode uses the explicit local identity.

## System and orchestration

- `GET /health` — service mode and optional-integration state.
- `GET /ready` — database, auth, model and storage readiness.
- `GET /providers` — model registry, RPM/TPM windows, latency, cooldown and breaker status.
- `GET /tools` — authoritative read-tool catalog.
- `GET /config`, `GET /me` — public client bootstrap and authenticated owner.
- `GET|PATCH /settings` — persisted owner preferences for timezone, response style, location, cycle visibility, freshness search and reminders.
- `POST /settings/test/{service}` — non-destructive live diagnostics for models, weather, news, search, browser, Gmail and WhatsApp.
- `POST /chat` — adaptive intent → planning → execution response. Returns `message`, `widgets`, `agent_cycle`, `tools`, `citations`, `provider`, `model`, `run_id`, `conversation_id`, `generated_at` and errors.
- `GET /runs/{run_id}` — owned orchestration checkpoint.

Explicit chat commands currently create approval cards for `create task: …`, `save note: …`, and `send WhatsApp to <number>: …`.

## Approvals, plans and jobs

- `POST /plans/{plan_id}/approval` — approve an owned persisted action plan.
- `POST /action-proposals/{id}/decision` — approve/reject a typed browser, communication, task or note proposal.
- `GET /jobs`, `GET /jobs/{id}` — local job views; still listed as a persistence/ownership remediation area.
- `GET /audit` — local audit feed.

## Conversations and notes

- `GET /conversations?q=&archived=false` — search active or archived conversations; pinned first.
- `PATCH /conversations/{id}` — rename, pin/unpin or archive/unarchive.
- `GET /conversations/{id}`
- `DELETE /conversations/{id}`
- `GET|POST /notes`
- `GET|PATCH|DELETE /notes/{id}`
- `POST /notes/ai/transform`

Conversation rename/search/pin/archive/branch/export and full message metadata persistence are not implemented yet.

## Study and personal organization

- `GET /syllabus`, `PATCH /progress/{topic_id}`
- `POST /planner`
- `GET|POST /tasks`, `PATCH /tasks/{id}`
- `GET|POST /calendar`, `DELETE /calendar/{id}`
- `GET /notifications/due`

## Files and research

- `GET /files`, `POST /files/upload`, `POST /files/ingest`, `POST /files/{id}/index`
- `GET /files/{id}/download`, `DELETE /files/{id}` — authenticated owner download and metadata/chunk deletion.
- `POST /research/query`
- `GET|POST /research/sources`, `POST /research/web-query`
- `POST /browser/read`, `POST /browser/ask`
- `GET|DELETE /browser/history`

## Controlled browser

- `POST /browser-control/sessions`
- `POST /browser-control/navigate`
- `GET /browser-control/sessions/{id}`
- `POST /browser-control/sessions/{id}/screenshot`
- `GET /browser-control/artifacts/{name}`
- `POST /browser-control/actions` — creates approval; does not immediately click/type.

## Optional communications

- `GET /integrations/status`
- `GET /mail/messages`, `GET /mail/messages/{id}`
- `POST /mail/drafts` — approval proposal.
- `POST /whatsapp/messages` — approval proposal using official Cloud API after approval.

Missing credentials return an honest unavailable state and do not prevent TILLU from starting.

## Live services and automations

- `GET /services/weather|news|trends|search`
- `GET|POST /automations`
- `PATCH|DELETE /automations/{id}`
- `POST /automations/{id}/run`
- `GET /automation-runs`
- `POST /internal/refresh-digest`
- `POST /internal/run-due-automations`

Internal routes require `CRON_SECRET`. Production due automation enqueueing uses the Postgres queue migration when cloud mode is active.

## Error and truthfulness rules

- `401/403`: missing session or non-owner identity.
- `404`: absent or unowned object.
- `409`: replayed/invalid state transition.
- `410`: expired approval.
- `422`: invalid or unsafe document.
- `429`: request or quota limit.
- `502/503`: optional provider/integration unavailable.

An accepted proposal is not a completed action; only a completed execution result confirms success.
