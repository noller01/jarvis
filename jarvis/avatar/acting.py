"""Facial acting — brows, gaze saccades, blinks, stress nods."""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field


@dataclass
class FacePose:
    brow_l: float = 0.0
    brow_r: float = 0.0
    gaze_x: float = 0.0
    gaze_y: float = 0.0
    lid_l: float = 1.0  # 1 open, 0 closed
    lid_r: float = 1.0
    nod: float = 0.0
    head_yaw: float = 0.0
    head_pitch: float = 0.0


@dataclass
class ActingState:
    pose: FacePose = field(default_factory=FacePose)
    _next_blink: float = 0.0
    _blink_t: float = 0.0
    _blinking: bool = False
    _next_saccade: float = 0.0
    _fix_x: float = 0.0
    _fix_y: float = 0.0
    _phrase_energy: float = 0.0


class FacialActing:
    def __init__(self) -> None:
        self.state = ActingState()
        self.state._next_blink = time.time() + random.uniform(2.5, 5.5)
        self.state._next_saccade = time.time() + random.uniform(0.8, 2.2)

    def on_phrase(self, text: str) -> None:
        # brows track phrase intensity / punctuation
        intensity = min(1.0, len(text) / 80.0)
        if "?" in text:
            self.state.pose.brow_l = 0.55 + 0.2 * intensity
            self.state.pose.brow_r = 0.55 + 0.2 * intensity
        elif "!" in text:
            self.state.pose.brow_l = 0.35
            self.state.pose.brow_r = 0.45
        else:
            self.state.pose.brow_l = 0.1 * intensity
            self.state.pose.brow_r = 0.12 * intensity
        self.state._phrase_energy = intensity

    def on_stress(self) -> None:
        """Small nod on stressed syllables."""
        self.state.pose.nod = 0.35

    def tick(self, dt: float, speaking: bool = False) -> FacePose:
        st = self.state
        now = time.time()
        # blink
        if not st._blinking and now >= st._next_blink:
            st._blinking = True
            st._blink_t = 0.0
        if st._blinking:
            st._blink_t += dt
            # close then open ~120ms
            phase = st._blink_t / 0.12
            if phase < 0.45:
                lid = 1.0 - phase / 0.45
            elif phase < 1.0:
                lid = (phase - 0.45) / 0.55
            else:
                lid = 1.0
                st._blinking = False
                st._next_blink = now + random.uniform(2.0, 6.0)
            st.pose.lid_l = st.pose.lid_r = max(0.0, min(1.0, lid))

        # gaze saccades between fixations
        if now >= st._next_saccade:
            st._fix_x = random.uniform(-0.35, 0.35)
            st._fix_y = random.uniform(-0.2, 0.25)
            st._next_saccade = now + random.uniform(0.6, 2.8)
        st.pose.gaze_x += (st._fix_x - st.pose.gaze_x) * min(1.0, dt * 14)
        st.pose.gaze_y += (st._fix_y - st.pose.gaze_y) * min(1.0, dt * 14)

        # nod decay + speech micro-nods
        st.pose.nod *= 0.85
        if speaking and random.random() < 0.04:
            st.pose.nod = max(st.pose.nod, 0.2 + 0.15 * st._phrase_energy)

        # brow settle
        st.pose.brow_l *= 0.98
        st.pose.brow_r *= 0.98
        return st.pose


acting = FacialActing()
