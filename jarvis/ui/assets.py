"""Higgsfield-generated HUD graphics."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QByteArray, QRectF, Qt, QSize
from PyQt6.QtGui import QIcon, QImage, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

from jarvis.config import ROOT

ASSETS = ROOT / "assets" / "hud"

FILES = {
    "icon": "icon.svg",
    "wordmark": "wordmark.svg",
    "splash": "splash_bg.png",
    "avatar": "avatar_holo.png",
    "icons": "icons_sheet.svg",
    "panel_header": "panel_header.png",
    "empty_memory": "empty_memory.png",
    "morning": "morning_banner.png",
    "confirm": "confirm_alert.svg",
    "waveform": "waveform_deco.svg",
    "remote": "remote_phone.svg",
    "status": "status_rings.svg",
}


def path(key: str) -> Path:
    name = FILES.get(key, key)
    return ASSETS / name


def exists(key: str) -> bool:
    return path(key).exists()


def pixmap(key: str, width: int | None = None, height: int | None = None) -> QPixmap:
    p = path(key)
    if not p.exists():
        return QPixmap()
    if p.suffix.lower() == ".svg":
        return _svg_pixmap(p, width or 256, height or 256)
    pm = QPixmap(str(p))
    if width or height:
        pm = pm.scaled(
            width or pm.width(),
            height or pm.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    return pm


def _svg_pixmap(p: Path, w: int, h: int) -> QPixmap:
    data = QByteArray(p.read_bytes())
    renderer = QSvgRenderer(data)
    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0)
    painter = QPainter(img)
    renderer.render(painter, QRectF(0, 0, w, h))
    painter.end()
    return QPixmap.fromImage(img)


def app_icon() -> QIcon:
    pm = pixmap("icon", 256, 256)
    return QIcon(pm) if not pm.isNull() else QIcon()


def label_with_image(key: str, width: int | None = None, height: int | None = None):
    from PyQt6.QtWidgets import QLabel

    lab = QLabel()
    pm = pixmap(key, width, height)
    if not pm.isNull():
        lab.setPixmap(pm)
        lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lab.setScaledContents(False)
    return lab
