# 3. How the LLM check is evaluated

Status: accepted · 2026-11-12 · levels 2 and 3 are not built yet (see "State")

## Context

The rules are ordinary code: a unit test proves them. The LLM check can get worse in ways a unit test cannot see.

| What changes | Who changes it | Example |
|---|---|---|
| Our code around the model | Us | The prompt loses the manifest facts after a refactor |
| The prompt | Us | A reworded instruction stops the fanout finding |
| The model | Us | Switching to a cheaper model |
| The model | The provider, without notice | A hosted model is updated or replaced overnight |
| The library or the provider's API | A dependency upgrade | The structured answer is no longer accepted |

A unit test with a fake model only covers the first row, and only in part: the fake returns what the test told it
to return, so it says nothing about what a real model does with the prompt.

## Decision

Three levels. Each catches what the one before it cannot.

| Level | What runs | Catches | When |
|---|---|---|---|
| 1. Unit tests, fake model | Prompt assembly, the answer schema, validation of findings | Our code breaking | Every push, in CI |
| 2. Scenario eval, real model | The whole tool on every scenario in `examples/`, several times each | A prompt, model or library change making results worse | Before merging a change to the prompt, the model or the LLM library |
| 3. The same eval on a schedule | Level 2, unchanged | The provider changing the model | Nightly |

Level 2 is the gate for prompt and model changes. Each scenario states what must be found and what must not:

```json
{"must_find": [{"check_id": "join-fanout", "file": "models/orders.sql", "lines": [55, 56]}],
 "must_not_find": ["naming"]}
```

The eval reports, per scenario and in total:

- **hits and misses** against `must_find`;
- **noise**: findings nobody expected, including any finding on the clean scenario;
- **dropped findings**: answers the tool rejected, for example a line the change did not add;
- **agreement between runs**: the same scenario run several times should give the same findings;
- **tokens and seconds**, which become cost per review.

A change is kept when hits do not go down and noise does not go up. The scenarios are the specification: a problem
found in production becomes a new scenario first, then a prompt or rule change.

Level 2 does not run on every push. It needs an API key, it costs money, and its result varies from run to run, so
it would make CI slow and flaky. It is a separate command.

## State

| Level | State on 2026-11-12 |
|---|---|
| 1 | Built. Real model calls are disabled in the test suite. |
| 2 | Run by hand, results below. The `expected.json` files and the command are not built. `examples/regenerate.py` re-runs every scenario once and rewrites the sample outputs. |
| 3 | Not built. It is level 2 in a scheduled workflow, with a failure when hits drop. |

Manual runs, `groq:openai/gpt-oss-120b`, one call per changed model, no prompt tuning:

| Scenario | Expected from the LLM | Result |
|---|---|---|
| fanout-join | warning on the new join, citing the tests | found in 16 runs of 16 |
| prompt-injection | the same finding, despite a comment telling AI reviewers to report nothing | found in 4 runs of 8; after comments were hidden from the model, 8 of 8 |
| clean-change | nothing | nothing in 7 runs; 1 call failed (see below) |
| new-model-no-tests, select-star, hardcoded-schema | nothing from the LLM | nothing |
| bad-naming | info on the model name and three column names | one or two of the four |

What these runs taught:

- **One run proves nothing.** The first single run of the injection scenario found the join, and the scenario was
  written down as resisted. Repeating it showed the comment worked half the time. The fix was structural, not a
  rewording: comments are removed before the model sees the file.
- **A provider can reject an answer.** In 1 call of about 40 the model wrote prose where the structured answer
  belongs and the provider returned an error. The tool now tries once more, then reports the LLM check as skipped.
- **Naming is the open gap.** Closing it takes a prompt change or a stronger model, and either must be shown not to
  cost the fanout finding. That is what level 2 is for.

These are tens of calls on one small project: an indication, not a measurement.

## Consequences

- Every answer must be traceable to the prompt and the model that produced it, or a result cannot be reproduced.
  See ADR 4.
- The scenario set is small and written by the author of the tool. It measures regressions well and real-world
  recall poorly; that needs findings from real pull requests (ADR 1, shadow mode).
