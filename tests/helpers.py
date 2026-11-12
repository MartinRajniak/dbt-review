"""Builders shared by the tests: a small manifest, and a fake LLM."""

import json
from pathlib import Path

from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel


def model_node(name: str, path: str, reads: tuple[str, ...] = ()) -> dict:
    return {
        "unique_id": f"model.shop.{name}",
        "resource_type": "model",
        "name": name,
        "original_file_path": path,
        "depends_on": {"nodes": [f"model.shop.{other}" for other in reads]},
    }


def column_test(model: str, column: str, test: str) -> dict:
    return {
        "unique_id": f"test.shop.{test}_{model}_{column}",
        "resource_type": "test",
        "name": f"{test}_{model}_{column}",
        "original_file_path": "models/schema.yml",
        "attached_node": f"model.shop.{model}",
        "column_name": column,
        "test_metadata": {"name": test},
    }


def write_manifest(folder: Path, *nodes: dict) -> Path:
    path = folder / "manifest.json"
    path.write_text(json.dumps({"nodes": {node["unique_id"]: node for node in nodes}}))
    return path


def model_answering(*findings: dict) -> FunctionModel:
    """A fake LLM that returns these findings whatever it is asked."""

    def answer(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {"findings": list(findings)})])

    return FunctionModel(answer)
