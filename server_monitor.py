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
_CPU_SAMPLES: dict[int, tuple[float, int]] = {}


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


def _port_number(value: Any) -> int | None:
    try:
        port = int(value)
    except (TypeError, ValueError):
        return None
    return port if 1 <= port <= 65535 else None


def _cpu_percent(pid: int, ticks: int) -> float:
    now = time.monotonic()
    previous = _CPU_SAMPLES.get(pid)
    _CPU_SAMPLES[pid] = (now, ticks)
    if previous is None:
        return 0.0
    elapsed = now - previous[0]
    if elapsed <= 0:
        return 0.0
    clock_ticks = max(os.sysconf(os.sysconf_names["SC_CLK_TCK"]), 1)
    return round(max(ticks - previous[1], 0) / clock_ticks / elapsed * 100, 1)


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


def _disks() -> list[dict[str, Any]]:
    sys_block = Path("/sys/block")
    disks: dict[str, dict[str, Any]] = {}
    try:
        block_devices = list(sys_block.iterdir())
    except OSError:
        block_devices = []
    for block in block_devices:
        if not (block / "device").exists():
            continue
        try:
            sectors = int((block / "size").read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            continue
        model = _read(block / "device" / "model").strip()
        disks[block.name] = {
            "device": f"/dev/{block.name}",
            "model": model,
            "total": sectors * 512,
            "used": 0,
            "free": 0,
            "used_percent": None,
            "mounted": False,
        }

    mounted_devices: set[str] = set()
    virtual_filesystems = {"autofs", "cgroup", "cgroup2", "devpts", "mqueue", "proc", "sysfs", "tmpfs"}
    for line in _read(PROC / "mounts").splitlines():
        fields = line.split()
        if len(fields) < 3 or fields[2] in virtual_filesystems or not fields[1].startswith("/") or not fields[0].startswith("/dev/"):
            continue
        device, mountpoint = fields[:2]
        device_name = Path(device).name
        disk_name = next(
            (name for name in disks if device_name == name or (sys_block / name / device_name).exists()),
            None,
        )
        if disk_name is None or device_name in mounted_devices:
            continue
        mounted_devices.add(device_name)
        try:
            usage = os.statvfs(mountpoint)
        except OSError:
            continue
        disk = disks[disk_name]
        disk["mounted"] = True
        disk["used"] += max(usage.f_blocks * usage.f_frsize - usage.f_bavail * usage.f_frsize, 0)
        disk["free"] += usage.f_bavail * usage.f_frsize
        disk["used_percent"] = round(disk["used"] / disk["total"] * 100, 1) if disk["total"] else None
    return sorted(disks.values(), key=lambda disk: disk["device"])


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
                pid = int(proc.name)
                return {"pid": pid, "memory": int(rss.group(1)) * 1024 if rss else 0, "cpu_percent": _cpu_percent(pid, ticks), "command": cmdline or _read(proc / "comm").strip()}
    return None


def collect(apps: list[dict[str, Any]], command_tools: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    memory = _memory()
    disks = _disks()
    root_disk = next((disk for disk in disks if disk["mounted"]), {})
    processes = []
    for app in apps:
        ports = app.get("process_ports", ())
        if not ports:
            ports = (app.get("hostname"),)
        process = None
        port = _port_number(app.get("hostname"))
        for raw_port in ports:
            candidate = _port_number(raw_port)
            if candidate is None:
                continue
            process = _process_for_port(candidate)
            if process:
                break
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
        "disk": root_disk,
        "disks": disks,
        "apps": processes,
        "linux_proc_available": PROC.is_dir(),
        "format": {"memory_used": _human_bytes(memory["used"]), "disk_used": _human_bytes(root_disk.get("used", 0))},
    }
