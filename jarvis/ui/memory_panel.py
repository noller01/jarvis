"""Memory panel — every stored fact, when learned, one-click delete."""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from jarvis.memory.store import memory
from jarvis.ui.assets import pixmap


class MemoryPanel(QFrame):
    closed = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("memoryPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        header = QHBoxLayout()
        title = QLabel("MEMORY")
        title.setObjectName("brand")
        title.setStyleSheet("font-size: 14px; letter-spacing: 3px;")
        header.addWidget(title)
        header.addStretch()
        close = QPushButton("Close")
        close.clicked.connect(self.closed.emit)
        header.addWidget(close)
        layout.addLayout(header)
        hint = QLabel("Facts JARVIS has stored about you")
        hint.setObjectName("muted")
        layout.addWidget(hint)
        self.empty = QLabel()
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        emp = pixmap("empty_memory", 280, 200)
        if not emp.isNull():
            self.empty.setPixmap(emp)
        else:
            self.empty.setText("No memories yet")
            self.empty.setObjectName("muted")
        layout.addWidget(self.empty)
        self.list = QListWidget()
        layout.addWidget(self.list)
        row = QHBoxLayout()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.reload)
        delete = QPushButton("Delete selected")
        delete.setObjectName("danger")
        delete.clicked.connect(self._delete)
        row.addWidget(refresh)
        row.addWidget(delete)
        layout.addLayout(row)
        self.reload()

    def reload(self) -> None:
        self.list.clear()
        facts = memory.list_all()
        self.empty.setVisible(len(facts) == 0)
        self.list.setVisible(len(facts) > 0)
        for fact in facts:
            when = datetime.fromtimestamp(fact.created_at).strftime("%Y-%m-%d %H:%M")
            item = QListWidgetItem(f"[{fact.category}] {fact.content}\n{when} · {fact.source}")
            item.setData(256, fact.id)
            self.list.addItem(item)

    def _delete(self) -> None:
        item = self.list.currentItem()
        if not item:
            return
        fid = item.data(256)
        memory.delete(fid)
        self.reload()
