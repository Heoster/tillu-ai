# Foundation remediation status

Updated: 2026-10-01

## Selected strategy

Foundation first. Live Supabase verification will run after Heoster provides/configures the project credentials.

## Completed in this phase

- Added `app/capabilities.py` as the canonical typed registry for read and action capabilities.
- Every action now has a single schema, label, risk, capabilities, kind, and approval requirement.
- The LangGraph planner receives read capabilities only; action capabilities cannot execute through the read runtime.
- `/api/tools` is generated from the unified registry and returns separate read/action catalogs.
- Model action payload validation is fail-closed and registry-backed.
- Added capability parity and permission tests.
- Added rich assistant-message metadata persistence for tools, widgets, citations, agent cycle, provider/model, run ID, generation time, and errors.
- Conversation reload now reconstructs persisted rich Chat widgets, tool chips, citations, and provider metadata.
- Added SQLite repository contract tests for rich messages, owner-scoped tasks, and single-use proposal claims.
- Added authenticated `POST /api/chat/stream` SSE transport with status, cycle, final, done, disconnect, and error events.
- Updated the unified Assistant UI with a live TILLU Brain panel, streamed phase state, cancellation controls, and authoritative final-response handling.
- Added an SSE contract test and runtime-tested the stream with the calculator tool.

## Verification

- Backend: 21 tests passed, including natural-language actions and atomic multi-capability plan execution.
- Frontend: production build passed (1,932 modules).

## Next foundation steps

1. Move action execution from `main.py` to a dedicated approval/action service backed by the capability registry.
2. Split API route groups without changing contracts.
3. Split the React monolith into feature modules.
4. Add Supabase repository contract/RLS scripts that fail clearly when credentials are absent.
5. Then add SSE streaming, durable run events/checkpoints, and browser session leasing.

## Credential-blocked item

Live Supabase/RLS/Storage/RPC verification is intentionally not marked complete. It requires Heoster's configured Supabase project and test identities.
