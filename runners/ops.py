"""Dagster @op adapters bridging UI layer to pure logic atoms."""

import json

from dagster import In, Nothing, OpExecutionContext, op

from helpers.file_picker import pick_files
from logic.vlookup_atom import vlookup


@op(out={"file_paths": None})
def pick_source_files_op(context: OpExecutionContext) -> list[str]:
    """Opens Tkinter file picker and returns selected file paths."""
    context.log.info("Opening file picker dialog...")
    paths = pick_files(count=2)
    context.log.info(f"Selected files: {paths}")
    context.add_output_metadata({"file_a": paths[0], "file_b": paths[1]})
    return paths


@op(ins={"file_paths": In(list)})
def vlookup_op(context: OpExecutionContext, file_paths: list[str]) -> None:
    """Wraps the vlookup atom with Dagster metadata and logging."""
    params = {
        "left_file": file_paths[0],
        "right_file": file_paths[1],
        "lookup_column": context.op_config.get("lookup_column", "id"),
        "output_columns": context.op_config.get("output_columns", []),
        "target_path": context.op_config.get("target_path", "data/output.csv"),
    }

    context.log.info(f"Running VLOOKUP with params: {json.dumps(params, indent=2)}")
    result_json = vlookup(json.dumps(params))
    result = json.loads(result_json)

    if result["success"]:
        context.log.info(result["message"])
        context.add_output_metadata({
            "row_count": result["row_count"],
            "output_file": params["target_path"],
            "status": "SUCCESS",
        })
    else:
        context.log.error(result["message"])
        raise RuntimeError(f"VLOOKUP failed: {result['message']}")
