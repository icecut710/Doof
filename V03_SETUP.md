# DOOF v0.3 — setup & acceptance

## Pull

```bash
git fetch origin
git checkout fix/production-polish
git pull origin fix/production-polish
```

Final production commits include model manager, DOOF-hosted brain route,
Windows updater helper, and hardware preference APIs.

## Architecture (node model)

```
User UI  →  local DOOF node  →  Supabase control plane
                │                      │
                ├─ local model cache   ├─ nodes / heartbeats
                ├─ contribution OFF    ├─ compute_jobs
                └─ optional GPU/CPU    ├─ model_registry
                                       └─ hosted_services
```

Inference order:

1. Local approved model (Torch)
2. Remote contributing DOOF node (queue + poll)
3. **DOOF-hosted cloud brain** (`DOOF_HOSTED_BRAIN_URL`)
4. Lightweight emergency path (compositional — not a FAQ table)

No third-party AI provider is required.

## Why Status shows CPU

If Status says Device: cpu with 32 cores / 32 GB RAM:

1. **Friend builds** install **CPU-only Torch** by default (`packaging/build.bat`).
2. Rebuild with GPU:

```bat
set DOOF_KEEP_CUDA=1
pip install torch --index-url https://download.pytorch.org/whl/cu124
packaging\build.bat
```

3. A 32-core / 32 GB machine is still a **strong CPU node** for inference,
   embeddings, and remote jobs when contribution is enabled.

Honest reporting separates:

- Physical GPU present?
- CUDA driver usable?
- Packaged Torch has CUDA?
- DOOF inference device preference?

## Model cache

```
%LOCALAPPDATA%\DOOF\models\
```

Metadata: Supabase `model_registry` (migration `006_model_registry.sql`).
Blobs: CDN / download_url with SHA-256 verify. Small `doof-base` may use
bundled `checkpoints/doof_v01.pt`.

## Hosted DOOF brain

```env
DOOF_HOSTED_BRAIN_URL=https://brain.your-domain/v1
DOOF_HOSTED_BRAIN_TOKEN=optional
```

Endpoint contract:

- `GET /health` → `{ label, model, capacity }`
- `POST /generate` → `{ text, model }` with JSON `{ prompt, system, temperature, max_new_tokens }`

## Supabase

```
%LOCALAPPDATA%\DOOF\.env
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
```

Apply migrations `001`–`006`.

## Updates

1. Publish `releases/manifest.json` with `download_url` + `sha256`.
2. User opens **Updates** → Check → Update now.
3. Client stages zip under `%LOCALAPPDATA%\DOOF\updates\`.
4. Helper `packaging/updater/doof_updater.py` (or `Update-DOOF.ps1`) runs after exit.

**Windows EXE swap cannot be fully verified in this CI sandbox.** Test on a real Windows install.

## Build

```bat
packaging\build.bat
```

Zip entire `dist\DOOF\` (EXE + `_internal`).

## Two-machine test (required on hardware)

1. A and B sign in, both online.
2. B: Contribution ON, accept inference.
3. A: chat while local model forced weak / disabled.
4. Job appears in queue → B claims → result returns to A.
5. B turns contribution OFF → A no longer schedules to B.
