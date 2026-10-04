# Proactive Briefings and Autonomous Execution

## Policy selected by Heoster

- Read-only collection and briefing generation may run automatically.
- Writes, external messages, and other consequential effects require per-run approval.
- Delivery targets are in-app, Web Push, Gmail, and WhatsApp.
- Default suite includes morning plan, evening review, urgent alerts, study review, and failed-run alerts.

## Implemented

### Durable briefing schedules

`briefing_schedules` stores owner, kind, cron schedule, timezone, channels, configuration, enabled state, and next/last run timestamps. Five defaults can be installed from the Briefings UI.

### Briefing intelligence

Briefings assemble owner-scoped tasks, calendar, syllabus progress, approved routine/preference memory, weather, current news, and failed automation runs. A configured model synthesizes the result; deterministic summaries remain available without a model.

### Notification inbox

Every briefing first creates a durable private in-app notification. Notifications support unread, read, and archived states. Delivery attempts are separately recorded per channel.

### Web Push

VAPID-backed PWA Web Push is implemented. The UI requests permission, creates a browser subscription, persists it owner-scoped, and the service worker displays/click-routes notifications. It remains disabled until VAPID keys are configured.

### Gmail and WhatsApp

Under Heoster's selected policy, external briefing delivery is recorded as `proposal_required`; it cannot silently send. Live delivery additionally requires configured Gmail OAuth or WhatsApp Cloud API credentials and destinations.

### Scheduler

`POST /api/internal/run-due-briefings` is protected by `CRON_SECRET` and processes due schedules. Hosted operation requires a real cron trigger.

### Autonomous task execution

TILLU can compile up to eight registered capabilities, persist exact calls, show one plan approval, atomically claim it, execute sequentially, save step results/progress, stop on failure, and block duplicate execution. Recurring read-only automations can run automatically. Consequential recurring effects remain approval-gated by policy.

## Production requirements

Apply `supabase/migrations/010_proactive_briefings.sql` after migrations 001–009. Configure:

- Supabase and Heoster owner ID
- `CRON_SECRET`
- `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, and `VAPID_SUBJECT`
- At least one model provider for synthesized prose (optional for deterministic summaries)
- Gmail and WhatsApp credentials for those optional channels
- A hosted cron request for due briefings

## Honest verification boundary

The complete local scheduling, composition, inbox, status, UI, and repository flow is implemented and tested. Web Push code is implemented but cannot be live-delivery verified without VAPID keys and a real browser origin. Gmail/WhatsApp delivery cannot be verified without credentials and remains per-run approval-gated. Supabase RLS and hosted cron remain unverified until Heoster's production project is configured.
