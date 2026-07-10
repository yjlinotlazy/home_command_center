from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

from app_settings import chinese_chars_output_dir


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
    kind: str = "text"
    required: bool = True
    default: str = ""
    placeholder: str = ""
    help: str = ""
    max_length: int = 200
    pattern: str | None = None
    choices: tuple[str, ...] = ()
    value_type: str = "string"

    def to_dict(self, tool_id: str | None = None) -> dict[str, Any]:
        default = _arg_default(tool_id, self)
        return {
            "name": self.name,
            "label": self.label,
            "kind": self.kind,
            "required": self.required,
            "default": default,
            "placeholder": default if self.name == "output_dir" else self.placeholder,
            "help": self.help,
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

    def to_app_dict(self) -> dict[str, Any]:
        return {
            "id": f"tool:{self.id}",
            "name": self.name,
            "url": f"/tools/{self.id}",
            "hostname": "Command tool",
            "thumbnail": None,
            "description": self.description,
            "tags": list(self.tags),
            "health_url": None,
            "health_verify_tls": True,
            "status": "online",
            "kind": "command",
        }

    def to_schema(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "args": [arg.to_dict(self.id) for arg in self.args],
        }


COMMAND_TOOLS: dict[str, CommandTool] = {
    "chinese-practice": CommandTool(
        id="chinese-practice",
        name="汉字练习纸",
        description="生成可打印的汉字练字 PDF。",
        script=ROOT / "cli_tools" / "chinese_practice.py",
        tags=("tools", "pdf", "chinese"),
        args=(
            ToolArg(
                name="chars",
                label="练习汉字",
                flag="--chars",
                placeholder="一二三",
                help="输入要练习的汉字。",
                max_length=40,
                pattern=r"[\u3400-\u9fff]+",
            ),
            ToolArg(
                name="density",
                label="每行格子数",
                flag="--density",
                kind="number",
                default="5",
                help="数字越小，格子越大。",
                choices=("3", "4", "5", "6", "7", "8"),
                max_length=1,
                value_type="integer",
            ),
            ToolArg(
                name="paper",
                label="纸张",
                flag="--paper",
                kind="select",
                default="us_letter",
                choices=("us_letter", "a4"),
                max_length=9,
            ),
            ToolArg(
                name="mode",
                label="练习模式",
                flag="--mode",
                kind="select",
                default="1",
                choices=("1", "2", "3"),
                help="1：参考字 + 笔画提示 + 描写格。2：笔画提示 + 空白格。3：只描写。",
                max_length=1,
                value_type="integer",
            ),
            ToolArg(
                name="copies",
                label="重复份数",
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
                flag="--output-dir",
                help="workbook_go 会在这个目录里按默认文件名保存 PDF。",
                max_length=500,
            ),
        ),
    ),
    "eat-what": CommandTool(
        id="eat-what",
        name="吃啥",
        description="生成每周菜单和跑腿清单，或列出所有菜谱。",
        script=ROOT / "cli_tools" / "eat_what.py",
        tags=("tools", "food", "menu"),
        args=(
            ToolArg(
                name="action",
                label="模式",
                flag="--action",
                kind="select",
                default="plan",
                choices=("plan", "list"),
                help="plan：生成菜单。list：只列出菜谱。",
                max_length=4,
            ),
            ToolArg(
                name="recipes",
                label="菜谱 CSV",
                flag="--recipes",
                default="/home/yli/e/Dropbox/github/eat_what/data/recipes.csv",
                placeholder="/home/yli/e/Dropbox/github/eat_what/data/recipes.csv",
                help="必须符合 eat_what 的 recipes.csv 格式。",
                max_length=500,
            ),
            ToolArg(
                name="max_time",
                label="单菜最长时间",
                flag="--max-time",
                kind="number",
                required=False,
                placeholder="留空表示不限制",
                max_length=4,
                value_type="integer",
            ),
            ToolArg(
                name="max_weekly_time",
                label="每周最长时间",
                flag="--max-weekly-time",
                kind="number",
                default="400",
                max_length=5,
                value_type="integer",
            ),
            ToolArg(
                name="max_overlap",
                label="食材重复上限",
                flag="--max-overlap",
                kind="number",
                default="6",
                max_length=3,
                value_type="integer",
            ),
            ToolArg(
                name="veg_dishes",
                label="额外素菜数",
                flag="--veg-dishes",
                kind="number",
                default="3",
                max_length=2,
                value_type="integer",
            ),
            ToolArg(
                name="spicy_dishes",
                label="额外辣菜数",
                flag="--spicy-dishes",
                kind="number",
                default="0",
                max_length=2,
                value_type="integer",
            ),
            ToolArg(
                name="seed",
                label="随机种子",
                flag="--seed",
                kind="number",
                required=False,
                placeholder="可选",
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


def run_command_tool(tool_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    tool = get_command_tool(tool_id)
    argv = [sys.executable, str(_safe_script_path(tool.script))]

    for arg in tool.args:
        value = _sanitize_arg(arg, payload.get(arg.name, _arg_default(tool.id, arg)))
        if value == "" and not arg.required:
            continue
        argv.extend([arg.flag, value])

    try:
        completed = subprocess.run(
            argv,
            cwd=ROOT,
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
    if tool_id == "chinese-practice" and arg.name == "output_dir":
        return str(chinese_chars_output_dir())
    return arg.default


def _sanitize_arg(arg: ToolArg, raw_value: Any) -> str:
    if raw_value is None:
        value = ""
    elif isinstance(raw_value, (str, int, float)):
        value = str(raw_value)
    else:
        raise ToolError(f"{arg.label}必须是文字")

    value = value.strip()
    if value == "" and not arg.required:
        return ""
    if arg.required and not value:
        raise ToolError(f"请填写{arg.label}")
    if len(value) > arg.max_length:
        raise ToolError(f"{arg.label}不能超过 {arg.max_length} 个字符")
    if arg.choices and value not in arg.choices:
        raise ToolError(f"{arg.label}只能是：{', '.join(arg.choices)}")
    if arg.pattern and not re.fullmatch(arg.pattern, value):
        raise ToolError(f"{arg.label}格式无效")
    if arg.value_type == "integer":
        try:
            int(value)
        except ValueError as exc:
            raise ToolError(f"{arg.label}必须是整数") from exc
    if arg.name == "output_dir":
        _validate_output_dir(value)
    return value


def _validate_output_dir(value: str) -> None:
    try:
        path = Path(value).expanduser().resolve()
    except OSError as exc:
        raise ToolError("输出目录无效") from exc
    if "\x00" in value:
        raise ToolError("输出目录无效")
    path.mkdir(parents=True, exist_ok=True)
