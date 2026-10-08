"""Undo — reverse file moves/renames/creates/writes and settings changes."""

from __future__ import annotations

import json
import shutil
import time
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from jarvis.config import DATA, settings


@dataclass
class UndoAction:
    id: str
    kind: str
    ts: float
    payload: dict
    description: str


class UndoStack:
    def __init__(self) -> None:
        self.dir = DATA / "undo"
        self.dir.mkdir(parents=True, exist_ok=True)
        self._stack: list[UndoAction] = []
        self._load()

    def _load(self) -> None:
        path = self.dir / "stack.json"
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                self._stack = [UndoAction(**a) for a in raw]
            except Exception:
                self._stack = []

    def _save(self) -> None:
        (self.dir / "stack.json").write_text(
            json.dumps([asdict(a) for a in self._stack[-200:]], indent=2),
            encoding="utf-8",
        )

    def push(self, kind: str, payload: dict, description: str) -> UndoAction:
        action = UndoAction(id=str(uuid.uuid4()), kind=kind, ts=time.time(), payload=payload, description=description)
        self._stack.append(action)
        self._save()
        return action

    def record_file_write(self, path: Path, previous: bytes | None) -> None:
        bak = self.dir / f"{uuid.uuid4()}.bak"
        if previous is not None:
            bak.write_bytes(previous)
        elif path.exists():
            shutil.copy2(path, bak)
            previous = b"__copied__"
        self.push(
            "file_write",
            {"path": str(path), "bak": str(bak) if previous is not None else None, "created": previous is None},
            f"Write {path.name}",
        )

    def record_file_move(self, src: Path, dst: Path) -> None:
        self.push("file_move", {"src": str(src), "dst": str(dst)}, f"Move {src.name} → {dst.name}")

    def record_file_create(self, path: Path) -> None:
        self.push("file_create", {"path": str(path)}, f"Create {path.name}")

    def record_settings(self, key: str, old: Any, new: Any) -> None:
        self.push("settings", {"key": key, "old": old, "new": new}, f"Settings {key}")

    def undo_last(self) -> str:
        if not self._stack:
            return "Nothing to undo."
        action = self._stack.pop()
        self._save()
        try:
            self._apply(action)
            return f"Undid: {action.description}"
        except Exception as exc:
            self._stack.append(action)
            self._save()
            return f"Undo failed: {exc}"

    def _apply(self, action: UndoAction) -> None:
        k = action.kind
        p = action.payload
        if k == "file_move":
            Path(p["dst"]).replace(Path(p["src"]))
        elif k == "file_create":
            path = Path(p["path"])
            if path.exists():
                path.unlink()
        elif k == "file_write":
            path = Path(p["path"])
            if p.get("created"):
                if path.exists():
                    path.unlink()
            elif p.get("bak"):
                bak = Path(p["bak"])
                if bak.exists():
                    shutil.copy2(bak, path)
        elif k == "settings":
            settings.set(p["key"], p["old"])

    def list_recent(self, n: int = 20) -> list[UndoAction]:
        return list(reversed(self._stack[-n:]))


undo_stack = UndoStack()
