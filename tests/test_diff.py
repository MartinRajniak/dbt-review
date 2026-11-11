from pathlib import Path

from dbt_review.diff import parse_diff

EXAMPLES = Path(__file__).parent.parent / "examples"


def example_diff(scenario: str) -> str:
    return (EXAMPLES / scenario / "input.diff").read_text(encoding="utf-8")


def test_added_lines_are_numbered_as_in_the_new_file():
    changed = {file.path: file.added_lines for file in parse_diff(example_diff("fanout-join"))}
    assert changed == {
        "models/orders.sql": [46, 47, 55, 56, 57],
        "models/schema.yml": [61, 62, 63],
    }


def test_empty_diff_gives_no_files():
    assert parse_diff("") == []
