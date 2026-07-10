from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"


def asset_url(path: str) -> str:
    if not path.startswith("/static/"):
        return path
    file_path = STATIC_DIR / path.removeprefix("/static/")
    try:
        version = int(file_path.stat().st_mtime)
    except OSError:
        return path
    return f"{path}?v={version}"
