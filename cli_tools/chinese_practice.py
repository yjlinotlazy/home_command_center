#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app_settings import workbook_go_root
from command_tools import get_command_tool
from i18n import normalize_lang, tr
from cli_tools.util import render_tool_arg_html, render_tool_page_shell

WORKBOOK_ROOT = workbook_go_root() / "chinese_chars"


def render_tool_page(lang: str = "zh") -> str:
    tool = get_command_tool("chinese-practice")
    schema = tool.to_schema(lang)
    args = {arg["name"]: arg for arg in schema["args"]}
    return render_tool_page_shell(
        tool.id,
        tool.name_for(lang),
        tool.description_for(lang),
        lang=lang,
        body_html=(
            """<form class="tool-panel tool-panel--practice" data-tool-form>
      <div class="tool-fields tool-fields--practice" data-tool-fields>
        <div class="tool-slot tool-slot--span-2" data-tool-slot="chars">"""
            + render_tool_arg_html(args["chars"])
            + """</div>
        <div class="tool-slot tool-slot--span-2" data-tool-slot="output_dir">"""
            + render_tool_arg_html(args["output_dir"])
            + """</div>
        <div class="tool-slot" data-tool-slot="density">"""
            + render_tool_arg_html(args["density"])
            + """</div>
        <div class="tool-slot" data-tool-slot="paper">"""
            + render_tool_arg_html(args["paper"])
            + """</div>
        <div class="tool-slot" data-tool-slot="mode">"""
            + render_tool_arg_html(args["mode"])
            + """</div>
        <div class="tool-slot" data-tool-slot="copies">"""
            + render_tool_arg_html(args["copies"])
            + """</div>
        <div class="tool-submit-row">
          <button class="open tool-submit tool-submit--large" type="submit" data-tool-submit>""" + tr(lang, "generate") + """</button>
        </div>
      </div>
    </form>

    <section class="notice" data-tool-status hidden></section>
    <section class="notice" data-tool-error hidden></section>
    <section class="tool-daka" data-tool-daka hidden></section>
    <section class="generated-files" data-tool-files hidden></section>
    <pre class="tool-output" data-tool-output></pre>"""
        ),
        extra_stylesheets=("/static/chinese_practice.css",),
        script_src="/static/chinese_practice.js",
        script_type="module",
    )


def main() -> None:
    lang = normalize_lang(os.environ.get("HCC_LANG"))
    parser = argparse.ArgumentParser(description="Generate a Chinese practice PDF.")
    parser.add_argument("--chars", required=True)
    parser.add_argument("--density", type=int, default=10)
    parser.add_argument("--paper", choices=("us_letter", "a4"), default="us_letter")
    parser.add_argument("--mode", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument("--copies", type=int, choices=range(1, 6), default=2)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    chars = _validate_chars(args.chars, lang)
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    before = {path.resolve() for path in output_dir.glob("*.pdf")}

    sys.path.insert(0, str(WORKBOOK_ROOT))
    from cli import main as workbook_main

    previous_cwd = Path.cwd()
    try:
        os.chdir(output_dir)
        workbook_main(
            argv=[
                chars,
                "--density",
                str(args.density),
                "--paper",
                args.paper,
                "--mode",
                str(args.mode),
                "--copies",
                str(args.copies),
            ]
        )
    finally:
        os.chdir(previous_cwd)

    output_path = _newest_created_pdf(output_dir, before)
    print(f"HCC_FILE={output_path}")


def _validate_chars(raw: str, lang: str) -> str:
    chars = raw.strip()
    if not chars:
        raise SystemExit(tr(lang, "required_field", label=tr(lang, "practice_chars")))
    if len(chars) > 40:
        raise SystemExit(tr(lang, "chars_too_long"))
    if not re.fullmatch(r"[\u3400-\u9fff]+", chars):
        raise SystemExit(tr(lang, "chars_only_chinese"))
    return chars


def _newest_created_pdf(output_dir: Path, before: set[Path]) -> Path:
    after = {path.resolve() for path in output_dir.glob("*.pdf")}
    created = sorted(after - before, key=lambda path: path.stat().st_mtime, reverse=True)
    if not created:
        raise SystemExit("Workbook did not create a PDF")
    return created[0]


if __name__ == "__main__":
    main()
