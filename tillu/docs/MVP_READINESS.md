# TILLU MVP readiness

**Current verdict:** functional private local MVP, not yet a durable hosted-production release.

## MVP flows now implemented

- Unified Assistant page with Chat, controlled Browser, Notes and persistent Canvas modes.
- Adaptive LangGraph intent → plan → tools → evidence evaluation → bounded replan → response → citation verification.
- General executable plans compile up to eight registered read/action capabilities, persist exact arguments, require one explicit approval, claim atomically, execute sequentially, checkpoint job progress/results, and stop on failure.
- Automatic read tools for current web, weather, news, trends, files, tasks, calendar, progress, notes, automations, runs, research sources, canvases, browser history, settings, activity, syllabus, calculator and system context.
- In-chat approval proposals for creating tasks, notes, events and automations; updating/deleting owned resources; running automations; indexing/deleting files; clearing browser history; changing settings; progress updates; and WhatsApp actions. Model-inferred mutations are schema-bounded, show the resolved payload, and never execute before approval.
- Persisted canvas create/list/load/save/delete and PNG export.
- Real server-side Playwright browser with isolated sessions, URL navigation, readable page state, screenshots, close controls, and approval-gated click/type/key actions. It is controllable manually from the unified Browser UI and automatically through Chat proposals.
- Files/RAG, research, task board, calendar, Discover, automation operations, communications, integrations, activity and settings pages.
- Adaptive model routing with cost/latency/quota health, 429 cooldown and circuit breakers.

## Natural Chat—no command syntax required

Heoster can ask normally, for example: “remind me to revise electrostatics”, “remember that Gauss law needs revision”, “make a canvas for ray diagrams”, “schedule Physics revision tomorrow at 6 pm”, “complete the task Revise optics”, “create a daily weather brief called Morning Update at 7 am”, “message +91… on WhatsApp saying…”, or “draft an email to … with subject … saying…”.

The deterministic router handles core MVP actions without a model provider. Configured models broaden interpretation and compile multi-capability plans. Ambiguous resource names fail closed instead of being guessed. The UI never requires command grammar, IDs, pipes, cron syntax, or JSON from Heoster. Consequential writes remain typed and approval-gated.

## Remaining blockers before hosted production

1. Apply migrations through `008_general_plan_execution.sql` to a real Supabase project and live-verify owner RLS, Storage, queue, repository, and atomic plan claims. This remains credential-blocked.
2. Add reconnect/resume semantics and provider token deltas to the existing SSE orchestration stream.
3. Add OCR/hybrid vector ingestion workers and parser isolation.
4. Deliver native/push notifications.
5. Make Playwright sessions durable before horizontal API scaling.
6. Add Gmail OAuth connection and WhatsApp webhooks when those optional APIs are needed.
7. Expand the current 21-test baseline with live RLS, browser durability, provider-contract, and broad end-to-end coverage.

No document or UI should describe these blockers as already complete.
