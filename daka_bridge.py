from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path
from typing import Any

from app_settings import daka_tracker_root


DAKA_SRC = daka_tracker_root() / "src"


class DakaToolError(Exception):
    pass


def _ensure_daka_path() -> None:
    daka_src = str(DAKA_SRC)
    if daka_src not in sys.path:
        sys.path.insert(0, daka_src)


def _load_modules():
    _ensure_daka_path()
    from daka import data_loader, handler
    from daka.color_config import PALETTE

    return data_loader, handler, PALETTE


def _resolve_date(date_text: str | None) -> str:
    _, handler, _ = _load_modules()
    try:
        return handler.parse_date(date_text)
    except SystemExit as exc:
        raise DakaToolError(str(exc)) from exc


def _find_resolution(data: dict[str, Any], resolution_name: str) -> dict[str, Any]:
    for resolution in data.get("resolutions", []):
        if str(resolution.get("name", "")).strip() == resolution_name:
            return resolution
    raise DakaToolError(f"找不到 Resolution：{resolution_name}")


def _find_item(resolution: dict[str, Any], item_name: str) -> dict[str, Any]:
    for item in resolution.get("items", []):
        if str(item.get("name", "")).strip() == item_name:
            return item
    raise DakaToolError(f"找不到 Task：{item_name}")


def _item_payload(item: dict[str, Any], date_str: str) -> dict[str, Any]:
    checkins = item.get("checkins", [])
    if not isinstance(checkins, list):
        checkins = []
    normalized = sorted({str(checkin).strip() for checkin in checkins if str(checkin).strip()})
    return {
        "name": str(item.get("name", "")).strip(),
        "checked": date_str in normalized,
        "checkin_count": len(normalized),
    }


def _parse_year(date_text: str | None) -> int:
    if not date_text:
        return dt.date.today().year
    try:
        return dt.date.fromisoformat(date_text).year
    except ValueError as exc:
        raise DakaToolError(f"Invalid date: {date_text}. Use YYYY-MM-DD.") from exc


def _year_metrics(year: int) -> tuple[int, int]:
    days_in_year = 366 if dt.date(year, 12, 31).timetuple().tm_yday == 366 else 365
    total_weeks_in_year = (days_in_year + 6) // 7
    return days_in_year, total_weeks_in_year


def _resolution_color_map(resolutions: list[dict[str, Any]], palette: list[str]) -> dict[str, str]:
    colors: dict[str, str] = {}
    next_idx = 0
    for resolution in resolutions:
        resolution_name = str(resolution.get("name", "")).strip()
        if not resolution_name or resolution_name in colors:
            continue
        colors[resolution_name] = palette[next_idx % len(palette)]
        next_idx += 1
    return colors


def _year_checkins(raw_checkins: Any, year: int) -> set[dt.date]:
    valid_dates: set[dt.date] = set()
    if not isinstance(raw_checkins, list):
        return valid_dates
    for raw in raw_checkins:
        date_text = str(raw).strip()
        if not date_text:
            continue
        try:
            date_value = dt.date.fromisoformat(date_text)
        except ValueError:
            continue
        if date_value.year == year:
            valid_dates.add(date_value)
    return valid_dates


def _completion_percent(checked: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return (checked / total) * 100


def _completion_bar(percent: float, width: int = 20) -> str:
    clamped = max(0.0, min(100.0, percent))
    filled = int(round((clamped / 100.0) * width))
    return "[" + ("#" * filled) + ("-" * (width - filled)) + "]"


def _resolution_payload(resolution: dict[str, Any], date_str: str) -> dict[str, Any]:
    return {
        "name": str(resolution.get("name", "")).strip(),
        "items": [
            _item_payload(item, date_str)
            for item in resolution.get("items", [])
            if str(item.get("name", "")).strip()
        ],
    }


def load_state(date_text: str | None = None) -> dict[str, Any]:
    data_loader, _, _ = _load_modules()
    date_str = _resolve_date(date_text)
    data = data_loader.load_data()
    return {
        "kind": "daka",
        "id": "daka",
        "name": "随缘打卡",
        "description": "按日期给已有的愿望和任务随缘打卡。",
        "date": date_str,
        "resolutions": [_resolution_payload(resolution, date_str) for resolution in data.get("resolutions", [])],
    }


def generate_report(report_kind: str, date_text: str | None = None) -> dict[str, Any]:
    data_loader, _, palette = _load_modules()
    year = _parse_year(date_text)
    days_in_year, total_weeks_in_year = _year_metrics(year)
    data = data_loader.load_data()
    color_map = _resolution_color_map(data.get("resolutions", []), list(palette))

    if report_kind == "summary":
        groups: list[dict[str, Any]] = []
        for resolution in data.get("resolutions", []):
            resolution_name = str(resolution.get("name", "")).strip()
            if not resolution_name:
                continue
            color = color_map.get(resolution_name, "")
            for item in resolution.get("items", []):
                item_name = str(item.get("name", "")).strip()
                if not item_name:
                    continue
                valid_dates = _year_checkins(item.get("checkins", []), year)
                checked_days = len(valid_dates)
                checked_weeks = len({((d.timetuple().tm_yday - 1) // 7) + 1 for d in valid_dates})
                groups.append(
                    {
                        "resolution": resolution_name,
                        "item": item_name,
                        "color": color,
                        "checked_days": checked_days,
                        "checked_weeks": checked_weeks,
                        "day_total": days_in_year,
                        "week_total": total_weeks_in_year,
                        "day_percent": round(_completion_percent(checked_days, days_in_year), 2),
                        "week_percent": round(_completion_percent(checked_weeks, total_weeks_in_year), 2),
                        "day_bar": _completion_bar(_completion_percent(checked_days, days_in_year)),
                        "week_bar": _completion_bar(_completion_percent(checked_weeks, total_weeks_in_year)),
                    }
                )
        return {
            "kind": "daka-report",
            "report_kind": report_kind,
            "year": year,
            "days_in_year": days_in_year,
            "total_weeks_in_year": total_weeks_in_year,
            "groups": groups,
        }

    if report_kind == "resolution-summary":
        groups = []
        for resolution in data.get("resolutions", []):
            resolution_name = str(resolution.get("name", "")).strip()
            if not resolution_name:
                continue
            color = color_map.get(resolution_name, "")
            valid_dates: set[dt.date] = set()
            for item in resolution.get("items", []):
                valid_dates.update(_year_checkins(item.get("checkins", []), year))
            checked_days = len(valid_dates)
            checked_weeks = len({((d.timetuple().tm_yday - 1) // 7) + 1 for d in valid_dates})
            groups.append(
                {
                    "resolution": resolution_name,
                    "color": color,
                    "checked_days": checked_days,
                    "checked_weeks": checked_weeks,
                    "day_total": days_in_year,
                    "week_total": total_weeks_in_year,
                    "day_percent": round(_completion_percent(checked_days, days_in_year), 2),
                    "week_percent": round(_completion_percent(checked_weeks, total_weeks_in_year), 2),
                    "day_bar": _completion_bar(_completion_percent(checked_days, days_in_year)),
                    "week_bar": _completion_bar(_completion_percent(checked_weeks, total_weeks_in_year)),
                }
            )
        return {
            "kind": "daka-report",
            "report_kind": report_kind,
            "year": year,
            "days_in_year": days_in_year,
            "total_weeks_in_year": total_weeks_in_year,
            "groups": groups,
        }

    raise DakaToolError("Unknown report type")


def record_checkin(date_text: str | None, resolution_name: str, item_name: str) -> dict[str, Any]:
    data_loader, handler, _ = _load_modules()
    date_str = _resolve_date(date_text)
    resolution_name = resolution_name.strip()
    item_name = item_name.strip()
    if not resolution_name:
        raise DakaToolError("请选择 Resolution")
    if not item_name:
        raise DakaToolError("请选择 Task")

    data = data_loader.load_data()
    resolution = _find_resolution(data, resolution_name)
    item = _find_item(resolution, item_name)
    already_checked = not handler.check_in(item, date_str)

    data_loader.save_resolutions(data)
    data_loader.save_checkins(data)

    state = load_state(date_str)
    message = (
        f"已打卡：{resolution_name} / {item_name}（{date_str}）"
        if not already_checked
        else f"已经打过：{resolution_name} / {item_name}（{date_str}）"
    )
    return {
        "ok": True,
        "message": message,
        "date": date_str,
        "resolution": resolution_name,
        "item": item_name,
        "already_checked": already_checked,
        "state": state,
    }
