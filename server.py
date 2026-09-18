#!/usr/bin/env python3
"""家用命令台: a small LAN app directory."""

from __future__ import annotations

import argparse
import html
import json
import mimetypes
import socket
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse
import yaml

from command_tools import ToolError, get_command_tool, list_command_tools, run_command_tool
from app_settings import chinese_chars_output_dir
from daka_bridge import DakaToolError, generate_report, load_state
import tomato_watch
from cli_tools import chinese_practice, daka_checkin, eat_what, quick_pic
from asset_urls import asset_url
from i18n import normalize_lang, tr
import server_monitor
import app_stats
from request_logging import CountingWriter, ToolRequestLogger


ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_DIR = Path.home() / ".config" / "home_command_center"
DEFAULT_APPS_DIR = DEFAULT_CONFIG_DIR / "apps"
STATIC_DIR = ROOT / "static"
HEALTH_CACHE_SECONDS = 15
HEALTH_TIMEOUT_SECONDS = 1.5


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class AppConfig:
    id: str
    name: str
    url: str
    source: Path
    thumbnail: str | None = None
    description: str = ""
    tags: tuple[str, ...] = ()
    health_url: str | None = None
    health_verify_tls: bool = True

    @property
    def hostname(self) -> str:
        parsed = urlparse(self.url)
        if parsed.port is not None:
            return str(parsed.port)
        if parsed.scheme == "https":
            return "443"
        if parsed.scheme == "http":
            return "80"
        return ""

    @property
    def process_ports(self) -> tuple[int, ...]:
        ports: list[int] = []
        for value in (self.health_url, self.url):
            if not value:
                continue
            try:
                port = urlparse(value).port
            except ValueError:
                continue
            if port is not None and port not in ports:
                ports.append(port)
        return tuple(ports)

    def thumbnail_path(self) -> Path | None:
        cover = self.source.with_suffix(".png")
        if cover.is_file():
            return cover.resolve()

        if not self.thumbnail:
            return None
        path = Path(self.thumbnail)
        if not path.is_absolute():
            path = self.source.parent / path
        try:
            resolved = path.resolve()
        except OSError:
            return None
        return resolved if resolved.is_file() else None

    def to_dict(self, status: str = "unknown") -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "hostname": self.hostname,
            "process_ports": list(self.process_ports),
            "thumbnail": f"/thumb/{self.id}" if self.thumbnail_path() else None,
            "description": self.description,
            "tags": list(self.tags),
            "health_url": self.health_url,
            "health_verify_tls": self.health_verify_tls,
            "status": status if self.health_url else "unknown",
        }


class AppRegistry:
    def __init__(self, apps_dir: Path) -> None:
        self.apps_dir = apps_dir.expanduser().resolve()
        self._health_cache: dict[str, tuple[float, str]] = {}

    def load(self) -> list[AppConfig]:
        apps: list[AppConfig] = []
        seen_ids: set[str] = set()

        for path in sorted(self.apps_dir.glob("*.yaml")):
            if self._is_command_tool_settings(path):
                continue
            app = self._load_one(path)
            if app.id in seen_ids:
                raise ConfigError(f"Duplicate app id '{app.id}' in {path}")
            seen_ids.add(app.id)
            apps.append(app)

        return apps

    def _is_command_tool_settings(self, path: Path) -> bool:
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            return False
        return isinstance(raw, dict) and raw.get("type") == "command_tool"

    def _load_one(self, path: Path) -> AppConfig:
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc

        if not isinstance(raw, dict):
            raise ConfigError(f"{path} must contain a YAML mapping")

        for field in ("id", "name", "url"):
            if not isinstance(raw.get(field), str) or not raw[field].strip():
                raise ConfigError(f"{path} is missing required string field '{field}'")

        tags = raw.get("tags", [])
        if tags is None:
            tags = []
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise ConfigError(f"{path} field 'tags' must be a list of strings")

        thumbnail = raw.get("thumbnail")
        if thumbnail is not None and not isinstance(thumbnail, str):
            raise ConfigError(f"{path} field 'thumbnail' must be a string")

        description = raw.get("description", "")
        if description is None:
            description = ""
        if not isinstance(description, str):
            raise ConfigError(f"{path} field 'description' must be a string")

        health_url = raw.get("health_url")
        if health_url is not None and not isinstance(health_url, str):
            raise ConfigError(f"{path} field 'health_url' must be a string")

        health_verify_tls = raw.get("health_verify_tls", True)
        if not isinstance(health_verify_tls, bool):
            raise ConfigError(f"{path} field 'health_verify_tls' must be a boolean")

        return AppConfig(
            id=raw["id"].strip(),
            name=raw["name"].strip(),
            url=raw["url"].strip(),
            thumbnail=thumbnail,
            description=description.strip(),
            tags=tuple(tag.strip() for tag in tags if tag.strip()),
            health_url=health_url.strip() if health_url else None,
            health_verify_tls=health_verify_tls,
            source=path,
        )

    def app_payload(self, lang: str = "zh") -> dict[str, Any]:
        apps = self.load()
        statuses = {app.id: self.health_status(app) for app in apps}
        command_tools = list_command_tools()
        tool_payloads = []
        for tool in command_tools:
            tool_id = f"tool:{tool.id}"
            thumbnail = f"/thumb/{tool_id}" if self.thumbnail_path(tool_id) else None
            tool_payloads.append(tool.to_app_dict(lang, thumbnail))
        all_tags = sorted(
            {tag for app in apps for tag in app.tags} | {tag for tool in command_tools for tag in tool.tags},
            key=str.lower,
        )
        app_payloads = [app.to_dict(statuses[app.id]) for app in apps] + tool_payloads
        app_payloads.append(
            {
                "id": "system-monitor",
                "name": tr(lang, "server_monitor"),
                "url": "/monitor",
                "hostname": "",
                "thumbnail": (
                    "/thumb/system-monitor"
                    if self.thumbnail_path("system-monitor")
                    else None
                ),
                "description": tr(lang, "monitor_subtitle"),
                "tags": ["system"],
                "health_url": None,
                "health_verify_tls": True,
                "status": "online",
                "kind": "monitor",
            }
        )
        return {
            "apps": app_payloads,
            "tags": all_tags,
        }

    def health_status(self, app: AppConfig) -> str:
        if not app.health_url:
            return "unknown"

        cached = self._health_cache.get(app.id)
        now = time.monotonic()
        if cached and now - cached[0] < HEALTH_CACHE_SECONDS:
            return cached[1]

        try:
            parsed = urlparse(app.health_url)
            host = parsed.hostname
            port = parsed.port
            if not host or port is None:
                status = "offline"
            else:
                with socket.create_connection((host, port), timeout=HEALTH_TIMEOUT_SECONDS):
                    status = "online"
        except Exception:
            status = "offline"

        self._health_cache[app.id] = (now, status)
        return status

    def thumbnail_path(self, app_id: str) -> Path | None:
        if app_id == "system-monitor":
            cover = self.apps_dir / "monitor.png"
            return cover.resolve() if cover.is_file() else None

        if app_id.startswith("tool:"):
            try:
                tool = get_command_tool(app_id.removeprefix("tool:"))
            except ToolError:
                return None
            if not tool.cover_image:
                return None
            cover = self.apps_dir / f"{tool.cover_image}.png"
            return cover.resolve() if cover.is_file() else None

        apps = {app.id: app for app in self.load()}
        app = apps.get(app_id)
        return app.thumbnail_path() if app else None


REGISTRY = AppRegistry(DEFAULT_APPS_DIR)
TOOL_PAGE_RENDERERS = {
    "chinese-practice": chinese_practice.render_tool_page,
    "daka": daka_checkin.render_tool_page,
    "eat-what": eat_what.render_tool_page,
    "quick_pic": quick_pic.render_tool_page,
}


class Handler(BaseHTTPRequestHandler):
    server_version = "HomeCommandCenter/0.1"
    request_logger = ToolRequestLogger(ROOT)

    def handle_one_request(self) -> None:
        started_at = time.time()
        self._telemetry_status = 500
        original_wfile = self.wfile
        counted_wfile = CountingWriter(original_wfile)
        self.wfile = counted_wfile
        try:
            super().handle_one_request()
        finally:
            self.wfile = original_wfile
            try:
                self.request_logger.record(
                    target=getattr(self, "path", ""),
                    method=getattr(self, "command", "UNKNOWN"),
                    status=getattr(self, "_telemetry_status", 500),
                    request_size=int(self.headers.get("Content-Length", "0") or 0),
                    response_size=counted_wfile.bytes_written,
                    started_at=started_at,
                )
            except Exception:
                pass

    def send_response(self, code: int, message: str | None = None) -> None:
        self._telemetry_status = int(code)
        super().send_response(code, message)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        lang = _request_lang(parsed)

        if path == "/":
            self._send_html(render_dashboard(lang))
            return

        if path == "/monitor":
            self._send_html(render_monitor(lang))
            return

        if path.startswith("/tools/"):
            tool_id = path.removeprefix("/tools/").strip("/")
            if tool_id == "tomato_watch":
                self._send_html(tomato_watch.render_tool_page(lang))
                return
            try:
                tool = get_command_tool(tool_id)
            except ToolError as exc:
                self._send_error(404, tr(lang, "unknown_tool", tool=tool_id))
                return
            renderer = TOOL_PAGE_RENDERERS.get(tool.id)
            if renderer is None:
                self._send_error(500, tr(lang, "unknown_tool_page", tool=tool.id))
                return
            self._send_html(renderer(lang))
            return

        if path == "/api/apps":
            try:
                self._send_json(REGISTRY.app_payload(lang))
            except ConfigError as exc:
                self._send_json({"error": str(exc)}, status=500)
            return

        if path == "/api/monitor":
            try:
                apps = [app for app in REGISTRY.app_payload(lang)["apps"] if app["id"] != "system-monitor"]
                tools = [{"id": tool.id, "name": tool.name_for(lang)} for tool in list_command_tools()]
                self._send_json(server_monitor.collect(apps, tools))
            except ConfigError as exc:
                self._send_json({"error": str(exc)}, status=500)
            return

        if path == "/api/stats":
            app_id = parse_qs(parsed.query).get("app_id", [""])[0]
            if not app_id or app_id == "system-monitor":
                self._send_json({"error": "app_id is required"}, status=400)
                return
            try:
                known_ids = {app["id"] for app in REGISTRY.app_payload(lang)["apps"]}
                if app_id not in known_ids:
                    self._send_json({"error": "Unknown app"}, status=404)
                    return
                days = int(parse_qs(parsed.query).get("days", ["30"])[0])
                self._send_json(app_stats.stats_for_app(app_id, days))
            except (ConfigError, ValueError) as exc:
                self._send_json({"error": str(exc)}, status=400)
            return

        if path == "/api/tools/quick_pic/candidates":
            try:
                self._send_json(quick_pic.initial_payload(lang))
            except quick_pic.QuickPicError as exc:
                self._send_json({"error": str(exc)}, status=500)
            return

        if path.startswith("/api/tools/quick_pic/source/"):
            candidate_id = path.removeprefix("/api/tools/quick_pic/source/")
            try:
                config = quick_pic.load_config()
                candidate = quick_pic.get_candidate(config, candidate_id)
                self._send_file(candidate.path, extra_roots=(config.input_dir,))
            except quick_pic.QuickPicError as exc:
                self._send_json({"error": str(exc)}, status=404)
            return

        if path.startswith("/api/tools/quick_pic/results/"):
            remainder = path.removeprefix("/api/tools/quick_pic/results/")
            try:
                output_dir_id, filename = remainder.split("/", 1)
                result, output_root = quick_pic.resolve_result(output_dir_id, filename)
                self._send_file(result, extra_roots=(output_root,))
            except (ValueError, quick_pic.QuickPicError) as exc:
                self._send_json({"error": str(exc)}, status=404)
            return

        if path.startswith("/api/tools/"):
            tool_id = path.removeprefix("/api/tools/").strip("/")
            try:
                if tool_id == "tomato_watch":
                    self._send_json(tomato_watch.payload())
                    return
                if tool_id == "daka":
                    query = parse_qs(parsed.query)
                    date_text = query.get("date", [None])[0]
                    report_kind = query.get("report", [None])[0]
                    if report_kind:
                        self._send_json(generate_report(report_kind, date_text))
                    else:
                        self._send_json(load_state(date_text))
                else:
                    self._send_json(get_command_tool(tool_id).to_schema(lang))
            except ToolError as exc:
                self._send_json({"error": tr(lang, "unknown_tool", tool=tool_id)}, status=404)
            except DakaToolError as exc:
                self._send_json({"error": str(exc)}, status=400)
            return

        if path.startswith("/static/"):
            self._send_file(STATIC_DIR / path.removeprefix("/static/"))
            return

        if path.startswith("/output/"):
            self._send_file(chinese_chars_output_dir() / path.removeprefix("/output/"))
            return

        if path.startswith("/thumb/"):
            app_id = path.removeprefix("/thumb/")
            try:
                thumb = REGISTRY.thumbnail_path(app_id)
            except ConfigError as exc:
                self._send_json({"error": str(exc)}, status=500)
                return
            if thumb:
                self._send_file(thumb)
            else:
                self._send_error(404, "Thumbnail not found")
            return

        self._send_error(404, "Not found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        lang = _request_lang(parsed)

        if path == "/api/tools/quick_pic/preview":
            try:
                payload = self._read_json_body()
                image, _config, _candidate, _background, _threshold = quick_pic.process_request(payload)
                self._send_bytes(image, "image/png")
            except (ValueError, quick_pic.QuickPicError) as exc:
                self._send_json({"error": str(exc)}, status=400)
            return

        if path == "/api/tools/quick_pic/save":
            try:
                payload = self._read_json_body()
                self._send_json(quick_pic.save_request(payload))
            except (ValueError, quick_pic.QuickPicError) as exc:
                self._send_json({"error": str(exc)}, status=400)
            return

        if path.startswith("/api/tools/") and path.endswith("/run"):
            tool_id = path.removeprefix("/api/tools/").removesuffix("/run").strip("/")
            try:
                payload = self._read_json_body()
                self._send_json(run_command_tool(tool_id, payload, lang))
            except ToolError as exc:
                self._send_json({"error": str(exc)}, status=400)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
            return

        if path == "/api/tools/tomato_watch/action":
            try:
                self._send_json(tomato_watch.action(self._read_json_body()))
            except tomato_watch.TomatoWatchError as exc:
                self._send_json({"error": str(exc)}, status=400)
            return

        self._send_error(404, "Not found")

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} - {fmt % args}")

    def _send_html(self, body: str) -> None:
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload: Any, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_bytes(self, data: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, path: Path, extra_roots: tuple[Path, ...] = ()) -> None:
        try:
            resolved = path.resolve()
        except OSError:
            self._send_error(404, "File not found")
            return

        allowed_roots = [
            STATIC_DIR.resolve(),
            REGISTRY.apps_dir,
            chinese_chars_output_dir().resolve(),
            *(root.resolve() for root in extra_roots),
        ]
        if not any(resolved == root or root in resolved.parents for root in allowed_roots):
            self._send_error(403, "Forbidden")
            return

        if not resolved.is_file():
            self._send_error(404, "File not found")
            return

        content_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
        data = resolved.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_error(self, status: int, message: str) -> None:
        self._send_json({"error": message}, status=status)

    def _read_json_body(self) -> dict[str, Any]:
        content_type = self.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            raise ValueError("Expected application/json")

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Invalid Content-Length") from exc

        if length > 64_000:
            raise ValueError("Request body is too large")

        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON body") from exc

        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload


def render_dashboard(lang: str = "zh") -> str:
    resolved_lang = normalize_lang(lang)
    title = tr(resolved_lang, "dashboard_title")
    return f"""<!doctype html>
<html lang="{ 'en' if resolved_lang == 'en' else 'zh-CN' }">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="{asset_url('/static/styles.css')}">
  <script>window.__HCC_LANG__ = {json.dumps(resolved_lang)};</script>
  <script src="{asset_url('/static/i18n.js')}" defer></script>
  <script src="{asset_url('/static/app.js')}" defer></script>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div>
        <h1>{html.escape(title)}</h1>
        <p>{html.escape(tr(resolved_lang, "dashboard_subtitle"))}</p>
      </div>
      <form class="lang-switch" method="get">
        <label class="select lang-select">
          <span>{html.escape(tr(resolved_lang, "language"))}</span>
          <select name="lang" data-lang-switcher>
            <option value="zh"{' selected' if resolved_lang == 'zh' else ''}>{html.escape(tr(resolved_lang, "chinese"))}</option>
            <option value="en"{' selected' if resolved_lang == 'en' else ''}>{html.escape(tr(resolved_lang, "english"))}</option>
          </select>
        </label>
      </form>
      <div class="count" data-count>{html.escape(tr(resolved_lang, "count_apps", count=0))}</div>
    </header>

    <!-- Filters are disabled for the current version.
    <section class="toolbar" aria-label="{html.escape(tr(resolved_lang, 'filters'))}">
      <label class="search">
        <span>{html.escape(tr(resolved_lang, "search"))}</span>
        <input data-search type="search" placeholder="{html.escape(tr(resolved_lang, 'search_placeholder'))}" autocomplete="off">
      </label>
      <label class="select">
        <span>{html.escape(tr(resolved_lang, "tags"))}</span>
        <select data-tag>
          <option value="">{html.escape(tr(resolved_lang, "all_tags"))}</option>
        </select>
      </label>
      <label class="select">
        <span>{html.escape(tr(resolved_lang, "status"))}</span>
        <select data-status>
          <option value="">{html.escape(tr(resolved_lang, "all_status"))}</option>
          <option value="online">{html.escape(tr(resolved_lang, "online"))}</option>
          <option value="offline">{html.escape(tr(resolved_lang, "offline"))}</option>
          <option value="unknown">{html.escape(tr(resolved_lang, "unknown"))}</option>
        </select>
      </label>
    </section>
    -->

    <section class="notice" data-error hidden></section>
    <section class="grid" data-apps></section>
    <section class="empty" data-empty hidden>{html.escape(tr(resolved_lang, "no_apps"))}</section>
  </main>
</body>
</html>
"""


def render_monitor(lang: str = "zh") -> str:
    resolved_lang = normalize_lang(lang)
    title = tr(resolved_lang, "server_monitor")
    return f"""<!doctype html>
<html lang="{'en' if resolved_lang == 'en' else 'zh-CN'}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title><link rel="stylesheet" href="{asset_url('/static/styles.css')}">
<script>window.__HCC_LANG__ = {json.dumps(resolved_lang)};</script>
<script src="{asset_url('/static/i18n.js')}" defer></script><script src="{asset_url('/static/monitor.js')}" defer></script></head>
<body class="monitor-page"><main class="shell monitor-shell"><header class="topbar"><div><a class="back" href="/">{html.escape(tr(resolved_lang, 'back_to_dashboard'))}</a><h1><span class="prompt">$</span> {html.escape(title)}</h1><p>{html.escape(tr(resolved_lang, 'monitor_subtitle'))}</p></div><div class="count" data-monitor-updated>—</div></header>
<nav class="monitor-tabs" data-monitor-tabs><button type="button" data-monitor-tab="overview">{html.escape(tr(resolved_lang, 'monitor_overview'))}</button><button type="button" data-monitor-tab="stats">{html.escape(tr(resolved_lang, 'monitor_stats'))}</button></nav>
<section data-monitor-panel="overview"><section class="notice" data-monitor-error hidden></section><section class="monitor-summary" data-monitor-summary></section><section class="monitor-apps" data-monitor-apps></section></section>
<section data-monitor-panel="stats" hidden><section class="notice" data-stats-error hidden></section><div class="monitor-stat-controls"><label>{html.escape(tr(resolved_lang, 'monitor_range'))}<select data-stats-range><option value="7">7d</option><option value="30" selected>30d</option><option value="90">90d</option><option value="3650">{html.escape(tr(resolved_lang, 'monitor_all'))}</option></select></label></div><section class="monitor-stat-list" data-stats-list></section></section></main></body></html>"""


def _request_lang(parsed_url) -> str:
    query = parse_qs(parsed_url.query)
    return normalize_lang(query.get("lang", [None])[0])
def main() -> None:
    parser = argparse.ArgumentParser(description="Run 家用命令台")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7000)
    parser.add_argument(
        "--apps-dir",
        type=Path,
        default=DEFAULT_APPS_DIR,
        help=f"Directory containing app YAML files (default: {DEFAULT_APPS_DIR})",
    )
    args = parser.parse_args()

    REGISTRY.apps_dir = args.apps_dir.expanduser().resolve()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Serving 家用命令台 at http://{args.host}:{args.port}")
    print(f"Loading apps from {REGISTRY.apps_dir}")
    server.serve_forever()


if __name__ == "__main__":
    main()
