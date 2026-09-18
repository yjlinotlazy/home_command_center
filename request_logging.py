"""Best-effort request telemetry used by the embedded tools."""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


_WRITE_LOCK = threading.Lock()


def tool_id_for_target(target: str) -> str | None:
    path = urlsplit(target).path
    if path.startswith("/tools/"):
        remainder = path.removeprefix("/tools/")
    elif path.startswith("/api/tools/"):
        remainder = path.removeprefix("/api/tools/")
    else:
        return None
    tool_id = remainder.split("/", 1)[0].strip()
    return f"tool:{tool_id}" if tool_id else None


def route_for_target(target: str) -> str:
    path = urlsplit(target).path or "/"
    if path.startswith("/api/tools/"):
        parts = path.removeprefix("/api/tools/").split("/")
        return "/api/tools/" + (parts[0] if parts else ":path") + ("/:path" if len(parts) > 1 else "")
    if path.startswith("/tools/"):
        parts = path.removeprefix("/tools/").split("/")
        return "/tools/" + (parts[0] if parts else ":path") + ("/:path" if len(parts) > 1 else "")
    return path


class CountingWriter:
    def __init__(self, wrapped: Any) -> None:
        self._wrapped = wrapped
        self.bytes_written = 0

    def write(self, data: bytes) -> int:
        self.bytes_written += len(data)
        return self._wrapped.write(data)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._wrapped, name)


class ToolRequestLogger:
    def __init__(self, root: Path) -> None:
        self.root = root / "server_logs"

    def record(self, *, target: str, method: str, status: int, request_size: int, response_size: int, started_at: float) -> None:
        app_id = tool_id_for_target(target)
        if not app_id:
            return
        event = {
            "timestamp": datetime.fromtimestamp(started_at).astimezone().isoformat(),
            "method": method,
            "route": route_for_target(target),
            "status": int(status),
            "request_bytes": int(request_size),
            "response_bytes": int(response_size),
            "latency_ms": round(max(0.0, (time.time() - started_at) * 1000), 3),
        }
        try:
            directory = self.root / app_id / "raw"
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / f"{datetime.fromtimestamp(started_at).date().isoformat()}.jsonl"
            line = json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
            with _WRITE_LOCK:
                with path.open("a", encoding="utf-8") as stream:
                    stream.write(line)
        except Exception:
            return
