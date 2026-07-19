# Air-Gapped Desktop Automation Engine

A local Dagster application for folder-driven CSV transformations. Source files,
saved column choices, generated outputs, and Dagster run storage remain on the
machine.

## How it works

Each business pipeline has an inbox and a Dagster sensor. The sensor waits for
the required number of stable files, moves them to staging, and launches a job.
The job prepares atom parameters, executes the transformation, then moves source
files to `processed/` or `rejected/`.

An **atom** is a reusable transformation module with an
`execute(params_json) -> result_json` interface. Atoms are domain-agnostic —
they have no opinion on which column or business context. They do read and write
files, so they are not side-effect-free.

A **business pipeline** applies an atom to specific domain data with its own
folder lifecycle, sensor, and saved configuration.

## Registered jobs

| Job | Files needed | Description |
|-----|-------------|-------------|
| `vlookup_rollnumber` | 2 CSV | Left-join on user-chosen columns (first run: Tkinter picker, then saved) |
| `groupby_religion` | 1 CSV | Group by user-chosen column with counts, sorted descending |
| `mock_generator` | 1+ CSV | Generate synthetic data from file headers using Faker |
| `vlookup_then_groupby` | 2 CSV | Composite: VLOOKUP → GroupBy in a single job |

Each job has a same-named sensor. Sensors must be enabled in Dagster UI before
they process inbox files.

## Installation

Python 3.10+ required.

```bash
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
```

Tkinter must be available in the Python installation for first-run config.

## Run

```bash
DAGSTER_HOME="$(pwd)" dagster dev -m definitions
```

Open `http://localhost:3000`, enable the desired sensor, and place files in
`pipelines/<job-name>/inbox/`.

Manual execution without UI:

```bash
DAGSTER_HOME="$(pwd)" dagster job execute -m definitions -j vlookup_rollnumber
```

## Source modules

### Entry points

| File | Role |
|------|------|
| `definitions.py` | Registers all jobs and sensors with Dagster |
| `pipeline.py` | Builds single-atom business jobs via the factory |
| `runners/composite.py` | Defines the `vlookup_then_groupby` composite job |

### `logic/atoms/`

| Module | Purpose |
|--------|---------|
| `vlookup.py` | Left join two CSVs on specified columns with dtype validation |
| `groupby.py` | Group by one column, count, sort descending |
| `mock_generate.py` | Infer Faker generators from headers, write synthetic CSVs |

### `runners/`

| Module | Purpose |
|--------|---------|
| `pipeline_factory.py` | Assembles load → preprocess → execute Dagster jobs |
| `atom_runner.py` | Reusable load/execute ops with processed/rejected/notification lifecycle |
| `ops.py` | First-run config ops for VLOOKUP, GroupBy, and mock generator |
| `composite.py` | VLOOKUP → GroupBy chain with shared config |

### `sensors/`

| Module | Purpose |
|--------|---------|
| `hot_folder_sensor.py` | Per-pipeline sensor factory: stability check, staging, sweeper |

### `helpers/`

| Module | Purpose |
|--------|---------|
| `folders.py` | `PipelineFolders` class — per-pipeline directory lifecycle |
| `config_store.py` | JSON config read/write per pipeline |
| `column_picker.py` | Tkinter UI for VLOOKUP join/output column selection |
| `notifier.py` | macOS/Windows toast notifications, opens output folder on success |
| `file_picker.py` | Standalone Tkinter file dialog (not used by registered jobs) |
| `mock_generator.py` | Standalone CLI mock generator (separate from the atom/job) |

### Runtime data

- `pipelines/<job>/` — inbox, staging, processed, rejected, output, config.json
- `dagster.yaml` — SQLite storage configuration
- `dagster_storage/` — Dagster run history (persists across restarts)

## File and configuration lifecycle

```text
inbox/ → sensor stability check → staging/ → job runs
                                    ├→ processed/ + output/       (success)
                                    └→ rejected/ + *.error.txt    (failure)
```

Non-matching files (not `*.csv`/`*.xlsx`) are swept to `rejected/` after 3
minutes with an error description.

### Config init pattern

1. First run: pre-process op detects no `config.json` → shows Tkinter UI → saves
2. Future runs: loads config silently, fully automated
3. To reconfigure: delete `pipelines/<job>/config.json`

### Saved config fields

| Job | Fields |
|-----|--------|
| `vlookup_rollnumber` | `left_column`, `right_column`, `left_output_columns`, `right_output_columns` |
| `groupby_religion` | `group_column` |
| `vlookup_then_groupby` | All VLOOKUP fields + `group_column` |
| `mock_generator` | None |

## Important behavior

- Two-file jobs: lexical filename order determines left/right assignment.
- Atom failures and config cancellation move staged files to `rejected/`.
- Unexpected crashes may leave files in `staging/` — recover manually.
- Notifications are best-effort. Linux has no implementation.
- On success, macOS/Windows opens the output folder immediately (not a click
  action).

## Adding a new business pipeline

1. Create or reuse an atom in `logic/atoms/` with `execute(params_json) -> str`
2. Create a pre-process op in `runners/ops.py` (with config init pattern)
3. Register in `pipeline.py`:
   ```python
   my_pipeline = build_business_pipeline(
       pipeline_name="my_pipeline",
       atom_module=my_atom,
       atom_label="My Pipeline",
       pre_process_op=my_pre_process_op,
   )
   ```
4. Add sensor in `definitions.py`:
   ```python
   my_sensor = build_hot_folder_sensor("my_pipeline", "my_pipeline", min_files=1)
   ```
5. Folders are created automatically on import.

## Development status

No automated tests, lint, or pinned dependency versions. Validate by loading
definitions and exercising jobs with disposable CSV inputs.
