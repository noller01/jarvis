"""Self-echo guard — drop the tail of JARVIS's own voice without muting the user."""

from __future__ import annotations

import hashlib
import time
from collections import deque

import numpy as np


def _pcm_energy(pcm: bytes) -> float:
    if not pcm:
        return 0.0
    arr = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    if arr.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(arr * arr)))


def _fingerprint(pcm: bytes, bins: int = 32) -> bytes:
    """Coarse spectral fingerprint for echo matching."""
    arr = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    if arr.size < 64:
        return b""
    # windowed magnitude downsample
    step = max(1, arr.size // bins)
    feats = []
    for i in range(0, arr.size - step, step):
        chunk = arr[i : i + step]
        feats.append(int(np.clip(np.mean(np.abs(chunk)) / 50.0, 0, 255)))
    return bytes(feats[:bins])


class EchoGuard:
    def __init__(self, hold_seconds: float = 1.8, similarity: float = 0.82) -> None:
        self.hold_seconds = hold_seconds
        self.similarity = similarity
        self._prints: deque[tuple[float, bytes, str]] = deque(maxlen=40)
        self._last_text = ""
        self._mute_until = 0.0

    def remember_assistant(self, audio: bytes, text: str = "") -> None:
        now = time.time()
        # store overlapping windows of the assistant audio
        frame = 2048
        for i in range(0, max(0, len(audio) - frame), frame // 2):
            fp = _fingerprint(audio[i : i + frame])
            if fp:
                self._prints.append((now, fp, text))
        self._last_text = (text or "").strip().lower()
        # brief soft gate right after TTS to catch near-field coupling
        self._mute_until = now + 0.12

    def should_drop(self, mic_pcm: bytes, transcript_tail: str = "") -> bool:
        now = time.time()
        # Never hard-mute the user — only drop frames that match own voice
        if now < self._mute_until and _pcm_energy(mic_pcm) > 500:
            # during soft gate, still allow loud user barge-in
            if _pcm_energy(mic_pcm) > 2500:
                return False
        fp = _fingerprint(mic_pcm)
        if not fp:
            return False
        # text echo: if ASR returns our own last sentence, drop
        tail = (transcript_tail or "").strip().lower()
        if self._last_text and tail and (tail in self._last_text or self._last_text in tail):
            if len(tail) > 12:
                return True
        # audio fingerprint match against recent assistant frames
        for ts, ref, _ in list(self._prints):
            if now - ts > self.hold_seconds:
                continue
            if self._sim(fp, ref) >= self.similarity:
                return True
        return False

    @staticmethod
    def _sim(a: bytes, b: bytes) -> float:
        n = min(len(a), len(b))
        if n == 0:
            return 0.0
        a2, b2 = a[:n], b[:n]
        diff = sum(abs(a2[i] - b2[i]) for i in range(n))
        return 1.0 - (diff / (n * 255.0))


echo_guard = EchoGuard()
