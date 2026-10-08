"""Push-to-talk — hold Ctrl+Space. Global on Windows, window-scoped elsewhere."""

from __future__ import annotations

import platform
import threading
from collections.abc import Callable


class PushToTalk:
    def __init__(self, on_down: Callable[[], None], on_up: Callable[[], None]) -> None:
        self.on_down = on_down
        self.on_up = on_up
        self._pressed = False
        self._listener = None
        self._global = platform.system().lower() == "windows"

    @property
    def pressed(self) -> bool:
        return self._pressed

    def start(self) -> None:
        if self._global:
            self._start_global()
        # window-scoped handled by HUD key events when not Windows

    def stop(self) -> None:
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None

    def handle_key(self, key: str, modifiers: set[str], down: bool) -> bool:
        """Window-scoped fallback. Returns True if handled."""
        mods = {m.lower() for m in modifiers}
        if key.lower() in ("space", " ") and ("ctrl" in mods or "control" in mods):
            if down and not self._pressed:
                self._pressed = True
                self.on_down()
            elif not down and self._pressed:
                self._pressed = False
                self.on_up()
            return True
        return False

    def _start_global(self) -> None:
        try:
            from pynput import keyboard
        except ImportError:
            return

        ctrl = False

        def on_press(key):  # noqa: ANN001
            nonlocal ctrl
            if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                ctrl = True
            if key == keyboard.Key.space and ctrl and not self._pressed:
                self._pressed = True
                self.on_down()

        def on_release(key):  # noqa: ANN001
            nonlocal ctrl
            if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                ctrl = False
                if self._pressed:
                    self._pressed = False
                    self.on_up()
            if key == keyboard.Key.space and self._pressed:
                self._pressed = False
                self.on_up()

        self._listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._listener.daemon = True
        self._listener.start()
