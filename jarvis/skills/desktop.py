"""Desktop control — windows, taskbar, screenshots."""

from __future__ import annotations

import platform
import subprocess
from typing import Any

from jarvis.core.openrouter import openrouter
from jarvis.skills.base import Skill

SYSTEM = platform.system().lower()


class DesktopSkill(Skill):
    name = "desktop_control"
    TOOLS = [
        {
            "name": "desktop_list_windows",
            "description": "List open window titles",
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "desktop_focus_window",
            "description": "Focus a window by title substring",
            "parameters": {
                "type": "object",
                "properties": {"title": {"type": "string"}},
                "required": ["title"],
            },
        },
        {
            "name": "desktop_minimize_all",
            "description": "Show desktop / minimize all windows",
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "desktop_screenshot",
            "description": "Capture the screen and optionally describe it",
            "parameters": {
                "type": "object",
                "properties": {"describe": {"type": "boolean"}},
            },
        },
    ]

    def handler(self, args: dict) -> Any:
        if args.get("describe") is not None or args.get("_tool") == "desktop_screenshot":
            return self._shot(bool(args.get("describe", True)))
        if "title" in args:
            return self._focus(args["title"])
        if args.get("_tool") == "desktop_minimize_all" or args.get("minimize"):
            return self._minimize_all()
        return self._list()

    def _list(self) -> dict:
        if SYSTEM == "windows":
            cmd = (
                "powershell -NoProfile -Command "
                "\"Get-Process | Where-Object {$_.MainWindowTitle} | "
                "Select-Object -ExpandProperty MainWindowTitle\""
            )
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
            titles = [t.strip() for t in r.stdout.splitlines() if t.strip()]
            return {"ok": True, "windows": titles}
        if SYSTEM == "darwin":
            script = 'tell application "System Events" to get name of every window of every process'
            r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=15)
            return {"ok": True, "windows": r.stdout}
        r = subprocess.run(["wmctrl", "-l"], capture_output=True, text=True, timeout=15)
        return {"ok": True, "windows": r.stdout.splitlines()}

    def _focus(self, title: str) -> dict:
        if SYSTEM == "windows":
            ps = (
                f"$w = Get-Process | Where-Object {{ $_.MainWindowTitle -match '{title}' }} | Select-Object -First 1; "
                "if ($w) { Add-Type '@\nusing System; using System.Runtime.InteropServices;\n"
                "public class W { [DllImport(\"user32.dll\")] public static extern bool SetForegroundWindow(IntPtr hWnd); }\n'@; "
                "[W]::SetForegroundWindow($w.MainWindowHandle) }"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], timeout=15)
            return {"ok": True}
        if SYSTEM == "darwin":
            subprocess.run(["osascript", "-e", f'tell application "{title}" to activate'], timeout=15)
            return {"ok": True}
        subprocess.run(["wmctrl", "-a", title], timeout=15)
        return {"ok": True}

    def _minimize_all(self) -> dict:
        if SYSTEM == "windows":
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(New-Object -ComObject Shell.Application).ToggleDesktop()"],
                timeout=10,
            )
            return {"ok": True}
        if SYSTEM == "darwin":
            subprocess.run(
                ["osascript", "-e", 'tell application "System Events" to key code 103'],
                timeout=10,
            )
            return {"ok": True}
        subprocess.run(["xdotool", "key", "super+d"], timeout=10)
        return {"ok": True}

    def _shot(self, describe: bool) -> dict:
        from jarvis.config import DATA
        import mss

        path = DATA / "uploads" / "screenshot.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        with mss.mss() as sct:
            sct.shot(output=str(path))
        result: dict[str, Any] = {"ok": True, "path": str(path)}
        if describe:
            try:
                from jarvis.core.gemini import generate_with_image

                result["description"] = generate_with_image(
                    "Describe this desktop screenshot briefly.",
                    path.read_bytes(),
                )
            except Exception as exc:
                if openrouter.available:
                    result["description"] = f"(vision unavailable: {exc})"
                else:
                    result["error_describe"] = str(exc)
        return result
