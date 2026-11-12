# 4. Observability: what a run records, and where it goes

Status: accepted · 2026-11-12 · not built yet (see "State")

## Context

A review has two readers who want different things.

- **The author of the pull request** wants the findings and nothing else. Every extra line makes the findings less
  likely to be read.
- **Whoever maintains the tool** wants to know how it behaved: which model answered, what it cost, what the tool
  threw away, and whether results are getting better or worse over time.

The tool itself is a command that runs and exits. It keeps no state between runs.

## Decision

**The text report is for the author.** It shows findings, counts, and checks that were skipped. It shows no debug
information.

**The JSON report is the record of a run.** Next to the findings it carries:

| Field | Why |
|---|---|
| Tool version | To reproduce the run |
| Model as requested, and model as reported back by the provider | A provider can serve a newer model under the same name |
| Prompt version (a hash of the assembled prompt) | To tie a result to the exact instructions |
| Calls, tokens in and out, seconds | Cost and speed per review |
| Dropped findings, in full, with the reason | To see how the prompt fails, not only how often |
| Skipped checks, with the reason | A review that could not look is not a clean review |

The prompt version and the model version together are what make a replay possible: the same change, the same
prompt and the same model should give the same findings, and when they do not, that is run-to-run variance and
worth a number of its own.

**CI keeps the record.** The workflow saves the JSON report as an artifact of the pull request's run. Nothing has
to be hosted, and the history lives next to the code review it belongs to.

**Statistics come from the artifacts.** A script collects the reports and adds them up: reviews per week, findings
by check, share of reviews with an LLM finding, dropped findings by reason, tokens and cost, slowest reviews. A
table in the repository is enough to start; a dashboard reads the same files.

## Not decided here

- **Tracing.** The LLM library can emit OpenTelemetry traces (every prompt, answer and token count) to any backend
  that accepts them. Worth adding when more than one person needs to look inside a single review.
- **Whether a finding was right.** The most useful number is how many findings the author fixed and how many they
  dismissed. That needs the findings posted as review comments and their outcome read back. It is the feedback
  loop that turns the statistics into a measure of quality.

## State

On 2026-11-12 the JSON report has findings, counts and skipped checks. The model, prompt version, usage and
dropped findings are not in it yet, and no workflow uploads it.

## Consequences

- Prompts and code under review appear in the JSON report and in traces. For a private repository the artifact
  inherits the repository's access; a tracing backend would need the same care.
- The JSON shape becomes an interface. Changes to it need a version field once anything reads the artifacts.
