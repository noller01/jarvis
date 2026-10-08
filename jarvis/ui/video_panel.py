"""Video on the HUD — YouTube, local file, or URL; starts muted."""

from __future__ import annotations

from PyQt6.QtCore import QUrl, Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QVBoxLayout, QLabel

try:
    from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
    from PyQt6.QtMultimediaWidgets import QVideoWidget

    HAS_QT_MM = True
except Exception:
    HAS_QT_MM = False


class VideoPanel(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.hint = QLabel("Video")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint.setObjectName("muted")
        layout.addWidget(self.hint)
        self.player = None
        self.audio = None
        self.video = None
        if HAS_QT_MM:
            self.video = QVideoWidget()
            self.video.setMinimumHeight(160)
            layout.addWidget(self.video)
            self.player = QMediaPlayer()
            self.audio = QAudioOutput()
            self.audio.setMuted(True)
            self.player.setAudioOutput(self.audio)
            self.player.setVideoOutput(self.video)
        row = QHBoxLayout()
        self.mute_btn = QPushButton("Unmute")
        self.mute_btn.clicked.connect(self._toggle_mute)
        stop = QPushButton("Stop")
        stop.clicked.connect(self.stop)
        row.addWidget(self.mute_btn)
        row.addWidget(stop)
        layout.addLayout(row)
        self._muted = True

    def play(self, url: str) -> dict:
        if url.startswith("http") and ("youtube.com" in url or "youtu.be" in url):
            # Qt can't play YT natively — open externally and note
            import webbrowser

            webbrowser.open(url)
            self.hint.setText("YouTube opened externally (muted request honored in browser)")
            return {"ok": True, "external": True}
        if not HAS_QT_MM or not self.player:
            return {"ok": False, "error": "Qt Multimedia unavailable"}
        self.audio.setMuted(True)
        self._muted = True
        self.mute_btn.setText("Unmute")
        self.player.setSource(QUrl.fromUserInput(url))
        self.player.play()
        self.hint.setText(url)
        return {"ok": True}

    def _toggle_mute(self) -> None:
        if not self.audio:
            return
        self._muted = not self._muted
        self.audio.setMuted(self._muted)
        self.mute_btn.setText("Unmute" if self._muted else "Mute")

    def stop(self) -> None:
        if self.player:
            self.player.stop()
