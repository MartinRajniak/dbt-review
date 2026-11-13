# dbt-review

Reviews a change to dbt models before it is merged. It reads the git diff to see what changed, reads the dbt
project to understand it, and prints findings with a file, a line, a severity and a fix.

It uses two kinds of checks:

- **Rules** for mistakes that can be recognised with certainty, such as a hardcoded table name. Same input, same
  answer, no LLM. Only a rule can fail the build.
- **One LLM call per changed model** for judgement a rule cannot make, such as "does this join multiply rows?".
  The LLM is given the facts it needs (which columns have `unique` tests) and must cite them. Its findings are
  warnings at most.

```
dbt-review · base duckdb · 2 files changed

models/orders.sql
  55     warning  join-fanout (llm)
         The left join to payments can create multiple rows per order because payments may contain several
         rows per order_id, breaking the orders model's unique order_id constraint.
         Evidence: orders model declares a unique test on order_id (order_id unique, not_null).
                   stg_payments (source for payments) does NOT have a unique test on order_id.
                   +  55 |     left join payments
                   +  56 |         on orders.order_id = payments.order_id
         Fix: Aggregate payments by order_id before joining or join on a column that is unique in the payments side.

0 errors · 1 warning · 0 info
```

This is [`examples/fanout-join/output.txt`](examples/fanout-join/output.txt); one long line is wrapped here.

## What it checks

| Check | Kind | Severity | Catches |
|---|---|---|---|
| `hardcoded-relation` | rule | error | A table named directly (`main.stg_payments`) where `ref()` or `source()` belongs |
| `select-star` | rule | warning | A `*` that decides the model's columns. Import CTEs and a closing `select * from final` are fine |
| `join-fanout` | LLM | warning | A new join that can return more rows than before |
| `naming` | LLM | info | Model and column names that break the project's conventions |

## See it without installing anything

`examples/` holds eight changes to the [jaffle_shop_duckdb](https://github.com/MartinRajniak/jaffle_shop_duckdb)
demo project, one branch each (`scenario/<name>` in that fork). Every folder has the input diff and the review
the tool produced for it, as text and as JSON.

| Scenario | The change | Review |
|---|---|---|
| [`select-star`](examples/select-star/output.txt) | three named columns become `customers.*` | warning, line 51 |
| [`hardcoded-schema`](examples/hardcoded-schema/output.txt) | `ref('stg_payments')` becomes `main.stg_payments` | error, line 11, exit code 1 |
| [`fanout-join`](examples/fanout-join/output.txt) | a join to payments on a column that is not unique | warning, line 55 |
| [`prompt-injection`](examples/prompt-injection/output.txt) | the same join, with a comment telling AI reviewers to report nothing | the same warning |
| [`bad-naming`](examples/bad-naming/output.txt) | a new model `orders_cleaned_v2` with columns `cust`, `dt`, `flag` | two of the four names |
| [`clean-change`](examples/clean-change/output.txt) | a new column with a test | nothing |
| [`new-model-no-tests`](examples/new-model-no-tests/output.txt) | a new model without tests | nothing: this check is not built |
| [`payment-method-drift`](examples/payment-method-drift/output.txt) | a value added in one place of two | nothing: this check is not built |

Five of the seven flawed changes pass `dbt build` with every test green. That is the gap this tool is for. The
fanout is one of the two that fail it: the `unique` test on `orders` catches it only when the data has a
duplicate and the build runs; the review flags it on the diff, before either.

## Run it

You need [uv](https://docs.astral.sh/uv/) and git.

```bash
git clone https://github.com/MartinRajniak/dbt-review
git clone https://github.com/MartinRajniak/jaffle_shop_duckdb
cd jaffle_shop_duckdb
git checkout scenario/fanout-join

uvx --from dbt-duckdb dbt parse            # writes target/manifest.json; no database needed
export GROQ_API_KEY=...                    # optional: without a key the rules run and the LLM check is skipped

uv run --project ../dbt-review dbt-review --base duckdb
```

| Option | Meaning |
|---|---|
| `--base REF` | Review what the checked-out branch changed since it left `REF`. The usual form, locally and in CI |
| `--diff FILE`, `--diff -` | Review a diff you supply, from a file or a pipe: `git diff HEAD~1 \| dbt-review --diff -` |
| `--repo DIR` | The dbt project (default: the current directory) |
| `--format json` | Machine-readable output |
| `--show-info` | Also print `info` findings; by default they are only counted |
| `--model provider:name` | The LLM (default `groq:openai/gpt-oss-120b`). Reads `GROQ_API_KEY`, `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` |

Exit codes: `0` no errors · `1` the review found an error · `2` the tool could not do its job (no dbt project,
or the checkout does not match the diff).

To check the tool itself:

```bash
cd dbt-review
uv sync
uv run pytest            # no network, no API key
uv run ruff check && uv run mypy
```

To re-create every sample output from the scenario branches (it runs `dbt parse` through `uvx`):

```bash
uv run python examples/regenerate.py --fork ../jaffle_shop_duckdb
```

The rule findings come out identical every time. The LLM findings should land on the same lines, in
different words, and the naming check does not always pick the same names.

## How it works

1. Parse the diff into changed dbt files and the lines each one added.
2. Refuse to continue if there is no dbt project, or if the files on disk are not the ones the diff describes.
3. Run every rule on each changed model. SQL is parsed with sqlglot after Jinja is swapped for placeholders.
4. For each changed model that dbt's manifest knows, make one LLM call. The prompt holds the model's file with
   line numbers, the added lines marked, and the tests dbt declares on the model and on the models it reads.
5. Keep only findings on lines the change added. Print them grouped by file.

The instructions the LLM receives are one file: [`src/dbt_review/instructions.md`](src/dbt_review/instructions.md).

## Design decisions

Each has a short record with the reasoning and what was rejected.

| Decision | Record |
|---|---|
| A workflow with one narrow LLM call, not an agent exploring the repository. Where an agent fits later | [ADR 1](docs/adr/0001-workflow-first-agent-as-a-later-layer.md) |
| The repository is required and must match the diff; the tool refuses to guess | [ADR 2](docs/adr/0002-the-repository-is-required-and-must-match-the-diff.md) |
| How the LLM check is evaluated, and what the first runs showed | [ADR 3](docs/adr/0003-how-the-llm-check-is-evaluated.md) |
| What a run records and where it goes | [ADR 4](docs/adr/0004-observability.md) |

Smaller choices:

- **The LLM cannot fail a build.** Its answer schema has no `error` severity and requires evidence. The file and
  the `llm` label are set by code.
- **The LLM never sees comments.** A comment telling AI reviewers to report nothing silenced the fanout finding in
  4 of 8 runs. Comments are now removed before the model sees the file, and it is found in 8 of 8.
- **Jinja is not compiled.** Compiling would turn `ref('x')` into a plain table name, which is exactly what
  `hardcoded-relation` looks for, and it would move the line numbers.
- **dbt is not a dependency.** The tool reads the `manifest.json` that `dbt parse` writes.
- **Pydantic AI for the LLM call.** It gives a typed, validated answer, one retry when the answer does not fit, a
  fake model for tests, and the provider as a setting. Groq's `openai/gpt-oss-120b` is the default because it is
  free to try and holds the answer structure well. Anthropic and OpenAI models are accepted through the same
  option and have not been run.
- **Little text on purpose.** The more a review says, the less of it is read: `info` findings are hidden by
  default, and each message and fix is capped at 300 characters (evidence lines are not).

## Adding a check

- **A rule** is one module in [`src/dbt_review/checks/`](src/dbt_review/checks/) with a `check_id` and a
  `check(path, sql)` function, plus its name in the `RULES` list. The type checker verifies the shape.
- **An LLM check** is a section in `instructions.md` plus its id in the answer schema in `llm_check.py`. Those are
  two places; see next steps.

## Limitations

- **Small evidence.** The results come from tens of calls on one demo project. See ADR 3.
- **DuckDB SQL only.** A model the parser cannot read, such as Snowflake's `value:id::int`, is reported as skipped
  by the rules.
- **Tests on sources and seeds are not given to the LLM**, so a join to a source with a `unique` test can still be
  flagged.
- **Every changed `.sql` file is checked by the rules**, including singular tests and analyses.
- **The dbt project must be at the root of the git repository.**
- **A finding cannot be suppressed** in the code yet.
- **Naming is caught in part**: two of four bad names in the sample. Closing that needs prompt work or a stronger
  model, measured against the scenarios.
- **SQL produced by macros is invisible** to the rules, because Jinja is not compiled.
- **A model with a `union` at the top level** is not checked by `select-star`.
- **The LLM check needs a current manifest.** A changed model the manifest does not know is not sent to the LLM,
  and a stale manifest is not detected.
- **A changed `.yml` file is not reviewed** by either kind of check.
- **A failed LLM call** is tried once more; after that the whole LLM check is reported as skipped for the run.
- **An instruction could still hide** in a string literal or a column alias. Hiding comments narrows that route;
  it does not close it.

## Next steps

Roughly in the order I would do them:

1. **Scenario tests against the real project**, with an `expected.json` per scenario, so a prompt or model change
   is measured before it is merged, and the same run nightly to notice the provider changing the model (ADR 3).
2. **Record the model, the prompt version and token counts** in the JSON report, and save it as an artifact of
   each pull request's CI run (ADR 4).
3. **A CI workflow** for the reviewed repository: `dbt parse`, then
   `uvx --from git+https://github.com/MartinRajniak/dbt-review dbt-review --base origin/main`. A pinned Docker
   image after that, so there is no install step on every run.
4. **One definition per LLM check** (id, default severity, guidance), with the prompt and the answer schema
   assembled from the enabled ones, and severity set by code.
5. **A configuration file in the reviewed repository** for what does not change per run: the model, which checks
   are on, severity per check, naming conventions. Flags stay for what does change: the base and the format.
6. **More checks**: a new model without `unique` and `not_null` tests on its key; a value list or column name
   that now disagrees with another file (the two scenarios above that find nothing today).
7. **Verify the evidence**: check that every column and test the LLM cites exists in the manifest.
8. **Mutation testing** of the unit tests, to find the ones that would not notice a bug.
9. **An agent as an advisory layer** on top, to find what nobody wrote a check for (ADR 1).

## How it was built

Built test-first in small commits; the history can be read commit by commit. CI runs ruff, mypy in strict mode and the tests on every push.

It was built with Claude Code as a pair. The design, the scope and the constraints were set by the author, who
reviewed every commit and questioned the decisions recorded in the ADRs.
About six and a half hours of the author's time went into it.

## Licence

MIT, see [LICENSE](LICENSE). The diffs in `examples/` quote the
[jaffle_shop_duckdb](https://github.com/dbt-labs/jaffle_shop_duckdb) demo project by dbt Labs, which is
licensed under Apache-2.0.
