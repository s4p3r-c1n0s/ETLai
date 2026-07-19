"""Pipeline factory — assembles Dagster jobs for business pipelines."""

from types import ModuleType
from typing import Callable

from dagster import In, OpExecutionContext, Out, job, op

from runners.atom_runner import build_execute_atom_op, build_load_files_op


def build_business_pipeline(
    pipeline_name: str,
    atom_module: ModuleType,
    atom_label: str,
    pre_process_op: Callable | None = None,
):
    """Build a complete Dagster job for a business pipeline.

    Args:
        pipeline_name: Folder name under pipelines/ and the Dagster job name.
        atom_module: Module with execute(params_json) -> result_json.
        atom_label: Human-readable label for notifications.
        pre_process_op: Optional op (file_paths -> params dict). If None, passthrough.
    """
    job_name = pipeline_name
    load_op = build_load_files_op(pipeline_name, f"{job_name}__load_files")
    exec_op = build_execute_atom_op(pipeline_name, atom_module, atom_label, f"{job_name}__execute")

    if pre_process_op is None:
        @op(name=f"{job_name}__passthrough", ins={"file_paths": In(list)}, out={"params": Out()})
        def pre_process_op(context: OpExecutionContext, file_paths: list[str]) -> dict:
            return {"input_file": file_paths[0]}

    @job(name=job_name)
    def _pipeline():
        file_paths = load_op()
        params = pre_process_op(file_paths)
        exec_op(file_paths, params)

    return _pipeline
