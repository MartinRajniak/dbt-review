"""The facts dbt knows about the project, read from the manifest.json that `dbt parse` writes."""

from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel


@dataclass(frozen=True)
class ModelFacts:
    name: str
    reads: list[str]  # names of the models, seeds and sources it selects from


class _DependsOn(BaseModel):
    nodes: list[str] = []


class _Node(BaseModel):
    resource_type: str
    name: str
    original_file_path: str
    depends_on: _DependsOn = _DependsOn()


class _ManifestFile(BaseModel):
    nodes: dict[str, _Node]


class Manifest:
    def __init__(self, file: _ManifestFile) -> None:
        self._models = {
            # dbt on Windows writes backslashes; git paths always use forward slashes
            node.original_file_path.replace("\\", "/"): node
            for node in file.nodes.values()
            if node.resource_type == "model"
        }

    def model_at(self, path: str) -> ModelFacts | None:
        node = self._models.get(path)
        if node is None:
            return None
        return ModelFacts(name=node.name, reads=[_name(unique_id) for unique_id in node.depends_on.nodes])


def load_manifest(path: Path) -> Manifest:
    return Manifest(_ManifestFile.model_validate_json(path.read_text(encoding="utf-8")))


def _name(unique_id: str) -> str:
    """`model.jaffle_shop.stg_orders` -> `stg_orders`"""
    return unique_id.rsplit(".", 1)[-1]
