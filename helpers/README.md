# helpers/

Cross-cutting utilities for file management, config, UI, and notifications.

## `folders.py`

`PipelineFolders(pipeline_name)` — per-pipeline directory lifecycle:
- Properties: `.inbox`, `.staging`, `.processed`, `.rejected`, `.output`,
  `.config_path`
- Methods: `.ensure()`, `.move_to_staging()`, `.move_to_processed()`,
  `.move_to_rejected(file_paths, reason)`, `.list_inbox_files(pattern)`,
  `.output_path(filename)`

## `config_store.py`

Per-pipeline JSON config persistence:
- `load_config(folders)` — Returns saved dict or None
- `save_config(folders, config)` — Writes `config.json`
- `config_exists(folders)` — Boolean check

## `column_picker.py`

Tkinter dialog for VLOOKUP join/output column selection. Shows columns from
both files with dtypes, validates type compatibility on join columns, and
allows multi-select for output columns from both sides.

## `notifier.py`

Best-effort native OS notifications:
- macOS: AppleScript via `osascript`
- Windows: PowerShell toast API
- Opens output folder immediately on success (not a click action)
- Fails silently on unsupported platforms (Linux)

## `file_picker.py`

Standalone Tkinter file-selection helper. Not used by registered Dagster jobs
(the sensor provides files). Available for manual/ad-hoc use.

## `mock_generator.py`

Standalone two-file CLI mock-data generator. This is separate from the
registered `mock_generator` atom/job — it predates the Dagster integration.
