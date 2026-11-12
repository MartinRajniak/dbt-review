import json
from pathlib import Path

from dbt_review.manifest import load_manifest


def model_node(name: str, path: str, reads: tuple[str, ...] = ()) -> dict:
    return {
        "unique_id": f"model.shop.{name}",
        "resource_type": "model",
        "name": name,
        "original_file_path": path,
        "depends_on": {"nodes": [f"model.shop.{other}" for other in reads]},
    }


def write_manifest(folder: Path, *nodes: dict) -> Path:
    path = folder / "manifest.json"
    path.write_text(json.dumps({"nodes": {node["unique_id"]: node for node in nodes}}))
    return path


def test_model_is_found_by_its_file_path_as_git_writes_it(tmp_path):
    on_windows = model_node("orders", r"models\marts\orders.sql", reads=("stg_orders", "stg_payments"))
    manifest = load_manifest(write_manifest(tmp_path, on_windows))

    model = manifest.model_at("models/marts/orders.sql")

    assert model is not None
    assert (model.name, model.reads) == ("orders", ["stg_orders", "stg_payments"])


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


def test_model_knows_which_tests_guard_each_column(tmp_path):
    manifest = load_manifest(
        write_manifest(
            tmp_path,
            model_node("orders", "models/orders.sql"),
            column_test("orders", "order_id", "unique"),
            column_test("orders", "order_id", "not_null"),
            column_test("orders", "status", "accepted_values"),
            column_test("customers", "customer_id", "unique"),
        )
    )

    model = manifest.model_at("models/orders.sql")

    assert model is not None
    assert model.column_tests == {"order_id": ["unique", "not_null"], "status": ["accepted_values"]}
