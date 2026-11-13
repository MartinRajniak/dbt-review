import os
from pathlib import Path

from pydantic_ai.exceptions import AgentRunError
from sqlglot.errors import SqlglotError

from dbt_review.checks import RULES
from dbt_review.diff import ChangedFile, parse_diff
from dbt_review.errors import ToolError
from dbt_review.llm_check import ModelContext, review_model
from dbt_review.manifest import load_manifest
from dbt_review.models import Finding, Review, ReviewContext, Skipped

DEFAULT_MODEL = "groq:openai/gpt-oss-120b"
# The environment variable each provider's key is read from.
API_KEYS = {"groq": "GROQ_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}


def review_diff(diff_text: str, repo: Path, base: str | None = None, model: str = DEFAULT_MODEL) -> Review:
    changed = parse_diff(diff_text)
    if not (repo / "dbt_project.yml").is_file():
        raise ToolError(f"no dbt project at {repo} (dbt_project.yml not found); the review needs the code")
    _require_matching_checkout(repo, changed)
    context = ReviewContext(base=base, files_changed=len(changed))
    rule_findings, rules_skipped = _rule_findings(repo, changed)
    llm_findings, llm_skipped = _llm_findings(repo, changed, model)
    return Review(context=context, findings=rule_findings + llm_findings, skipped=rules_skipped + llm_skipped)


def _require_matching_checkout(project: Path, changed: list[ChangedFile]) -> None:
    """Every added line must be in the checkout, or findings would be missed or misplaced."""
    hint = "check out the branch the diff was made from"
    for file in changed:
        path = project / file.path
        if not path.is_file():
            raise ToolError(f"{file.path} is in the diff but not in the checkout; {hint}")
        lines = path.read_text(encoding="utf-8").splitlines()
        for number, text in file.added_lines.items():
            if number > len(lines) or lines[number - 1] != text:
                raise ToolError(f"{file.path}:{number} does not match the diff; {hint}")


def _rule_findings(project: Path, changed: list[ChangedFile]) -> tuple[list[Finding], list[Skipped]]:
    """Findings on the lines the change added; older problems are not this author's to fix."""
    findings, skipped = [], []
    for file in changed:
        if file.path.endswith(".sql"):
            sql = (project / file.path).read_text(encoding="utf-8")
            for rule in RULES:
                try:
                    found = rule.check(file.path, sql)
                except SqlglotError:  # a parse error, or a string or comment left open
                    skipped.append(Skipped(check_id=rule.check_id, reason=f"could not parse {file.path}"))
                    continue
                findings += [finding for finding in found if finding.line in file.added_lines]
    return findings, skipped


def _llm_findings(
    project: Path, changed: list[ChangedFile], model: str
) -> tuple[list[Finding], list[Skipped]]:
    """One LLM call per changed model that dbt's manifest knows, or the reason the check could not run."""
    manifest_path = project / "target" / "manifest.json"
    if not manifest_path.is_file():
        return [], [_llm_skipped("no target/manifest.json: run `dbt parse`")]
    key = API_KEYS.get(model.split(":")[0])
    if key and not os.environ.get(key):
        return [], [_llm_skipped(f"{key} is not set")]
    manifest = load_manifest(manifest_path)
    findings = []
    for file in changed:
        facts = manifest.model_at(file.path)
        if facts is not None:
            context = ModelContext(
                path=file.path,
                sql=(project / file.path).read_text(encoding="utf-8"),
                added_lines=list(file.added_lines),
                model=facts,
                inputs=[known for name in facts.reads if (known := manifest.model_named(name))],
            )
            try:
                findings += review_model(context, model)
            except AgentRunError as error:
                return [], [_llm_skipped(f"the model call failed: {type(error).__name__}")]
    return findings, []


def _llm_skipped(reason: str) -> Skipped:
    return Skipped(check_id="llm-review", reason=reason)
