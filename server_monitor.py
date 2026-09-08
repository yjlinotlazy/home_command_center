"""Small, Linux-friendly server metrics collector with no extra dependencies."""

from __future__ import annotations

import os
import platform
import re
import socket
import time
from pathlib import Path
from typing import Any


PROC = Path("/proc")


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _human_bytes(value: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    number = float(value)
    for unit in units:
        if number < 1024 or unit == units[-1]:
            return f"{number:.1f} {unit}"
        number /= 1024
    return f"{value} B"


def _memory() -> dict[str, Any]:
    values: dict[str, int] = {}
    for line in _read(PROC / "meminfo").splitlines():
        match = re.match(r"(MemTotal|MemAvailable):\s+(\d+)", line)
        if match:
            values[match.group(1)] = int(match.group(2)) * 1024
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", 0)
    used = max(total - available, 0)
    return {"total": total, "available": available, "used": used, "used_percent": round(used / total * 100, 1) if total else None}


def _process_for_port(port: int | None) -> dict[str, Any] | None:
    if not port or not PROC.is_dir():
        return None
    inodes: set[str] = set()
    wanted = f":{port:04X}"
    for table in (PROC / "net/tcp", PROC / "net/tcp6"):
        for line in _read(table).splitlines()[1:]:
            fields = line.split()
            if len(fields) >= 10 and fields[1].upper().endswith(wanted) and fields[3] == "0A":
                inodes.add(fields[9])
    if not inodes:
        return None
    for proc in PROC.iterdir():
        if not proc.name.isdigit():
            continue
        fd_dir = proc / "fd"
        try:
            fds = list(fd_dir.iterdir())
        except OSError:
            continue
        for fd in fds:
            try:
                target = os.readlink(fd)
            except OSError:
                continue
            if target.startswith("socket:[") and target[8:-1] in inodes:
                status = _read(proc / "status")
                rss = re.search(r"VmRSS:\s+(\d+)", status)
                cpu = _read(proc / "stat").split()
                ticks = int(cpu[13]) + int(cpu[14]) if len(cpu) > 14 else 0
                cmdline = _read(proc / "cmdline").replace("\x00", " ").strip()
                return {"pid": int(proc.name), "memory": int(rss.group(1)) * 1024 if rss else 0, "cpu_time": round(ticks / max(os.sysconf(os.sysconf_names["SC_CLK_TCK"]), 1), 1), "command": cmdline or _read(proc / "comm").strip()}
    return None


def collect(apps: list[dict[str, Any]], command_tools: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    memory = _memory()
    disk = os.statvfs("/")
    disk_total = disk.f_blocks * disk.f_frsize
    disk_free = disk.f_bavail * disk.f_frsize
    processes = []
    for app in apps:
        port = None
        try:
            port = int(app.get("hostname", ""))
        except (TypeError, ValueError):
            pass
        process = _process_for_port(port)
        status = app.get("status", "unknown")
        if status == "unknown" and process:
            status = "online"
        processes.append({"id": app["id"], "name": app["name"], "port": port, "status": status, "process": process})
    for tool in command_tools or []:
        processes.append({"id": f"tool:{tool['id']}", "name": tool["name"], "port": None, "status": "embedded", "process": None})
    uptime = _read(PROC / "uptime").split()
    uptime_seconds = int(float(uptime[0])) if uptime else 0
    return {
        "updated_at": int(time.time()),
        "host": socket.gethostname(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "uptime_seconds": uptime_seconds,
        "cpu": {"cores": os.cpu_count() or 1, "load": [round(value, 2) for value in os.getloadavg()] if hasattr(os, "getloadavg") else []},
        "memory": memory,
        "disk": {"total": disk_total, "free": disk_free, "used": max(disk_total - disk_free, 0), "used_percent": round((disk_total - disk_free) / disk_total * 100, 1) if disk_total else None},
        "apps": processes,
        "linux_proc_available": PROC.is_dir(),
        "format": {"memory_used": _human_bytes(memory["used"]), "disk_used": _human_bytes(max(disk_total - disk_free, 0))},
    }
