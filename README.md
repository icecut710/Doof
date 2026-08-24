# DOOF v0.2 Alpha

**Private collaborative AI OS** Not a chatbot wrapper.

DOOF is a continuously improving local-first AI system where knowledge persists, training folds memory into versioned brains, and everyone connected to the same instance shares one intelligence state.

## Vision

- Knowledge can be added and is permanent
- Training uses stored knowledge
- The AI improves over time
- Everyone on the same DOOF network inherits the same brain
- Feels like owning a personal evolving AI (Raycast / Linear / Arc / Vision Pro energy)

## Sign in

- **First launch** opens a centered login window (DOOF logo + email/password).
- "Create account" → first account is **Owner**; friends later join as **Trusted Users**.
- **Join existing brain** lets you point at a friend's DOOF API host (LAN) to share the
  same memory + training data + compute pool. Sessions are remembered locally.
- Email/password is stored locally (data/profiles.json) unless **Supabase auth** is
  configured by setting `SUPABASE_URL` + an anon key in `.env`.
- Google / X buttons are placeholders ready for Supabase OAuth.

## What you can do

| Surface | Capability |
|---------|------------|
| **Chat** | Talks as DOOF using shared memory (Brain `v1.0.x` after training) |
| **Memory** | Add a fact like “Kaeden likes futuristic dark UI” — permanent, visible to every node |
| **Training** | Start Training folds memory into a new version (`1.0.0` → `1.0.1`) with live loss & epoch |
| **Network** | Your machine reports in as a worker node (hardware + heartbeat) |
| **Models** | Checkpoints, active brain version, architecture |
| **Hardware** | CUDA / MPS / CPU, cores, platform |
| **Settings** | Inference params, compute sharing, cloud status |

The **Naddaf** portrait sits in the window as the cinematic core — glass panels, violet glow, centered desktop frame.

## Quick start

```bash
git clone https://github.com/icecut710/Doof.git
cd Doof

python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

# Optional: train a checkpoint
python -m doof train --epochs 5

# Terminal 1 — API (shared brain + network)
python -m doof serve

# Terminal 2 — UI
cd frontend && npm install && npm run build && npm run preview
# → http://127.0.0.1:8080
```

Or:

```bash
chmod +x startup.sh && ./startup.sh
```

Desktop window:

```bash
python -m doof gui
```

## Shared intelligence (local alpha)

Without external cloud, DOOF still runs a **single-instance shared brain** on the API process:

- `data/memory.json` — permanent memory items
- `data/profiles.json` — local accounts (Owner / Trusted)
- `data/nodes.json` — network workers + heartbeat
- `data/versions.json` — model version history
- `data/sync_state.json` — last train / brain version / knowledge count
- `data/train.txt` — training corpus (synced from approved memory)

Point multiple friends at the **same API host** (LAN IP + port `8765`) so they join the same network and inherit the same intelligence.

### Optional Supabase

```bash
# data/cloud.json
{
  "url": "https://YOUR_PROJECT.supabase.co",
  "anon_key": "YOUR_ANON_KEY"
}
```

Schema: `supabase/migrations/001_doof_schema.sql` + `002_doof_v02_network.sql`

## API

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/health` | service + version |
| POST | `/api/auth/login` `/api/auth/signup` | local profiles |
| GET | `/api/me` | current session profile |
| GET/POST | `/api/memory` | permanent shared memory |
| GET | `/api/network` `/api/nodes` | workers online |
| POST | `/api/nodes/heartbeat` | hardware + presence |
| GET | `/api/versions` | brain version history |
| GET | `/api/sync` | shared sync state |
| GET | `/api/model` `/api/checkpoints` `/api/hardware` | system |
| POST | `/api/generate` | chat (uses knowledge context) |
| POST | `/api/training/start` `/api/training/stop` | collaborative train |

## Model

- Decoder-only Transformer (~4.9M params)
- `d_model=256`, 8 heads, 6 layers
- Byte-level tokenizer (vocab 259)
- Checkpoint: `checkpoints/doof_v01.pt`
- Brain versions bump on successful training (`1.0.0` → `1.0.1` → …)

## Windows EXE

A full offline installer with bundled runtime is **not** produced from every environment. From a Windows machine with the stack installed:

Use the deterministic pipeline (builds the frontend, then the EXE):

```bat
packaging\build.bat
```

Zip the **entire** `dist\DOOF` folder (`DOOF.exe` **and** `_internal`). Sending only the EXE causes a missing Python DLL on friends' PCs. Friend machines do not need Python or Node.

Default friend builds use CPU torch so the zip is hundreds of MB, not 5 GB. Set `DOOF_KEEP_CUDA=1` before `build.bat` if you need a CUDA owner build.

Packaging goal: `DOOF.exe` + `DOOF Setup.exe` with frontend, backend, runtime — no separate Python/Node install for end users.

## Status

**v0.2 Alpha** — private collaborative network. Teach it. Train it. Everyone inherits the same intelligence.

---

DOOF · local-first · shared brain · cinematic control center
