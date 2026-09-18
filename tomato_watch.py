from __future__ import annotations

import csv
import html
import json
import time
import uuid
from pathlib import Path
from typing import Any

from asset_urls import asset_url
from cli_tools.util import render_tool_page_shell

CONFIG_PATH = Path.home() / ".config" / "home_command_center" / "apps" / "tomato_watch.yaml"


class TomatoWatchError(Exception):
    pass


def _paths(config_path: Path = CONFIG_PATH) -> tuple[Path, Path]:
    import yaml
    if not config_path.is_file():
        raise TomatoWatchError(f"tomato_watch 配置不存在: {config_path}")
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise TomatoWatchError("tomato_watch 配置无法读取") from exc
    settings = raw.get("tomato_watch", {}) if isinstance(raw, dict) else {}
    if not isinstance(settings, dict):
        raise TomatoWatchError("tomato_watch 配置必须是映射")
    projects_value = settings.get("projects_csv")
    history_value = settings.get("history_csv")
    if not isinstance(projects_value, str) or not projects_value.strip():
        raise TomatoWatchError("tomato_watch.projects_csv 未配置")
    if not isinstance(history_value, str) or not history_value.strip():
        raise TomatoWatchError("tomato_watch.history_csv 未配置")
    projects = Path(projects_value).expanduser()
    history = Path(history_value).expanduser()
    return projects, history


def _read(path: Path) -> list[dict[str, str]]:
    if not path.exists(): return []
    with path.open(newline="", encoding="utf-8-sig") as f: return list(csv.DictReader(f))


def _write(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(rows)


def payload() -> dict[str, Any]:
    projects_path, history_path = _paths()
    now = time.time(); projects = _read(projects_path)
    totals: dict[str, float] = {}
    for item in _read(history_path):
        key = item.get("project_id") or item.get("project", "")
        totals[key] = totals.get(key, 0) + float(item.get("seconds", 0) or 0)
    result = []
    for p in projects:
        elapsed = float(p.get("elapsed_seconds", 0) or 0)
        if p.get("status") == "running": elapsed += max(0, now - float(p.get("started_at", now)))
        if p.get("archived") == "1": continue
        result.append({"id": p["id"], "name": p["name"], "owner": p.get("owner") or "瓜瓜", "elapsed": round(elapsed), "status": p.get("status", "paused"), "last_elapsed": round(float(p.get("last_elapsed", 0) or 0)), "history_total": round(totals.get(p["id"], 0))})
    return {"server_time": now, "projects": result}


def action(data: dict[str, Any]) -> dict[str, Any]:
    project_id, command = data.get("id"), data.get("action")
    if command not in {"create", "start", "pause", "finish", "reset", "archive"}: raise TomatoWatchError("无效操作")
    projects_path, history_path = _paths(); rows = _read(projects_path); now = time.time()
    project = next((p for p in rows if p.get("id") == project_id), None)
    if command == "create" and not project:
        name = str(data.get("name", "")).strip()
        if not name: raise TomatoWatchError("项目名称不能为空")
        owner = str(data.get("owner") or "瓜瓜")
        if owner not in {"瓜瓜", "小黑"}: raise TomatoWatchError("无效 owner")
        project = {"id": uuid.uuid4().hex, "name": name, "owner": owner, "elapsed_seconds": "0", "status": "paused", "started_at": ""}; rows.append(project)
    elif not project: raise TomatoWatchError("项目不存在")
    else:
        if command == "archive":
            project["archived"] = "1"
            _write(projects_path, rows, ["id", "name", "owner", "elapsed_seconds", "status", "started_at", "last_elapsed", "archived"])
            return payload()
        elapsed = float(project.get("elapsed_seconds", 0) or 0)
        if project.get("status") == "running": elapsed += max(0, now - float(project.get("started_at", now)))
        project.update(elapsed_seconds=str(round(elapsed)), started_at="")
        if command == "start": project.update(status="running", started_at=str(now))
        elif command == "pause": project["status"] = "paused"
        elif command == "reset": project.update(elapsed_seconds="0", status="paused")
        elif command == "finish":
            project["last_elapsed"] = project["elapsed_seconds"]
            history = _read(history_path); history.append({"ended_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "project_id": project["id"], "project": project["name"], "owner": project.get("owner", "瓜瓜"), "seconds": project["elapsed_seconds"]})
            _write(history_path, history, ["ended_at", "project_id", "project", "owner", "seconds"])
            project.update(elapsed_seconds="0", status="paused")
    _write(projects_path, rows, ["id", "name", "owner", "elapsed_seconds", "status", "started_at", "last_elapsed", "archived"])
    return payload()


def render_tool_page(lang: str = "zh") -> str:
    tool = {"name": "番茄钟", "description": "按项目记录专注时间。"}
    body = '''<section class="tomato-watch" data-tomato-watch>
      <nav class="tomato-tabs" data-tabs><button type="button" data-owner="瓜瓜">瓜瓜</button><button type="button" data-owner="小黑">小黑</button></nav>
      <section class="tomato-projects" data-projects></section>
      <form class="tool-panel tomato-add" data-add-project><input name="name" placeholder="新项目名称" required><button class="open" type="submit">添加项目</button></form>
      <section class="notice" data-error hidden></section>
    </section>'''
    return render_tool_page_shell("tomato_watch", tool["name"], tool["description"], lang=lang, body_html=body, extra_stylesheets=("/static/tomato_watch.css",), script_src="/static/tomato_watch.js")
