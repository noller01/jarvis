"""Continuous hardware telemetry alerts."""

from __future__ import annotations

import time
from typing import Callable

from jarvis.config import settings
from jarvis.skills.hardware import HardwareSkill


class HardwareWatch:
    def __init__(self, alert: Callable[[str], None] | None = None) -> None:
        self.alert = alert
        self._last = 0.0
        self._last_alert = 0.0

    def tick(self) -> None:
        if not settings.get("hardware_alerts", True):
            return
        now = time.time()
        if now - self._last < 30:
            return
        self._last = now
        data = HardwareSkill().handler({})
        alerts = data.get("alerts") or []
        if alerts and now - self._last_alert > 120:
            self._last_alert = now
            lang = settings.get("language") or "en"
            msg = "; ".join(alerts)
            if self.alert:
                self.alert(msg)
