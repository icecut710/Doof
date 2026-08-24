"""Capability detection, lazy torch, low-end guards.

Importing torch is expensive and, in frozen CPU builds, can raise
``ModuleNotFoundError: No module named torchdistribute`` (PyInstaller
excludes ``torch.distributed``; some crash paths strip the dots).

Nothing in the UI thread should import torch. Callers go through this
module, which caches results and never raises on a missing optional dep.
"""
from __future__ import annotations

import os
import platform
import sys
import threading
import types
from typing import Any

_lock = threading.Lock()
_torch_mod: Any = None
_torch_error: str | None = None
_torch_tried = False
_hw_cache: dict[str, Any] | None = None
_hw_cache_at = 0.0

# Install a stub so `import torch.distributed` / `import torchdistribute`
# cannot crash the process even if PyInstaller excluded the real module.
def _install_torch_stubs() -> None:
    if "torchdistribute" not in sys.modules:
        stub = types.ModuleType("torchdistribute")
        stub.is_available = lambda: False  # type: ignore[attr-defined]
        sys.modules["torchdistribute"] = stub
    dist = sys.modules.get("torch.distributed")
    if dist is None:
        dist = types.ModuleType("torch.distributed")
        dist.is_available = lambda: False  # type: ignore[attr-defined]
        sys.modules["torch.distributed"] = dist


_install_torch_stubs()


def is_low_end() -> bool:
    """Heuristic: weak RAM / forced CPU / explicit flag."""
    if os.environ.get("DOOF_LOW_END") == "1":
        return True
    if os.environ.get("DOOF_FORCE_CPU") == "1":
        return True
    try:
        if sys.platform.startswith("linux"):
            with open("/proc/meminfo", encoding="utf-8") as fh:
                txt = fh.read()
            for line in txt.splitlines():
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    return kb < 6 * 1024 * 1024  # < 6 GB
        if sys.platform == "win32":
            # Avoid ctypes probing loops; env flag is the override.
            return False
    except Exception:
        pass
    # Very small CPU count is a hint, not a requirement.
    cpus = os.cpu_count() or 2
    return cpus <= 2


def import_torch() -> Any | None:
    """Return the torch module or None. Never raises. Cached."""
    global _torch_mod, _torch_error, _torch_tried
    with _lock:
        if _torch_tried:
            return _torch_mod
        _torch_tried = True
        if os.environ.get("DOOF_DISABLE_TORCH") == "1":
            _torch_error = "torch disabled (DOOF_DISABLE_TORCH=1)"
            return None
        try:
            _install_torch_stubs()
            import torch  # type: ignore

            _torch_mod = torch
            return torch
        except Exception as e:  # ModuleNotFoundError, OSError, etc.
            _torch_error = f"{type(e).__name__}: {e}"
            _torch_mod = None
            return None


def torch_error() -> str | None:
    import_torch()
    return _torch_error


def torch_available() -> bool:
    return import_torch() is not None


def probe_hardware(*, force: bool = False) -> dict[str, Any]:
    """Cheap hardware snapshot. Torch is imported at most once.

    CUDA is probed once and cached. No polling loops.
    """
    global _hw_cache, _hw_cache_at
    import time

    now = time.time()
    with _lock:
        if _hw_cache is not None and not force and (now - _hw_cache_at) < 30:
            return dict(_hw_cache)

    info: dict[str, Any] = {
        "platform": platform.system(),
        "python": platform.python_version(),
        "machine": platform.machine(),
        "hostname": platform.node() or "DOOF",
        "cuda_available": False,
        "cuda_device_count": 0,
        "cuda_devices": [],
        "cuda_version": None,
        "mps_available": False,
        "device": "cpu",
        "torch_version": None,
        "torch_available": False,
        "torch_error": None,
        "cpu_count": os.cpu_count(),
        "low_end": is_low_end(),
        "ram_gb": _ram_gb(),
        "force_cpu": os.environ.get("DOOF_FORCE_CPU") == "1",
    }
    torch = import_torch()
    if torch is None:
        info["torch_error"] = _torch_error
        info["error"] = _torch_error
    else:
        try:
            info["torch_available"] = True
            info["torch_version"] = getattr(torch, "__version__", None)
            if os.environ.get("DOOF_FORCE_CPU") == "1" or is_low_end():
                info["device"] = "cpu"
            else:
                cuda_ok = bool(getattr(torch, "cuda", None) and torch.cuda.is_available())
                info["cuda_available"] = cuda_ok
                if cuda_ok:
                    info["device"] = "cuda"
                    info["cuda_device_count"] = int(torch.cuda.device_count())
                    info["cuda_version"] = getattr(torch.version, "cuda", None)
                    for i in range(info["cuda_device_count"]):
                        p = torch.cuda.get_device_properties(i)
                        info["cuda_devices"].append(
                            {
                                "index": i,
                                "name": p.name,
                                "total_memory_gb": round(p.total_memory / (1024**3), 2),
                            }
                        )
                elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                    info["mps_available"] = True
                    info["device"] = "mps"
        except Exception as e:
            info["torch_error"] = f"{type(e).__name__}: {e}"
            info["error"] = info["torch_error"]

    with _lock:
        _hw_cache = dict(info)
        _hw_cache_at = now
    return info


def _ram_gb() -> float | None:
    try:
        if sys.platform.startswith("linux"):
            with open("/proc/meminfo", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("MemTotal:"):
                        return round(int(line.split()[1]) / (1024 * 1024), 1)
    except Exception:
        return None
    return None


def capabilities_from_hardware(hw: dict[str, Any] | None = None) -> dict[str, Any]:
    hw = hw or probe_hardware()
    torch_ok = bool(hw.get("torch_available"))
    gpu = bool(hw.get("cuda_available") or hw.get("mps_available"))
    low = bool(hw.get("low_end"))
    ram = hw.get("ram_gb") or 0
    return {
        "cpu_inference": torch_ok,
        "gpu_inference": torch_ok and gpu,
        "large_model_inference": torch_ok and gpu and ram >= 16,
        "small_model_inference": torch_ok,
        "embedding": torch_ok,
        "memory_database": True,
        "remote_jobs": True,
        "low_end": low,
    }


def should_load_model() -> bool:
    """Do not load weights until a chat/job actually needs them."""
    if os.environ.get("DOOF_DISABLE_TORCH") == "1":
        return False
    return torch_available()
