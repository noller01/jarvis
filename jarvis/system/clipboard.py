"""Clipboard intelligence watcher."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable


class ClipboardWatcher:
    def __init__(self, on_text: Callable[[str], None] | None = None) -> None:
        self.on_text = on_text
        self._last = ""
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="jarvis-clipboard")
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _loop(self) -> None:
        try:
            import pyperclip
        except ImportError:
            return
        while self._running:
            try:
                text = pyperclip.paste()
                if isinstance(text, str) and text.strip() and text != self._last:
                    # ignore huge pastes
                    if 8 <= len(text) <= 8000 and "\x00" not in text:
                        self._last = text
                        if self.on_text:
                            self.on_text(text)
            except Exception:
                pass
            time.sleep(1.0)
