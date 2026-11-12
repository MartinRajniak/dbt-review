"""The facts dbt knows about the project, read from the manifest.json that `dbt parse` writes."""

from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel


@dataclass(frozen=True)
class ModelFacts:
    name: str
    reads: list[str]  # names of the models, seeds and sources it selects from
    column_tests: dict[str, list[str]]  # column -> names of the tests on it, e.g. unique


class _DependsOn(BaseModel):
    nodes: list[str] = []


class _TestMetadata(BaseModel):
    name: str


class _Node(BaseModel):
    unique_id: str
    resource_type: str
    name: str
    original_file_path: str
    depends_on: _DependsOn = _DependsOn()
    attached_node: str | None = None
    column_name: str | None = None
    test_metadata: _TestMetadata | None = None


class _ManifestFile(BaseModel):
    nodes: dict[str, _Node]


class Manifest:
    def __init__(self, file: _ManifestFile) -> None:
        nodes = list(file.nodes.values())
        self._models = {_git_path(node): node for node in nodes if node.resource_type == "model"}
        self._tests = [node for node in nodes if node.resource_type == "test"]

    def model_at(self, path: str) -> ModelFacts | None:
        node = self._models.get(path)
        if node is None:
            return None
        return ModelFacts(
            name=node.name,
            reads=[_name(unique_id) for unique_id in node.depends_on.nodes],
            column_tests=self._column_tests(node.unique_id),
        )

    def _column_tests(self, model_id: str) -> dict[str, list[str]]:
        tests: dict[str, list[str]] = {}
        for test in self._tests:
            if test.attached_node == model_id and test.column_name and test.test_metadata:
                tests.setdefault(test.column_name, []).append(test.test_metadata.name)
        return tests


def load_manifest(path: Path) -> Manifest:
    return Manifest(_ManifestFile.model_validate_json(path.read_text(encoding="utf-8")))


def _name(unique_id: str) -> str:
    """`model.jaffle_shop.stg_orders` -> `stg_orders`"""
    return unique_id.rsplit(".", 1)[-1]


def _git_path(node: _Node) -> str:
    """dbt on Windows writes backslashes; git always uses forward slashes."""
    return node.original_file_path.replace("\\", "/")
