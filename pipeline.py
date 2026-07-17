"""Layer 1: Dagster Job definition — the orchestration UI entry point."""

from dagster import job

from runners.ops import pick_source_files_op, vlookup_op


@job(
    config={
        "ops": {
            "vlookup_op": {
                "config": {
                    "lookup_column": "id",
                    "output_columns": [],
                    "target_path": "data/output.csv",
                }
            }
        }
    }
)
def vlookup_pipeline():
    """Desktop VLOOKUP pipeline: pick files → join → output CSV."""
    file_paths = pick_source_files_op()
    vlookup_op(file_paths)
