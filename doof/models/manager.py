"""Model registry + local cache with SHA-256 verification."""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


@dataclass
class ModelInfo:
    model_id: str
    version: str
    label: str = ""
    format: str = "doof-pt"  # doof-pt | gguf | onnx
    size_bytes: int = 0
    sha256: str = ""
    download_url: str = ""
    channel: str = "stable"
    status: str = "approved"  # approved | candidate | archived
    cpu_supported: bool = True
    gpu_supported: bool = True
    min_ram_gb: float = 4.0
    recommended_ram_gb: float = 8.0
    min_vram_gb: float = 0.0
    recommended_vram_gb: float = 0.0
    notes: str = ""
    local_path: str | None = None
    installed: bool = False
    verified: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def cache_dir() -> Path:
    try:
        from doof.paths import user_data_dir

        d = user_data_dir() / "models"
    except Exception:
        d = Path.home() / ".doof" / "models"
    d.mkdir(parents=True, exist_ok=True)
    return d


def local_path(model_id: str, version: str) -> Path:
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in model_id)
    safe_ver = "".join(c if c.isalnum() or c in "._-" else "_" for c in version)
    return cache_dir() / f"{safe_id}-{safe_ver}.pt"


def verify_checksum(path: Path, expected: str) -> bool:
    if not expected or not path.is_file():
        return False
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().lower() == expected.lower()


def _builtin_registry() -> list[ModelInfo]:
    """Seed registry for the small DOOF transformer checkpoint shipped in checkpoints/."""
    from doof.paths import bundle_root

    root = bundle_root()
    ckpt = root / "checkpoints" / "doof_v01.pt"
    size = int(ckpt.stat().st_size) if ckpt.is_file() else 0
    sha = ""
    if ckpt.is_file() and size < 80 * 1024 * 1024:
        try:
            h = hashlib.sha256()
            with ckpt.open("rb") as fh:
                for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                    h.update(chunk)
            sha = h.hexdigest()
        except Exception:
            sha = ""
    return [
        ModelInfo(
            model_id="doof-base",
            version="0.3.0",
            label="DOOF Base",
            format="doof-pt",
            size_bytes=size,
            sha256=sha,
            download_url="",
            channel="stable",
            status="approved",
            cpu_supported=True,
            gpu_supported=True,
            min_ram_gb=2.0,
            recommended_ram_gb=4.0,
            min_vram_gb=0.0,
            recommended_vram_gb=2.0,
            notes="Small local transformer checkpoint. Training improves it over time.",
            local_path=str(ckpt) if ckpt.is_file() else None,
            installed=ckpt.is_file(),
            verified=bool(sha and ckpt.is_file()),
        )
    ]


def _fetch_remote_registry() -> list[ModelInfo]:
    url = os.environ.get("DOOF_MODEL_REGISTRY_URL") or ""
    if not url:
        # Prefer Supabase table if DB adapter supports it
        try:
            from database import get_db

            db = get_db()
            if hasattr(db, "list_models"):
                rows = db.list_models() or []
                out: list[ModelInfo] = []
                for r in rows:
                    out.append(
                        ModelInfo(
                            model_id=str(r.get("model_id") or r.get("id") or ""),
                            version=str(r.get("version") or "0"),
                            label=str(r.get("label") or ""),
                            format=str(r.get("format") or "doof-pt"),
                            size_bytes=int(r.get("size_bytes") or 0),
                            sha256=str(r.get("sha256") or ""),
                            download_url=str(r.get("download_url") or ""),
                            channel=str(r.get("channel") or "stable"),
                            status=str(r.get("status") or "approved"),
                            cpu_supported=bool(r.get("cpu_supported", True)),
                            gpu_supported=bool(r.get("gpu_supported", True)),
                            min_ram_gb=float(r.get("min_ram_gb") or 4),
                            recommended_ram_gb=float(r.get("recommended_ram_gb") or 8),
                            min_vram_gb=float(r.get("min_vram_gb") or 0),
                            recommended_vram_gb=float(r.get("recommended_vram_gb") or 0),
                            notes=str(r.get("notes") or ""),
                        )
                    )
                return [m for m in out if m.model_id]
        except Exception:
            pass
        return []
    try:
        req = Request(url, headers={"Accept": "application/json", "User-Agent": "DOOF/0.3"})
        with urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        models = data.get("models") or data if isinstance(data, list) else []
        out = []
        for r in models:
            if not isinstance(r, dict):
                continue
            out.append(
                ModelInfo(
                    model_id=str(r.get("model_id") or ""),
                    version=str(r.get("version") or "0"),
                    label=str(r.get("label") or ""),
                    format=str(r.get("format") or "doof-pt"),
                    size_bytes=int(r.get("size_bytes") or 0),
                    sha256=str(r.get("sha256") or ""),
                    download_url=str(r.get("download_url") or ""),
                    channel=str(r.get("channel") or "stable"),
                    status=str(r.get("status") or "approved"),
                    cpu_supported=bool(r.get("cpu_supported", True)),
                    gpu_supported=bool(r.get("gpu_supported", True)),
                    min_ram_gb=float(r.get("min_ram_gb") or 4),
                    recommended_ram_gb=float(r.get("recommended_ram_gb") or 8),
                    min_vram_gb=float(r.get("min_vram_gb") or 0),
                    recommended_vram_gb=float(r.get("recommended_vram_gb") or 0),
                    notes=str(r.get("notes") or ""),
                )
            )
        return [m for m in out if m.model_id]
    except Exception:
        return []


def list_registry() -> list[ModelInfo]:
    remote = _fetch_remote_registry()
    builtin = _builtin_registry()
    by_key: dict[str, ModelInfo] = {}
    for m in builtin + remote:
        key = f"{m.model_id}@{m.version}"
        by_key[key] = m
    # Mark installed from cache
    for m in by_key.values():
        p = local_path(m.model_id, m.version)
        if m.local_path and Path(m.local_path).is_file():
            m.installed = True
            if m.sha256:
                m.verified = verify_checksum(Path(m.local_path), m.sha256)
        elif p.is_file():
            m.installed = True
            m.local_path = str(p)
            m.verified = verify_checksum(p, m.sha256) if m.sha256 else True
    return list(by_key.values())


def list_cached() -> list[dict[str, Any]]:
    items = []
    for p in cache_dir().glob("*.pt"):
        items.append({"path": str(p), "name": p.name, "size": p.stat().st_size})
    return items


def model_compatible(model: ModelInfo, hw: dict[str, Any] | None = None) -> tuple[bool, str]:
    from doof.runtime import probe_hardware

    hw = hw or probe_hardware()
    ram = float(hw.get("ram_gb") or 0)
    if ram and ram < model.min_ram_gb:
        return False, f"Needs at least {model.min_ram_gb} GB RAM (this machine: {ram} GB)"
    vram = 0.0
    devices = hw.get("cuda_devices") or []
    if devices:
        vram = float(devices[0].get("total_memory_gb") or 0)
    if model.min_vram_gb > 0 and vram < model.min_vram_gb:
        if not model.cpu_supported:
            return False, f"Needs {model.min_vram_gb} GB VRAM (have {vram} GB)"
        return True, "GPU VRAM low — will use CPU"
    if not model.cpu_supported and not hw.get("cuda_available"):
        return False, "GPU required; CUDA not available"
    return True, "Compatible"


def ensure_model(model_id: str, version: str | None = None) -> ModelInfo:
    """Ensure model is cached and verified. Downloads if URL present."""
    models = list_registry()
    matches = [m for m in models if m.model_id == model_id]
    if version:
        matches = [m for m in matches if m.version == version]
    if not matches:
        raise FileNotFoundError(f"Model {model_id} not in registry")
    matches.sort(key=lambda m: m.version, reverse=True)
    model = matches[0]

    # Prefer existing local path (bundled checkpoint)
    if model.local_path and Path(model.local_path).is_file():
        if model.sha256 and not verify_checksum(Path(model.local_path), model.sha256):
            raise ValueError(f"Checksum failed for {model.local_path}")
        model.installed = True
        model.verified = True
        return model

    dest = local_path(model.model_id, model.version)
    if dest.is_file():
        if model.sha256 and not verify_checksum(dest, model.sha256):
            dest.unlink(missing_ok=True)
        else:
            model.local_path = str(dest)
            model.installed = True
            model.verified = True
            return model

    if not model.download_url:
        # Fall back to bundled checkpoints path
        from doof.paths import bundle_root

        ckpt = bundle_root() / "checkpoints" / "doof_v01.pt"
        if ckpt.is_file():
            model.local_path = str(ckpt)
            model.installed = True
            model.verified = True
            return model
        raise FileNotFoundError(
            f"Model {model.model_id}@{model.version} is not cached and has no download_url"
        )

    # Download
    req = Request(
        model.download_url,
        headers={"User-Agent": "DOOF/0.3", "Accept": "application/octet-stream"},
    )
    tmp = dest.with_suffix(".part")
    try:
        with urlopen(req, timeout=300) as resp, tmp.open("wb") as out:
            while True:
                chunk = resp.read(256 * 1024)
                if not chunk:
                    break
                out.write(chunk)
        if model.sha256 and not verify_checksum(tmp, model.sha256):
            tmp.unlink(missing_ok=True)
            raise ValueError("Downloaded model failed SHA-256 verification")
        tmp.replace(dest)
    except URLError as e:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"Model download failed: {e}") from e

    model.local_path = str(dest)
    model.installed = True
    model.verified = True
    # Write sidecar metadata
    meta = dest.with_suffix(".json")
    meta.write_text(json.dumps(model.as_dict(), indent=2), encoding="utf-8")
    return model


def resolve_active_model() -> ModelInfo:
    """Pick the approved model for this node."""
    pref = os.environ.get("DOOF_MODEL_ID", "doof-base")
    models = [m for m in list_registry() if m.status == "approved"]
    preferred = [m for m in models if m.model_id == pref]
    pool = preferred or models or _builtin_registry()
    pool.sort(key=lambda m: m.version, reverse=True)
    return ensure_model(pool[0].model_id, pool[0].version)
