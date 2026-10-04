# Required Honcho integration

Honcho is a required production dependency of TILLU Brain. It is not required by Runtime and may be omitted in local test mode.

## Production configuration

```env
HONCHO_REQUIRED=true
HONCHO_API_KEY=hch-...
HONCHO_BASE_URL=https://api.honcho.dev
HONCHO_WORKSPACE_ID=tillu-heoster
HONCHO_USER_PEER=heoster
HONCHO_ASSISTANT_PEER=tillu
HONCHO_REASONING_LEVEL=medium
```

Use one stable workspace and two stable peers. Each TILLU conversation maps to a Honcho session with the same conversation ID.

## Runtime loop

1. Before model response synthesis, Brain asks the Heoster peer a session-aware dialectic question based on the current request.
2. The bounded dialectic response is injected into orchestration context.
3. After the exchange, the user and assistant messages are uploaded together to that Honcho session.
4. Honcho performs background derivation and updates representations.
5. TILLU's local/Supabase evidence-backed memory remains available for audit, approvals, citations, and fail-safe data ownership, but it no longer substitutes for required production Honcho dialectic recall.

## Startup and health

Production Brain refuses startup if Honcho configuration is missing or the workspace metadata call is unreachable. `/api/health/ready` checks configuration and connectivity. Authenticated `/api/health/dependencies` reports Honcho state without exposing its key.

## APIs

- `GET /api/honcho/status`
- `POST /api/honcho/recall`
- `GET /api/honcho/sessions/{conversation_id}/context`

## Privacy

Conversation content sent to managed Honcho leaves TILLU's Supabase boundary. Heoster must choose managed Honcho knowingly or self-host Honcho and point `HONCHO_BASE_URL` to that deployment. Never expose `HONCHO_API_KEY` to Vercel or browser code.
