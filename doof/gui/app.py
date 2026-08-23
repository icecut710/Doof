from __future__ import annotations

import os
import sys
import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtGui import QColor


def _root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]


ROOT = _root()
FRONTEND = ROOT / "frontend"
DIST = FRONTEND / "dist"
if not DIST.exists():
    DIST = ROOT / "frontend" / "dist"


def build_frontend() -> bool:
    index = DIST / "index.html"
    if index.exists():
        return True
    print("DOOF: Frontend build not found.")
    print("DOOF: Building React/Tailwind frontend...")
    try:
        subprocess.run(
            ["npm", "run", "build"],
            cwd=str(FRONTEND),
            check=True,
        )
        return (FRONTEND / "dist" / "index.html").exists()
    except Exception as exc:
        print(f"DOOF: Frontend build failed: {exc}")
        return False


def start_api_background() -> None:
    """Start local API on :8765 if not already running."""
    import socket
    try:
        with socket.create_connection(("127.0.0.1", 8765), timeout=0.3):
            return
    except OSError:
        pass

    def run():
        try:
            from doof.api import run_server
            run_server(host="127.0.0.1", port=8765)
        except Exception as e:
            print(f"DOOF API failed: {e}")

    t = threading.Thread(target=run, daemon=True, name="doof-api")
    t.start()


class DOOFWindow(QWebEngineView):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DOOF")
        self.resize(1180, 720)
        self.setMinimumSize(900, 560)
        self.setStyleSheet(
            "QWebEngineView { background: #050506; border: none; }"
        )
        settings = self.settings()
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls,
            True,
        )
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,
            True,
        )
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptEnabled,
            True,
        )
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled,
            True,
        )
        self.page().setBackgroundColor(QColor("#050506"))
        self._load_frontend()

    def _load_frontend(self):
        index = DIST / "index.html"
        if not index.exists():
            index = FRONTEND / "dist" / "index.html"
        if not index.exists():
            self.setHtml("""
                <!doctype html>
                <html>
                <body style="margin:0;background:#050506;color:#aaa;font-family:Segoe UI,sans-serif;
                    display:flex;align-items:center;justify-content:center;height:100vh">
                    <div style="text-align:center">
                        <div style="color:#a78bfa;font-size:22px;font-weight:700;margin-bottom:10px">DOOF</div>
                        <div style="font-size:13px;color:#666">Frontend build not found.</div>
                        <div style="margin-top:8px;font-size:11px;color:#444">Run: cd frontend && npm run build</div>
                    </div>
                </body>
                </html>
            """)
            return
        print(f"DOOF: Loading GUI from {index}")
        self.load(QUrl.fromLocalFile(str(index.resolve())))


def main() -> int:
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    start_api_background()
    app = QApplication(sys.argv)
    app.setApplicationName("DOOF")
    app.setOrganizationName("DOOF")
    app.setApplicationVersion("0.1.0")
    if not build_frontend():
        print("DOOF GUI could not build the frontend.")
        print(f"Frontend: {FRONTEND}")
        return 1
    window = DOOFWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
