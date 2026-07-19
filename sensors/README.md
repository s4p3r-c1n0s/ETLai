# sensors/

Event-driven Dagster sensors. Each business pipeline gets its own sensor
watching its own inbox.

## `hot_folder_sensor.py`

`build_hot_folder_sensor(pipeline_name, job_name, min_files,
load_files_op_name=None)`:

- Creates lifecycle folders on import.
- Evaluates at most once every 10 seconds.
- Selects the first `min_files` matching inbox paths in lexical order.
- Compares file size over two seconds before staging.
- Moves stable files to `pipelines/<name>/staging/`.
- Sends staged paths to the configured load op via `RunRequest`.
- Moves names that do not end in `.csv` or `.xlsx` to `rejected/` after three
  minutes.

The filename filter accepts Excel, but current downstream atoms use CSV readers.
Use CSV for end-to-end processing.

The `load_files_op_name` parameter defaults to `<job_name>__load_files` — only
override it for composite jobs that use custom op names (e.g. `vtg__load_files`).
