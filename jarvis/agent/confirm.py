"""Real confirmation — model cannot confirm irreversible actions."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


IRREVERSIBLE = {"shutdown", "restart", "wifi_toggle", "wifi", "power_off", "reboot"}


@dataclass
class PendingConfirm:
    action: str
    args: dict
    description: str
    created_at: float
    resolve: Callable[[bool], None] | None = None


class ConfirmGate:
    """UI must press a button — LLM tool replies never auto-approve."""

    def __init__(self) -> None:
        self.pending: PendingConfirm | None = None
        self._ui_callback: Callable[[PendingConfirm], None] | None = None
        self._lock = threading.Lock()

    def set_ui(self, cb: Callable[[PendingConfirm], None]) -> None:
        self._ui_callback = cb

    def requires_confirm(self, action: str) -> bool:
        return action.lower().replace("-", "_") in IRREVERSIBLE

    def request(self, action: str, args: dict, description: str) -> dict[str, Any]:
        """Called from tool handler. Blocks until UI confirms/denies (timeout)."""
        event = threading.Event()
        result = {"ok": False, "confirmed": False, "error": "waiting"}

        def resolve(ok: bool) -> None:
            result["ok"] = ok
            result["confirmed"] = ok
            result["error"] = None if ok else "denied_by_user"
            event.set()

        pending = PendingConfirm(
            action=action,
            args=args,
            description=description,
            created_at=time.time(),
            resolve=resolve,
        )
        with self._lock:
            self.pending = pending
        if self._ui_callback:
            self._ui_callback(pending)
        # Wait up to 60s for human
        if not event.wait(timeout=60):
            result["error"] = "confirmation_timeout"
            with self._lock:
                self.pending = None
            return result
        with self._lock:
            self.pending = None
        return result

    def approve(self) -> None:
        with self._lock:
            if self.pending and self.pending.resolve:
                self.pending.resolve(True)

    def deny(self) -> None:
        with self._lock:
            if self.pending and self.pending.resolve:
                self.pending.resolve(False)


confirm_gate = ConfirmGate()
