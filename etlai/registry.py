"""Registry — scans pipeline manifests and dynamically builds Dagster Definitions."""

import importlib
import importlib.util
import json
import os
import sys
from pathlib import Path

import yaml
from dagster import Definitions, In, OpExecutionContext, Out, ScheduleDefinition, job, op

from etlai.helpers.config_store import config_exists, load_config, save_config
from etlai.helpers.env_loader import load_env_file
from etlai.helpers.folders import PipelineFolders
from etlai.helpers.notifier import notify
from etlai.sensors.hot_folder_sensor import build_hot_folder_sensor


def build_definitions() -> Definitions:
    """Scan all pipeline manifests and return a complete Dagster Definitions object."""
    project_root = Path(os.getcwd())
    config = _load_etlai_config(project_root)
    pipelines_root = Path(config.get("pipelines_root", "./pipelines"))
    if not pipelines_root.is_absolute():
        pipelines_root = project_root / pipelines_root

    jobs = []
    sensors = []
    schedules = []

    if not pipelines_root.is_dir():
        return Definitions(jobs=[], sensors=[], schedules=[])

    # First pass: build all jobs
    jobs_by_name = {}
    for manifest_path in sorted(pipelines_root.glob("*/manifest.yaml")):
        manifest = _load_manifest(manifest_path)
        if not manifest:
            continue

        pipeline_name = manifest["name"]

        if "steps" in manifest:
            j = _build_composite_job(manifest, project_root)
        else:
            j = _build_single_job(manifest, project_root)

        jobs.append(j)
        jobs_by_name[pipeline_name] = (j, manifest)

    # Second pass: build triggers from all manifests
    for manifest_path in sorted(pipelines_root.glob("*/manifest.yaml")):
        manifest = _load_manifest(manifest_path)
        if not manifest:
            continue

        pipeline_name = manifest["name"]
        job_obj = jobs_by_name[pipeline_name][0]

        sensors_for_pipeline, schedules_for_pipeline = _build_triggers(manifest, pipeline_name, job_obj)
        sensors.extend(sensors_for_pipeline)
        schedules.extend(schedules_for_pipeline)

    return Definitions(jobs=jobs, sensors=sensors, schedules=schedules)


def _build_triggers(manifest: dict, pipeline_name: str, job):
    """Build sensors and schedules from manifest trigger rules.

    Returns: (sensors_list, schedules_list)
    """
    sensors = []
    schedules = []

    trigger_config = manifest.get("trigger", {})
    rules = trigger_config.get("rules", [])

    if not rules:
        # Default: inbox file sensor (only if min_files > 0)
        s = _build_inbox_files_sensor(manifest, pipeline_name)
        if s:
            sensors.append(s)
    else:
        for rule in rules:
            rule_type = rule.get("type")
            if rule_type == "inbox_files":
                s = _build_inbox_files_sensor(manifest, pipeline_name, rule)
                if s:
                    sensors.append(s)
            elif rule_type == "schedule":
                sched = _build_schedule_definition(pipeline_name, job, rule)
                if sched:
                    schedules.append(sched)

    return sensors, schedules


def _build_inbox_files_sensor(manifest: dict, pipeline_name: str, rule: dict | None = None):
    """Build a hot-folder sensor for file-based triggers.

    If rule is None, builds default sensor from manifest min_files.
    Returns sensor or None if min_files is 0.
    """
    if rule:
        min_files = rule.get("min_files", manifest.get("min_files", 1))
        stability_seconds = rule.get("stability_seconds", 2)
    else:
        min_files = manifest.get("min_files", 1)
        stability_seconds = 2

    if min_files == 0:
        return None

    load_op_name = manifest.get("load_files_op_name", f"{pipeline_name}__load_files")
    return build_hot_folder_sensor(
        pipeline_name, pipeline_name,
        min_files=min_files,
        load_files_op_name=load_op_name,
        stability_seconds=stability_seconds,
    )


def _build_schedule_definition(pipeline_name: str, job, rule: dict):
    """Build a Dagster ScheduleDefinition from a schedule trigger rule."""
    cron = rule.get("cron", "0 * * * *")
    return ScheduleDefinition(
        name=f"{pipeline_name}_schedule",
        job=job,
        cron_schedule=cron,
    )


def _load_etlai_config(project_root: Path) -> dict:
    config_path = project_root / "etlai.yaml"
    if config_path.is_file():
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    return {}


def _load_manifest(path: Path) -> dict | None:
    try:
        with open(path) as f:
            return yaml.safe_load(f)
    except Exception:
        return None


def _resolve_atom(atom_name: str, project_root: Path):
    """Resolve atom module: user atoms/ first, then etlai.atoms."""
    user_atom_path = project_root / "atoms" / f"{atom_name}.py"
    if user_atom_path.is_file():
        spec = importlib.util.spec_from_file_location(f"user_atoms.{atom_name}", user_atom_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    return importlib.import_module(f"etlai.atoms.{atom_name}")


def _resolve_form(form_name: str, project_root: Path):
    """Resolve form module: user forms/ first, then etlai.forms."""
    user_form_path = project_root / "forms" / f"{form_name}.py"
    if user_form_path.is_file():
        spec = importlib.util.spec_from_file_location(f"user_forms.{form_name}", user_form_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    return importlib.import_module(f"etlai.forms.{form_name}")


def _execute_step(
    atom_module,
    form_module,
    folders: PipelineFolders,
    pipeline_name: str,
    step_index: int,
    file_paths: list[str],
    is_first: bool,
    is_last: bool,
    prev_output: str | None = None,
    context=None,
):
    """Shared logic for configuring and executing a single step (used by single and composite jobs).

    Returns the target_path (output location) for this step.
    """
    # Load full config (we'll update a step section)
    existing = load_config(folders)
    step_config_key = f"step_{step_index}" if step_index > 0 else None

    # For single-job pipelines, use the flat config. For composites, use step_N key.
    if is_first and step_index == 0:
        step_existing = existing
        step_config_key = None
    else:
        step_existing = existing.get(f"step_{step_index}") if existing else None

    reconfigure = bool(context.op_config.get("reconfigure")) if context else False
    if reconfigure:
        step_existing = None

    # Call form to get/update config
    try:
        if is_first:
            form_input = file_paths
        else:
            form_input = [prev_output]

        config = form_module.configure(form_input, step_existing)
    except Exception as e:
        folders.move_to_rejected(file_paths, f"Step {step_index} config cancelled: {e}")
        notify(title=f"{pipeline_name} — Failed", message=str(e)[:200])
        raise

    # Save updated config
    if step_config_key:
        full_config = existing or {}
        full_config[step_config_key] = config
        save_config(folders, full_config)
    else:
        save_config(folders, config)

    # Inject file paths or previous output
    if is_first:
        if file_paths and "left_file" not in config and "input_file" not in config and "input_files" not in config:
            if len(file_paths) >= 2:
                config["left_file"] = file_paths[0]
                config["right_file"] = file_paths[1]
            else:
                config["input_file"] = file_paths[0]
    else:
        if "input_file" not in config:
            config["input_file"] = prev_output

    # Inject reference files
    ref_files = folders.list_reference_files()
    if ref_files:
        config["reference_files"] = ref_files

    # Determine target path
    if is_last:
        target_path = folders.output_path("output.csv")
    else:
        target_path = folders.output_path(f"_intermediate_{step_index}.csv")
    config["target_path"] = target_path

    # Execute atom
    result = json.loads(atom_module.execute(json.dumps(config)))

    if result["success"]:
        if context:
            context.log.info(f"Step {step_index}: {result['message']}")

        # On last step, move files and notify
        if is_last:
            folders.move_to_processed(file_paths)
            notify(
                title=f"{pipeline_name} — Success",
                message=result["message"][:200],
                open_folder=folders.output,
            )
    else:
        folders.move_to_rejected(file_paths, f"Step {step_index} failed: {result['message']}")
        notify(title=f"{pipeline_name} — Failed", message=result["message"][:200])
        raise RuntimeError(result["message"])

    return target_path


def _build_single_job(manifest: dict, project_root: Path):
    """Build a Dagster job for a single-atom pipeline from its manifest."""
    pipeline_name = manifest["name"]
    atom_name = manifest["atom"]
    form_name = manifest.get("form", "passthrough")
    env_file = manifest.get("env_file")

    atom_module = _resolve_atom(atom_name, project_root)
    form_module = _resolve_form(form_name, project_root)
    folders = PipelineFolders(pipeline_name)

    min_files = manifest.get("min_files", 1)

    @op(name=f"{pipeline_name}__load_files", out={"file_paths": Out()})
    def _load_files(context: OpExecutionContext) -> list[str]:
        if env_file:
            try:
                load_env_file(env_file)
            except FileNotFoundError as e:
                raise RuntimeError(f"Env file missing for {pipeline_name}: {e}")

        import re
        config_paths = context.op_config.get("file_paths") if context.op_config else None
        if config_paths:
            return config_paths
        if min_files == 0:
            return []
        pattern = re.compile(r"^(.+)\.(csv|xlsx)$", re.IGNORECASE)
        paths = folders.list_inbox_files(pattern)
        if not paths:
            raise RuntimeError(f"No files found in {folders.inbox}")
        return paths

    @op(name=f"{pipeline_name}__execute", ins={"file_paths": In(list)})
    def _execute(context: OpExecutionContext, file_paths: list[str]) -> None:
        _execute_step(
            atom_module=atom_module,
            form_module=form_module,
            folders=folders,
            pipeline_name=pipeline_name,
            step_index=0,
            file_paths=file_paths,
            is_first=True,
            is_last=True,
            context=context,
        )

    @job(name=pipeline_name)
    def _job():
        file_paths = _load_files()
        _execute(file_paths)

    return _job


def _build_composite_job(manifest: dict, project_root: Path):
    """Build a Dagster job for a multi-step composite pipeline."""
    pipeline_name = manifest["name"]
    steps = manifest["steps"]
    min_files = manifest.get("min_files", 1)
    env_file = manifest.get("env_file")
    folders = PipelineFolders(pipeline_name)

    load_op_name = manifest.get("load_files_op_name", f"{pipeline_name}__load_files")

    @op(name=load_op_name, out={"file_paths": Out()})
    def _load_files(context: OpExecutionContext) -> list[str]:
        if env_file:
            try:
                load_env_file(env_file)
            except FileNotFoundError as e:
                raise RuntimeError(f"Env file missing for {pipeline_name}: {e}")

        import re
        config_paths = context.op_config.get("file_paths") if context.op_config else None
        if config_paths:
            return config_paths
        pattern = re.compile(r"^(.+)\.(csv|xlsx)$", re.IGNORECASE)
        paths = folders.list_inbox_files(pattern)
        if len(paths) < min_files:
            raise RuntimeError(f"Need {min_files} files in {folders.inbox}, found {len(paths)}.")
        return paths[:min_files]

    # Build step ops dynamically
    step_ops = []
    for i, step in enumerate(steps):
        atom_module = _resolve_atom(step["atom"], project_root)
        form_module = _resolve_form(step.get("form", "passthrough"), project_root)
        step_op_name = f"{pipeline_name}__step_{i}_{step['atom']}"
        is_first = (i == 0)
        is_last = (i == len(steps) - 1)

        def _make_step_op(atom_mod, form_mod, op_name, step_index, first, last):
            if first:
                @op(name=op_name, ins={"file_paths": In(list)}, out={"output_path": Out()})
                def _step(context: OpExecutionContext, file_paths: list[str]) -> str:
                    return _execute_step(
                        atom_module=atom_mod,
                        form_module=form_mod,
                        folders=folders,
                        pipeline_name=pipeline_name,
                        step_index=step_index,
                        file_paths=file_paths,
                        is_first=True,
                        is_last=last,
                        context=context,
                    )
            else:
                @op(name=op_name, ins={"file_paths": In(list), "prev_output": In(str)}, out={"output_path": Out()})
                def _step(context: OpExecutionContext, file_paths: list[str], prev_output: str) -> str:
                    return _execute_step(
                        atom_module=atom_mod,
                        form_module=form_mod,
                        folders=folders,
                        pipeline_name=pipeline_name,
                        step_index=step_index,
                        file_paths=file_paths,
                        is_first=False,
                        is_last=last,
                        prev_output=prev_output,
                        context=context,
                    )

            return _step

        step_ops.append(_make_step_op(atom_module, form_module, step_op_name, i, is_first, is_last))

    @job(name=pipeline_name)
    def _composite_job():
        file_paths = _load_files()
        prev_output = step_ops[0](file_paths)
        for step_op in step_ops[1:]:
            prev_output = step_op(file_paths, prev_output)

    return _composite_job
