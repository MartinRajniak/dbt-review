"""End to end: on every scenario branch of the demo fork, the rules find what the sample in examples/ shows.

Needs the fork: set DBT_REVIEW_FORK to its URL or a local path (CI uses the GitHub URL). Skipped otherwise.
LLM findings are not compared: they need an API key and vary between runs.
"""

import json
import os
import subprocess
from collections.abc import Iterable
from pathlib import Path

import pytest

from dbt_review.diff import git_diff
from dbt_review.review import API_KEYS, review_diff

FORK = os.environ.get("DBT_REVIEW_FORK")
EXAMPLES = Path(__file__).parent.parent / "examples"
BASE = "origin/duckdb"

pytestmark = pytest.mark.skipif(not FORK, reason="set DBT_REVIEW_FORK to run against the demo fork")


@pytest.fixture(scope="module")
def fork(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A fresh clone, so the developer's own checkout of the fork is never switched."""
    path = tmp_path_factory.mktemp("fork")
    subprocess.run(["git", "clone", "--quiet", str(FORK), str(path)], check=True)
    return path


@pytest.mark.parametrize(
    "scenario", sorted(p.name for p in EXAMPLES.iterdir() if (p / "input.diff").is_file())
)
def test_the_rules_find_what_the_sample_shows(
    fork: Path, scenario: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in API_KEYS.values():
        monkeypatch.delenv(key, raising=False)
    subprocess.run(["git", "-C", str(fork), "checkout", "--quiet", f"origin/scenario/{scenario}"], check=True)

    review = review_diff(git_diff(fork, BASE), fork, BASE)

    sample = json.loads((EXAMPLES / scenario / "output.json").read_text(encoding="utf-8"))
    assert _rules(f.model_dump(mode="json") for f in review.findings) == _rules(sample["findings"])


def _rules(findings: Iterable[dict]) -> list[tuple[str, int, str, str]]:
    return sorted(
        (f["file"], f["line"], f["check_id"], f["severity"]) for f in findings if f["source"] == "rule"
    )
