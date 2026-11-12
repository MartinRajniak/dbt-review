# 2. The repository is required, and it must match the diff

Status: accepted · 2026-11-12

## Context

The tool has two inputs with two jobs. **The diff says what changed and where to look. The repository is what the
review reads.** The question is what the tool should do when the repository is missing, or is not the code the
diff describes.

Three common problems in dbt models show why the repository is needed: `SELECT *`, hardcoded schema names and
exploding joins. Two of the three cannot be judged from a diff:

- **`SELECT *`** is the dbt convention in an import CTE and in a closing `select * from final`, and a problem when
  it decides the model's columns. Only the whole file tells which.
- **An exploding join** depends on whether the joined column is unique in the other model. That is written in
  another file.

A review from the diff alone therefore has two outcomes, both bad. It stays silent, and CI shows a green result for
a review that looked at nothing. Or it guesses, and produces false alarms for reviewers who are already the
bottleneck.

## Decision

The diff is accepted in three forms:

| Form | Command |
|---|---|
| A base to compare against | `dbt-review --base HEAD~1` (the tool runs `git diff` itself) |
| A `.diff` file | `dbt-review --diff change.diff` |
| A pipe | `git diff HEAD~1 \| dbt-review --diff -` |

The repository is required, and the tool refuses to guess. Each of these is a tool failure, exit code 2, with a
message that says what to fix:

- there is no dbt project at `--repo`;
- a file changed by the diff is not in the checkout;
- a line the diff added is not at that line in the checkout, for example because the base branch is checked out
  instead of the branch under review.

Exit code 2 is separate from exit code 1 (the review found an error), so CI can tell "the change has a problem"
from "the reviewer could not do its job".

## Consequences

- A wrongly configured CI job fails loudly instead of passing forever.
- `--base` is the recommended form for CI: the diff is made from the checkout, so the two cannot disagree.
- The sample diffs in `examples/` can only be re-run against the fork with the matching scenario branch checked
  out. Each sample's committed output shows the result without any setup.
- Partial context is handled differently: when only something optional is missing (the manifest, an API key), the
  checks that need it are skipped and the report names them and says why.
- A reduced review from the diff alone stays possible later, for the few checks that are safe without the file,
  such as a schema-qualified table name on an added line.

## Considered and not built

**Reading the files from git instead of from disk** (`--base A --head B`, each file via `git show B:path`). The
state of the checkout would then not matter. It was rejected because it solves no case we have:

- In CI the checkout is the head commit, so `--base` already compares two commits.
- Locally, people review work in progress, which is not in any commit yet. `git diff <base> | dbt-review --diff -`
  covers that: the diff and the files both come from the working tree.
- The LLM check needs dbt's manifest, which is built from a checkout. Reviewing a commit that is not checked out
  would need a checkout anyway; `git worktree` gives one without a second way of reading files.

**Special handling of uncommitted changes** (a warning, or a flag to include them). One check already covers
the harmful case: a local edit that changes or moves an added line fails the comparison with the diff. Other
local edits are read as they are on disk. To review work in progress on purpose, give the tool that diff:
`git diff <base> | dbt-review --diff -` (run `git add -N <file>` first for a file git does not track yet).

**Checking a `.diff` file against the checkout by fingerprint.** A git diff records a hash of each file after the
change (the `index` line). Comparing it with the file on disk would be an exact whole-file check, where today only
the added lines are compared. It is a possible next step; it needs git to compute the hash the same way on every
platform.
