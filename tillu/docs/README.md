# TILLU documentation

TILLU is Heoster’s private, single-owner personal AI assistant for general daily assistance, research, browser work, communications, files, planning, automations and Class 12 study. It is built by and for Heoster and is not a public SaaS.

## Documentation map

| Document | Purpose |
|---|---|
| [FEATURE_STATUS.md](FEATURE_STATUS.md) | Source of truth for implemented, partial and missing capabilities |
| [MVP_READINESS.md](MVP_READINESS.md) | End-to-end MVP flows, command forms and production blockers |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Runtime components, data flow and trust boundaries |
| [ADAPTIVE_MULTI_LLM.md](ADAPTIVE_MULTI_LLM.md) | Intent → Planning → Execution routing and self-healing model gateway |
| [API_REFERENCE.md](API_REFERENCE.md) | Current HTTP endpoints and approval flow |
| [CONFIGURATION.md](CONFIGURATION.md) | Environment variables and optional integrations |
| [GETTING_STARTED.md](GETTING_STARTED.md) | Local installation and startup |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Repository layout, checks and contribution rules |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Deployment requirements and release checklist |
| [`../deploy/README.md`](../deploy/README.md) | Separated frontend/backend hosting entry folders |
| [HOSTING_LAYOUT.md](HOSTING_LAYOUT.md) | Exact repository layout and Render/Vercel/Supabase setup |
| [SECURITY.md](SECURITY.md) | Owner boundary, model/tool policy, SSRF and secrets |
| [USER_GUIDE.md](USER_GUIDE.md) | Using Assistant, Browser, Communications, files and automations |
| [ARCHITECTURE_AUDIT.md](ARCHITECTURE_AUDIT.md) | Historical and current security/reliability findings |

## Documentation policy

- `FEATURE_STATUS.md` describes what works now; plans must not be presented as shipped.
- Optional Gmail, WhatsApp and model providers must remain optional.
- Production claims require live tests with the relevant cloud credentials.
- Security findings remain documented even when public multi-user support is out of scope.
