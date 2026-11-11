"""Command line entry point.

Exit code 2 means the tool itself could not do its job. It is kept apart from the exit
codes of a review result, so CI can tell "your change has a problem" from "the reviewer broke".
"""

import argparse
import subprocess
import sys
from pathlib import Path

from dbt_review.diff import git_diff, parse_diff
from dbt_review.models import Review, ReviewContext
from dbt_review.report import render_json, render_text

EXIT_OK = 0
EXIT_TOOL_FAILED = 2


class ToolError(Exception):
    """The tool was called in a way it cannot work with. Nothing to do with the code under review."""


def main(argv: list[str] | None = None) -> int:
    # The report is UTF-8 on every platform; Windows would otherwise pick a legacy code page.
    sys.stdout.reconfigure(encoding="utf-8")
    args = _parse_arguments(argv)
    try:
        diff_text = _read_diff(args)
    except ToolError as error:
        print(f"dbt-review: {error}", file=sys.stderr)
        return EXIT_TOOL_FAILED
    changed = parse_diff(diff_text)
    has_repo = (Path(args.repo) / "dbt_project.yml").is_file()
    context = ReviewContext(repo=has_repo, base=args.base, files_changed=len(changed))
    review = Review(context=context)
    render = render_json if args.format == "json" else render_text
    print(render(review))
    return EXIT_OK


def _parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="dbt-review", description="Review dbt model changes in a git diff."
    )
    parser.add_argument("--repo", default=".", help="dbt project under review (default: here)")
    parser.add_argument("--base", help="git ref the checked-out branch is compared against")
    parser.add_argument("--diff", help="file holding the diff to review, or - for standard input")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser.parse_args(argv)


def _read_diff(args: argparse.Namespace) -> str:
    if args.base and args.diff:
        raise ToolError("use either --base or --diff, not both")
    if args.base:
        return _diff_against_base(Path(args.repo), args.base)
    if args.diff == "-":
        return sys.stdin.read()
    if args.diff:
        return _diff_from_file(Path(args.diff))
    raise ToolError("nothing to review: pass --base REF or --diff FILE")


def _diff_against_base(repo: Path, base: str) -> str:
    try:
        return git_diff(repo, base)
    except subprocess.CalledProcessError as error:
        raise ToolError(f"git diff against '{base}' failed: {error.stderr.strip()}") from error


def _diff_from_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise ToolError(f"cannot read diff file: {error}") from error
