# helpers/

Cross-cutting utilities for UI, file management, config, and platform abstractions.

## Modules

### folders.py

`PipelineFolders(pipeline_name)` — Manages per-pipeline folder lifecycle:
- `.inbox`, `.staging`, `.processed`, `.rejected`, `.output`, `.config_path`
- `.move_to_staging()`, `.move_to_processed()`, `.move_to_rejected(reason)`
- `.list_inbox_files(pattern)`, `.output_path(filename)`, `.ensure()`

### config_store.py

Per-pipeline JSON config persistence:
- `load_config(folders)` — Returns saved dict or None
- `save_config(folders, config)` — Writes config.json
- `config_exists(folders)` — Check if config exists

### column_picker.py

Tkinter dialog for selecting join and output columns with dtype validation.

### notifier.py

Cross-platform OS notifications (macOS: osascript, Windows: PowerShell). Opens output folder on success.

### file_picker.py

Tkinter file dialog for manual file selection.

### mock_generator.py

Generates fake CSV data from real file headers using Faker.
