# sensors/

Event-driven Dagster sensors. Each business pipeline gets its own sensor watching its own inbox.

## Modules

### hot_folder_sensor.py

`build_hot_folder_sensor(pipeline_name, job_name, min_files)` — Factory:

- Watches `pipelines/<name>/inbox/` for files matching `*.csv`/`*.xlsx`
- File size stability check (2s interval) ensures files are fully copied
- Moves stable files to `pipelines/<name>/staging/` before triggering
- Sweeps unrecognized files to `pipelines/<name>/rejected/` after 3 minutes
- Passes staged file paths to the job via RunConfig
