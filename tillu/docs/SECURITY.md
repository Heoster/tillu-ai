# Security

## Identity boundary

TILLU is private and single-owner. Production requires Supabase authentication plus `OWNER_USER_ID` or `OWNER_EMAIL`; every other authenticated identity is rejected. The service-role key remains server-only. Local development identity is forbidden in production.

## Model boundary

Model output is untrusted. Intent and planning models return proposals only. Server code validates registered tools, arguments, ownership, quotas and policy. Read tools execute through the authoritative registry. Writes and external effects use typed, expiring, persisted proposals with explicit approval.

## Action levels

- **Read:** workspace retrieval, current sources, calculator and browser page reading.
- **Write:** tasks, notes, progress and calendar changes.
- **External:** browser interaction, downloads, Gmail/WhatsApp and future outbound services.
- **Sensitive:** credentials, private communications and destructive operations.

Approval is not proof of success; only a completed server execution result is.

## Model/provider safety

The adaptive gateway predicts RPM/TPM pressure, reserves headroom, honors HTTP 429 `Retry-After`, tracks latency and opens circuit breakers. This reduces outages but cannot guarantee zero downtime. Provider keys never enter the client.

## Network and browser safety

- URL scheme, host, credentials, ports and all resolved addresses are checked.
- Private, loopback, link-local, reserved and metadata targets are blocked.
- Safe-reader redirects are rejected.
- Controlled-browser requests are intercepted and revalidated.
- Downloads are HTTPS and trusted-domain constrained.

A fully pinned outbound resolver/egress proxy is still recommended to eliminate DNS-rebinding timing risk.

## Files

- 25 MB transport limit
- PDF signature and strict structure checks
- encrypted-PDF rejection
- 500-page maximum
- extracted-character cap
- quarantine/inspection metadata
- internal paths excluded from API responses

Structural validation is not malware certification. Production parsing should run in a resource-limited worker with malware scanning or equivalent isolation.

## Communications

Gmail and WhatsApp are optional. OAuth refresh tokens and Meta access tokens are backend-only. Outbound drafts/messages require approval. Automatic replies are not enabled. Future auto-reply rules require sender allowlists, loop detection, quiet hours, content limits and auditability.

## Persistence limitations

SQLite remains the active repository for several core routes and is not encrypted or durable on ephemeral Render storage. Do not rely on it for irreplaceable hosted data. Production must complete Postgres repository migration, RLS verification, backups and restore drills.

## Required testing not yet complete

- non-owner rejection and object ownership
- approval replay/expiration/races
- SSRF redirects and DNS rebinding
- malicious PDFs and parser resource exhaustion
- queue lease recovery and idempotency
- automation concurrent claiming
- provider 429, latency and breaker behavior
- Supabase RLS and backups
- end-to-end controlled-browser and communications flows
