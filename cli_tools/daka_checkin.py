#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from daka_bridge import DakaToolError, record_checkin
from command_tools import get_command_tool
from cli_tools.util import render_tool_page_shell


def render_tool_page(lang: str = "zh") -> str:
    tool = get_command_tool("daka")
    return render_tool_page_shell(tool.id, tool.name_for(lang), tool.description_for(lang), lang=lang)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a single daka check-in.")
    parser.add_argument("--date", help="check-in date in YYYY-MM-DD (default: today)")
    parser.add_argument("--resolution", required=True)
    parser.add_argument("--item", required=True)
    args = parser.parse_args()

    try:
        result = record_checkin(args.date, args.resolution, args.item)
    except DakaToolError as exc:
        raise SystemExit(str(exc)) from exc

    print(result["message"])


if __name__ == "__main__":
    main()
