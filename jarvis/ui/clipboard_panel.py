"""Clipboard intelligence — Translate / Summarise / Explain / Fix."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout

from jarvis.core.gemini import generate_text


class ClipboardPanel(QFrame):
    closed = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("panel")
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        header = QHBoxLayout()
        header.addWidget(QLabel("CLIPBOARD"))
        header.addStretch()
        close = QPushButton("×")
        close.clicked.connect(self.closed.emit)
        header.addWidget(close)
        layout.addLayout(header)
        self.text = QTextEdit()
        self.text.setMaximumHeight(120)
        layout.addWidget(self.text)
        self.out = QTextEdit()
        self.out.setReadOnly(True)
        layout.addWidget(self.out)
        row = QHBoxLayout()
        for label, mode in (
            ("Translate", "translate"),
            ("Summarise", "summarise"),
            ("Explain", "explain"),
            ("Fix", "fix"),
        ):
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, m=mode: self._run(m))
            row.addWidget(b)
        layout.addLayout(row)
        self.resize(420, 360)

    def set_clipboard_text(self, text: str) -> None:
        self.text.setPlainText(text)
        self.show()
        self.raise_()

    def _run(self, mode: str) -> None:
        src = self.text.toPlainText().strip()
        if not src:
            return
        prompts = {
            "translate": "Detect language and translate to English (or to the user's preferred language if obvious). Return only the translation.\n\n",
            "summarise": "Summarise concisely:\n\n",
            "explain": "Explain clearly for a smart non-expert:\n\n",
            "fix": "Fix grammar, spelling and clarity. Return only the corrected text:\n\n",
        }
        try:
            result = generate_text(prompts[mode] + src, prefer_openrouter=True, module="summarize")
            self.out.setPlainText(result)
        except Exception as exc:
            self.out.setPlainText(str(exc))
