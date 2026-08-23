from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtGui import QColor


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
DIST = FRONTEND / "dist"


def build_frontend() -> bool:
    """Build the React/Tailwind frontend if dist does not exist."""

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
            shell=True,
        )
        return index.exists()

    except Exception as exc:
        print(f"DOOF: Frontend build failed: {exc}")
        return False


class DOOFWindow(QWebEngineView):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("DOOF")

        # Premium compact desktop size
        self.resize(1180, 720)
        self.setMinimumSize(900, 560)

        self.setStyleSheet("""
            QWebEngineView {
                background: #050506;
                border: none;
            }
        """)

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

        # Remove the normal browser-looking background.
        self.page().setBackgroundColor(QColor("#050506"))

        self._load_frontend()

    def _load_frontend(self):
        index = DIST / "index.html"

        if not index.exists():
            self.setHtml("""
                <!doctype html>
                <html>
                <body style="
                    margin:0;
                    background:#050506;
                    color:#aaa;
                    font-family:Segoe UI,sans-serif;
                    display:flex;
                    align-items:center;
                    justify-content:center;
                    height:100vh;
                ">
                    <div style="text-align:center">
                        <div style="
                            color:#a78bfa;
                            font-size:24px;
                            font-weight:700;
                            margin-bottom:10px;
                        ">
                            DOOF
                        </div>

                        <div style="font-size:13px;color:#666">
                            Frontend build not found.
                        </div>

                        <div style="
                            margin-top:8px;
                            font-size:11px;
                            color:#444;
                        ">
                            Run: npm run build
                        </div>
                    </div>
                </body>
                </html>
            """)
            return

        print(f"DOOF: Loading GUI from {index}")

        self.load(
            QUrl.fromLocalFile(str(index.resolve()))
        )


def main() -> int:
    app = QApplication(sys.argv)

    app.setApplicationName("DOOF")
    app.setOrganizationName("DOOF")
    app.setApplicationVersion("0.1.0")

    # Make sure the React app exists before launching.
    if not build_frontend():
        print()
        print("DOOF GUI could not build the frontend.")
        print(f"Frontend: {FRONTEND}")
        return 1

    window = DOOFWindow()

    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())