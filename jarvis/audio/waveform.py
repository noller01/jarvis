"""Reactive waveform levels from mic / assistant audio."""

from __future__ import annotations

import threading

import numpy as np


class WaveformMeter:
    def __init__(self) -> None:
        self._level = 0.0
        self._source = "idle"  # idle | mic | assistant
        self._lock = threading.Lock()

    def feed(self, pcm: bytes, source: str) -> None:
        if not pcm:
            return
        arr = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
        if arr.size == 0:
            return
        rms = float(np.sqrt(np.mean(arr * arr))) / 32768.0
        with self._lock:
            self._level = min(1.0, self._level * 0.6 + rms * 2.4)
            self._source = source

    def tick_decay(self) -> None:
        with self._lock:
            self._level *= 0.92
            if self._level < 0.02:
                self._level = 0.0
                self._source = "idle"

    @property
    def level(self) -> float:
        with self._lock:
            return self._level

    @property
    def source(self) -> str:
        with self._lock:
            return self._source


waveform = WaveformMeter()
