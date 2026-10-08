"""Auto-start on boot — registry / LaunchAgent / .desktop."""

from __future__ import annotations

import platform
import sys
from pathlib import Path

from jarvis.config import ROOT


def set_autostart(enabled: bool) -> dict:
    system = platform.system().lower()
    try:
        if system == "windows":
            return _windows(enabled)
        if system == "darwin":
            return _macos(enabled)
        return _linux(enabled)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _windows(enabled: bool) -> dict:
    import winreg

    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    name = "JARVIS"
    cmd = f'"{sys.executable}" "{ROOT / "main.py"}"'
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, name)
            except FileNotFoundError:
                pass
    return {"ok": True}


def _macos(enabled: bool) -> dict:
    plist = Path.home() / "Library/LaunchAgents/com.jarvis.assistant.plist"
    if not enabled:
        if plist.exists():
            plist.unlink()
        return {"ok": True}
    body = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.jarvis.assistant</string>
  <key>ProgramArguments</key>
  <array><string>{sys.executable}</string><string>{ROOT / "main.py"}</string></array>
  <key>RunAtLoad</key><true/>
</dict></plist>
"""
    plist.write_text(body, encoding="utf-8")
    return {"ok": True}


def _linux(enabled: bool) -> dict:
    desk = Path.home() / ".config/autostart/jarvis.desktop"
    desk.parent.mkdir(parents=True, exist_ok=True)
    if not enabled:
        if desk.exists():
            desk.unlink()
        return {"ok": True}
    desk.write_text(
        f"""[Desktop Entry]
Type=Application
Name=JARVIS
Exec={sys.executable} {ROOT / "main.py"}
X-GNOME-Autostart-enabled=true
""",
        encoding="utf-8",
    )
    return {"ok": True}
