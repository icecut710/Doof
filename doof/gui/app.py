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

from PySide6.QtCore import QPoint, QUrl, Qt
from PySide6.QtGui import QColor
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


def _root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]


ROOT = _root()
FRONTEND = ROOT / "frontend"
DIST = FRONTEND / "dist"

UI_PORT = 8766
API_PORT = 8765
VERIFY_PORT = 3000


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
    """Locate production frontend. Never npm in frozen EXE."""
    global DIST
    try:
        from doof.paths import frontend_dist, is_frozen

        dist = frontend_dist()
        frozen = is_frozen()
    except Exception:
        dist = DIST
        frozen = bool(getattr(sys, "frozen", False))
    index = dist / "index.html"
    if index.is_file():
        print(f"DOOF: frontend build found: {index}")
        DIST = dist
        return True
    if frozen:
        print(f"DOOF: FATAL — bundled UI missing at {index}")
        print("DOOF: Rebuild with packaging\\build.bat")
        return False
    print("DOOF: frontend/dist missing — running npm run build…")
    if not (FRONTEND / "package.json").is_file():
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
            print("DOOF: npm build failed")
            return False
        return (DIST / "index.html").is_file()
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
            try:
                from doof.api_mount import install

                install()
            except Exception as e:
                print(f"DOOF api_mount: {e}")
            from doof.api import run_server

            host = os.environ.get("DOOF_API_HOST", "0.0.0.0")
            run_server(host=host, port=API_PORT)
        except Exception as e:
            print(f"DOOF API failed: {e}")

    threading.Thread(target=run, daemon=True, name="doof-api").start()
    print(f"DOOF: starting API on :{API_PORT}")


def start_static_server(directory: Path, port: int) -> None:
    root = str(directory.resolve())

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        extensions_map = {
            **http.server.SimpleHTTPRequestHandler.extensions_map,
            ".html": "text/html; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".mjs": "application/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".svg": "image/svg+xml; charset=utf-8",
            ".txt": "text/plain; charset=utf-8",
        }

        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=root, **kwargs)

        def log_message(self, format: str, *args) -> None:
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


class DOOFPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        print(f"[JS {level}] {sourceID}:{lineNumber} {message}")


class TitleBar(QFrame):
    def __init__(self, window: "DOOFWindow") -> None:
        super().__init__(window)
        self._win = window
        self.setObjectName("titlebar")
        self.setFixedHeight(34)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 0, 0)
        layout.setSpacing(8)
        logo = QLabel("D")
        logo.setObjectName("tb-logo")
        title = QLabel("DOOF")
        title.setObjectName("tb-title")
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.btn_min = QPushButton("–")
        self.btn_max = QPushButton("□")
        self.btn_close = QPushButton("✕")
        for b in (self.btn_min, self.btn_max, self.btn_close):
            b.setObjectName("tb-button")
            b.setFixedSize(42, 34)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setObjectName("tb-close")
        for w in (logo, title, spacer, self.btn_min, self.btn_max, self.btn_close):
            layout.addWidget(w)
        self.btn_min.clicked.connect(window.showMinimized)
        self.btn_max.clicked.connect(window.toggle_maximize)
        self.btn_close.clicked.connect(window.close)


class DOOFWindow(QWidget):
    DEFAULT_W, DEFAULT_H = 900, 600
    MIN_W, MIN_H = 850, 550
    MAX_W, MAX_H = 1200, 750

    def __init__(self, ui_url: str):
        super().__init__()
        self.setWindowTitle("DOOF")
        self.resize(self.DEFAULT_W, self.DEFAULT_H)
        self.setMinimumSize(self.MIN_W, self.MIN_H)
        self.setMaximumSize(self.MAX_W, self.MAX_H)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self._drag_pos: QPoint | None = None
        self.setStyleSheet(
            """
            QWidget#doof-root { background: #050506; }
            QFrame#titlebar { background: #070708; border-bottom: 1px solid #17171b; }
            QLabel#tb-logo { color: #a78bfa; font-size: 13px; }
            QLabel#tb-title { color: #e4e4e7; font-size: 11px; font-weight: 600;
                              font-family: 'Segoe UI'; letter-spacing: 1px; }
            QPushButton#tb-button, QPushButton#tb-close {
                border: none; background: transparent; color: #71717a;
                font-size: 12px; font-family: 'Segoe UI'; }
            QPushButton#tb-button:hover { background: #18181b; color: #ffffff; }
            QPushButton#tb-close:hover { background: #ef4444; color: white; }
            QWebEngineView { border: none; background: #050506; }
            """
        )
        root = QWidget(objectName="doof-root")
        lay = QVBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.titlebar = TitleBar(self)
        lay.addWidget(self.titlebar)
        self.view = QWebEngineView()
        page = DOOFPage(self.view)
        self.view.setPage(page)
        s = self.view.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.ErrorPageEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, True)
        self.view.page().setBackgroundColor(QColor("#050506"))
        self.view.loadFinished.connect(self._on_load_finished)
        lay.addWidget(self.view)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(root)
        print(f"DOOF: loading {ui_url}")
        self.view.load(QUrl(ui_url))

    def toggle_maximize(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event) -> None:
        if (
            self._drag_pos is not None
            and event.buttons() & Qt.MouseButton.LeftButton
            and not self.isMaximized()
        ):
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None

    def _on_load_finished(self, ok: bool) -> None:
        print(f"DOOF: page load {'ok' if ok else 'FAILED'}")
        if not ok:
            self.view.setHtml(
                "<!doctype html><html><body style=\"margin:0;background:#050506;color:#ccc;"
                "font-family:Segoe UI,sans-serif;display:flex;align-items:center;"
                "justify-content:center;height:100vh\">"
                "<div style=\"text-align:center;max-width:420px;padding:24px\">"
                "<div style=\"color:#a78bfa;font-size:22px;font-weight:700\">DOOF</div>"
                "<div style=\"margin-top:12px;font-size:13px;color:#888\">"
                "UI failed to load. Rebuild with packaging\\build.bat.</div></div></body></html>"
            )


def _make_splash(app: QApplication):
    from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
    from PySide6.QtWidgets import QSplashScreen

    icon_path = ROOT / "assets" / "doof_icon.ico"
    if not icon_path.is_file():
        icon_path = ROOT / "assets" / "doof.ico"
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))

    mrn = ROOT / "assets" / "mrnaddaf.png"
    pix = QPixmap(520, 360)
    pix.fill(QColor("#050506"))
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    if mrn.is_file():
        face = QPixmap(str(mrn))
        if not face.isNull():
            scaled = face.scaled(
                120,
                120,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (pix.width() - 120) // 2
            y = 48
            p.drawPixmap(x, y, scaled.copy(0, 0, 120, 120))
    else:
        p.setPen(QColor("#c4b5fd"))
        p.setFont(QFont("Segoe UI", 28, QFont.Weight.DemiBold))
        p.drawText(pix.rect().adjusted(0, -40, 0, 0), int(Qt.AlignmentFlag.AlignCenter), "D")
    p.setPen(QColor("#a1a1aa"))
    p.setFont(QFont("Segoe UI", 10))
    p.drawText(
        pix.rect().adjusted(0, 100, 0, 0),
        int(Qt.AlignmentFlag.AlignCenter),
        "Warming the grill…",
    )
    # Draw subtle grid pattern for "neural" feel
    p.setPen(QColor("#18181b"))
    for i in range(0, 520, 40):
        p.drawLine(i, 0, i, 360)
    for i in range(0, 360, 40):
        p.drawLine(0, i, 520, i)
    p.end()
    splash = QSplashScreen(pix)
    splash.show()
    splash.showMessage(
        "Checking the brain…",
        int(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter),
        QColor("#a1a1aa"),
    )
    app.processEvents()
    return splash


def main() -> int:
    from doof import __version__

    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    if os.environ.get("DOOF_SOFTWARE_RENDERING") == "1":
        os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --no-sandbox")

    app = QApplication(sys.argv)
    app.setApplicationName("DOOF")
    app.setOrganizationName("DOOF")
    app.setApplicationVersion(__version__)

    splash = _make_splash(app)

    if not build_frontend():
        QMessageBox.critical(
            None,
            "DOOF — UI not found",
            "Frontend UI is missing. Rebuild with packaging\\build.bat\n"
            f"Expected: {DIST / 'index.html'}",
        )
        print(f"DOOF: missing {DIST / 'index.html'}")
        return 1

    ui_port = _find_free_port(UI_PORT)
    ui_origin = f"http://127.0.0.1:{ui_port}/"
    os.environ["DOOF_UI_ORIGIN"] = ui_origin
    os.environ.setdefault("DOOF_VERIFY_REDIRECT", ui_origin)
    print(f"DOOF: UI origin {ui_origin}")

    start_api_background()
    start_static_server(DIST, ui_port)
    time.sleep(0.15)

    verify_port = int(os.environ.get("DOOF_VERIFY_PORT", VERIFY_PORT))
    if verify_port != ui_port and not _port_open("127.0.0.1", verify_port):
        try:
            start_static_server(DIST, verify_port)
            print(f"DOOF: verification callback on :{verify_port}")
        except Exception as e:
            print(f"DOOF: could not open :{verify_port} ({e})")

    window = DOOFWindow(ui_origin)
    window.show()
    if splash is not None:
        splash.finish(window)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
