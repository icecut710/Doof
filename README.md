# DOOF v0.1

Local personal AI desktop application. Your own small transformer, trained on your data, running offline.

## Features

- **Chat** — real local inference from your checkpoint
- **Knowledge** — edit `data/train.txt` training corpus
- **Training** — start/stop training, live loss curve
- **Models** — inspect architecture, parameters, checkpoints
- **Hardware** — CUDA / CPU / MPS detection
- **Settings** — temperature, max tokens

## Quick start

```bash
pip install -r requirements.txt

# Train (creates checkpoints/doof_v01.pt)
python -m doof train --epochs 5

# Terminal 1 — API
python -m doof serve

# Terminal 2 — UI
cd frontend && npm install && npm run build && npm run preview
# open http://127.0.0.1:8080

# Or desktop GUI (PySide6 + frontend/dist):
python -m doof gui
```

## CLI

| Command | Description |
|---------|-------------|
| `python -m doof` / `gui` | Desktop window |
| `python -m doof serve` | API on :8765 |
| `python -m doof chat` | Terminal chat |
| `python -m doof train` | Train model |

## Model

- Decoder-only Transformer (~4.9M params)
- d_model=256, 8 heads, 6 layers
- Byte-level tokenizer (vocab 259)
- Checkpoint: `checkpoints/doof_v01.pt`

## API

- `GET  /api/health` `/api/model` `/api/hardware` `/api/checkpoints` `/api/training` `/api/knowledge` `/api/settings`
- `POST /api/generate` `{ "prompt": "..." }`
- `POST /api/training/start` `/api/training/stop`
- `POST /api/knowledge` `/api/settings`

## Windows EXE

```bash
pip install pyinstaller
pyinstaller --noconfirm packaging/doof.spec
```
