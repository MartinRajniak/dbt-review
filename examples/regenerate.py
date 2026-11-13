"""Re-create every sample output by running the reviewer on the scenario branches of the demo project.

    uv run python examples/regenerate.py --fork ../jaffle_shop_duckdb

For each folder in examples/ it checks out `scenario/<name>` in the fork, runs `dbt parse` so the manifest
matches the branch, reviews the branch against `duckdb`, and writes output.txt and output.json from that one review.
Without an API key the LLM check is skipped and the outputs say so.
"""

import argparse
import shlex
import subprocess
from pathlib import Path

from dbt_review.diff import git_diff
from dbt_review.report import render_json, render_text
from dbt_review.review import DEFAULT_MODEL, review_diff

BASE = "duckdb"
EXAMPLES = Path(__file__).parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fork", required=True, type=Path, help="checkout of the jaffle_shop_duckdb fork")
    parser.add_argument(
        "--dbt", default="uvx --from dbt-duckdb dbt", help="dbt command (default: %(default)s)"
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    for folder in sorted(path for path in EXAMPLES.iterdir() if (path / "input.diff").is_file()):
        git(args.fork, "checkout", "--quiet", f"scenario/{folder.name}")
        subprocess.run(
            [*shlex.split(args.dbt), "parse", "--quiet"], cwd=args.fork, check=True, capture_output=True
        )
        review = review_diff(git_diff(args.fork, BASE), args.fork, BASE, args.model)
        (folder / "output.txt").write_text(render_text(review) + "\n", encoding="utf-8")
        (folder / "output.json").write_text(render_json(review) + "\n", encoding="utf-8")
        print(f"{folder.name}: {len(review.findings)} findings, {len(review.skipped)} skipped")
    git(args.fork, "checkout", "--quiet", BASE)


def git(repo: Path, *arguments: str) -> None:
    subprocess.run(["git", "-C", str(repo), *arguments], check=True)


if __name__ == "__main__":
    main()
