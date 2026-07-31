#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import yaml

from asset_urls import asset_url
from cli_tools.util import render_tool_page_shell
from command_tools import get_command_tool
from i18n import normalize_lang


CONFIG_PATH = Path.home() / ".config" / "home_command_center" / "apps" / "quick_pic.yaml"
DEFAULT_EXTENSIONS = (".jpg", ".jpeg", ".png")
PROCESS_TIMEOUT_SECONDS = 20
MAX_OUTPUT_BYTES = 40 * 1024 * 1024


class QuickPicError(Exception):
    pass


@dataclass(frozen=True)
class QuickPicConfig:
    input_dir: Path
    output_root: Path
    recent_count: int = 5
    output_root_label: str = "Images"
    default_background: str = "white"
    default_threshold: int = 50
    default_scale_percent: int = 25
    crop_padding: int = 24
    extensions: tuple[str, ...] = DEFAULT_EXTENSIONS


@dataclass(frozen=True)
class Candidate:
    id: str
    path: Path
    modified_ns: int
    size: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.path.name,
            "modified": datetime.fromtimestamp(
                self.modified_ns / 1_000_000_000
            ).astimezone().isoformat(timespec="seconds"),
            "source_url": f"/api/tools/quick_pic/source/{quote(self.id)}",
        }


@dataclass(frozen=True)
class OutputDirectory:
    id: str
    path: Path
    label: str

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "label": self.label}


def load_config(config_path: Path | None = None) -> QuickPicConfig:
    path = config_path or CONFIG_PATH
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise QuickPicError("quick_pic configuration is missing") from exc
    except (OSError, yaml.YAMLError) as exc:
        raise QuickPicError("quick_pic configuration cannot be read") from exc

    if not isinstance(raw, dict) or not isinstance(raw.get("quick_pic"), dict):
        raise QuickPicError("quick_pic configuration must contain a quick_pic mapping")
    settings = raw["quick_pic"]

    input_dir = _configured_directory(settings, "input_dir")
    output_root = _configured_directory(settings, "output_root")
    recent_count = _bounded_int(settings.get("recent_count", 5), "recent_count", 1, 20)
    default_threshold = _bounded_int(
        settings.get("default_threshold", 50), "default_threshold", 1, 99
    )
    default_scale_percent = _bounded_int(
        settings.get("default_scale_percent", 25), "default_scale_percent", 1, 100
    )
    crop_padding = _bounded_int(settings.get("crop_padding", 24), "crop_padding", 0, 500)

    output_root_label = settings.get("output_root_label", "Images")
    if not isinstance(output_root_label, str) or not output_root_label.strip():
        raise QuickPicError("output_root_label must be a non-empty string")

    default_background = settings.get("default_background", "white")
    if default_background not in {"transparent", "white"}:
        raise QuickPicError("default_background must be transparent or white")

    raw_extensions = settings.get("extensions", list(DEFAULT_EXTENSIONS))
    if (
        not isinstance(raw_extensions, list)
        or not raw_extensions
        or not all(isinstance(item, str) and re.fullmatch(r"\.[A-Za-z0-9]+", item) for item in raw_extensions)
    ):
        raise QuickPicError("extensions must be a non-empty list such as [.jpg, .png]")
    extensions = tuple(dict.fromkeys(item.lower() for item in raw_extensions))

    if not input_dir.is_dir():
        raise QuickPicError("Configured input directory is unavailable")
    if not output_root.is_dir():
        raise QuickPicError("Configured output root is unavailable")

    return QuickPicConfig(
        input_dir=input_dir,
        output_root=output_root,
        recent_count=recent_count,
        output_root_label=output_root_label.strip(),
        default_background=default_background,
        default_threshold=default_threshold,
        default_scale_percent=default_scale_percent,
        crop_padding=crop_padding,
        extensions=extensions,
    )


def list_candidates(config: QuickPicConfig) -> list[Candidate]:
    candidates: list[Candidate] = []
    try:
        entries = list(config.input_dir.iterdir())
    except OSError as exc:
        raise QuickPicError("Configured input directory is unavailable") from exc

    for path in entries:
        if path.suffix.lower() not in config.extensions:
            continue
        try:
            resolved = path.resolve(strict=True)
            stat = resolved.stat()
        except OSError:
            continue
        if not resolved.is_file() or resolved.parent != config.input_dir:
            continue
        candidate_id = _opaque_id(f"{resolved.name}\0{stat.st_mtime_ns}\0{stat.st_size}")
        candidates.append(
            Candidate(
                id=candidate_id,
                path=resolved,
                modified_ns=stat.st_mtime_ns,
                size=stat.st_size,
            )
        )

    candidates.sort(key=lambda item: (item.modified_ns, item.path.name), reverse=True)
    return candidates[: config.recent_count]


def get_candidate(config: QuickPicConfig, candidate_id: str) -> Candidate:
    if not isinstance(candidate_id, str):
        raise QuickPicError("Invalid source image")
    for candidate in list_candidates(config):
        if candidate.id == candidate_id:
            return candidate
    raise QuickPicError("Source image is no longer in the recent list")


def list_output_directories(config: QuickPicConfig) -> list[OutputDirectory]:
    root = config.output_root.resolve()
    root_label = _display_output_path(root, config.output_root_label)
    found: list[tuple[str, Path]] = [("", root)]
    try:
        for current, dirnames, _filenames in os.walk(root, followlinks=False):
            current_path = Path(current)
            safe_names: list[str] = []
            for name in dirnames:
                path = current_path / name
                if path.is_symlink():
                    continue
                try:
                    resolved = path.resolve(strict=True)
                    resolved.relative_to(root)
                except (OSError, ValueError):
                    continue
                safe_names.append(name)
                relative = resolved.relative_to(root).as_posix()
                found.append((relative, resolved))
            dirnames[:] = safe_names
    except OSError as exc:
        raise QuickPicError("Configured output root is unavailable") from exc

    found.sort(key=lambda item: (item[0] != "", item[0].casefold()))
    return [
        OutputDirectory(
            id=_opaque_id(relative or "."),
            path=path,
            label=root_label if not relative else f"{root_label}/{relative}",
        )
        for relative, path in found
    ]


def get_output_directory(config: QuickPicConfig, output_dir_id: str) -> OutputDirectory:
    if not isinstance(output_dir_id, str):
        raise QuickPicError("Invalid output directory")
    for output_dir in list_output_directories(config):
        if output_dir.id == output_dir_id:
            return output_dir
    raise QuickPicError("Output directory is no longer available")


def initial_payload(lang: str = "zh", config_path: Path | None = None) -> dict[str, Any]:
    config = load_config(config_path)
    candidates = list_candidates(config)
    output_dirs = list_output_directories(config)
    return {
        "candidates": [candidate.to_dict() for candidate in candidates],
        "output_dirs": [output_dir.to_dict() for output_dir in output_dirs],
        "defaults": {
            "background": config.default_background,
            "threshold": config.default_threshold,
            "scale_percent": config.default_scale_percent,
        },
        "lang": normalize_lang(lang),
    }


def process_request(
    payload: dict[str, Any],
    config_path: Path | None = None,
) -> tuple[bytes, QuickPicConfig, Candidate, str, int]:
    config = load_config(config_path)
    candidate = get_candidate(config, payload.get("candidate_id"))
    background = payload.get("background", config.default_background)
    if background not in {"transparent", "white"}:
        raise QuickPicError("Background must be transparent or white")
    threshold = _bounded_int(
        payload.get("threshold", config.default_threshold), "threshold", 1, 99
    )
    scale_percent = _bounded_int(
        payload.get("scale_percent", config.default_scale_percent), "scale_percent", 1, 100
    )
    return (
        process_image(config, candidate, background, threshold, scale_percent),
        config,
        candidate,
        background,
        threshold,
    )


def process_image(
    config: QuickPicConfig,
    candidate: Candidate,
    background: str,
    threshold: int,
    scale_percent: int = 25,
) -> bytes:
    binary = shutil.which("magick")
    if not binary:
        raise QuickPicError("ImageMagick is not installed")

    command = [
        binary,
        "-limit",
        "memory",
        "256MiB",
        "-limit",
        "map",
        "512MiB",
        str(candidate.path),
        "-auto-orient",
        "-alpha",
        "on",
        "-fuzz",
        f"{100 - threshold}%",
        "-transparent",
        "white",
        "-trim",
        "+repage",
        "-bordercolor",
        "none",
        "-border",
        str(config.crop_padding),
        "-resize",
        f"{scale_percent}%",
    ]
    if background == "white":
        command.extend(["-background", "white", "-alpha", "remove", "-alpha", "off"])
    command.append("png:-")

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            timeout=PROCESS_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise QuickPicError("Image processing timed out") from exc
    except OSError as exc:
        raise QuickPicError("ImageMagick could not be started") from exc

    if completed.returncode != 0 or not completed.stdout:
        raise QuickPicError("ImageMagick could not process this image")
    if len(completed.stdout) > MAX_OUTPUT_BYTES:
        raise QuickPicError("Processed image is too large")
    _reject_blank_image(binary, completed.stdout, background)
    return completed.stdout


def save_request(payload: dict[str, Any], config_path: Path | None = None) -> dict[str, str]:
    image, config, _candidate, _background, _threshold = process_request(payload, config_path)
    output_dir = get_output_directory(config, payload.get("output_dir_id"))
    filename = _output_filename(payload.get("output_name"))
    final_path = _atomic_unique_write(output_dir.path, filename, image)
    return {
        "name": final_path.name,
        "output_label": output_dir.label,
        "url": (
            f"/api/tools/quick_pic/results/{quote(output_dir.id)}/"
            f"{quote(final_path.name)}"
        ),
    }


def resolve_result(
    output_dir_id: str, filename: str, config_path: Path | None = None
) -> tuple[Path, Path]:
    config = load_config(config_path)
    output_dir = get_output_directory(config, output_dir_id)
    if (
        not isinstance(filename, str)
        or Path(filename).name != filename
        or not filename.lower().endswith(".png")
    ):
        raise QuickPicError("Invalid result filename")
    try:
        result = (output_dir.path / filename).resolve(strict=True)
        result.relative_to(config.output_root)
    except (OSError, ValueError) as exc:
        raise QuickPicError("Result file not found") from exc
    if not result.is_file() or result.parent != output_dir.path:
        raise QuickPicError("Result file not found")
    return result, config.output_root


def render_tool_page(lang: str = "zh") -> str:
    resolved_lang = normalize_lang(lang)
    tool = get_command_tool("quick_pic")
    text = _page_text(resolved_lang)
    body = f"""<section class="quick-pic" data-quick-pic>
      <form class="quick-pic-controls" data-quick-pic-form>
        <label class="tool-field">
          <span>{html.escape(text["output_name"])}</span>
          <input type="text" maxlength="100" required data-quick-pic-output-name>
        </label>
        <label class="tool-field">
          <span>{html.escape(text["background"])}</span>
          <select data-quick-pic-background>
            <option value="transparent">{html.escape(text["transparent"])}</option>
            <option value="white" selected>{html.escape(text["white"])}</option>
          </select>
        </label>
        <label class="tool-field quick-pic-strength">
          <span>{html.escape(text["strength"])}: <output data-quick-pic-threshold-value>50</output>%</span>
          <input type="range" min="1" max="99" value="50" data-quick-pic-threshold>
        </label>
        <label class="tool-field">
          <span>{html.escape(text["scale"])}</span>
          <input type="number" min="1" max="100" step="1" value="25" required data-quick-pic-scale>
        </label>
        <label class="tool-field">
          <span>{html.escape(text["output"])}</span>
          <select data-quick-pic-output required></select>
        </label>
        <button class="open tool-submit" type="submit" data-quick-pic-save>{html.escape(text["save"])}</button>
      </form>
      <section class="notice" data-quick-pic-error hidden></section>
      <section class="notice" data-quick-pic-status hidden></section>
      <div class="quick-pic-workspace">
        <aside class="quick-pic-candidates" aria-label="{html.escape(text["source"])}" data-quick-pic-candidates></aside>
        <div class="quick-pic-previews">
          <figure class="quick-pic-preview">
            <div class="quick-pic-canvas"><img data-quick-pic-original alt=""></div>
          </figure>
          <figure class="quick-pic-preview">
            <div class="quick-pic-canvas quick-pic-canvas--checker">
              <img data-quick-pic-processed alt="">
              <span data-quick-pic-loading>{html.escape(text["loading"])}</span>
            </div>
          </figure>
        </div>
      </div>
    </section>"""
    extra_head = (
        "<script>window.__QUICK_PIC_TEXT__ = "
        + json.dumps(text, ensure_ascii=False)
        + ";</script>"
    )
    return render_tool_page_shell(
        tool.id,
        tool.name_for(resolved_lang),
        tool.description_for(resolved_lang),
        lang=resolved_lang,
        body_html=body,
        extra_stylesheets=("/static/quick_pic.css",),
        extra_head=extra_head,
        script_src="/static/quick_pic.js",
    )


def _configured_directory(settings: dict[str, Any], key: str) -> Path:
    value = settings.get(key)
    if not isinstance(value, str) or not value.strip():
        raise QuickPicError(f"{key} must be a non-empty string")
    return Path(value).expanduser().resolve()


def _bounded_int(value: Any, name: str, low: int, high: int) -> int:
    if isinstance(value, bool):
        raise QuickPicError(f"{name} must be between {low} and {high}")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise QuickPicError(f"{name} must be between {low} and {high}") from exc
    if result < low or result > high:
        raise QuickPicError(f"{name} must be between {low} and {high}")
    return result


def _validated_output_name(value: Any) -> str:
    if not isinstance(value, str):
        raise QuickPicError("Output name is required")
    name = value.strip()
    if not name:
        raise QuickPicError("Output name is required")
    if name.lower().endswith(".png"):
        raise QuickPicError("Enter the output name without .png")
    if (
        len(name) > 100
        or name in {".", ".."}
        or "/" in name
        or "\\" in name
        or any(ord(character) < 32 for character in name)
    ):
        raise QuickPicError("Invalid output name")
    return re.sub(r" +", "_", name).lower()


def _opaque_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def _display_output_path(root: Path, fallback: str) -> str:
    parts = root.parts
    try:
        dropbox_index = parts.index("Dropbox")
    except ValueError:
        return fallback
    suffix = parts[dropbox_index + 1 :]
    return "/".join(("D", *suffix))


def _reject_blank_image(binary: str, image: bytes, background: str) -> None:
    expression = "%[fx:mean.a]" if background == "transparent" else "%[fx:mean]"
    try:
        completed = subprocess.run(
            [binary, "identify", "-format", expression, "png:-"],
            input=image,
            capture_output=True,
            timeout=PROCESS_TIMEOUT_SECONDS,
            check=False,
        )
        value = float(completed.stdout.decode("ascii"))
    except (OSError, ValueError, UnicodeDecodeError, subprocess.TimeoutExpired) as exc:
        raise QuickPicError("Processed image could not be verified") from exc
    if completed.returncode != 0:
        raise QuickPicError("Processed image could not be verified")
    if (background == "transparent" and value <= 0.000001) or (
        background == "white" and value >= 0.999999
    ):
        raise QuickPicError("No drawing was detected")


def _output_filename(output_name: Any) -> str:
    return f"{_validated_output_name(output_name)}.png"


def _atomic_unique_write(directory: Path, filename: str, data: bytes) -> Path:
    fd, temp_name = tempfile.mkstemp(prefix=".quick_pic-", suffix=".tmp", dir=directory)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        base = Path(filename).stem
        for index in range(1000):
            candidate = directory / (filename if index == 0 else f"{base}-{index}.png")
            try:
                os.link(temp_path, candidate)
                return candidate
            except FileExistsError:
                continue
        raise QuickPicError("Could not choose a unique output filename")
    except OSError as exc:
        raise QuickPicError("Could not save the processed image") from exc
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass


def _page_text(lang: str) -> dict[str, str]:
    if lang == "en":
        return {
            "source": "Source image",
            "output_name": "Image name (without .png)",
            "background": "Background",
            "transparent": "Transparent",
            "white": "White",
            "strength": "Cleanup threshold",
            "scale": "Output size (%)",
            "output": "Output directory",
            "save": "Save PNG",
            "original": "Original",
            "processed": "Processed",
            "loading": "Processing…",
            "load_error": "Could not load quick_pic",
            "preview_error": "Could not create preview",
            "saving": "Saving…",
            "saved": "Saved",
            "no_images": "No recent images found",
        }
    return {
        "source": "原图",
        "output_name": "图片名称（无需 .png）",
        "background": "背景",
        "transparent": "透明",
        "white": "纯白",
        "strength": "清理阈值",
        "scale": "输出比例（%）",
        "output": "输出目录",
        "save": "保存 PNG",
        "original": "原始照片",
        "processed": "处理预览",
        "loading": "处理中…",
        "load_error": "无法加载素写速食",
        "preview_error": "无法生成预览",
        "saving": "正在保存…",
        "saved": "已保存",
        "no_images": "没有找到最近的图片",
    }


def main() -> None:
    print("quick_pic uses its dedicated web page.")


if __name__ == "__main__":
    main()
