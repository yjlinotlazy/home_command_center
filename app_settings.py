from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


CONFIG_DIR = Path.home() / ".config" / "home_command_center"
APPS_DIR = CONFIG_DIR / "apps"
WORKBOOK_GO_CONFIG = APPS_DIR / "workbook_go.yaml"
DEFAULT_CHINESE_CHARS_OUTPUT_DIR = CONFIG_DIR / "output"


class AppSettingsError(Exception):
    pass


def chinese_chars_output_dir(config_path: Path | None = None) -> Path:
    if config_path is None:
        config_path = WORKBOOK_GO_CONFIG
    raw = _load_mapping(config_path)
    chinese_chars = raw.get("chinese_chars", {})
    if chinese_chars is None:
        chinese_chars = {}
    if not isinstance(chinese_chars, dict):
        raise AppSettingsError(f"{config_path} field 'chinese_chars' must be a mapping")

    output_dir = chinese_chars.get("output_dir", str(DEFAULT_CHINESE_CHARS_OUTPUT_DIR))
    if not isinstance(output_dir, str) or not output_dir.strip():
        raise AppSettingsError(
            f"{config_path} field 'chinese_chars.output_dir' must be a non-empty string"
        )
    return Path(output_dir).expanduser().resolve()


def _load_mapping(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise AppSettingsError(f"Invalid YAML in {config_path}: {exc}") from exc

    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise AppSettingsError(f"{config_path} must contain a YAML mapping")
    return raw
