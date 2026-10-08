"""Startup splash using Higgsfield splash background + wordmark."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from jarvis.config import settings
from jarvis.ui.assets import pixmap


class SplashScreen(QWidget):
    finished = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setFixedSize(720, 420)
        self._bg = pixmap("splash", 720, 420)
        self._mark = pixmap("wordmark", 480, 180)
        self._icon = pixmap("icon", 96, 96)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addStretch()
        self.status = QLabel("Initializing…")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setStyleSheet("color: #9A9A9A; letter-spacing: 3px; font-size: 12px;")
        layout.addWidget(self.status)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        if not self._bg.isNull():
            p.drawPixmap(self.rect(), self._bg)
        else:
            p.fillRect(self.rect(), Qt.GlobalColor.black)
        if not self._icon.isNull():
            x = (self.width() - self._icon.width()) // 2
            p.drawPixmap(x, 70, self._icon)
        if not self._mark.isNull():
            x = (self.width() - self._mark.width()) // 2
            p.drawPixmap(x, 180, self._mark)
        else:
            p.setPen(Qt.GlobalColor.lightGray)
            p.drawText(
                self.rect().adjusted(0, 160, 0, 0),
                Qt.AlignmentFlag.AlignHCenter,
                settings.get("assistant_name", "JARVIS"),
            )
        p.end()

    def show_and_fade(self, ms: int = 2200) -> None:
        self.show()
        QTimer.singleShot(ms, self._done)

    def _done(self) -> None:
        self.finished.emit()
        self.close()
