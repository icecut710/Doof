"""Capability detection, lazy torch, device preference, low-end guards.

Frozen builds previously pre-installed a fake ``torch.distributed`` which
caused circular initialization:
  AttributeError: partially initialized module 'torch' has no attribute 'distributed'

Rules:
  1. Never put a stub in sys.modules["torch.distributed"] *before* importing torch.
  2. Import torch normally; collect real CUDA/MPS state.
  3. Only after a successful import, soft-fill missing optional attrs if needed.
  4. The misspelled name ``torchdistribute`` may be stubbed anytime.
"""
from __future__ import annotations

import json
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

# Device preference: auto | cpu | gpu | low_end
_DEVICE_PREF_DEFAULT = "auto"


def _stub_torchdistribute() -> None:
    if "torchdistribute" not in sys.modules:
        stub = types.ModuleType("torchdistribute")
        stub.is_available = lambda: False  # type: ignore[attr-defined]
        sys.modules["torchdistribute"] = stub


def _soft_patch_distributed(torch: Any) -> None:
    """If packaged torch is missing distributed, attach a minimal no-op module
    *after* torch fully initialized — never before."""
    try:
        _ = torch.distributed
        return
    except Exception:
        pass
    if "torch.distributed" in sys.modules:
        return
    mod = types.ModuleType("torch.distributed")
    mod.is_available = lambda: False  # type: ignore[attr-defined]
    mod.is_initialized = lambda: False  # type: ignore[attr-defined]
    mod.is_torchelastic_launched = lambda: False  # type: ignore[attr-defined]
    sys.modules["torch.distributed"] = mod
    try:
        torch.distributed = mod  # type: ignore[attr-defined]
    except Exception:
        pass


def _settings_path() -> Any:
    try:
        from doof.paths import user_data_dir

        return user_data_dir() / "device_settings.json"
    except Exception:
        from pathlib import Path

        return Path.home() / ".doof" / "device_settings.json"


def get_device_preference() -> str:
    pref = os.environ.get("DOOF_DEVICE") or os.environ.get("DOOF_FORCE_DEVICE")
    if pref:
        p = pref.strip().lower()
        if p in ("auto", "cpu", "gpu", "cuda", "low_end", "low-end"):
            return "gpu" if p == "cuda" else ("low_end" if p in ("low_end", "low-end") else p)
    if os.environ.get("DOOF_FORCE_CPU") == "1":
        return "cpu"
    if os.environ.get("DOOF_LOW_END") == "1":
        return "low_end"
    try:
        path = _settings_path()
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            p = str(data.get("preference") or "auto").lower()
            if p in ("auto", "cpu", "gpu", "low_end"):
                return p
    except Exception:
        pass
    return _DEVICE_PREF_DEFAULT


def set_device_preference(preference: str) -> str:
    p = (preference or "auto").strip().lower()
    if p == "cuda":
        p = "gpu"
    if p not in ("auto", "cpu", "gpu", "low_end"):
        p = "auto"
    try:
        path = _settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"preference": p}, indent=2), encoding="utf-8")
    except Exception:
        pass
    # Invalidate hardware cache so next probe respects preference
    global _hw_cache, _hw_cache_at
    with _lock:
        _hw_cache = None
        _hw_cache_at = 0.0
    if p == "cpu":
        os.environ["DOOF_FORCE_CPU"] = "1"
    else:
        os.environ.pop("DOOF_FORCE_CPU", None)
    if p == "low_end":
        os.environ["DOOF_LOW_END"] = "1"
    else:
        os.environ.pop("DOOF_LOW_END", None)
    return p


def is_low_end() -> bool:
    if get_device_preference() == "low_end":
        return True
    if os.environ.get("DOOF_LOW_END") == "1":
        return True
    try:
        if sys.platform.startswith("linux"):
            with open("/proc/meminfo", encoding="utf-8") as fh:
                txt = fh.read()
            for line in txt.splitlines():
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    return kb < 6 * 1024 * 1024
        if sys.platform == "win32":
            return False
    except Exception:
        pass
    cpus = os.cpu_count() or 2
    return cpus <= 2


def import_torch() -> Any | None:
    """Return the torch module or None. Never raises. Cached.

    Critical: do not stub torch.distributed before this import.
    """
    global _torch_mod, _torch_error, _torch_tried
    with _lock:
        if _torch_tried:
            return _torch_mod
        _torch_tried = True
        if os.environ.get("DOOF_DISABLE_TORCH") == "1":
            _torch_error = "torch disabled (DOOF_DISABLE_TORCH=1)"
            return None
        try:
            _stub_torchdistribute()
            # Clear a *broken* stub left by older hooks so torch can re-init.
            existing = sys.modules.get("torch.distributed")
            if existing is not None and not hasattr(existing, "__file__"):
                # Likely our old empty stub — remove so real torch can load
                try:
                    del sys.modules["torch.distributed"]
                except Exception:
                    pass
                # Also clear partial torch if previous attempt left it broken
                tmod = sys.modules.get("torch")
                if tmod is not None and not hasattr(tmod, "__version__"):
                    try:
                        del sys.modules["torch"]
                    except Exception:
                        pass

            import torch  # type: ignore

            _soft_patch_distributed(torch)
            _torch_mod = torch
            _torch_error = None
            return torch
        except Exception as e:
            _torch_error = f"{type(e).__name__}: {e}"
            _torch_mod = None
            return None


def torch_error() -> str | None:
    import_torch()
    return _torch_error


def torch_available() -> bool:
    return import_torch() is not None


def resolve_device(torch: Any | None = None) -> tuple[str, str]:
    """Return (device_string, human_label) based on preference + detection.

    device_string is for torch.device(...): "cpu" | "cuda" | "cuda:0" | "mps"
    human_label is for UI: "CPU" | "NVIDIA GPU" | "Apple GPU" | etc.
    """
    torch = torch if torch is not None else import_torch()
    pref = get_device_preference()

    if torch is None:
        return "cpu", "CPU (model unavailable)"

    if pref == "cpu" or pref == "low_end":
        return "cpu", "CPU"

    cuda_ok = False
    try:
        cuda_ok = bool(getattr(torch, "cuda", None) and torch.cuda.is_available())
    except Exception:
        cuda_ok = False

    mps_ok = False
    try:
        mps_ok = bool(hasattr(torch.backends, "mps") and torch.backends.mps.is_available())
    except Exception:
        mps_ok = False

    if pref == "gpu":
        if cuda_ok:
            name = "NVIDIA GPU"
            try:
                name = torch.cuda.get_device_name(0) or name
            except Exception:
                pass
            return "cuda", name
        if mps_ok:
            return "mps", "Apple GPU"
        return "cpu", "CPU (requested GPU unavailable)"

    # auto
    if cuda_ok:
        name = "NVIDIA GPU"
        try:
            name = torch.cuda.get_device_name(0) or name
        except Exception:
            pass
        return "cuda", name
    if mps_ok:
        return "mps", "Apple GPU"
    return "cpu", "CPU"


def _ram_gb() -> float | None:
    try:
        if sys.platform.startswith("linux"):
            with open("/proc/meminfo", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("MemTotal:"):
                        return round(int(line.split()[1]) / (1024 * 1024), 1)
        if sys.platform == "win32":
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return round(stat.ullTotalPhys / (1024**3), 1)
    except Exception:
        return None
    return None


def probe_hardware(*, force: bool = False) -> dict[str, Any]:
    """Hardware snapshot. Torch imported at most once. Preference-aware."""
    global _hw_cache, _hw_cache_at
    import time

    now = time.time()
    with _lock:
        if _hw_cache is not None and not force and (now - _hw_cache_at) < 30:
            return dict(_hw_cache)

    pref = get_device_preference()
    info: dict[str, Any] = {
        "platform": platform.system(),
        "python": platform.python_version(),
        "machine": platform.machine(),
        "hostname": platform.node() or "DOOF",
        "cuda_available": False,
        "cuda_detected": False,
        "cuda_device_count": 0,
        "cuda_devices": [],
        "cuda_version": None,
        "mps_available": False,
        "device": "cpu",
        "device_label": "CPU",
        "preference": pref,
        "torch_version": None,
        "torch_available": False,
        "torch_error": None,
        "cpu_count": os.cpu_count(),
        "low_end": is_low_end() or pref == "low_end",
        "ram_gb": _ram_gb(),
        "force_cpu": pref == "cpu",
        "acceleration": "Unavailable",
        "acceleration_detail": None,
    }

    torch = import_torch()
    if torch is None:
        info["torch_error"] = _torch_error
        info["error"] = _torch_error
        info["acceleration"] = "Unavailable"
        info["acceleration_detail"] = (
            "The local model runtime could not start. "
            + (str(_torch_error) if _torch_error else "")
        )
    else:
        try:
            info["torch_available"] = True
            info["torch_version"] = getattr(torch, "__version__", None)

            # Detection independent of preference
            try:
                cuda_ok = bool(getattr(torch, "cuda", None) and torch.cuda.is_available())
            except Exception as e:
                cuda_ok = False
                info["acceleration_detail"] = f"CUDA probe failed: {e}"

            info["cuda_detected"] = cuda_ok
            info["cuda_available"] = cuda_ok

            if cuda_ok:
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

            try:
                if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                    info["mps_available"] = True
            except Exception:
                pass

            device_str, device_label = resolve_device(torch)
            info["device"] = device_str if device_str != "cuda" else "cuda"
            info["device_label"] = device_label

            if device_str.startswith("cuda"):
                info["acceleration"] = "Available"
                info["acceleration_detail"] = f"Using {device_label}"
            elif device_str == "mps":
                info["acceleration"] = "Available"
                info["acceleration_detail"] = "Using Apple GPU"
            elif info["cuda_detected"] and pref in ("cpu", "low_end"):
                info["acceleration"] = "Detected, not in use"
                info["acceleration_detail"] = (
                    f"GPU detected ({info['cuda_devices'][0]['name'] if info['cuda_devices'] else 'CUDA'}) "
                    f"but preference is {pref}. DOOF is using CPU."
                )
            elif info["cuda_detected"]:
                info["acceleration"] = "Detected, unavailable"
                info["acceleration_detail"] = (
                    "A GPU was detected but could not be selected. Using CPU."
                )
            else:
                info["acceleration"] = "Unavailable"
                info["acceleration_detail"] = "No supported GPU acceleration detected."

        except Exception as e:
            info["torch_error"] = f"{type(e).__name__}: {e}"
            info["error"] = info["torch_error"]
            info["acceleration"] = "Unavailable"
            info["acceleration_detail"] = info["torch_error"]

    with _lock:
        _hw_cache = dict(info)
        _hw_cache_at = now
    return info


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
    if os.environ.get("DOOF_DISABLE_TORCH") == "1":
        return False
    return torch_available()


def device_options() -> list[dict[str, Any]]:
    """UI-facing list of selectable inference devices."""
    hw = probe_hardware()
    opts: list[dict[str, Any]] = [
        {
            "id": "auto",
            "label": "Auto",
            "detail": "DOOF picks the best supported device",
            "available": True,
        }
    ]
    for d in hw.get("cuda_devices") or []:
        opts.append(
            {
                "id": "gpu",
                "label": d.get("name") or "NVIDIA GPU",
                "detail": f"{d.get('total_memory_gb', '?')} GB VRAM",
                "available": True,
            }
        )
        break
    if hw.get("mps_available") and not (hw.get("cuda_devices")):
        opts.append(
            {
                "id": "gpu",
                "label": "Apple GPU",
                "detail": "Metal Performance Shaders",
                "available": True,
            }
        )
    if not hw.get("cuda_devices") and not hw.get("mps_available"):
        opts.append(
            {
                "id": "gpu",
                "label": "GPU",
                "detail": hw.get("acceleration_detail") or "No supported GPU detected",
                "available": False,
            }
        )
    opts.append(
        {
            "id": "cpu",
            "label": "CPU",
            "detail": f"{hw.get('cpu_count') or '?'} cores",
            "available": True,
        }
    )
    opts.append(
        {
            "id": "low_end",
            "label": "Low-end",
            "detail": "Favor responsiveness, lower memory use",
            "available": True,
        }
    )
    return opts
