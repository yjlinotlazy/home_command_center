#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import io
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app_settings import eat_what_root
from command_tools import get_command_tool
from cli_tools.util import render_tool_page_shell

EAT_WHAT_ROOT = eat_what_root()


def render_tool_page() -> str:
    tool = get_command_tool("eat-what")
    return render_tool_page_shell(
        tool.id,
        tool.name,
        tool.description,
        body_html="""<form class="tool-panel tool-panel--eat-what" data-tool-form>
      <div class="tool-fields tool-fields--eat-what" data-tool-fields></div>
      <div class="tool-submit-row">
        <button class="open tool-submit tool-submit--eat-what" type="submit" data-tool-submit>生成</button>
      </div>
    </form>

    <section class="notice" data-tool-status hidden></section>
    <section class="notice" data-tool-error hidden></section>
    <section class="tool-daka" data-tool-daka hidden></section>
    <section class="generated-files" data-tool-files hidden></section>
    <pre class="tool-output" data-tool-output></pre>""",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run eat_what menu planner.")
    parser.add_argument("--action", choices=("plan", "list"), default="plan")
    parser.add_argument("--recipes", required=True)
    parser.add_argument("--max-time", type=int)
    parser.add_argument("--max-weekly-time", type=int, default=400)
    parser.add_argument("--max-overlap", type=int, default=6)
    parser.add_argument("--veg-dishes", type=int, default=3)
    parser.add_argument("--spicy-dishes", type=int, default=0)
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()

    recipes = Path(args.recipes).expanduser().resolve()
    if not recipes.is_file():
        raise SystemExit(f"菜谱文件不存在：{recipes}")

    sys.path.insert(0, str(EAT_WHAT_ROOT / "src"))
    from eat_what import cli

    eat_argv = ["eat-what", "--recipes", str(recipes)]
    if args.action == "list":
        eat_argv.append("--list")
    else:
        if args.max_time is not None:
            eat_argv.extend(["--max-time", str(args.max_time)])
        eat_argv.extend(
            [
                "--max-weekly-time",
                str(args.max_weekly_time),
                "--max-overlap",
                str(args.max_overlap),
                "--veg-dishes",
                str(args.veg_dishes),
                "--spicy-dishes",
                str(args.spicy_dishes),
            ]
        )
        if args.seed is not None:
            eat_argv.extend(["--seed", str(args.seed)])

    old_argv = sys.argv
    buffer = io.StringIO()
    try:
        sys.argv = eat_argv
        with contextlib.redirect_stdout(buffer):
            exit_code = cli.main()
    finally:
        sys.argv = old_argv

    print(buffer.getvalue().rstrip())
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
