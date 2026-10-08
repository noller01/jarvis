"""Reactive HUD waveform — mic while listening, JARVIS while speaking."""

from __future__ import annotations

import math

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from jarvis.audio.waveform import waveform
from jarvis.config import settings


class WaveformWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(36)
        self.setMinimumWidth(160)
        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(33)

    def _tick(self) -> None:
        waveform.tick_decay()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        theme = settings.get("theme")
        accent = QColor(theme.get("accent_bright", "#9CA3AF"))
        muted = QColor(theme.get("border", "#2A2A2A"))
        level = waveform.level
        source = waveform.source
        bars = 32
        bw = w / bars
        for i in range(bars):
            # pseudo spatial distribution from level
            phase = abs(math.sin(i * 0.55 + level * 8))
            bh = max(2.0, (h - 8) * level * (0.35 + 0.65 * phase))
            x = i * bw + 1
            y = (h - bh) / 2
            color = accent if source != "idle" else muted
            if source == "mic":
                color = QColor(theme.get("text_muted", "#9A9A9A"))
            elif source == "assistant":
                color = accent
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            p.drawRect(int(x), int(y), max(1, int(bw - 2)), int(bh))
        p.end()
