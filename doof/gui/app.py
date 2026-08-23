"""DOOF desktop shell — PySide6 + local HTTP frontend (not file://)."""
from __future__ import annotations

import http.server
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QColor
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QMessageBox


def _root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]


ROOT = _root()
FRONTEND = ROOT / "frontend"
DIST = FRONTEND / "dist"

UI_PORT = 8766
API_PORT = 8765


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.25):
            return True
    except OSError:
        return False


def _find_free_port(start: int = UI_PORT) -> int:
    for p in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    return start


def build_frontend() -> bool:
    index = DIST / "index.html"
    if index.exists():
        print(f"DOOF: frontend build found: {index}")
        return True

    print("DOOF: frontend/dist missing — running npm run build…")
    if not (FRONTEND / "package.json").exists():
        print(f"DOOF: no package.json at {FRONTEND}")
        return False

    try:
        r = subprocess.run(
            "npm run build",
            cwd=str(FRONTEND),
            shell=True,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if r.returncode != 0:
            print("DOOF: npm build failed:")
            print(r.stdout[-2000:] if r.stdout else "")
            print(r.stderr[-2000:] if r.stderr else "")
            return False
        ok = (DIST / "index.html").exists()
        print(f"DOOF: build {'ok' if ok else 'missing index.html'}")
        return ok
    except Exception as exc:
        print(f"DOOF: frontend build failed: {exc}")
        return False


def start_api_background() -> None:
    if _port_open("127.0.0.1", API_PORT):
        print(f"DOOF: API already on :{API_PORT}")
        return

    def run() -> None:
        try:
            time.sleep(0.3)
            from doof.api import run_server

            run_server(host="127.0.0.1", port=API_PORT)
        except Exception as e:
            print(f"DOOF API failed: {e}")

    threading.Thread(target=run, daemon=True, name="doof-api").start()
    print(f"DOOF: starting API on :{API_PORT}")


def start_static_server(directory: Path, port: int) -> None:
    """Serve dist over HTTP so QWebEngine can load ES modules reliably."""
    root = str(directory.resolve())

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=root, **kwargs)

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            pass

    def run() -> None:
        try:
            httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), QuietHandler)
            print(f"DOOF: UI static server http://127.0.0.1:{port}/  (dir={root})")
            httpd.serve_forever()
        except Exception as e:
            print(f"DOOF UI server failed: {e}")

    threading.Thread(target=run, daemon=True, name="doof-ui").start()
    for _ in range(40):
        if _port_open("127.0.0.1", port):
            return
        time.sleep(0.05)
    print("DOOF: warning — UI port not open yet")


class DOOFPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):  # noqa: N802
        print(f"[JS {level}] {sourceID}:{lineNumber} {message}")


class DOOFWindow(QWebEngineView):
    def __init__(self, ui_url: str):
        super().__init__()
        self.setWindowTitle("DOOF")
        self.resize(1180, 720)
        self.setMinimumSize(900, 560)
        self.setStyleSheet("QWebEngineView { background: #050506; border: none; }")

        page = DOOFPage(self)
        self.setPage(page)

        s = self.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.ErrorPageEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, True)

        self.page().setBackgroundColor(QColor("#050506"))
        self.loadFinished.connect(self._on_load_finished)

        print(f"DOOF: loading {ui_url}")
        self.load(QUrl(ui_url))

    def _on_load_finished(self, ok: bool) -> None:
        print(f"DOOF: page load {'ok' if ok else 'FAILED'}")
        if not ok:
            self.setHtml(
                """
                <!doctype html><html><body style="margin:0;background:#050506;color:#ccc;
                font-family:Segoe UI,sans-serif;display:flex;align-items:center;
                justify-content:center;height:100vh">
                <div style="text-align:center;max-width:420px;padding:24px">
                  <div style="color:#a78bfa;font-size:22px;font-weight:700">DOOF</div>
                  <div style="margin-top:12px;font-size:13px;color:#888">
                    UI failed to load. Build the frontend, then relaunch.
                  </div>
                  <pre style="margin-top:16px;text-align:left;background:#111;padding:12px;
                    border-radius:8px;font-size:11px;color:#aaa">cd frontend
npm install
npm run build
cd ..
python -m doof gui</pre>
                </div></body></html>
                """
            )


def main() -> int:
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --no-sandbox")
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

    start_api_background()

    app = QApplication(sys.argv)
    app.setApplicationName("DOOF")
    app.setOrganizationName("DOOF")
    app.setApplicationVersion("0.1.0")

    if not build_frontend():
        QMessageBox.critical(
            None,
            "DOOF",
            "Frontend build not found.\n\n"
            "Run in PowerShell:\n\n"
            "  cd frontend\n"
            "  npm install\n"
            "  npm run build\n\n"
            f"Expected: {DIST / 'index.html'}",
        )
        print(f"DOOF: missing {DIST / 'index.html'}")
        return 1

    ui_port = _find_free_port(UI_PORT)
    start_static_server(DIST, ui_port)
    time.sleep(0.15)

    window = DOOFWindow(f"http://127.0.0.1:{ui_port}/")
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
