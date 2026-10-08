"""System control — apps, volume, brightness, WiFi, power, shell."""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path
from typing import Any

from jarvis.agent.confirm import confirm_gate
from jarvis.skills.base import Skill

SYSTEM = platform.system().lower()


def _run(cmd: list[str] | str, shell: bool = False) -> dict[str, Any]:
    try:
        r = subprocess.run(
            cmd,
            shell=shell,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return {"ok": r.returncode == 0, "stdout": r.stdout[-4000:], "stderr": r.stderr[-2000:], "code": r.returncode}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


class SystemControlSkill(Skill):
    name = "system_control"
    TOOLS = [
        {
            "name": "launch_app",
            "description": "Launch an application by name or path",
            "parameters": {
                "type": "object",
                "properties": {"app": {"type": "string"}, "args": {"type": "string"}},
                "required": ["app"],
            },
        },
        {
            "name": "run_terminal",
            "description": "Execute a shell command (non-destructive preferred)",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
        {
            "name": "set_volume",
            "description": "Set system volume 0-100",
            "parameters": {
                "type": "object",
                "properties": {"level": {"type": "integer"}},
                "required": ["level"],
            },
        },
        {
            "name": "set_brightness",
            "description": "Set display brightness 0-100",
            "parameters": {
                "type": "object",
                "properties": {"level": {"type": "integer"}},
                "required": ["level"],
            },
        },
        {
            "name": "wifi_toggle",
            "description": "Enable or disable WiFi — requires real user confirmation",
            "parameters": {
                "type": "object",
                "properties": {"enable": {"type": "boolean"}},
                "required": ["enable"],
            },
        },
        {
            "name": "shutdown",
            "description": "Shut down the computer — requires real user confirmation",
            "parameters": {"type": "object", "properties": {"delay_seconds": {"type": "integer"}}},
        },
        {
            "name": "restart",
            "description": "Restart the computer — requires real user confirmation",
            "parameters": {"type": "object", "properties": {"delay_seconds": {"type": "integer"}}},
        },
        {
            "name": "open_shortcut",
            "description": "Open a desktop shortcut or known OS location",
            "parameters": {
                "type": "object",
                "properties": {"target": {"type": "string"}},
                "required": ["target"],
            },
        },
    ]

    def handler(self, args: dict) -> Any:
        # Multi-tool skill: Gemini passes tool name via _tool injected by registry wrapper
        tool = args.pop("_tool", None) or args.pop("tool", None)
        # When called from dispatcher with name separately, args alone — detect by keys
        if tool is None:
            if "app" in args:
                tool = "launch_app"
            elif "command" in args:
                tool = "run_terminal"
            elif "level" in args and "brightness" in str(args):
                tool = "set_brightness"
            elif "level" in args:
                tool = "set_volume"
            elif "enable" in args:
                tool = "wifi_toggle"
            elif "target" in args:
                tool = "open_shortcut"
            else:
                tool = args.get("action", "run_terminal")

        if tool == "launch_app":
            return self._launch(args.get("app", ""), args.get("args", ""))
        if tool == "run_terminal":
            return _run(args.get("command", ""), shell=True)
        if tool == "set_volume":
            return self._volume(int(args.get("level", 50)))
        if tool == "set_brightness":
            return self._brightness(int(args.get("level", 50)))
        if tool == "wifi_toggle":
            conf = confirm_gate.request("wifi_toggle", args, f"Toggle WiFi enable={args.get('enable')}")
            if not conf.get("confirmed"):
                return conf
            return self._wifi(bool(args.get("enable", True)))
        if tool == "shutdown":
            conf = confirm_gate.request("shutdown", args, "Shut down this computer")
            if not conf.get("confirmed"):
                return conf
            return self._power("shutdown", int(args.get("delay_seconds", 0)))
        if tool == "restart":
            conf = confirm_gate.request("restart", args, "Restart this computer")
            if not conf.get("confirmed"):
                return conf
            return self._power("restart", int(args.get("delay_seconds", 0)))
        if tool == "open_shortcut":
            return self._launch(args.get("target", ""), "")
        return {"ok": False, "error": f"unknown system tool {tool}"}

    def _launch(self, app: str, extra: str) -> dict:
        if not app:
            return {"ok": False, "error": "no app"}
        try:
            if SYSTEM == "windows":
                os.startfile(app)  # type: ignore[attr-defined]
                return {"ok": True}
            if SYSTEM == "darwin":
                return _run(["open", app] + ([extra] if extra else []))
            return _run(["xdg-open", app])
        except Exception:
            return _run(f'"{app}" {extra}'.strip(), shell=True)

    def _volume(self, level: int) -> dict:
        level = max(0, min(100, level))
        if SYSTEM == "windows":
            cmd = (
                "powershell -NoProfile -Command \""
                f"$wshell = New-Object -ComObject WScript.Shell; "
                f"for ($i=0; $i -lt 50; $i++) {{ $wshell.SendKeys([char]174) }}; "
                f"$n = [int]({level}/2); for ($i=0; $i -lt $n; $i++) {{ $wshell.SendKeys([char]175) }}\""
            )
            return _run(cmd, shell=True)
        if SYSTEM == "darwin":
            return _run(["osascript", "-e", f"set volume output volume {level}"])
        return _run(["amixer", "sset", "Master", f"{level}%"])

    def _brightness(self, level: int) -> dict:
        level = max(0, min(100, level))
        if SYSTEM == "windows":
            cmd = (
                "powershell -NoProfile -Command "
                "\"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods)"
                f".WmiSetBrightness(1,{level})\""
            )
            return _run(cmd, shell=True)
        if SYSTEM == "darwin":
            val = level / 100.0
            return _run(["brightness", str(val)])  # may need brew brightness
        path = Path("/sys/class/backlight")
        if path.exists():
            for d in path.iterdir():
                maxb = int((d / "max_brightness").read_text())
                (d / "brightness").write_text(str(int(maxb * level / 100)))
                return {"ok": True}
        return {"ok": False, "error": "brightness unsupported"}

    def _wifi(self, enable: bool) -> dict:
        if SYSTEM == "windows":
            state = "enabled" if enable else "disabled"
            return _run(f'netsh interface set interface "Wi-Fi" admin={state}', shell=True)
        if SYSTEM == "darwin":
            device = "en0"
            return _run(["networksetup", "-setairportpower", device, "on" if enable else "off"])
        return _run(["nmcli", "radio", "wifi", "on" if enable else "off"])

    def _power(self, kind: str, delay: int) -> dict:
        if SYSTEM == "windows":
            flag = "/s" if kind == "shutdown" else "/r"
            return _run(f"shutdown {flag} /t {delay}", shell=True)
        if SYSTEM == "darwin":
            return _run(["osascript", "-e", f'tell app "System Events" to {kind}'])
        return _run(["shutdown", "-h" if kind == "shutdown" else "-r", f"+{max(0, delay // 60)}"])
