"""Live theming — black/grey base, hue wheel retints accent + avatar."""

from __future__ import annotations

from PyQt6.QtGui import QColor

from jarvis.config import settings


def hue_to_hex(hue: int, sat: int = 28, val: int = 55) -> str:
    c = QColor()
    c.setHsv(int(hue) % 360, sat, val)
    return c.name()


def apply_hue(hue: int) -> dict:
    accent = hue_to_hex(hue, 22, 55)
    bright = hue_to_hex(hue, 18, 72)
    theme = {
        "bg": "#0A0A0A",
        "bg_elevated": "#121212",
        "bg_panel": "#161616",
        "border": "#2A2A2A",
        "text": "#E8E8E8",
        "text_muted": "#9A9A9A",
        "accent": accent,
        "accent_bright": bright,
        "danger": "#B91C1C",
        "success": "#3F3F46",
        "hue": hue,
    }
    settings.set("hue", hue)
    settings.set("hex_color", accent)
    settings.set("theme", theme)
    return theme


def stylesheet(theme: dict | None = None, opacity: float | None = None) -> str:
    t = theme or settings.get("theme")
    op = opacity if opacity is not None else float(settings.get("opacity", 0.92))
    # Qt stylesheets don't do window opacity; colors only
    return f"""
    QWidget {{
        background-color: {t['bg']};
        color: {t['text']};
        font-family: 'Segoe UI', 'IBM Plex Sans', 'Helvetica Neue', sans-serif;
        font-size: 13px;
    }}
    QMainWindow, QDialog {{
        background-color: {t['bg']};
    }}
    QFrame#panel, QFrame#contentPanel, QFrame#memoryPanel {{
        background-color: {t['bg_panel']};
        border: 1px solid {t['border']};
        border-radius: 2px;
    }}
    QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox {{
        background-color: {t['bg_elevated']};
        border: 1px solid {t['border']};
        border-radius: 2px;
        padding: 6px 8px;
        color: {t['text']};
        selection-background-color: {t['accent']};
    }}
    QPushButton {{
        background-color: {t['bg_elevated']};
        border: 1px solid {t['border']};
        border-radius: 2px;
        padding: 6px 12px;
        color: {t['text']};
    }}
    QPushButton:hover {{
        border-color: {t['accent_bright']};
        color: {t['accent_bright']};
    }}
    QPushButton#primary {{
        background-color: {t['accent']};
        border-color: {t['accent']};
        color: #0A0A0A;
        font-weight: 600;
    }}
    QPushButton#danger {{
        border-color: {t['danger']};
        color: {t['danger']};
    }}
    QLabel#muted {{
        color: {t['text_muted']};
    }}
    QLabel#brand {{
        color: {t['text']};
        font-size: 22px;
        font-weight: 300;
        letter-spacing: 6px;
    }}
    QSlider::groove:horizontal {{
        height: 2px;
        background: {t['border']};
    }}
    QSlider::handle:horizontal {{
        background: {t['accent_bright']};
        width: 10px;
        margin: -5px 0;
        border-radius: 1px;
    }}
    QScrollArea {{
        border: none;
        background: transparent;
    }}
    QListWidget {{
        background: {t['bg_elevated']};
        border: 1px solid {t['border']};
        outline: none;
    }}
    QListWidget::item {{
        padding: 8px;
        border-bottom: 1px solid {t['border']};
    }}
    QTabWidget::pane {{
        border: 1px solid {t['border']};
        background: {t['bg_panel']};
    }}
    QTabBar::tab {{
        background: {t['bg_elevated']};
        color: {t['text_muted']};
        padding: 8px 14px;
        border: 1px solid {t['border']};
        border-bottom: none;
        margin-right: 2px;
    }}
    QTabBar::tab:selected {{
        color: {t['text']};
        background: {t['bg_panel']};
    }}
    """
