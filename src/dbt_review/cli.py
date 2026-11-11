"""Command line entry point.

Exit code 2 means the tool itself could not do its job. It is kept apart from the exit
codes of a review result, so CI can tell "your change has a problem" from "the reviewer broke".
"""

import argparse
import sys
from pathlib import Path

from dbt_review.diff import parse_diff
from dbt_review.models import Review, ReviewContext
from dbt_review.report import render_text

EXIT_OK = 0
EXIT_TOOL_FAILED = 2


class ToolError(Exception):
    """The tool was called in a way it cannot work with. Nothing to do with the code under review."""


def main(argv: list[str] | None = None) -> int:
    args = _parse_arguments(argv)
    try:
        diff_text = _read_diff(args)
    except ToolError as error:
        print(f"dbt-review: {error}", file=sys.stderr)
        return EXIT_TOOL_FAILED
    changed = parse_diff(diff_text)
    review = Review(context=ReviewContext(repo=False, files_changed=len(changed)))
    print(render_text(review))
    return EXIT_OK


def _parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="dbt-review", description="Review dbt model changes in a git diff."
    )
    parser.add_argument("--diff", help="file holding the diff to review")
    return parser.parse_args(argv)


def _read_diff(args: argparse.Namespace) -> str:
    if not args.diff:
        raise ToolError("nothing to review: pass --diff FILE")
    try:
        return Path(args.diff).read_text(encoding="utf-8")
    except OSError as error:
        raise ToolError(f"cannot read diff file: {error}") from error
