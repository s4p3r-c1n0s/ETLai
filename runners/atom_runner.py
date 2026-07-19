"""Generic AtomRunner — handles file lifecycle, execution, and notifications for any business pipeline."""

import json
import os
from types import ModuleType

from dagster import In, OpExecutionContext, Out, op

from helpers.folders import PipelineFolders
from helpers.notifier import notify


def build_load_files_op(pipeline_name: str, name: str):
    """Factory: creates an op that loads files from config or inbox."""
    folders = PipelineFolders(pipeline_name)

    @op(name=name, out={"file_paths": Out()})
    def _load_files_op(context: OpExecutionContext) -> list[str]:
        config_paths = context.op_config.get("file_paths") if context.op_config else None

        if config_paths:
            paths = config_paths
            context.log.info(f"Files from config: {paths}")
        else:
            import re
            pattern = re.compile(r"^(.+)\.(csv|xlsx)$", re.IGNORECASE)
            paths = folders.list_inbox_files(pattern)
            if not paths:
                raise RuntimeError(f"No files found in {folders.inbox}")
            context.log.info(f"Inbox files: {paths}")

        context.add_output_metadata({"files": paths})
        return paths

    return _load_files_op


def build_execute_atom_op(pipeline_name: str, atom_module: ModuleType, atom_label: str, name: str):
    """Factory: creates an op that executes an atom, moves files to processed/rejected, and notifies."""
    folders = PipelineFolders(pipeline_name)

    @op(name=name, ins={"file_paths": In(list), "params": In(dict)})
    def _execute_atom_op(context: OpExecutionContext, file_paths: list[str], params: dict) -> None:
        if "target_path" not in params:
            default_output = folders.output_path("output.csv")
            params["target_path"] = context.op_config.get("target_path", default_output) if context.op_config else default_output
        target_path = params["target_path"]

        context.log.info(f"Running {atom_label} with params: {json.dumps(params, indent=2)}")

        try:
            result_json = atom_module.execute(json.dumps(params))
            result = json.loads(result_json)
        except Exception as e:
            folders.move_to_rejected(file_paths, f"Exception during {atom_label}: {e}")
            notify(title=f"{atom_label} — Failed", message=str(e)[:200])
            raise

        if result["success"]:
            context.log.info(result["message"])
            context.add_output_metadata({
                "row_count": result.get("row_count", 0),
                "output_file": target_path,
                "status": "SUCCESS",
            })

            folders.move_to_processed(file_paths)
            context.log.info(f"Moved source files to processed")

            notify(
                title=f"{atom_label} — Success",
                message=result["message"][:200],
                open_folder=os.path.dirname(os.path.abspath(target_path)),
            )
        else:
            folders.move_to_rejected(file_paths, f"{atom_label} failure: {result['message']}")
            notify(title=f"{atom_label} — Failed", message=result["message"][:200])
            raise RuntimeError(f"{atom_label} failed: {result['message']}")

    return _execute_atom_op
