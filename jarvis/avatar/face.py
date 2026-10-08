"""Holographic avatar — animated human head, real facial geometry, CPU-lit, no GPU packs."""

from __future__ import annotations

import math
import time
from typing import TYPE_CHECKING

from PyQt6.QtCore import QPointF, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QRadialGradient, QLinearGradient
from PyQt6.QtWidgets import QWidget

from jarvis.avatar.acting import FacialActing, FacePose
from jarvis.avatar.lipsync import LipSyncEngine, MouthTarget
from jarvis.avatar.status import AvatarStatus, apply_status

if TYPE_CHECKING:
    pass


def _qcolor_hue(hue: int, sat: int = 18, val: int = 72, alpha: int = 255) -> QColor:
    c = QColor()
    c.setHsv(hue % 360, sat, val, alpha)
    return c


class HolographicFace(QWidget):
    """Software-rasterized head mesh with Phong-ish shading via QPainter."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(280, 320)
        self.hue = 210
        self.status = AvatarStatus.ASLEEP
        self.acting = FacialActing()
        self.lipsync = LipSyncEngine()
        self._t0 = time.time()
        self._last = self._t0
        self._mouth = MouthTarget()
        self._pose = FacePose()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(20)  # ~50 fps mouth + acting

    def set_hue(self, hue: int) -> None:
        self.hue = int(hue) % 360
        self.update()

    def set_status(self, status: AvatarStatus | str) -> None:
        self.status = AvatarStatus(status) if isinstance(status, str) else status
        self.update()

    def feed_assistant_audio(self, pcm: bytes, rate: int = 24000) -> None:
        self._mouth = self.lipsync.feed_audio(pcm, rate)
        if self.status != AvatarStatus.SPEAKING:
            self.status = AvatarStatus.SPEAKING

    def set_transcript(self, text: str) -> None:
        self.lipsync.set_transcript(text)
        self.acting.on_phrase(text)

    def _tick(self) -> None:
        now = time.time()
        dt = now - self._last
        self._last = now
        speaking = self.status == AvatarStatus.SPEAKING
        pose = self.acting.tick(dt, speaking=speaking)
        pose = apply_status(pose, self.status, now - self._t0)
        self._pose = pose
        if not speaking:
            self._mouth = self.lipsync.idle()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(10, 10, 10, 0))

        cx, cy = w * 0.5, h * 0.48
        scale = min(w, h) * 0.42
        yaw = self._pose.head_yaw
        pitch = self._pose.head_pitch + self._pose.nod * 0.25

        # ambient plate
        glow = QRadialGradient(cx, cy, scale * 1.35)
        base = _qcolor_hue(self.hue, 22, 40, 90)
        glow.setColorAt(0.0, base)
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(glow)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), scale * 1.2, scale * 1.35)

        # build head geometry in unit space, then project
        verts = self._head_vertices()
        faces = self._head_faces()
        light = (0.35, -0.55, 0.75)
        light = self._norm(light)

        projected = []
        world = []
        for x, y, z in verts:
            # rotate yaw/pitch
            x, z = self._rot_y(x, z, yaw)
            y, z = self._rot_x(y, z, pitch)
            world.append((x, y, z))
            # perspective
            zc = z + 3.2
            px = cx + (x / zc) * scale * 2.6
            py = cy + (y / zc) * scale * 2.6
            projected.append((px, py, z))

        # painter's algorithm back-to-front
        order = []
        for i, (a, b, c) in enumerate(faces):
            depth = (world[a][2] + world[b][2] + world[c][2]) / 3.0
            order.append((depth, i))
        order.sort()

        for _, fi in order:
            a, b, c = faces[fi]
            n = self._normal(world[a], world[b], world[c])
            if n[2] > 0.02:  # backface
                continue
            ndot = max(0.0, -self._dot(n, light))
            amb = 0.18
            diff = 0.55 * ndot
            spec = (max(0.0, ndot) ** 12) * 0.35
            val = int(min(255, (amb + diff) * 200 + spec * 80))
            sat = int(12 + 20 * ndot)
            col = _qcolor_hue(self.hue, sat, max(28, val // 2 + 30), 220)
            path = QPainterPath()
            path.moveTo(*projected[a][:2])
            path.lineTo(*projected[b][:2])
            path.lineTo(*projected[c][:2])
            path.closeSubpath()
            p.setBrush(col)
            p.setPen(QPen(_qcolor_hue(self.hue, 10, 55, 90), 0.6))
            p.drawPath(path)

        # features overlay (eyes, brows, mouth) in screen space
        self._draw_features(p, cx, cy, scale, yaw, pitch)
        p.end()

    def _draw_features(self, p: QPainter, cx: float, cy: float, scale: float, yaw: float, pitch: float) -> None:
        ox = yaw * scale * 0.55
        oy = pitch * scale * 0.55
        pose = self._pose
        mouth = self._mouth

        # brows
        pen = QPen(_qcolor_hue(self.hue, 8, 180, 230), max(1.5, scale * 0.035))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        for side, brow in ((-1, pose.brow_l), (1, pose.brow_r)):
            bx = cx + ox + side * scale * 0.28
            by = cy + oy - scale * 0.22 - brow * scale * 0.08
            p.drawLine(
                QPointF(bx - scale * 0.12, by + side * 0.01 * scale),
                QPointF(bx + scale * 0.12, by - brow * 0.02 * scale),
            )

        # eyes
        for side in (-1, 1):
            ex = cx + ox + side * scale * 0.26 + pose.gaze_x * scale * 0.04
            ey = cy + oy - scale * 0.08 + pose.gaze_y * scale * 0.04
            lid = pose.lid_l if side < 0 else pose.lid_r
            eye_h = scale * 0.09 * lid
            eye_w = scale * 0.11
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(_qcolor_hue(self.hue, 5, 200, 230))
            p.drawEllipse(QPointF(ex, ey), eye_w, max(0.5, eye_h))
            # iris
            if lid > 0.15:
                p.setBrush(_qcolor_hue(self.hue, 40, 90, 255))
                p.drawEllipse(
                    QPointF(ex + pose.gaze_x * scale * 0.03, ey + pose.gaze_y * scale * 0.02),
                    scale * 0.045,
                    scale * 0.045 * lid,
                )
                p.setBrush(QColor(20, 20, 20, 240))
                p.drawEllipse(
                    QPointF(ex + pose.gaze_x * scale * 0.03, ey + pose.gaze_y * scale * 0.02),
                    scale * 0.02,
                    scale * 0.02 * lid,
                )

        # mouth from lip-sync targets
        mx = cx + ox
        my = cy + oy + scale * 0.28
        jaw = mouth.jaw * (1.0 - mouth.closure * 0.85)
        spread = 0.55 + mouth.lip_spread * 0.55
        round_n = mouth.lip_round
        mw = scale * 0.22 * (spread * (1.0 - round_n * 0.35))
        mh = scale * 0.04 + jaw * scale * 0.16
        if mouth.closure > 0.7:
            mh = scale * 0.012
        path = QPainterPath()
        path.moveTo(mx - mw, my)
        path.cubicTo(mx - mw * 0.4, my - mh * 0.2, mx + mw * 0.4, my - mh * 0.2, mx + mw, my)
        path.cubicTo(mx + mw * 0.5, my + mh, mx - mw * 0.5, my + mh, mx - mw, my)
        p.setBrush(_qcolor_hue(self.hue, 25, 45, 230))
        p.setPen(QPen(_qcolor_hue(self.hue, 10, 160, 200), 1.2))
        p.drawPath(path)
        # inner mouth
        if jaw > 0.15 and mouth.closure < 0.6:
            p.setBrush(QColor(8, 8, 8, 220))
            p.drawEllipse(QPointF(mx, my + mh * 0.25), mw * 0.55, mh * 0.45)

    # --- geometry ------------------------------------------------------------
    def _head_vertices(self) -> list[tuple[float, float, float]]:
        """Lathe-ish head + nose bridge vertices (unit sphere deformed)."""
        verts: list[tuple[float, float, float]] = []
        rings, segs = 10, 12
        for i in range(rings + 1):
            v = i / rings
            # egg profile
            y = (v - 0.5) * 2.05
            r = math.sin(math.pi * v) ** 0.9
            r *= 0.92 + 0.08 * math.cos(v * math.pi)
            if v > 0.55:  # jaw taper
                r *= 1.0 - (v - 0.55) * 0.55
            for j in range(segs):
                u = j / segs
                a = u * math.tau
                x = math.cos(a) * r * 0.85
                z = math.sin(a) * r * 0.78
                # cheek / brow bump
                if 0.28 < v < 0.48 and abs(math.cos(a)) > 0.3:
                    x *= 1.06
                verts.append((x, y, z))
        # nose tip
        verts.append((0.0, 0.02, 0.72))
        return verts

    def _head_faces(self) -> list[tuple[int, int, int]]:
        rings, segs = 10, 12
        faces: list[tuple[int, int, int]] = []
        for i in range(rings):
            for j in range(segs):
                a = i * segs + j
                b = i * segs + (j + 1) % segs
                c = (i + 1) * segs + j
                d = (i + 1) * segs + (j + 1) % segs
                faces.append((a, c, b))
                faces.append((b, c, d))
        nose = (rings + 1) * segs
        # attach nose to front verts roughly
        mid = 5 * segs
        faces.append((mid, mid + 1, nose))
        faces.append((mid, nose, mid + segs - 1))
        return faces

    @staticmethod
    def _rot_y(x: float, z: float, a: float) -> tuple[float, float]:
        c, s = math.cos(a), math.sin(a)
        return x * c + z * s, -x * s + z * c

    @staticmethod
    def _rot_x(y: float, z: float, a: float) -> tuple[float, float]:
        c, s = math.cos(a), math.sin(a)
        return y * c - z * s, y * s + z * c

    @staticmethod
    def _norm(v: tuple[float, float, float]) -> tuple[float, float, float]:
        l = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2) or 1.0
        return v[0] / l, v[1] / l, v[2] / l

    @staticmethod
    def _dot(a, b) -> float:  # noqa: ANN001
        return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

    @staticmethod
    def _normal(a, b, c):  # noqa: ANN001
        ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
        n = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
        l = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2) or 1.0
        return n[0] / l, n[1] / l, n[2] / l
