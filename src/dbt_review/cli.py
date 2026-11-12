"""Command line entry point."""

import argparse
import subprocess
import sys
from pathlib import Path

from dbt_review.diff import git_diff, parse_diff
from dbt_review.models import Review, ReviewContext, Severity
from dbt_review.report import render_json, render_text
from dbt_review.review import run_checks

EXIT_OK = 0
EXIT_FOUND_ERRORS = 1
EXIT_TOOL_FAILED = 2  # the tool broke; says nothing about the change under review


class ToolError(Exception):
    """The tool cannot run with the input it was given."""


def main(argv: list[str] | None = None) -> int:
    # Windows would otherwise pick a legacy code page.
    sys.stdout.reconfigure(encoding="utf-8")
    args = _parse_arguments(argv)
    try:
        diff_text = _read_diff(args)
    except ToolError as error:
        print(f"dbt-review: {error}", file=sys.stderr)
        return EXIT_TOOL_FAILED
    changed = parse_diff(diff_text)
    repo = Path(args.repo)
    has_repo = (repo / "dbt_project.yml").is_file()
    context = ReviewContext(repo=has_repo, base=args.base, files_changed=len(changed))
    review = Review(context=context, findings=run_checks(repo, changed) if has_repo else [])
    render = render_json if args.format == "json" else render_text
    print(render(review))
    return EXIT_FOUND_ERRORS if review.count(Severity.ERROR) else EXIT_OK


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
