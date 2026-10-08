"""Nine-rung Gemini model ladder — quota/timeout/outage steps down."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from jarvis.config import settings

log = logging.getLogger("jarvis.ladder")


class ModelLadder:
    def __init__(self, models: list[str] | None = None) -> None:
        self.models = list(models or settings.get("model_ladder", []))
        self._index = 0
        self._failures: dict[str, float] = {}
        self.cooldown = 120.0  # seconds before retrying a failed model

    @property
    def current(self) -> str:
        return self.models[min(self._index, len(self.models) - 1)]

    def mark_failure(self, model: str | None = None) -> None:
        m = model or self.current
        self._failures[m] = time.time()
        if self._index < len(self.models) - 1:
            self._index += 1
            log.warning("Ladder step → %s", self.current)

    def reset(self) -> None:
        self._index = 0

    def available_models(self) -> list[str]:
        now = time.time()
        out = []
        for m in self.models:
            failed_at = self._failures.get(m)
            if failed_at and (now - failed_at) < self.cooldown:
                continue
            out.append(m)
        return out or list(self.models)

    def call(
        self,
        fn: Callable[[str], Any],
        *,
        is_failure: Callable[[BaseException], bool] | None = None,
    ) -> Any:
        """Try current model, step on quota/timeout/outage."""

        def _default_fail(exc: BaseException) -> bool:
            msg = str(exc).lower()
            needles = ("quota", "429", "timeout", "503", "unavailable", "overloaded", "resource_exhausted")
            return any(n in msg for n in needles)

        check = is_failure or _default_fail
        last_exc: BaseException | None = None
        for model in self.available_models():
            try:
                return fn(model)
            except BaseException as exc:  # noqa: BLE001 — ladder must catch provider errors
                last_exc = exc
                if check(exc):
                    self.mark_failure(model)
                    continue
                raise
        if last_exc:
            raise last_exc
        raise RuntimeError("Model ladder exhausted")


ladder = ModelLadder()
