from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QUrl
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtWebEngineWidgets import QWebEngineView


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self._drag_position = QPoint()
        self._maximized = False

        self.setWindowTitle("DOOF")
        self.setMinimumSize(900, 600)
        self.resize(1100, 700)

        # Completely remove the ugly Windows title bar.
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Window
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            False,
        )

        self._apply_native_style()
        self._build_shell()
        self._load_frontend()

    # ---------------------------------------------------------
    # NATIVE SHELL
    # ---------------------------------------------------------

    def _apply_native_style(self):
        self.setStyleSheet(
            """
            QMainWindow {
                background: #050506;
            }

            QWidget {
                background: transparent;
                color: #f4f4f5;
                font-family: "Segoe UI";
            }

            QFrame#titlebar {
                background: #070708;
                border-bottom: 1px solid #19191d;
            }

            QLabel#window-title {
                color: #f4f4f5;
                font-size: 12px;
                font-weight: 600;
            }

            QPushButton#window-button {
                border: none;
                background: transparent;
                color: #71717a;
                font-size: 14px;
                min-width: 42px;
                max-width: 42px;
                min-height: 30px;
                max-height: 30px;
            }

            QPushButton#window-button:hover {
                background: #18181b;
                color: #ffffff;
            }

            QPushButton#close-button {
                border: none;
                background: transparent;
                color: #71717a;
                font-size: 14px;
                min-width: 42px;
                max-width: 42px;
                min-height: 30px;
                max-height: 30px;
            }

            QPushButton#close-button:hover {
                background: #ef4444;
                color: white;
            }

            QWebEngineView {
                border: none;
                background: #050506;
            }
            """
        )

    def _build_shell(self):
        root = QWidget()
        root.setObjectName("root")

        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # -----------------------------------------------------
        # CUSTOM TITLE BAR
        # -----------------------------------------------------

        titlebar = QFrame()
        titlebar.setObjectName("titlebar")
        titlebar.setFixedHeight(32)

        title_layout = QHBoxLayout(titlebar)
        title_layout.setContentsMargins(12, 0, 0, 0)
        title_layout.setSpacing(0)

        title = QLabel("DOOF")
        title.setObjectName("window-title")

        title_layout.addWidget(title)
        title_layout.addStretch()

        minimize = QPushButton("—")
        minimize.setObjectName("window-button")
        minimize.clicked.connect(self.showMinimized)

        maximize = QPushButton("□")
        maximize.setObjectName("window-button")
        maximize.clicked.connect(self._toggle_maximize)

        close = QPushButton("×")
        close.setObjectName("close-button")
        close.clicked.connect(self.close)

        title_layout.addWidget(minimize)
        title_layout.addWidget(maximize)
        title_layout.addWidget(close)

        root_layout.addWidget(titlebar)

        # -----------------------------------------------------
        # WEB UI
        # -----------------------------------------------------

        self.web = QWebEngineView()
        self.web.setContextMenuPolicy(
            Qt.ContextMenuPolicy.NoContextMenu
        )

        root_layout.addWidget(self.web)

        self.setCentralWidget(root)

        # Make titlebar draggable.
        titlebar.mousePressEvent = self._title_mouse_press
        titlebar.mouseMoveEvent = self._title_mouse_move

    # ---------------------------------------------------------
    # FRONTEND
    # ---------------------------------------------------------

    def _load_frontend(self):
        project_root = Path(__file__).resolve().parents[2]

        frontend_dist = (
            project_root
            / "frontend"
            / "dist"
            / "index.html"
        )

        if not frontend_dist.exists():
            self._show_missing_frontend(frontend_dist)
            return

        self.web.load(
            QUrl.fromLocalFile(
                str(frontend_dist.resolve())
            )
        )

    def _show_missing_frontend(self, path: Path):
        html = f"""
        <!doctype html>
        <html>
        <body style="
            margin:0;
            background:#050506;
            color:#f4f4f5;
            font-family:Segoe UI,sans-serif;
            display:flex;
            align-items:center;
            justify-content:center;
            height:100vh;
        ">
            <div style="
                width:600px;
                border:1px solid #202024;
                border-radius:18px;
                padding:32px;
                background:#09090b;
            ">
                <div style="
                    font-size:24px;
                    font-weight:700;
                    margin-bottom:10px;
                ">
                    DOOF frontend not built
                </div>

                <div style="
                    color:#71717a;
                    margin-bottom:20px;
                ">
                    Build the Tailwind frontend first.
                </div>

                <code style="
                    display:block;
                    background:#111114;
                    padding:16px;
                    border-radius:10px;
                    color:#a78bfa;
                ">
                    cd frontend<br>
                    npm install<br>
                    npm run build
                </code>

                <div style="
                    color:#52525b;
                    margin-top:18px;
                    font-size:12px;
                ">
                    Expected:<br>
                    {path}
                </div>
            </div>
        </body>
        </html>
        """

        self.web.setHtml(html)

    # ---------------------------------------------------------
    # WINDOW CONTROLS
    # ---------------------------------------------------------

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def _title_mouse_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_position = (
                event.globalPosition().toPoint()
                - self.frameGeometry().topLeft()
            )

    def _title_mouse_move(self, event):
        if (
            event.buttons()
            & Qt.MouseButton.LeftButton
        ):
            if not self.isMaximized():
                self.move(
                    event.globalPosition().toPoint()
                    - self._drag_position
                )