"""Main HUD — black/grey minimal shell with avatar, waveform, panels."""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QKeyEvent, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from jarvis.avatar.face import HolographicFace
from jarvis.avatar.status import AvatarStatus
from jarvis.config import settings
from jarvis.ui.assets import app_icon, pixmap
from jarvis.ui.content_panel import ContentPanel
from jarvis.ui.memory_panel import MemoryPanel
from jarvis.ui.settings_panel import SettingsPanel
from jarvis.ui.theme import stylesheet
from jarvis.ui.video_panel import VideoPanel
from jarvis.ui.waveform_widget import WaveformWidget


class _SplashBackdrop(QWidget):
    """Paints the Higgsfield splash texture behind the HUD chrome."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._bg = pixmap("splash", 1600, 900)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        if not self._bg.isNull():
            p.setOpacity(0.35)
            p.drawPixmap(self.rect(), self._bg)
            p.setOpacity(1.0)
        else:
            p.fillRect(self.rect(), Qt.GlobalColor.black)
        p.end()


class HUD(QMainWindow):
    text_submitted = pyqtSignal(str)
    ptt_key = pyqtSignal(str, set, bool)  # key, mods, down
    settings_changed = pyqtSignal(dict)
    file_dropped = pyqtSignal(str)
    undo_requested = pyqtSignal()
    status_message = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(settings.get("assistant_name", "JARVIS"))
        self.setWindowIcon(app_icon())
        self.setMinimumSize(720, 560)
        self.resize(980, 720)
        self.setWindowOpacity(float(settings.get("opacity", 0.92)))
        self.setAcceptDrops(True)
        self.setStyleSheet(stylesheet())

        root = _SplashBackdrop()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        # Top bar — Higgsfield wordmark + status rings
        top = QHBoxLayout()
        self.brand_icon = QLabel()
        icon_pm = pixmap("icon", 36, 36)
        if not icon_pm.isNull():
            self.brand_icon.setPixmap(icon_pm)
        top.addWidget(self.brand_icon)
        self.brand = QLabel()
        word = pixmap("wordmark", 220, 48)
        if not word.isNull():
            self.brand.setPixmap(word)
        else:
            self.brand.setText(settings.get("assistant_name", "JARVIS").upper())
            self.brand.setObjectName("brand")
        top.addWidget(self.brand)
        top.addStretch()
        self.status_ring = QLabel()
        ring = pixmap("status", 44, 44)
        if not ring.isNull():
            self.status_ring.setPixmap(ring)
        top.addWidget(self.status_ring)
        self.state_label = QLabel("ASLEEP")
        self.state_label.setObjectName("muted")
        top.addWidget(self.state_label)
        outer.addLayout(top)

        # Body splitter
        split = QSplitter(Qt.Orientation.Horizontal)
        left = QFrame()
        left.setObjectName("panel")
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(8, 8, 8, 8)
        self.face = HolographicFace()
        self.face.set_hue(int(settings.get("hue", 210)))
        left_l.addWidget(self.face, stretch=3)
        # Holographic reference art behind/under face when idle art preferred
        self.avatar_art = QLabel()
        self.avatar_art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        av = pixmap("avatar", 280, 360)
        if not av.isNull():
            self.avatar_art.setPixmap(av)
            self.avatar_art.setMaximumHeight(0)  # shown via toggle / asleep overlay
            self.avatar_art.hide()
        left_l.addWidget(self.avatar_art)
        self.wave = WaveformWidget()
        left_l.addWidget(self.wave)
        deco = QLabel()
        wf = pixmap("waveform", 320, 56)
        if not wf.isNull():
            deco.setPixmap(wf)
            deco.setAlignment(Qt.AlignmentFlag.AlignCenter)
            deco.setStyleSheet("opacity: 0.5;")
        left_l.addWidget(deco)
        self.video = VideoPanel()
        self.video.setMaximumHeight(200)
        self.video.hide()
        left_l.addWidget(self.video)
        split.addWidget(left)

        right = QStackedWidget()
        self.content = ContentPanel()
        self.memory = MemoryPanel()
        self.settings = SettingsPanel()
        self.content.closed.connect(lambda: right.setCurrentWidget(self.chat_wrap))
        self.memory.closed.connect(lambda: right.setCurrentWidget(self.chat_wrap))
        self.settings.changed.connect(self._on_settings)

        self.chat_wrap = QFrame()
        self.chat_wrap.setObjectName("panel")
        chat_l = QVBoxLayout(self.chat_wrap)
        chat_l.setContentsMargins(12, 12, 12, 12)
        self.transcript = QLabel("Hold Ctrl+Space to talk · type below for hybrid input")
        self.transcript.setObjectName("muted")
        self.transcript.setWordWrap(True)
        self.transcript.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        chat_l.addWidget(self.transcript, stretch=1)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Type a message…")
        self.input.returnPressed.connect(self._submit)
        chat_l.addWidget(self.input)

        right.addWidget(self.chat_wrap)
        right.addWidget(self.content)
        right.addWidget(self.memory)
        right.addWidget(self.settings)
        self.stack = right
        split.addWidget(right)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        outer.addWidget(split, stretch=1)

        # Bottom toolbar
        bar = QHBoxLayout()
        for label, slot in (
            ("Memory", lambda: self.stack.setCurrentWidget(self.memory) or self.memory.reload()),
            ("Content", lambda: self.stack.setCurrentWidget(self.content)),
            ("Settings", lambda: self.stack.setCurrentWidget(self.settings)),
            ("Undo", lambda: self.undo_requested.emit()),
            ("Video", self._toggle_video),
        ):
            b = QPushButton(label)
            b.clicked.connect(slot)
            bar.addWidget(b)
        bar.addStretch()
        self.ptt_hint = QLabel("Ctrl+Space")
        self.ptt_hint.setObjectName("muted")
        bar.addWidget(self.ptt_hint)
        outer.addLayout(bar)

        self._transcript_lines: list[str] = []

    def _submit(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self.append_transcript("you", text)
        self.text_submitted.emit(text)

    def append_transcript(self, role: str, text: str) -> None:
        if role == "assistant_partial":
            return
        prefix = "You" if role == "user" else settings.get("assistant_name", "JARVIS")
        self._transcript_lines.append(f"{prefix}: {text}")
        self._transcript_lines = self._transcript_lines[-40:]
        self.transcript.setText("\n\n".join(self._transcript_lines))
        self.transcript.setObjectName("")
        self.transcript.setStyleSheet(f"color: {settings.get('theme', {}).get('text', '#E8E8E8')};")

    def set_status(self, state: str) -> None:
        self.state_label.setText(state.upper().replace("_", " "))
        map_status = {
            "listening": AvatarStatus.LISTENING,
            "thinking": AvatarStatus.THINKING,
            "speaking": AvatarStatus.SPEAKING,
            "asleep": AvatarStatus.ASLEEP,
            "new_content": AvatarStatus.NEW_CONTENT,
            "confirm": AvatarStatus.CONFIRM,
        }
        self.face.set_status(map_status.get(state, AvatarStatus.IDLE))

    def show_content(self, title: str, body) -> None:  # noqa: ANN001
        self.content.show_content(title, body)
        self.stack.setCurrentWidget(self.content)
        self.face.set_status(AvatarStatus.NEW_CONTENT)

    def _on_settings(self, payload: dict) -> None:
        self.setStyleSheet(stylesheet(payload.get("theme"), payload.get("opacity")))
        self.setWindowOpacity(float(payload.get("opacity", 0.92)))
        if self.brand.pixmap() is None or self.brand.pixmap().isNull():
            self.brand.setText(payload.get("assistant_name", "JARVIS").upper())
        self.setWindowTitle(payload.get("assistant_name", "JARVIS"))
        self.setWindowIcon(app_icon())
        self.face.set_hue(int(payload.get("hue", 210)))
        self.settings_changed.emit(payload)

    def _toggle_video(self) -> None:
        self.video.setVisible(not self.video.isVisible())

    def play_video(self, url: str) -> None:
        self.video.show()
        self.video.play(url)

    # --- input / DnD ---------------------------------------------------------
    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        mods = set()
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            mods.add("ctrl")
        self.ptt_key.emit(event.key().__str__(), mods, True)
        # Space with Ctrl
        if event.key() == Qt.Key.Key_Space and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.ptt_key.emit("space", {"ctrl"}, True)
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        mods = set()
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            mods.add("ctrl")
        if event.key() == Qt.Key.Key_Space:
            self.ptt_key.emit("space", mods | {"ctrl"}, False)
        super().keyReleaseEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path:
                self.file_dropped.emit(path)
