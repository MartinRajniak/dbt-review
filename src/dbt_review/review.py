from pathlib import Path

from dbt_review.checks import RULES
from dbt_review.diff import ChangedFile, parse_diff
from dbt_review.errors import ToolError
from dbt_review.llm_check import ModelContext, review_model
from dbt_review.manifest import load_manifest
from dbt_review.models import Finding, Review, ReviewContext

DEFAULT_MODEL = "groq:openai/gpt-oss-120b"


def review_diff(diff_text: str, repo: Path, base: str | None = None) -> Review:
    changed = parse_diff(diff_text)
    if not (repo / "dbt_project.yml").is_file():
        raise ToolError(f"no dbt project at {repo} (dbt_project.yml not found); the review needs the code")
    _require_matching_checkout(repo, changed)
    context = ReviewContext(base=base, files_changed=len(changed))
    findings = _rule_findings(repo, changed) + _llm_findings(repo, changed, DEFAULT_MODEL)
    return Review(context=context, findings=findings)


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


def _rule_findings(project: Path, changed: list[ChangedFile]) -> list[Finding]:
    """Findings on the lines the change added; older problems are not this author's to fix."""
    findings = []
    for file in changed:
        if file.path.endswith(".sql"):
            sql = (project / file.path).read_text(encoding="utf-8")
            found = [finding for rule in RULES for finding in rule.check(file.path, sql)]
            findings += [finding for finding in found if finding.line in file.added_lines]
    return findings


def _llm_findings(project: Path, changed: list[ChangedFile], model: str) -> list[Finding]:
    """One LLM call per changed model that dbt's manifest knows."""
    manifest_path = project / "target" / "manifest.json"
    if not manifest_path.is_file():
        return []
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
            findings += review_model(context, model)
    return findings
