"""Turn a unified diff into the changed files and the line numbers that were added.

The diff only says *where to look*. Line numbers are those of the new version of each file,
which is the version on disk when the PR branch is checked out.
"""

from dataclasses import dataclass

from unidiff import PatchSet


@dataclass
class ChangedFile:
    path: str  # relative to the repo root, with forward slashes, as git prints it
    added_lines: list[int]


def parse_diff(diff_text: str) -> list[ChangedFile]:
    return [
        ChangedFile(
            path=patched_file.path,
            added_lines=[
                line.target_line_no for hunk in patched_file for line in hunk if line.is_added
            ],
        )
        for patched_file in PatchSet(diff_text)
    ]
