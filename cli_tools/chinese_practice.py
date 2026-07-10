#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WORKBOOK_ROOT = Path("/home/yli/e/Dropbox/github/workbook_go/chinese_chars")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a Chinese practice PDF.")
    parser.add_argument("--chars", required=True)
    parser.add_argument("--density", type=int, default=5)
    parser.add_argument("--paper", choices=("us_letter", "a4"), default="us_letter")
    parser.add_argument("--mode", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument("--copies", type=int, choices=range(1, 6), default=2)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    chars = _validate_chars(args.chars)
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    before = {path.resolve() for path in output_dir.glob("*.pdf")}

    sys.path.insert(0, str(WORKBOOK_ROOT))
    from cli import main as workbook_main

    previous_cwd = Path.cwd()
    try:
        import os

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


def _validate_chars(raw: str) -> str:
    chars = raw.strip()
    if not chars:
        raise SystemExit("Characters are required")
    if len(chars) > 40:
        raise SystemExit("Characters must be 40 characters or fewer")
    if not re.fullmatch(r"[\u3400-\u9fff]+", chars):
        raise SystemExit("Only Chinese characters are supported")
    return chars


def _newest_created_pdf(output_dir: Path, before: set[Path]) -> Path:
    after = {path.resolve() for path in output_dir.glob("*.pdf")}
    created = sorted(after - before, key=lambda path: path.stat().st_mtime, reverse=True)
    if not created:
        raise SystemExit("Workbook did not create a PDF")
    return created[0]


if __name__ == "__main__":
    main()
