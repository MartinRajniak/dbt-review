"""Turn a unified diff into the changed dbt files and the line numbers that were added.

The diff only says *where to look*. Line numbers are those of the new version of each file,
which is the version on disk when the PR branch is checked out.
"""

from dataclasses import dataclass
from pathlib import Path

from unidiff import PatchedFile, PatchSet

DBT_SUFFIXES = {".sql", ".yml", ".yaml"}


@dataclass
class ChangedFile:
    path: str  # relative to the repo root, with forward slashes, as git prints it
    added_lines: list[int]


def parse_diff(diff_text: str) -> list[ChangedFile]:
    """Changed dbt files in the diff. Deleted files are left out: nothing is left to review."""
    return [
        ChangedFile(path=patched_file.path, added_lines=_added_lines(patched_file))
        for patched_file in PatchSet(diff_text)
        if not patched_file.is_removed_file and _is_dbt_file(patched_file.path)
    ]


def _added_lines(patched_file: PatchedFile) -> list[int]:
    return [line.target_line_no for hunk in patched_file for line in hunk if line.is_added]


def _is_dbt_file(path: str) -> bool:
    in_hidden_folder = any(part.startswith(".") for part in Path(path).parts)  # e.g. .github/
    return Path(path).suffix in DBT_SUFFIXES and not in_hidden_folder
