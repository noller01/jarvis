"""Real confirmation dialog — human button only."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from jarvis.ui.assets import pixmap


class ConfirmDialog(QDialog):
    decided = pyqtSignal(bool)

    def __init__(self, description: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Confirm")
        self.setModal(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        art = QLabel()
        art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pm = pixmap("confirm", 96, 96)
        if not pm.isNull():
            art.setPixmap(pm)
        layout.addWidget(art)
        layout.addWidget(QLabel("This action needs your confirmation."))
        desc = QLabel(description)
        desc.setWordWrap(True)
        layout.addWidget(desc)
        note = QLabel("The model cannot confirm this for you.")
        note.setObjectName("muted")
        layout.addWidget(note)
        row = QHBoxLayout()
        deny = QPushButton("Deny")
        deny.setObjectName("danger")
        allow = QPushButton("Confirm")
        allow.setObjectName("primary")
        deny.clicked.connect(lambda: self._done(False))
        allow.clicked.connect(lambda: self._done(True))
        row.addWidget(deny)
        row.addWidget(allow)
        layout.addLayout(row)
        self.resize(400, 280)

    def _done(self, ok: bool) -> None:
        self.decided.emit(ok)
        self.accept() if ok else self.reject()
