from __future__ import annotations

import datetime as dt
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote
import os

from app_settings import chinese_chars_output_dir, eat_what_recipes_csv
from i18n import normalize_lang, tr


ROOT = Path(__file__).resolve().parent
TOOL_TIMEOUT_SECONDS = 20
FILE_MARKER = "HCC_FILE="


class ToolError(Exception):
    pass


@dataclass(frozen=True)
class ToolArg:
    name: str
    label: str
    flag: str
    label_en: str = ""
    kind: str = "text"
    required: bool = True
    default: str = ""
    placeholder: str = ""
    placeholder_en: str = ""
    help: str = ""
    help_en: str = ""
    max_length: int = 200
    pattern: str | None = None
    choices: tuple[str, ...] = ()
    value_type: str = "string"

    def label_for(self, lang: str | None = None) -> str:
        if normalize_lang(lang) == "en" and self.label_en:
            return self.label_en
        return self.label

    def help_for(self, lang: str | None = None) -> str:
        if normalize_lang(lang) == "en" and self.help_en:
            return self.help_en
        return self.help

    def placeholder_for(self, lang: str | None = None) -> str:
        if normalize_lang(lang) == "en" and self.placeholder_en:
            return self.placeholder_en
        return self.placeholder

    def to_dict(self, tool_id: str | None = None, lang: str | None = None) -> dict[str, Any]:
        default = _arg_default(tool_id, self)
        return {
            "name": self.name,
            "label": self.label_for(lang),
            "label_zh": self.label,
            "label_en": self.label_en,
            "kind": self.kind,
            "required": self.required,
            "default": default,
            "placeholder": default if self.name == "output_dir" else self.placeholder_for(lang),
            "placeholder_zh": self.placeholder,
            "placeholder_en": self.placeholder_en,
            "help": self.help_for(lang),
            "help_zh": self.help,
            "help_en": self.help_en,
            "max_length": self.max_length,
            "pattern": self.pattern,
            "choices": list(self.choices),
            "value_type": self.value_type,
        }


@dataclass(frozen=True)
class CommandTool:
    id: str
    name: str
    description: str
    script: Path
    args: tuple[ToolArg, ...]
    tags: tuple[str, ...] = ("tools",)
    name_en: str = ""
    description_en: str = ""

    def name_for(self, lang: str | None = None) -> str:
        if normalize_lang(lang) == "en" and self.name_en:
            return self.name_en
        return self.name

    def description_for(self, lang: str | None = None) -> str:
        if normalize_lang(lang) == "en" and self.description_en:
            return self.description_en
        return self.description

    def to_app_dict(self, lang: str | None = None) -> dict[str, Any]:
        return {
            "id": f"tool:{self.id}",
            "name": self.name_for(lang),
            "name_zh": self.name,
            "name_en": self.name_en,
            "url": f"/tools/{self.id}",
            "hostname": tr(lang, "command_tool"),
            "thumbnail": None,
            "description": self.description_for(lang),
            "description_zh": self.description,
            "description_en": self.description_en,
            "tags": list(self.tags),
            "health_url": None,
            "health_verify_tls": True,
            "status": "online",
            "kind": "command",
        }

    def to_schema(self, lang: str | None = None) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name_for(lang),
            "name_zh": self.name,
            "name_en": self.name_en,
            "description": self.description_for(lang),
            "description_zh": self.description,
            "description_en": self.description_en,
            "args": [arg.to_dict(self.id, lang) for arg in self.args],
        }


COMMAND_TOOLS: dict[str, CommandTool] = {
    "chinese-practice": CommandTool(
        id="chinese-practice",
        name="汉字练习纸",
        description="生成可打印的汉字练字 PDF。",
        script=ROOT / "cli_tools" / "chinese_practice.py",
        tags=("tools", "pdf", "chinese"),
        name_en="Chinese Practice Sheets",
        description_en="Generate printable Chinese handwriting practice PDFs.",
        args=(
            ToolArg(
                name="chars",
                label="练习汉字",
                label_en="Chinese characters",
                flag="--chars",
                placeholder="一二三",
                placeholder_en="一二三",
                help="输入要练习的汉字。",
                help_en="Enter the Chinese characters to practice.",
                max_length=40,
                pattern=r"[\u3400-\u9fff]+",
            ),
            ToolArg(
                name="density",
                label="每行格子数",
                label_en="Cells per row",
                flag="--density",
                kind="number",
                default="5",
                help="数字越小，格子越大。",
                help_en="Smaller numbers make larger practice cells.",
                choices=("3", "4", "5", "6", "7", "8"),
                max_length=1,
                value_type="integer",
            ),
            ToolArg(
                name="paper",
                label="纸张",
                label_en="Paper size",
                flag="--paper",
                kind="select",
                default="us_letter",
                choices=("us_letter", "a4"),
                max_length=9,
            ),
            ToolArg(
                name="mode",
                label="练习模式",
                label_en="Practice mode",
                flag="--mode",
                kind="select",
                default="1",
                choices=("1", "2", "3"),
                help="1：参考字 + 笔画提示 + 描写格。2：笔画提示 + 空白格。3：只描写。",
                help_en="1: reference characters, stroke hints, and tracing boxes. 2: stroke hints and blank boxes. 3: tracing only.",
                max_length=1,
                value_type="integer",
            ),
            ToolArg(
                name="copies",
                label="重复份数",
                label_en="Copies",
                flag="--copies",
                kind="number",
                default="2",
                choices=("1", "2", "3", "4", "5"),
                max_length=1,
                value_type="integer",
            ),
            ToolArg(
                name="output_dir",
                label="输出目录",
                label_en="Output directory",
                flag="--output-dir",
                help="workbook_go 会在这个目录里按默认文件名保存 PDF。",
                help_en="workbook_go saves the PDF in this directory with its default filename pattern.",
                max_length=500,
            ),
        ),
    ),
    "daka": CommandTool(
        id="daka",
        name="新年愿望打卡",
        description="按日期给已有的愿望和任务打卡。",
        script=ROOT / "cli_tools" / "daka_checkin.py",
        tags=("tools", "tracker", "daka"),
        name_en="New Year Check-in",
        description_en="Check off existing resolutions and tasks by date.",
        args=(
            ToolArg(
                name="date",
                label="日期",
                label_en="Date",
                flag="--date",
                kind="date",
                default=dt.date.today().isoformat(),
                help="默认是今天。",
                help_en="Defaults to today.",
                max_length=10,
            ),
            ToolArg(
                name="resolution",
                label="类别",
                label_en="Category",
                flag="--resolution",
                max_length=80,
            ),
            ToolArg(
                name="item",
                label="子类别",
                label_en="Subcategory",
                flag="--item",
                max_length=120,
            ),
        ),
    ),
    "eat-what": CommandTool(
        id="eat-what",
        name="吃啥",
        description="生成每周菜单和跑腿清单，或列出所有菜谱。",
        script=ROOT / "cli_tools" / "eat_what.py",
        tags=("tools", "food", "menu"),
        name_en="What to Eat",
        description_en="Generate weekly menus and shopping lists, or list all recipes.",
        args=(
            ToolArg(
                name="action",
                label="模式",
                label_en="Mode",
                flag="--action",
                kind="select",
                default="plan",
                choices=("plan", "list"),
                help="plan：生成菜单。list：只列出菜谱。",
                help_en="plan: generate a menu. list: only list recipes.",
                max_length=4,
            ),
            ToolArg(
                name="recipes",
                label="菜谱 CSV",
                label_en="Recipes CSV",
                flag="--recipes",
                default="",
                placeholder="recipes.csv",
                placeholder_en="recipes.csv",
                help="必须符合 eat_what 的 recipes.csv 格式。",
                help_en="Must match the eat_what recipes.csv format.",
                max_length=500,
            ),
            ToolArg(
                name="max_time",
                label="单菜最长时间",
                label_en="Max single-dish time",
                flag="--max-time",
                kind="number",
                required=False,
                placeholder="留空表示不限制",
                placeholder_en="Leave blank for no limit",
                max_length=4,
                value_type="integer",
            ),
            ToolArg(
                name="max_weekly_time",
                label="每周最长时间",
                label_en="Max weekly time",
                flag="--max-weekly-time",
                kind="number",
                default="400",
                max_length=5,
                value_type="integer",
            ),
            ToolArg(
                name="max_overlap",
                label="食材重复上限",
                label_en="Ingredient overlap limit",
                flag="--max-overlap",
                kind="number",
                default="6",
                max_length=3,
                value_type="integer",
            ),
            ToolArg(
                name="veg_dishes",
                label="额外素菜数",
                label_en="Extra vegetarian dishes",
                flag="--veg-dishes",
                kind="number",
                default="3",
                max_length=2,
                value_type="integer",
            ),
            ToolArg(
                name="spicy_dishes",
                label="额外辣菜数",
                label_en="Extra spicy dishes",
                flag="--spicy-dishes",
                kind="number",
                default="0",
                max_length=2,
                value_type="integer",
            ),
            ToolArg(
                name="seed",
                label="随机种子",
                label_en="Random seed",
                flag="--seed",
                kind="number",
                required=False,
                placeholder="可选",
                placeholder_en="Optional",
                max_length=10,
                value_type="integer",
            ),
        ),
    ),
}


def list_command_tools() -> list[CommandTool]:
    return sorted(COMMAND_TOOLS.values(), key=lambda tool: tool.name.lower())


def get_command_tool(tool_id: str) -> CommandTool:
    try:
        return COMMAND_TOOLS[tool_id]
    except KeyError as exc:
        raise ToolError(f"Unknown command tool '{tool_id}'") from exc


def run_command_tool(tool_id: str, payload: dict[str, Any], lang: str | None = None) -> dict[str, Any]:
    tool = get_command_tool(tool_id)
    resolved_lang = normalize_lang(lang)
    argv = [sys.executable, str(_safe_script_path(tool.script))]
    env = os.environ.copy()
    env["HCC_LANG"] = resolved_lang

    for arg in tool.args:
        value = _sanitize_arg(arg, payload.get(arg.name, _arg_default(tool.id, arg)), resolved_lang)
        if value == "" and not arg.required:
            continue
        argv.extend([arg.flag, value])

    try:
        completed = subprocess.run(
            argv,
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=TOOL_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ToolError(f"{tool.name} timed out after {TOOL_TIMEOUT_SECONDS} seconds") from exc

    return {
        "tool_id": tool.id,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "ok": completed.returncode == 0,
        "files": _extract_files(completed.stdout, payload),
    }


def _safe_script_path(path: Path) -> Path:
    resolved = path.resolve()
    tools_root = (ROOT / "cli_tools").resolve()
    if not resolved.is_file() or tools_root not in resolved.parents:
        raise ToolError(f"Registered command script is not available: {path}")
    return resolved


def _extract_files(stdout: str, payload: dict[str, Any]) -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    output_root = _output_root_for_payload(payload)
    for line in stdout.splitlines():
        if not line.startswith(FILE_MARKER):
            continue
        raw_path = line.removeprefix(FILE_MARKER).strip()
        path = Path(raw_path)
        if not path.is_absolute():
            path = ROOT / path
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved.is_file() and (resolved == output_root or output_root in resolved.parents):
            files.append(
                {
                    "name": resolved.name,
                    "url": "/output/" + quote(resolved.relative_to(output_root).as_posix()),
                }
            )
    return files


def _output_root_for_payload(payload: dict[str, Any]) -> Path:
    raw_output_dir = payload.get("output_dir")
    if isinstance(raw_output_dir, str) and raw_output_dir.strip():
        return Path(raw_output_dir).expanduser().resolve()
    return chinese_chars_output_dir().resolve()


def _arg_default(tool_id: str | None, arg: ToolArg) -> str:
    if tool_id == "daka" and arg.name == "date":
        return dt.date.today().isoformat()
    if tool_id == "eat-what" and arg.name == "recipes":
        return str(eat_what_recipes_csv())
    if tool_id == "chinese-practice" and arg.name == "output_dir":
        return str(chinese_chars_output_dir())
    return arg.default


def _sanitize_arg(arg: ToolArg, raw_value: Any, lang: str | None = None) -> str:
    if raw_value is None:
        value = ""
    elif isinstance(raw_value, (str, int, float)):
        value = str(raw_value)
    else:
        raise ToolError(tr(lang, "required_text", label=arg.label_for(lang)))

    value = value.strip()
    if value == "" and not arg.required:
        return ""
    if arg.required and not value:
        raise ToolError(tr(lang, "required_field", label=arg.label_for(lang)))
    if len(value) > arg.max_length:
        raise ToolError(tr(lang, "too_long", label=arg.label_for(lang), max_length=arg.max_length))
    if arg.choices and value not in arg.choices:
        raise ToolError(tr(lang, "invalid_choice", label=arg.label_for(lang), choices=", ".join(arg.choices)))
    if arg.pattern and not re.fullmatch(arg.pattern, value):
        raise ToolError(tr(lang, "invalid_pattern", label=arg.label_for(lang)))
    if arg.value_type == "integer":
        try:
            int(value)
        except ValueError as exc:
            raise ToolError(tr(lang, "must_be_integer", label=arg.label_for(lang))) from exc
    if arg.name == "output_dir":
        _validate_output_dir(value, lang)
    return value


def _validate_output_dir(value: str, lang: str | None = None) -> None:
    try:
        path = Path(value).expanduser().resolve()
    except OSError as exc:
        raise ToolError(tr(lang, "invalid_output_dir")) from exc
    if "\x00" in value:
        raise ToolError(tr(lang, "invalid_output_dir"))
    path.mkdir(parents=True, exist_ok=True)
