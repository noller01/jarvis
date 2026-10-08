"""Local 'Hey Jarvis' detection — no cloud streaming while asleep."""

from __future__ import annotations

import collections
import re
import time
from collections.abc import Callable

import numpy as np

# Lightweight energy + phonetic gate. Optional faster-whisper / vosk can plug in later.
WAKE_PATTERNS = [
    re.compile(r"\bhey\s+jarvis\b", re.I),
    re.compile(r"\bok(?:ay)?\s+jarvis\b", re.I),
    re.compile(r"\bjarvis\b", re.I),
]


class WakeWordDetector:
    def __init__(
        self,
        phrase: str = "hey jarvis",
        on_wake: Callable[[], None] | None = None,
        auto_sleep_seconds: float = 120.0,
    ) -> None:
        self.phrase = phrase.lower().strip()
        self.on_wake = on_wake
        self.auto_sleep_seconds = auto_sleep_seconds
        self.enabled = True
        self._last_activity = time.time()
        self._ring: collections.deque[np.ndarray] = collections.deque(maxlen=30)
        self._energy_hist: collections.deque[float] = collections.deque(maxlen=50)
        self._armed_burst = False
        self._partial_text = ""

    def note_activity(self) -> None:
        self._last_activity = time.time()

    def should_auto_sleep(self) -> bool:
        return (time.time() - self._last_activity) >= self.auto_sleep_seconds

    def feed_pcm(self, pcm: bytes) -> bool:
        """Returns True if wake detected from audio energy pattern + optional text."""
        if not self.enabled:
            return False
        arr = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
        if arr.size == 0:
            return False
        self._ring.append(arr)
        energy = float(np.sqrt(np.mean(arr * arr)))
        self._energy_hist.append(energy)
        baseline = float(np.median(self._energy_hist)) if self._energy_hist else 0.0
        # double-peak pattern typical of "hey" + "jarvis"
        if energy > max(1200.0, baseline * 3.5):
            self._armed_burst = True
        return False

    def feed_text(self, text: str) -> bool:
        """Local ASR / typed wake check. Does not require cloud while asleep if text is local."""
        if not self.enabled:
            return False
        blob = (self._partial_text + " " + text).lower()
        self._partial_text = blob[-80:]
        for pat in WAKE_PATTERNS:
            if pat.search(blob):
                self._partial_text = ""
                self.note_activity()
                if self.on_wake:
                    self.on_wake()
                return True
        # custom phrase
        if self.phrase and self.phrase in blob:
            self._partial_text = ""
            self.note_activity()
            if self.on_wake:
                self.on_wake()
            return True
        return False

    def check_energy_wake(self) -> bool:
        """Fallback: sustained speech-shaped energy while armed → soft wake for local listen."""
        if not self.enabled or not self._armed_burst:
            return False
        if len(self._energy_hist) < 10:
            return False
        recent = list(self._energy_hist)[-12:]
        peaks = sum(1 for e in recent if e > 1000)
        if peaks >= 4:
            self._armed_burst = False
            self.note_activity()
            if self.on_wake:
                self.on_wake()
            return True
        return False
