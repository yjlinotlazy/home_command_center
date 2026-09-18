"""Lazy, per-app usage and Git statistics."""

from __future__ import annotations

import json
import subprocess
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable


HCC_ROOT = Path(__file__).resolve().parent
REPO_ROOT = HCC_ROOT.parent
REPO_ALIASES = {
    "inspire": "inspiration_bank",
    "drum_buddy": "drummer_buddy",
    "paint_shop": "my_painter_shop",
}
# These apps are registered as ordinary dashboard apps but are served by HCC.
# Their request logger uses the tool: namespace.
EMBEDDED_APP_IDS = {"tomato_watch"}
_GIT_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def repo_for_app(app_id: str) -> Path | None:
    if app_id.startswith("tool:") or app_id in EMBEDDED_APP_IDS:
        return HCC_ROOT
    name = REPO_ALIASES.get(app_id, app_id)
    candidate = (REPO_ROOT / name).resolve()
    return candidate if (candidate / ".git").exists() else None


def _raw_files(repo: Path, first_day: date) -> Iterable[Path]:
    raw = repo / "server_logs" / repo.name / "raw"
    # The app id normally equals the repo name; aliases are handled below.
    if not raw.is_dir():
        for candidate in (repo / "server_logs").glob("*/raw"):
            raw = candidate
            break
    if not raw.is_dir():
        return ()
    return (path for path in raw.glob("*.jsonl") if path.stem >= first_day.isoformat())


def _read_events(repo: Path, app_id: str, first_day: date) -> list[dict[str, Any]]:
    raw = next(
        (repo / "server_logs" / log_id / "raw" for log_id in _log_ids(app_id)
         if (repo / "server_logs" / log_id / "raw").is_dir()),
        repo / "server_logs" / repo.name / "raw",
    )
    events: list[dict[str, Any]] = []
    for path in raw.glob("*.jsonl") if raw.is_dir() else ():
        if path.stem < first_day.isoformat():
            continue
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict):
                    events.append(event)
        except OSError:
            continue
    return events


def _log_ids(app_id: str) -> tuple[str, ...]:
    if app_id in EMBEDDED_APP_IDS:
        return (f"tool:{app_id}", app_id)
    return (app_id,)


def refresh_hourly(repo: Path, app_id: str, now: date | None = None) -> None:
    """Materialize hourly aggregates and remove raw files older than 30 days."""
    today = now or date.today()
    cutoff = today - timedelta(days=29)
    raw = next(
        (repo / "server_logs" / log_id / "raw" for log_id in _log_ids(app_id)
         if (repo / "server_logs" / log_id / "raw").is_dir()),
        repo / "server_logs" / app_id / "raw",
    )
    if not raw.is_dir():
        return
    hourly: defaultdict[str, dict[str, Any]] = defaultdict(
        lambda: {"requests": 0, "errors": 0, "request_bytes": 0, "response_bytes": 0, "methods": {}}
    )
    for path in raw.glob("*.jsonl"):
        try:
            file_day = date.fromisoformat(path.stem)
        except ValueError:
            continue
        if file_day < cutoff:
            try:
                path.unlink()
            except OSError:
                pass
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                event = json.loads(line)
                timestamp = str(event.get("timestamp", ""))
                hour = timestamp[:13]
                if len(hour) != 13 or "T" not in hour:
                    continue
                bucket = hourly[hour]
                bucket["requests"] += 1
                bucket["errors"] += int(int(event.get("status", 0)) >= 400)
                bucket["request_bytes"] += int(event.get("request_bytes", 0) or 0)
                bucket["response_bytes"] += int(event.get("response_bytes", 0) or 0)
                method = str(event.get("method", "UNKNOWN"))
                bucket["methods"][method] = bucket["methods"].get(method, 0) + 1
            except (ValueError, TypeError, json.JSONDecodeError):
                continue
    directory = raw.parent / "hourly"
    directory.mkdir(parents=True, exist_ok=True)
    for hour, bucket in hourly.items():
        (directory / f"{hour.replace(':', '-')}.json").write_text(
            json.dumps({"hour": hour, **bucket}, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )


def aggregate_events(events: Iterable[dict[str, Any]], first_day: date) -> dict[str, Any]:
    method_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    route_counts: Counter[str] = Counter()
    daily: defaultdict[str, dict[str, int]] = defaultdict(lambda: {"requests": 0, "errors": 0})
    total = request_bytes = response_bytes = latency_total = 0.0
    latencies = []
    active_days: set[str] = set()
    for event in events:
        timestamp = str(event.get("timestamp", ""))
        day = timestamp[:10]
        try:
            if date.fromisoformat(day) < first_day:
                continue
        except ValueError:
            continue
        status = int(event.get("status", 0))
        method = str(event.get("method", "UNKNOWN"))
        route = str(event.get("route", ""))
        total += 1
        request_bytes += float(event.get("request_bytes", 0) or 0)
        response_bytes += float(event.get("response_bytes", 0) or 0)
        latency = float(event.get("latency_ms", 0) or 0)
        latency_total += latency
        latencies.append(latency)
        method_counts[method] += 1
        status_counts[str(status)] += 1
        route_counts[route] += 1
        active_days.add(day)
        daily[day]["requests"] += 1
        if status >= 400:
            daily[day]["errors"] += 1
    return {
        "requests": int(total),
        "active_days": len(active_days),
        "request_bytes": int(request_bytes),
        "response_bytes": int(response_bytes),
        "error_requests": sum(count for code, count in status_counts.items() if code.isdigit() and int(code) >= 400),
        "average_latency_ms": round(latency_total / total, 1) if total else 0,
        "methods": dict(method_counts),
        "statuses": dict(status_counts),
        "top_routes": [{"route": route, "requests": count} for route, count in route_counts.most_common(5)],
        "daily": [{"date": day, **daily[day]} for day in sorted(daily)],
    }


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def _repo_size(repo: Path, *, include_git: bool = False) -> int:
    total = 0
    for path in repo.rglob("*"):
        if path.is_file() and (include_git or ".git" not in path.parts) and "node_modules" not in path.parts:
            try:
                total += path.stat().st_size
            except OSError:
                pass
    return total


def git_stats(repo: Path | None, now: datetime | None = None) -> dict[str, Any]:
    if repo is None:
        return {"available": False}
    cache_key = str(repo)
    cached = _GIT_CACHE.get(cache_key)
    if cached and time.time() - cached[0] < 86400:
        return cached[1]
    try:
        current = now or datetime.now().astimezone()
        recent = _git(repo, "log", "-30", "--format=%ad", "--date=short").splitlines()
        commits_7d = int(_git(repo, "rev-list", "--count", "--since=7 days ago", "HEAD") or 0)
        commits_30d = int(_git(repo, "rev-list", "--count", "--since=30 days ago", "HEAD") or 0)
        status = _git(repo, "status", "--porcelain").splitlines()
        dirty = sum(1 for line in status if line.strip())
        result = {
            "available": True,
            "path": str(repo),
            "branch": _git(repo, "branch", "--show-current"),
            "head": _git(repo, "rev-parse", "HEAD"),
            "last_commit": recent[0] if recent else None,
            "commits_7d": commits_7d,
            "commits_30d": commits_30d,
            "active_days_7d": len({day for day in recent if day >= (current.date() - timedelta(days=6)).isoformat()}),
            "days_since_commit": None,
            "dirty": dirty > 0,
            "uncommitted_files": dirty,
            "working_tree_bytes": _repo_size(repo),
            "git_bytes": _repo_size(repo / ".git", include_git=True),
        }
        last = _git(repo, "log", "-1", "--format=%ct")
        if last:
            result["days_since_commit"] = max(0, (current.date() - datetime.fromtimestamp(int(last)).date()).days)
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        result = {"available": False, "error": str(exc)}
    _GIT_CACHE[cache_key] = (time.time(), result)
    return result


def stats_for_app(app_id: str, days: int = 30) -> dict[str, Any]:
    days = max(1, min(days, 3650))
    repo = repo_for_app(app_id)
    first_day = date.today() - timedelta(days=days - 1)
    if repo:
        refresh_hourly(repo, app_id)
    usage = aggregate_events(_read_events(repo, app_id, first_day), first_day) if repo else aggregate_events((), first_day)
    return {"app_id": app_id, "range_days": days, "usage": usage, "git": git_stats(repo)}
