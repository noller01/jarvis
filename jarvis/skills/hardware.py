"""Hardware monitoring — CPU, RAM, GPU, temperature with alert thresholds."""

from __future__ import annotations

from typing import Any

import psutil

from jarvis.skills.base import Skill


class HardwareSkill(Skill):
    name = "hardware"
    TOOL = {
        "name": "hardware_status",
        "description": "Report CPU, RAM, disk, and temperature telemetry",
        "parameters": {"type": "object", "properties": {}},
    }

    def handler(self, args: dict) -> Any:
        vm = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        temps = {}
        try:
            if hasattr(psutil, "sensors_temperatures"):
                t = psutil.sensors_temperatures() or {}
                for k, entries in t.items():
                    if entries:
                        temps[k] = entries[0].current
        except Exception:
            pass
        gpu = None
        try:
            import subprocess

            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,temperature.gpu", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if r.returncode == 0 and r.stdout.strip():
                parts = [p.strip() for p in r.stdout.strip().split(",")]
                gpu = {"util": parts[0], "mem_mb": parts[1], "temp_c": parts[2]}
        except Exception:
            pass
        data = {
            "cpu_percent": psutil.cpu_percent(interval=0.2),
            "ram_percent": vm.percent,
            "ram_used_gb": round(vm.used / (1024**3), 2),
            "disk_percent": disk.percent,
            "temps": temps,
            "gpu": gpu,
        }
        alerts = []
        if data["cpu_percent"] > 90:
            alerts.append("CPU critically high")
        if data["ram_percent"] > 90:
            alerts.append("RAM critically high")
        if any(v > 90 for v in temps.values()):
            alerts.append("Temperature critically high")
        return {"ok": True, "telemetry": data, "alerts": alerts, "display": data}
