# Tillu AI Study OS — First-Time Setup

> Complete this guide once before running `run.bat` for the first time.
> After setup, every future launch is just double-clicking `run.bat`.

---

## Prerequisites

| Tool | Minimum version | Where to get it |
|------|-----------------|-----------------|
| Python | 3.11+ | https://www.python.org/downloads/ |
| Node.js | 18+ | https://nodejs.org/ |
| Git | any | https://git-scm.com/ |

Verify you have them:

```cmd
python --version
node --version
npm --version
```

---

## Step 1 — Get API keys

You need accounts on three services (all have free tiers):

### Supabase (database)
1. Go to https://supabase.com → New project
2. After creation open **Project Settings → API**
3. Copy **Project URL** and **anon / public** key

### Groq (primary AI)
1. Go to https://console.groq.com → API Keys → Create key
2. Copy the key

### Cerebras (fallback AI)
1. Go to https://cloud.cerebras.ai → API Keys → Create key
2. Copy the key

---

## Step 2 — Fill in `backend/.env`

Open `backend/.env` (it already exists, just fill in the placeholders):

```
SUPABASE_URL=https://xxxxxxxxxxxx.supabase.co
SUPABASE_ANON_KEY=eyJh...
GROQ_API_KEY=gsk_...
CEREBRAS_API_KEY=csk-...
```

Leave everything else at its default value for now.

> **Never commit `.env`** — it is already listed in `.gitignore`.

---

## Step 3 — Create `frontend/.env.local`

Copy the example file:

```cmd
copy frontend\.env.local.example frontend\.env.local
```

No edits needed unless you changed the default ports.

---

## Step 4 — Run the database migrations

1. Open your Supabase project → **SQL Editor**
2. Paste and run `supabase/migrations/001_initial_schema.sql`
3. Paste and run `supabase/migrations/002_seed_data.sql`

This creates all 11 tables and seeds the five CBSE Class 12 subjects with their chapters.

---

## Step 5 — Install Python dependencies

```cmd
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cd ..
```

---

## Step 6 — Install frontend dependencies

```cmd
cd frontend
npm install
cd ..
```

---

## Step 7 — (Optional) Add a notification chime

The reminder system plays a short audio chime. Drop any short sound file into:

```
backend/assets/chime.mp3
```

If the file is absent, a warning is logged and the other two notification channels (Windows toast + dashboard banner) still fire normally.

---

## Step 8 — Launch

```cmd
run.bat
```

Or directly:

```cmd
python start.py
```

The launcher will:
1. Start the FastAPI backend on port 8000
2. Wait for `/health` to return 200 (up to 30 seconds)
3. Start the Next.js frontend on port 3000
4. Print the dashboard URL when both are ready

Open **http://localhost:3000** in your browser.
The API explorer is at **http://localhost:8000/docs**.

Press `Ctrl+C` to stop both processes.

---

## Optional — Voice interaction (Phase 4)

Voice is off by default. To enable it:

1. Get a Sarvam API key from https://dashboard.sarvam.ai
2. Edit `backend/.env`:
   ```
   SARVAM_API_KEY=your-sarvam-api-key
   SARVAM_ENABLED=true
   ```
3. Restart the app. The microphone button on the Home page will become active.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ModuleNotFoundError` on startup | Run `pip install -r requirements.txt` inside the `backend/` venv |
| Backend exits immediately | Check `SUPABASE_URL` and `SUPABASE_ANON_KEY` in `backend/.env` |
| Frontend shows "Cannot connect to backend" | Ensure the backend is running and `NEXT_PUBLIC_BACKEND_URL` in `frontend/.env.local` matches |
| "audio output unavailable" in logs | Place `chime.mp3` in `backend/assets/` or ignore — toast + WS still fire |
| Port already in use | Change `BACKEND_PORT` / `FRONTEND_PORT` in `backend/.env` (and update `frontend/.env.local` to match) |

---

## Directory quick-reference

```
tillu-study-os/
├── run.bat                   ← double-click to launch on Windows
├── start.py                  ← cross-platform launcher
├── backend/
│   ├── .env                  ← your secrets (fill this in)
│   ├── .env.example          ← reference template
│   ├── requirements.txt
│   ├── assets/chime.mp3      ← optional notification sound
│   └── app/                  ← FastAPI application
├── frontend/
│   ├── .env.local            ← frontend config (copy from .env.local.example)
│   └── app/                  ← Next.js pages
└── supabase/
    └── migrations/           ← run these once in Supabase SQL Editor
        ├── 001_initial_schema.sql
        └── 002_seed_data.sql
```
