# What TILLU Is — Honest Capability and Readiness Guide

**Updated:** 1 October 2026  
**Product:** TILLU — a private personal AI assistant built by and for Heoster

## Honest definition

TILLU is a private, single-owner personal AI assistant and agent harness. It is more than a chatbot: TILLU can reason, select tools, retrieve private information, create plans, request permission, and execute registered actions.

TILLU is currently a **strong working local MVP**, not yet a fully deployed, always-online production Jarvis system.

## What TILLU can do now

### Understand normal language

Special command syntax is not required for core workflows. Heoster can say things such as:

- “Remind me to revise electrostatics.”
- “Remember my friend Aman’s email.”
- “Make a canvas for ray diagrams.”
- “Schedule Physics revision tomorrow at 6 pm.”
- “Complete the task Revise optics.”
- “Create a daily weather brief.”
- “Find current education news.”
- “Search my PDFs for Kirchhoff’s laws.”

When no model is configured, conservative deterministic understanding handles common actions. Configured models provide broader natural-language understanding.

### Call read tools automatically

TILLU has approximately 20 registered read capabilities:

- Live web search
- Safe webpage reading
- Weather
- News
- Technology trends
- Private PDF/document search
- Tasks and calendar
- Study progress and syllabus
- Notes
- Files
- Saved research
- Canvas list
- Automations and run history
- Browser history
- Settings
- Activity log
- Private memory
- Gmail search when configured
- Calculator
- Current system context

Read tools can run automatically when relevant.

### Execute approval-gated actions

TILLU has approximately 29 typed action capabilities:

- Create, update, complete, and delete tasks
- Create, update, and delete notes
- Create, rename, clear, and delete canvases
- Create, update, and delete calendar events
- Create, update, run, pause, and delete automations
- Update study progress
- Save and delete research sources
- Index and delete files
- Start, navigate, and control its browser
- Clear browser history
- Create Gmail drafts
- Send WhatsApp Cloud API messages
- Update settings
- Create, delete, or clear private memories

Consequential actions do not execute until Heoster approves them.

### Create and execute plans

TILLU can compile a plan containing up to eight registered capabilities. It can:

1. Select ordered capabilities.
2. Display every step and argument.
3. Wait for approval.
4. Atomically claim the plan.
5. Execute each step sequentially.
6. Save progress and individual results.
7. Stop and report failure if a step fails.
8. Block duplicate execution.

TILLU cannot execute arbitrary shell commands, arbitrary Python, or unregistered functions.

### Use a bounded reasoning cycle

The LangGraph brain follows:

1. Detect intent.
2. Create a read-tool plan.
3. Call tools.
4. Assemble evidence.
5. Evaluate whether evidence is sufficient.
6. Revise no more than twice.
7. Produce an answer.
8. Verify citations.

This prevents unlimited autonomous loops.

### Stream brain activity

The unified Assistant UI uses SSE to show:

- Request accepted
- Intent detection
- Planning
- Tool execution
- Evidence verification
- Response generation
- Final result

Generation can be cancelled. Orchestration phases are streamed, but individual model tokens are not yet streamed.

### Control a real browser

TILLU runs real server-side Chromium through Playwright. It supports:

- Isolated sessions
- URL navigation
- Reading page content
- Screenshots
- Clicking
- Typing
- Key presses
- Manual control through the Browser UI
- Automatic Chat-generated browser proposals

Page-changing operations remain approval-gated.

### Remember personal information

TILLU has private memory layers for:

- Identity
- Friends and contacts
- Preferences
- Projects
- Routines
- Experiences

Memory is owner-visible and deletable. Sensitive contact details are marked accordingly.

TILLU does not secretly monitor Heoster’s device, microphone, GPS, or other applications. Optional activity tracking applies only to approved activity inside TILLU.

### Use multiple AI providers

The model library can catalog hundreds of models. The active routing pool includes free/free-tier models from:

- Groq
- Cerebras
- Google Gemini, including Gemini 2.5 Flash
- Cloudflare Workers AI
- OpenRouter

The adaptive router considers task phase, capabilities, cost, latency, rate limits, provider health, cooldowns, and circuit-breaker state.

A model appearing in the library does not mean it is callable. Provider API keys must be configured.

## Current limitations

### Not hosted-production ready

Production Supabase code exists, but the real project has not been credential-tested. Remaining work includes:

- Apply migrations through `009_private_memory_layers.sql`.
- Verify owner and non-owner RLS.
- Test Storage operations.
- Test queue RPCs.
- Test atomic proposal and plan claims.
- Run every repository contract against real Supabase.

### AI providers are not currently connected

Without keys, free-form synthesis and natural-language planning are less flexible. Deterministic tools and common natural actions still work. TILLU cannot create provider accounts or API keys automatically.

### PYQ collection is incomplete

The local PYQ background connector still produces demo-style results. It is not yet a complete trusted-source search, download, validation, Storage, and indexing worker.

### Browser sessions are not durable

Sessions live in API process memory. Restarting the backend destroys them, sessions cannot move between servers, and horizontal scaling is unsafe.

### Streaming is incomplete

SSE streams phases and final results, but it does not yet provide individual model-token deltas, durable reconnect after browser refresh, resume after server restart, or complete background-run continuation.

### Plans are limited to registered capabilities

TILLU cannot invent arbitrary backend functionality. Failed multi-step plans stop safely, but completed earlier steps are not automatically rolled back.

### RAG is mostly lexical

PDF retrieval supports bounded parsing, chunks, scoring, and page citations. It still needs OCR, tables and formulas, embeddings, pgvector, hybrid retrieval, reranking, asynchronous ingestion workers, and stronger parser isolation.

### Integrations are incomplete

Gmail still needs OAuth connection UI, token lifecycle management, attachments, MIME normalization, sending, and Gmail watch/webhooks.

WhatsApp still needs webhook verification, incoming messages, templates, delivery receipts, contacts, and opt-in management.

### Proactive behavior is limited

TILLU can suggest routine improvements when explicitly enabled. It does not yet have a durable proactive scheduler, push notifications, quiet hours, snooze, delivery receipts, or reliable cross-device background delivery.

### Mobile and desktop are foundations

Expo and Tauri structures exist, but they do not yet have complete feature parity, secure native token storage, signing, updates, or native notifications.

### Backend and frontend remain too large

`main.py` and `main.jsx` contain too many responsibilities. They need to be separated into feature routes, capability services, approval services, repository interfaces, React feature modules, and dedicated state/streaming logic.

### Testing is still insufficient

There are currently 23 passing backend tests, but critical missing coverage includes live RLS, Supabase repository contracts, browser security and durability, DNS-rebinding defenses, malicious PDF handling, queue retries, provider contracts, complete end-to-end workflows, and frontend browser tests.

## Most important remaining implementation

### Priority 1 — Prove production persistence

- Configure Supabase.
- Apply every migration.
- Verify RLS with owner and non-owner users.
- Test Storage and queue behavior.
- Remove remaining production process-state dependencies.

### Priority 2 — Replace the PYQ demo connector

Build a real worker that searches approved sources, validates redirects, downloads bounded PDFs, quarantines and inspects files, deduplicates them, uploads them to Storage, extracts and indexes content, and reports durable progress.

### Priority 3 — Durable runs and streaming

- Stream actual model tokens.
- Save every run event.
- Add cancellation checkpoints.
- Reconnect by run ID.
- Continue after API restart.

### Priority 4 — Durable browser service

- Session leases and expiration
- Remote browser workers
- Sticky routing
- Encrypted browser state
- Multiple tabs
- Accessibility-tree targets
- Artifact cleanup

### Priority 5 — Complete memory and proactive planning

- Memory conflict detection
- Confidence decay
- Review reminders
- Memory editing
- Routine planner
- Notification delivery
- Explanation of why each memory was used

### Priority 6 — Split the architecture

Move capability execution, approvals, routes, streaming, and integrations into dedicated modules. Split the frontend into Chat, Brain, Browser, Memory, Notes, Canvas, and Settings features.

## Final verdict

TILLU is currently a **functional private AI assistant, agent harness, tool-calling system, controlled browser, memory system, and approval-based plan executor**.

It is capable enough to be genuinely useful locally. It is not yet an always-running production Jarvis because cloud verification, durable execution, real document collection, browser persistence, notifications, integrations, and comprehensive security testing remain unfinished.
