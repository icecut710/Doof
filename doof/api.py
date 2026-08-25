"""DOOF local HTTP API — v0.3.0.

Implementation lives in ``doof.api_full`` so the complete handler surface can
be shipped as one module. This file re-exports the public API.
"""
from __future__ import annotations

from doof.api_full import *  # noqa: F403
from doof.api_full import Handler, run_server, DOOF_API_VERSION, DOOF_PROTOCOL
