"""Layer 1: Dagster Job definition — the orchestration UI entry point."""

from dagster import job

from runners.ops import pick_columns_op, pick_source_files_op, vlookup_op


@job(
    config={
        "ops": {
            "vlookup_op": {
                "config": {
                    "target_path": "data/output.csv",
                }
            }
        }
    }
)
def vlookup_pipeline():
    """Desktop VLOOKUP pipeline: pick files → pick columns → join → output CSV."""
    file_paths = pick_source_files_op()
    column_mapping = pick_columns_op(file_paths)
    vlookup_op(file_paths, column_mapping)
