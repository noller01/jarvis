"""Assistant customization + audio/voice/theme controls."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
)

from jarvis.audio.devices import list_devices
from jarvis.config import settings
from jarvis.ui.assets import pixmap
from jarvis.ui.theme import apply_hue


class SettingsPanel(QFrame):
    changed = pyqtSignal(dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("panel")
        layout = QVBoxLayout(self)
        title = QLabel("SETTINGS")
        title.setStyleSheet("font-size: 14px; letter-spacing: 3px; font-weight: 300;")
        layout.addWidget(title)
        icons = QLabel()
        icons.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sheet = pixmap("icons", 280, 280)
        if not sheet.isNull():
            icons.setPixmap(sheet)
        layout.addWidget(icons)
        remote = QLabel()
        remote.setAlignment(Qt.AlignmentFlag.AlignCenter)
        phone = pixmap("remote", 120, 160)
        if not phone.isNull():
            remote.setPixmap(phone)
            layout.addWidget(remote)
            hint = QLabel("Remote dashboard QR is saved under data/uploads/")
            hint.setObjectName("muted")
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(hint)
        form = QFormLayout()
        self.assistant_name = QLineEdit(settings.get("assistant_name", "JARVIS"))
        self.user_name = QLineEdit(settings.get("user_name", ""))
        self.city = QLineEdit(settings.get("city", ""))
        self.voice = QComboBox()
        for v in settings.get("voices", ["Puck", "Charon", "Kore", "Fenrir", "Aoede"]):
            self.voice.addItem(v)
        idx = self.voice.findText(settings.get("voice", "Puck"))
        if idx >= 0:
            self.voice.setCurrentIndex(idx)
        self.mic = QComboBox()
        self.speaker = QComboBox()
        self._load_devices()
        self.hue = QSlider(Qt.Orientation.Horizontal)
        self.hue.setRange(0, 359)
        self.hue.setValue(int(settings.get("hue", 210)))
        self.hex_edit = QLineEdit(settings.get("hex_color", "#6B7280"))
        self.opacity = QSlider(Qt.Orientation.Horizontal)
        self.opacity.setRange(40, 100)
        self.opacity.setValue(int(float(settings.get("opacity", 0.92)) * 100))
        self.wake = QCheckBox("Wake word enabled")
        self.wake.setChecked(bool(settings.get("wake_word_enabled", True)))
        self.autostart = QCheckBox("Auto-start on boot")
        self.autostart.setChecked(bool(settings.get("auto_start", False)))
        form.addRow("Assistant name", self.assistant_name)
        form.addRow("Your name", self.user_name)
        form.addRow("City", self.city)
        form.addRow("Voice", self.voice)
        form.addRow("Microphone", self.mic)
        form.addRow("Speakers", self.speaker)
        form.addRow("Hue", self.hue)
        form.addRow("Hex", self.hex_edit)
        form.addRow("Opacity", self.opacity)
        form.addRow("", self.wake)
        form.addRow("", self.autostart)
        layout.addLayout(form)
        apply = QPushButton("Apply")
        apply.setObjectName("primary")
        apply.clicked.connect(self._apply)
        layout.addWidget(apply)
        layout.addStretch()

    def _load_devices(self) -> None:
        try:
            devices = list_devices(measure=True)
        except Exception:
            devices = []
        self.mic.clear()
        self.speaker.clear()
        self.mic.addItem("System default", None)
        self.speaker.addItem("System default", None)
        for d in devices:
            label = f"{d.name} [{d.index}]"
            if d.kind == "input":
                self.mic.addItem(label, d.index)
            else:
                self.speaker.addItem(label, d.index)
        # restore
        for combo, key in ((self.mic, "mic_device"), (self.speaker, "speaker_device")):
            want = settings.get(key)
            if want is None:
                continue
            for i in range(combo.count()):
                if combo.itemData(i) == want:
                    combo.setCurrentIndex(i)
                    break

    def _apply(self) -> None:
        hue = self.hue.value()
        hex_color = self.hex_edit.text().strip()
        if hex_color.startswith("#") and len(hex_color) == 7:
            from PyQt6.QtGui import QColor

            c = QColor(hex_color)
            if c.isValid():
                hue = c.hue() if c.hue() >= 0 else hue
        theme = apply_hue(hue)
        payload = {
            "assistant_name": self.assistant_name.text().strip() or "JARVIS",
            "user_name": self.user_name.text().strip(),
            "city": self.city.text().strip(),
            "voice": self.voice.currentText(),
            "mic_device": self.mic.currentData(),
            "speaker_device": self.speaker.currentData(),
            "hue": hue,
            "hex_color": theme["accent"],
            "opacity": self.opacity.value() / 100.0,
            "wake_word_enabled": self.wake.isChecked(),
            "auto_start": self.autostart.isChecked(),
            "theme": theme,
        }
        settings.update(payload)
        self.changed.emit(payload)
