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


def test_deleted_files_and_non_dbt_files_are_left_out():
    diff_text = """\
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1 +1,2 @@
 # Title
+More text
diff --git a/models/old.sql b/models/old.sql
deleted file mode 100644
--- a/models/old.sql
+++ /dev/null
@@ -1 +0,0 @@
-select 1
"""
    assert parse_diff(diff_text) == []


def test_yaml_in_hidden_folders_is_not_a_dbt_file():
    diff_text = """\
diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml
--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -1 +1,2 @@
 name: ci
+on: push
"""
    assert parse_diff(diff_text) == []
