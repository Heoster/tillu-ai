# User guide

## Assistant

Ask naturally. TILLU displays its adaptive cycle, selected tools, citations, provider/model and typed widgets. It knows the authoritative Asia/Kolkata date/time, but uses live tools for facts that can change.

Examples:

- `What is the weather today?`
- `Find the latest CBSE announcement.`
- `Search Gauss law in my uploaded files.`
- `Show my tasks and upcoming calendar events.`
- `Find electrochemistry in my notes.`
- `Show enabled automations.`
- `Calculate (25*4)+18.`

## Chat actions and approval

Explicit commands can create reviewable actions:

- `create task: Revise current electricity`
- `save note: Remember to practise Nernst equation numericals`
- `send WhatsApp to 919999999999: I will call later`

Review the exact payload and choose **Reject** or **Approve once**. A proposal does nothing until approved. External integrations must also be configured.

## Files and research

Upload a PDF up to 25 MB, then index it. Ask document questions from Assistant or Research; citations include file and page. Image-only PDFs currently require future OCR support. Saved public sources can be queried separately.

## Browser

- **Reader browser:** safely extracts a bounded public HTML page without running it in the client.
- **Controlled browser:** start an isolated Playwright session, navigate/read, enter a selector, and propose click/type. Interaction requires approval.

Do not use controlled browser automation for passwords, payments or irreversible account changes during alpha.

## Communications

Communications shows Gmail search/read, email draft proposals and official WhatsApp Cloud API message proposals. These are optional and display configuration errors honestly. Automatic email replies and personal WhatsApp Web automation are not enabled.

## Notes, tasks and calendar

Create/edit notes, use AI transforms when a model is configured, manage task columns and schedule calendar events. Canvas supports drawing, highlighting, erasing, undo and PNG export; cloud canvas persistence is not complete.

## Automations

Create scheduled or manual briefs, enable/pause/delete them, run manually and inspect run history. Read-only briefs may run automatically. External effects remain approval-gated. Timezone controls, retries, cancellation and dead-letter management remain future work.

## Integrations and Settings

Integrations shows actual readiness. Model status includes health, availability, 60-second RPM/token use, latency, cooldown and errors. `disabled` means the feature is optional and no credentials are configured.

Settings persists timezone, response style, default weather coordinates, cycle visibility, automatic freshness search and reminder discovery. Its diagnostics invoke real non-destructive backend checks; Gmail and WhatsApp tests never send a message. Appearance is stored on the current device, while assistant preferences are stored through the owner-scoped settings API.

## Themes and devices

Use the sun/moon button for light/dark mode. The PWA is installable. Expo Android and Tauri Windows are foundations and do not yet provide complete PWA feature parity or signed production releases.

## Data warning

Local alpha data is stored primarily in SQLite. Until Postgres migration and backups are complete, do not treat hosted data as irreplaceable. Export important notes separately.
