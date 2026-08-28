"""DOOF Networking — Tailscale detection and node discovery.

Detects whether Tailscale is installed and what the local Tailscale IP is.
Provides friendly status for the UI.
"""
from __future__ import annotations

import subprocess
import re
import shutil
import json
from typing import Any


def detect_tailscale() -> dict[str, Any]:
    """Detect Tailscale status on this machine.

    Returns a dict with:
        installed: bool
        running: bool
        ip: str | None (Tailscale IP)
        hostname: str | None
        status: str (human-readable)
        version: str | None
    """
    result: dict[str, Any] = {
        "installed": False,
        "running": False,
        "enabled": False,
        "connected": False,
        "ip": None,
        "hostname": None,
        "status": "Not installed",
        "version": None,
    }

    tailscale_path = shutil.which("tailscale")
    if not tailscale_path:
        # Try common Windows path
        import os
        common = r"C:\Program Files\Tailscale\tailscale.exe"
        if os.path.isfile(common):
            tailscale_path = common

    if not tailscale_path:
        result["status"] = "Tailscale is not installed on this computer."
        return result

    result["installed"] = True
    result["enabled"] = True

    try:
        proc = subprocess.run(
            [tailscale_path, "version"],
            capture_output=True, text=True, timeout=5,
        )
        if proc.returncode == 0:
            result["version"] = proc.stdout.strip().split("\n")[0]
    except Exception:
        pass

    try:
        proc = subprocess.run(
            [tailscale_path, "status", "--json"],
            capture_output=True, text=True, timeout=10,
        )
        if proc.returncode == 0:
            data = json.loads(proc.stdout)
            self_node = data.get("Self", {})
            result["running"] = True
            result["connected"] = True
            result["ip"] = self_node.get("TailscaleIPs", [None])[0]
            result["hostname"] = self_node.get("HostName") or self_node.get("DNSName", "").rstrip(".")
            result["status"] = "Connected"
        elif proc.returncode == 1:
            result["status"] = "Installed but not running. Start Tailscale first."
        else:
            result["status"] = "Installed but status unknown."
    except FileNotFoundError:
        result["status"] = "Tailscale is not installed on this computer."
    except subprocess.TimeoutExpired:
        result["status"] = "Tailscale status check timed out."
    except Exception as e:
        result["status"] = f"Could not check Tailscale: {type(e).__name__}"

    return result


def get_tailscale_ip() -> str | None:
    """Quick check for Tailscale IP only."""
    info = detect_tailscale()
    return info.get("ip")


def tailscale_summary() -> str:
    """One-line summary for UI."""
    info = detect_tailscale()
    if not info["installed"]:
        return "Tailscale is not installed on this computer."
    if not info["running"]:
        return "Tailscale is installed but not running."
    ip = info.get("ip")
    hostname = info.get("hostname") or "unknown"
    if ip:
        return f"Tailscale connected as {hostname} ({ip})"
    return f"Tailscale connected as {hostname}"
