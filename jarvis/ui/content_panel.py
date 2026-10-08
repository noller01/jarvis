"""Dynamic content panel — web results, news, search data."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QLabel, QPushButton, QTextBrowser, QVBoxLayout, QHBoxLayout

from jarvis.ui.assets import pixmap


class ContentPanel(QFrame):
    closed = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("contentPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        self.banner = QLabel()
        self.banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hdr = pixmap("panel_header", 640, 72)
        if not hdr.isNull():
            self.banner.setPixmap(hdr)
        layout.addWidget(self.banner)
        header = QHBoxLayout()
        title = QLabel("CONTENT")
        title.setStyleSheet("font-size: 14px; letter-spacing: 3px; font-weight: 300;")
        header.addWidget(title)
        header.addStretch()
        clear = QPushButton("Clear")
        clear.clicked.connect(self.clear)
        close = QPushButton("Close")
        close.clicked.connect(self.closed.emit)
        header.addWidget(clear)
        header.addWidget(close)
        layout.addLayout(header)
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        layout.addWidget(self.browser)

    def show_content(self, title: str, body) -> None:  # noqa: ANN001
        # Morning briefing uses sunrise banner; others use panel header
        if "morning" in title.lower() or "briefing" in title.lower():
            morn = pixmap("morning", 640, 180)
            if not morn.isNull():
                self.banner.setPixmap(morn)
        else:
            hdr = pixmap("panel_header", 640, 72)
            if not hdr.isNull():
                self.banner.setPixmap(hdr)
        if isinstance(body, (dict, list)):
            import json

            text = json.dumps(body, indent=2, ensure_ascii=False)
            html = f"<h3 style='color:#E8E8E8;font-weight:300'>{title}</h3><pre style='color:#9A9A9A'>{text}</pre>"
        else:
            html = f"<h3 style='color:#E8E8E8;font-weight:300'>{title}</h3><div style='color:#C0C0C0;white-space:pre-wrap'>{body}</div>"
        self.browser.setHtml(html)

    def clear(self) -> None:
        self.browser.clear()
