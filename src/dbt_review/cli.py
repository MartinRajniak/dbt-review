"""Command line entry point.

Exit code 2 means the tool itself could not do its job. It is kept apart from the exit
codes of a review result, so CI can tell "your change has a problem" from "the reviewer broke".
"""

import argparse
import sys

EXIT_TOOL_FAILED = 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dbt-review", description="Review dbt model changes in a git diff."
    )
    parser.parse_args(argv)
    print("dbt-review: nothing to review", file=sys.stderr)
    return EXIT_TOOL_FAILED
