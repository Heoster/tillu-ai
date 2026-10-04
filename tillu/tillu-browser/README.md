# tillu-browser

A mini Electron browser that lets the **Tillu agent control a real browser window** remotely, while you can also interact with it manually — no Playwright, no headless Chromium, no display server required.

## Why this exists

The Render runtime runs Playwright in a headless Docker container. That stack is heavy and fragile on free-tier hosts. `tillu-browser` runs **on your local machine** as an Electron app:

- Opens a real Chromium window (Electron's built-in renderer)
- Exposes the exact same `/api/browser-control/*` HTTP API the brain already calls
- Streams a live MJPEG view to the control-panel UI so you can watch what the agent is doing
- You can also drive the browser manually through the UI — click, type, navigate

---

## Setup

```bash
cd tillu-browser
npm install          # installs electron + express locally
```

---

## Run

```bash
npm start
```

This opens two windows:
1. **Control Panel** — the operator UI (URL bar, element inspector, live MJPEG canvas)
2. **Agent View** — the actual browser the agent drives (hidden by default)

To reveal the agent view as a normal window:

```bash
npm start -- --show-agent-view
```

---

## Connect the brain

In `apps/api/.env` (or your deployment env), set:

```env
TILLU_RUNTIME_URL=http://localhost:7788
```

The brain's `service_role` is already `brain` by default, which makes every `browser_start / browser_navigate / browser_action` proposal route through `internal_rpc` to this address.

The app binds to `127.0.0.1` only — it is never exposed to the network.

---

## Optional: bearer token auth

Set the same secret in both places to require authentication:

```bash
# tillu-browser side (environment variable before npm start)
TILLU_BROWSER_SECRET=mysecret npm start

# brain side (.env)
TILLU_INTERNAL_SECRET=mysecret
```

---

## Custom port

```bash
TILLU_BROWSER_PORT=8899 npm start
# and set TILLU_RUNTIME_URL=http://localhost:8899 in the brain
```

---

## API surface

The Express server in `api.js` implements:

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/browser-control/sessions` | Start a session |
| `DELETE` | `/api/browser-control/sessions/:sid` | Close session |
| `GET` | `/api/browser-control/sessions/:sid` | DOM snapshot + elements |
| `POST` | `/api/browser-control/navigate` | Navigate to URL |
| `POST` | `/api/browser-control/sessions/:sid/go-back` | Go back |
| `POST` | `/api/browser-control/sessions/:sid/go-forward` | Go forward |
| `POST` | `/api/browser-control/sessions/:sid/reload` | Reload |
| `POST` | `/api/browser-control/sessions/:sid/screenshot` | Base64 JPEG |
| `GET` | `/api/browser-control/sessions/:sid/stream` | MJPEG stream |
| `POST` | `/api/browser-control/mouse/click` | Mouse click at x,y |
| `POST` | `/api/browser-control/mouse/move` | Mouse move |
| `POST` | `/api/browser-control/mouse/scroll` | Scroll wheel |
| `POST` | `/api/browser-control/keyboard/press` | Key press |
| `POST` | `/api/browser-control/keyboard/type` | Type text |
| `POST` | `/api/browser-control/action` | Selector-based action (click/type/check/select/press/scroll) |
| `GET` | `/api/browser-control/history` | Navigation history |
| `DELETE` | `/api/browser-control/history` | Clear history |
| `GET` | `/health` | Liveness check |

All coordinates are in the agent-view's 1280×800 logical viewport.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  Electron app                    │
│                                                  │
│  ┌──────────────┐      ┌─────────────────────┐  │
│  │ controlPanel │ IPC  │     agentView        │  │
│  │  (UI window) │◄────►│  (browsing window)   │  │
│  └──────┬───────┘      └─────────┬───────────┘  │
│         │                        │               │
│         └──────────┬─────────────┘               │
│                    │ webContents API              │
│         ┌──────────▼─────────────┐               │
│         │   Express API server   │               │
│         │   localhost:7788       │               │
│         └──────────▲─────────────┘               │
└────────────────────│────────────────────────────┘
                     │ HTTP
              ┌──────┴───────┐
              │  Tillu brain │
              │  (FastAPI)   │
              └──────────────┘
```

- `main.js` — Electron main process: creates both windows, starts Express, handles IPC
- `api.js` — Express server: translates HTTP calls into `webContents` API calls on the agent view
- `preload.js` — context bridge: lets the control-panel renderer call IPC safely
- `ui/index.html` — the control panel UI (MJPEG canvas + element inspector)
