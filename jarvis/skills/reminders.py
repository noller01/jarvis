"""Smart reminders — OS-native schedulers."""

from __future__ import annotations

import platform
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from jarvis.config import DATA
from jarvis.skills.base import Skill

SYSTEM = platform.system().lower()


class RemindersSkill(Skill):
    name = "reminders"
    TOOL = {
        "name": "set_reminder",
        "description": "Schedule an OS-native reminder notification",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "message": {"type": "string"},
                "when": {
                    "type": "string",
                    "description": "ISO datetime or relative like 'in 20 minutes'",
                },
            },
            "required": ["title", "when"],
        },
    }

    def handler(self, args: dict) -> Any:
        title = args.get("title") or "JARVIS Reminder"
        message = args.get("message") or title
        when = args.get("when") or ""
        try:
            if SYSTEM == "windows":
                return self._windows(title, message, when)
            if SYSTEM == "darwin":
                return self._macos(title, message, when)
            return self._linux(title, message, when)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _windows(self, title: str, message: str, when: str) -> dict:
        # Task Scheduler via schtasks — parse simple relative minutes
        minutes = self._rel_minutes(when)
        task = f"JARVIS_Reminder_{abs(hash(title + when)) % 10_000_000}"
        # Use a one-shot msg or powershell balloon
        ps = DATA / "uploads" / f"{task}.ps1"
        ps.parent.mkdir(parents=True, exist_ok=True)
        ps.write_text(
            f"[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null\n"
            f"Add-Type -AssemblyName System.Windows.Forms\n"
            f"[System.Windows.Forms.MessageBox]::Show('{message.replace(chr(39), chr(39)+chr(39))}', '{title.replace(chr(39), chr(39)+chr(39))}')\n",
            encoding="utf-8",
        )
        # create/run once after delay using schtasks
        delay = max(1, minutes)
        cmd = (
            f'schtasks /Create /F /SC ONCE /TN "{task}" /TR "powershell -ExecutionPolicy Bypass -File \\"{ps}\\"" '
            f"/ST {self._once_time(delay)}"
        )
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return {"ok": r.returncode == 0, "task": task, "stdout": r.stdout, "stderr": r.stderr}

    def _macos(self, title: str, message: str, when: str) -> dict:
        minutes = self._rel_minutes(when)
        label = f"com.jarvis.reminder.{abs(hash(title+when)) % 10_000_000}"
        plist = Path.home() / "Library/LaunchAgents" / f"{label}.plist"
        # For simplicity use `at` alternative: sleep in background launch agent is heavy —
        # use osascript delay in background process
        script = f"delay {minutes * 60}\ndisplay notification \"{message}\" with title \"{title}\""
        subprocess.Popen(["osascript", "-e", script])
        return {"ok": True, "method": "osascript", "label": label, "plist": str(plist)}

    def _linux(self, title: str, message: str, when: str) -> dict:
        minutes = self._rel_minutes(when)
        unit = f"jarvis-reminder-{abs(hash(title+when)) % 10_000_000}.service"
        # transient systemd timer via systemd-run
        cmd = [
            "systemd-run",
            f"--on-active={minutes * 60}s",
            "notify-send",
            title,
            message,
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            # fallback
            subprocess.Popen(["bash", "-c", f"sleep {minutes*60} && notify-send {title!r} {message!r}"])
        return {"ok": True, "unit": unit}

    @staticmethod
    def _rel_minutes(when: str) -> int:
        import re
        from datetime import datetime

        w = when.lower().strip()
        m = re.search(r"(\d+)\s*(minute|min|hour|hr|h|day|d)", w)
        if m:
            n = int(m.group(1))
            unit = m.group(2)
            if unit.startswith("h"):
                return n * 60
            if unit.startswith("d"):
                return n * 60 * 24
            return n
        try:
            dt = datetime.fromisoformat(when.replace("Z", "+00:00"))
            delta = (dt - datetime.now(dt.tzinfo)).total_seconds()
            return max(1, int(delta // 60))
        except Exception:
            return 10

    @staticmethod
    def _once_time(minutes_from_now: int) -> str:
        from datetime import datetime, timedelta

        t = datetime.now() + timedelta(minutes=minutes_from_now)
        return t.strftime("%H:%M")
