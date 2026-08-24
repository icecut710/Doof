# Rebuild required — Torch circular import fix

## What broke

Frozen `DOOF.exe` reported:

```
AttributeError: partially initialized module 'torch'
has no attribute 'distributed'
```

**Cause:** `packaging/rthooks/pyi_rth_doof_torch.py` and `doof/runtime.py` installed a **fake** `torch.distributed` into `sys.modules` *before* `import torch` finished. Torch’s own `__init__` then hit a circular initialization and never exposed CUDA or `.distributed`.

Chat fell back to memory-only answers and Status showed CPU-only.

## What we fixed

1. Runtime hook only stubs the misspelled name `torchdistribute` — **never** `torch.distributed`.
2. `doof.spec` **no longer excludes** `torch.distributed`.
3. `runtime.import_torch()` imports torch normally; soft-patches only *after* success.
4. Clears leftover broken stubs from older builds when possible.
5. Device preference API: `GET/POST /api/device` (`auto` | `cpu` | `gpu` | `low_end`).
6. Inference uses `resolve_device()`.
7. Chat fallback uses `doof.brain` compositional answers — not “I do not have that in memory yet” for every question.
8. Supabase status distinguishes `not_configured` / `unauthorized` / `connected` / `unreachable`.

## You must rebuild the EXE

Old `dist/DOOF` still contains the broken hook. Pull and rebuild:

```bat
cd Doof
git checkout fix/production-polish
git pull origin fix/production-polish

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install torch --index-url https://download.pytorch.org/whl/cu124
REM or CPU wheel if you truly want CPU-only:
REM pip install torch --index-url https://download.pytorch.org/whl/cpu

pip install pyinstaller PySide6
cd frontend && npm install && npm run build && cd ..
python packaging/build_exe.py
```

### GPU wheel note

If Status should show your RTX, install a **CUDA-enabled** PyTorch into the venv *before* packaging. Packaging a CPU-only torch will correctly report no CUDA.

### Supabase 401

Put a valid **anon** key (not service role in the client path) in:

- `%LOCALAPPDATA%\DOOF\.env`, or
- next to `DOOF.exe` as `.env`, or
- `%LOCALAPPDATA%\DOOF\cloud.json` as `{"url":"...","anon_key":"..."}`

Status should then say **Connected** or **Unauthorized** (bad key) — not a vague “Local kitchen only” when keys are present.

## Verify after rebuild

1. Open DOOF → Status → Brain should not show the circular-import traceback.
2. Hardware should list GPU if the packaged torch has CUDA.
3. Chat “Tell me about yourself” should not answer only with the memory-train message.
4. `GET http://127.0.0.1:8765/api/device` returns preference + options.
