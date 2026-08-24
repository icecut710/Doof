"""DOOF auto-update subsystem.

Hybrid design:
  - Remotely updateable: frontend assets, personality, config, pure-Python logic
    shipped inside a release package.
  - Requires full binary rebuild: PySide6, Torch, native DLLs, bootloader.

The client never executes arbitrary code from the network. Updates are:
  1. Fetched over HTTPS from a configured manifest URL
  2. Version-compared against the installed __version__
  3. Checksum-verified (SHA-256)
  4. Optionally signature-verified if a public key is configured
  5. Applied atomically into a staging directory, then swapped
  6. Rolled back on failure
"""
from __future__ import annotations

from doof.updates.client import (
    UpdateStatus,
    check_for_update,
    current_version,
    apply_update,
    get_update_settings,
    save_update_settings,
)

__all__ = [
    "UpdateStatus",
    "check_for_update",
    "current_version",
    "apply_update",
    "get_update_settings",
    "save_update_settings",
]
