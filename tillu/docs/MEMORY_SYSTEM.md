# TILLU private layered memory

TILLU's memory is owner-controlled and built by and for Heoster.

## Layers

- `identity`: stable facts about Heoster.
- `people`: friends, contacts, and relationships; contact details are marked sensitive.
- `preferences`: likes, dislikes, response and workflow preferences.
- `projects`: things Heoster builds, studies, or maintains.
- `routines`: approved habits and routine constraints.
- `episodic`: explicit experiences and, when enabled, TILLU activity summaries.

## Capture policy

- Explicit phrases such as “remember…” create an approval proposal before persistence.
- TILLU does not silently monitor the device, GPS, microphone, other apps, or browsing outside its controlled browser.
- `activity_tracking_enabled` is off by default. If Heoster enables it, TILLU records summaries of approved actions performed inside TILLU only.
- `proactive_planning_enabled` is off by default. If enabled, TILLU may suggest one grounded routine adjustment; it still cannot create tasks, events, messages, or automations without approval.
- Sensitive people/contact memory remains private and owner-scoped.

## Control

The Memory page lists all active memories and supports explicit creation and deletion. Settings control memory use, proactive suggestions, and in-app activity tracking. API endpoints support list, create, delete, and layer-scoped clearing.

## Production

Apply `supabase/migrations/009_private_memory_layers.sql`. Live RLS behavior must still be verified with Heoster's configured Supabase project before hosted-production readiness is claimed.
