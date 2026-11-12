from helpers import column_test, model_node, write_manifest

from dbt_review.manifest import load_manifest


def test_model_is_found_by_its_file_path_as_git_writes_it(tmp_path):
    on_windows = model_node("orders", r"models\marts\orders.sql", reads=("stg_orders", "stg_payments"))
    manifest = load_manifest(write_manifest(tmp_path, on_windows))

    model = manifest.model_at("models/marts/orders.sql")

    assert model is not None
    assert (model.name, model.reads) == ("orders", ["stg_orders", "stg_payments"])


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


def test_model_is_found_by_name_and_other_names_are_unknown(tmp_path):
    manifest = load_manifest(
        write_manifest(tmp_path, model_node("stg_orders", "models/staging/stg_orders.sql"))
    )

    found = manifest.model_named("stg_orders")

    assert found is not None and found.name == "stg_orders"
    assert manifest.model_named("raw_orders") is None
