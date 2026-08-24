"""DOOF desktop GUI package.

Keep QtWebEngine on hardware acceleration in desktop builds.  The previous
shell explicitly disabled Chromium GPU rendering, which made the entire
QWebEngine UI feel sluggish on capable machines.
"""
from __future__ import annotations

import os

# app.py uses setdefault(), so setting this here (before doof.gui.app imports)
# prevents the old "--disable-gpu" default from taking effect.
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")

from .main_window import MainWindow

__all__ = ["MainWindow"]
