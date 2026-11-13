"""Command line entry point."""

import argparse
import io
import subprocess
import sys
from enum import IntEnum
from pathlib import Path

from dbt_review.diff import git_diff
from dbt_review.errors import ToolError
from dbt_review.models import Severity
from dbt_review.report import render_json, render_text
from dbt_review.review import DEFAULT_MODEL, review_diff


class ExitCode(IntEnum):
    OK = 0
    FOUND_ERRORS = 1
    TOOL_FAILED = 2  # the tool broke; says nothing about the change under review


def main(argv: list[str] | None = None) -> ExitCode:
    # Windows would otherwise pick a legacy code page.
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    args = _parse_arguments(argv)
    try:
        review = review_diff(_read_diff(args), Path(args.repo), args.base, args.model)
    except ToolError as error:
        print(f"dbt-review: {error}", file=sys.stderr)
        return ExitCode.TOOL_FAILED
    except Exception as error:  # noqa: BLE001 - exit code 1 must only ever mean the review found an error
        print(f"dbt-review: unexpected failure ({type(error).__name__}): {error}", file=sys.stderr)
        return ExitCode.TOOL_FAILED
    render = render_json if args.format == "json" else render_text
    print(render(review, show_info=args.show_info))
    return ExitCode.FOUND_ERRORS if review.count(Severity.ERROR) else ExitCode.OK


def _parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="dbt-review", description="Review dbt model changes in a git diff.")
    parser.add_argument("--repo", default=".", help="dbt project under review (default: here)")
    parser.add_argument("--base", help="git ref the checked-out branch is compared against")
    parser.add_argument("--diff", help="file holding the diff to review, or - for standard input")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--show-info", action="store_true", help="also print info findings")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="LLM as provider:name (default: %(default)s)")
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
