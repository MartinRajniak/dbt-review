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
- Partial context is handled differently: when only something optional is missing (the manifest, an API key), the
  checks that need it are skipped and the report names them and says why.

## Considered and not built

Reading the files from git instead of from disk (`--base A --head B`): it solves no case we have, because CI checks
out the head commit anyway and the LLM check needs a manifest built from a checkout.
