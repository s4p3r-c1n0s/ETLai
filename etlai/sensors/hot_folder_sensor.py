"""Generic hot folder sensor factory with file stability check and sweeper."""

import os
import re
import time

from dagster import RunRequest, SensorEvaluationContext, SkipReason, sensor

from etlai.helpers.folders import PipelineFolders

FILE_PATTERN = re.compile(r"^(.+)\.(csv|xlsx)$", re.IGNORECASE)
STABILITY_WAIT_SECONDS = 2
REJECT_AFTER_SECONDS = 180


def _get_file_size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return -1


def _is_stable(path: str, wait_seconds: int = STABILITY_WAIT_SECONDS) -> bool:
    size_before = _get_file_size(path)
    if size_before <= 0:
        return False
    time.sleep(wait_seconds)
    size_after = _get_file_size(path)
    return size_before == size_after


def _sweep_rejected(folders: PipelineFolders, context: SensorEvaluationContext):
    if not os.path.isdir(folders.inbox):
        return
    now = time.time()
    for filename in os.listdir(folders.inbox):
        filepath = os.path.join(folders.inbox, filename)
        if not os.path.isfile(filepath):
            continue
        if FILE_PATTERN.match(filename):
            continue
        file_age = now - os.path.getmtime(filepath)
        if file_age < REJECT_AFTER_SECONDS:
            continue
        folders.move_to_rejected([filepath], f"File does not match expected pattern (*.csv or *.xlsx). Sat in inbox for {int(file_age)} seconds.")
        context.log.warning(f"Swept rejected file: {filename}")


def build_hot_folder_sensor(pipeline_name: str, job_name: str, min_files: int = 2, load_files_op_name: str | None = None, stability_seconds: int = STABILITY_WAIT_SECONDS):
    folders = PipelineFolders(pipeline_name)
    folders.ensure()
    _stability = stability_seconds
    sensor_name = f"{pipeline_name}_sensor"
    if load_files_op_name is None:
        load_files_op_name = f"{job_name}__load_files"

    @sensor(name=sensor_name, job_name=job_name, minimum_interval_seconds=30)
    def _sensor(context: SensorEvaluationContext):
        _sweep_rejected(folders, context)
        file_paths = folders.list_inbox_files(FILE_PATTERN)

        if len(file_paths) < min_files:
            yield SkipReason(f"Waiting for {min_files} files in inbox, have {len(file_paths)}.")
            return

        file_paths = file_paths[:min_files]

        for path in file_paths:
            if not _is_stable(path, _stability):
                yield SkipReason(f"File still being copied: {os.path.basename(path)}")
                return

        staged_paths = folders.move_to_staging(file_paths)
        context.log.info(f"Moved to staging: {staged_paths}")

        run_key = f"{int(time.time())}|{'|'.join(staged_paths)}"
        yield RunRequest(
            run_key=run_key,
            run_config={"ops": {load_files_op_name: {"config": {"file_paths": staged_paths}}}},
            tags={"source": sensor_name, "pipeline": pipeline_name},
        )

    return _sensor
