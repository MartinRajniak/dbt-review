"""Turn a unified diff into the changed dbt files and their added line numbers.

Line numbers are those of the new version of each file.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path

from unidiff.patch import PatchedFile, PatchSet

DBT_SUFFIXES = {".sql", ".yml", ".yaml"}


@dataclass
class ChangedFile:
    path: str  # relative to the repo root, forward slashes
    added_lines: list[int]


def git_diff(repo: Path, base: str) -> str:
    """Three dots, as a pull request does: two would also report what landed on `base` since."""
    command = ["git", "-C", str(repo), "diff", "--no-color", "--no-ext-diff", f"{base}...HEAD"]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=True)
    return result.stdout


def parse_diff(diff_text: str) -> list[ChangedFile]:
    return [
        ChangedFile(path=patched_file.path, added_lines=_added_lines(patched_file))
        for patched_file in PatchSet(diff_text)
        if not patched_file.is_removed_file and _is_dbt_file(patched_file.path)
    ]


def _added_lines(patched_file: PatchedFile) -> list[int]:
    numbers = [line.target_line_no for hunk in patched_file for line in hunk if line.is_added]
    return [number for number in numbers if number is not None]


def _is_dbt_file(path: str) -> bool:
    in_hidden_folder = any(part.startswith(".") for part in Path(path).parts)  # e.g. .github/
    return Path(path).suffix in DBT_SUFFIXES and not in_hidden_folder
