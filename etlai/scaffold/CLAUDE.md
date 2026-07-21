# CLAUDE.md — ETLai Project

This is an ETLai project. It uses a local Dagster instance to run CSV transformation
pipelines triggered by hot folder sensors.

## How it works

1. User drops CSV files into `pipelines/<name>/inbox/`
2. A sensor detects stable files, moves them to `staging/`, triggers a job
3. The job runs: load files → configure (form UI on first run) → execute atom → notify
4. On success: files → `processed/`, output → `output/`
5. On failure: files → `rejected/` with error reason

## Creating a new pipeline

When the user asks for a new data transformation, create up to 4 things:

### 1. Atom (if no existing atom fits)

Location: `atoms/<name>.py`

Contract:
```python
def execute(params_json: str) -> str:
    """
    Accepts JSON params, performs file I/O transformation, returns JSON result.
    Must return: {"success": bool, "message": str, ...optional extra fields}
    """
```

Rules:
- Domain-agnostic — no business knowledge
- Reads input CSV(s), writes output CSV to `target_path`
- All params come from JSON (file paths, column names, options)
- Catch exceptions and return `{"success": False, "message": "..."}`
- No Dagster imports — atoms are pure Python + pandas/duckdb

### 2. Form (always, unless passthrough)

Location: `forms/<name>.py`

Contract:
```python
def configure(file_paths: list[str], existing_config: dict | None) -> dict:
    """
    First run: show Tkinter UI, return config dict.
    Subsequent runs: return existing_config if valid.
    Raise RuntimeError to reject files.
    """
```

Rules:
- If `existing_config` is not None and valid for these files, return it immediately (no UI)
- The returned dict keys must match what the atom expects in `params_json`
- Do NOT include `target_path` or file paths in the returned dict — the framework injects those
- Use Tkinter for the UI — must work on macOS and Windows
- Set `root.attributes("-topmost", True)` so the dialog appears above Dagster

### 3. Manifest (always)

Location: `pipelines/<name>/manifest.yaml`

Single-atom pipeline:
```yaml
name: my_pipeline
atom: my_atom           # resolves: atoms/ → etlai.atoms
form: my_form           # resolves: forms/ → etlai.forms
min_files: 1            # how many input files the sensor waits for
path: ask               # prompts user to pick data folder during etlai sync
```

The `path` field controls where inbox/staging/processed/rejected/output folders live:
- `path: ask` — `etlai sync` opens a folder picker, writes the chosen path back into the manifest
- `path: /absolute/path` — uses that path directly
- Omitted — defaults to `pipelines/<name>/` inside the project

Composite pipeline (chains multiple atoms):
```yaml
name: my_composite
min_files: 2
load_files_op_name: my_composite__load_files
steps:
  - atom: first_atom
    form: first_form
  - atom: second_atom
    form: second_form
```

In composites, the output of step N becomes the input file for step N+1's form and atom.

### 4. Helper (only if needed)

Location: `helpers/<name>.py` — for shared utilities used by multiple forms or atoms.

## After creating files

Run `etlai sync` to validate manifests and create missing folders.
Then `etlai run` to start Dagster with the new pipeline active.

## Shipped atoms (available without creating new ones)

### vlookup
Left join between two CSV files on specified columns.
```json
{"left_file", "right_file", "left_column", "right_column",
 "left_output_columns": [], "right_output_columns": [], "target_path"}
```

### groupby
Group by a column with count aggregation.
```json
{"input_file", "group_column", "target_path"}
```

### mock_generate
Generate synthetic CSV from source file headers using Faker.
```json
{"input_files": [], "target_path": "dir/", "rows": 20}
```

## Shipped forms (available without creating new ones)

- `vlookup_column_picker` — join column + output column multi-select with dtype validation
- `groupby_picker` — single column selection for group-by
- `passthrough` — no UI, reads config.json and passes it to the atom

## No-UI pipelines

For pipelines that don't need user interaction, use `form: passthrough` and pre-write
the `config.json` in the pipeline's data folder:

```json
// pipelines/groupby_religion/config.json
{"group_column": "religion"}
```

The passthrough form reads this and passes it as atom params. This is how Claude Code
sets business logic without requiring a Tkinter UI — just write the config file directly.

## Config persistence

- Saved to `pipelines/<name>/config.json` inside the **project directory** (not the data path)
- Even when `path` points elsewhere, config stays in the project where Claude Code can read/write it
- Delete `config.json` to force reconfiguration
- Composite pipelines store per-step config as `{"step_0": {...}, "step_1": {...}}`

## Resolution order

- Atoms: `./atoms/<name>.py` → `etlai.atoms.<name>` (installed package)
- Forms: `./forms/<name>.py` → `etlai.forms.<name>` (installed package)

User-created files take precedence over shipped ones.

## Reference folder

Each pipeline has a `reference/` folder for permanent supporting data:
- Lookup tables used on every run
- Previous API fetch results (for diff comparison)
- Any file the atom needs across multiple runs

Reference files are passed to the atom as `reference_files: [paths]` in params.
Unlike inbox files, they are never moved or consumed.

## Trigger rules

Triggers determine when a pipeline runs. Defined in manifest under `trigger.rules`:

```yaml
trigger:
  rules:
    - type: inbox_files          # watch for new files (default if no trigger specified)
      min_files: 2
      stability_seconds: 2
    - type: schedule             # cron-based trigger
      cron: "0 8 * * *"         # daily at 8am
```

Multiple rules can coexist — a pipeline can trigger on both new files AND a schedule.
If no `trigger` block is specified, defaults to `inbox_files` with the manifest's `min_files`.

Available trigger types:
- `inbox_files` — hot folder sensor (today's default)
- `schedule` — cron expression via Dagster schedule

## Constraints

- Python 3.10+ required
- CSV files only for processing (sensors accept .xlsx filenames but atoms use CSV readers)
- Two-file jobs assign left/right by lexical filename order
- First-run config opens Tkinter — process needs desktop access
- Do not commit `pipelines/*/inbox/`, `staging/`, `processed/`, `rejected/`, `output/`, or `config.json`
- Reference files are permanent — do not gitignore `reference/` if they should be version-controlled

## Common commands

```bash
etlai init .          # scaffold project (already done)
etlai sync            # validate manifests, create folders
etlai run             # start Dagster dev server
etlai list            # show registered pipelines
```

## API pipelines

For pipelines that ingest data from APIs instead of (or in addition to) inbox files:

### Manifest with env_file

```yaml
name: fetch_hr_attendance
atom: hr_attendance_fetch       # custom atom per API
form: passthrough
min_files: 0
env_file: ~/.etlai/secrets.env  # absolute path, outside project
requires_env:                   # validated during etlai sync
  - HR_API_TOKEN
  - HR_API_BASE_URL
trigger:
  rules:
    - type: schedule
      cron: "0 8 * * *"
```

### How env vars work

1. User creates `~/.etlai/secrets.env` (never committed, never in project):
   ```
   HR_API_TOKEN=sk-xxxxx
   HR_API_BASE_URL=https://hr.company.com/api/v2
   ```

2. Framework loads env file before atom execution — vars available via `os.environ`

3. Atom reads credentials from environment, never from config:
   ```python
   token = os.environ["HR_API_TOKEN"]
   base_url = os.environ["HR_API_BASE_URL"]
   ```

### Writing API atoms

Each API gets its own atom because auth, pagination, parsing, and error handling
differ per API. The atom handles:
- HTTP client logic (auth headers, request signing)
- Response parsing (JSON/XML/CSV/NDJSON)
- Pagination (cursor, offset, link header)
- Rate limiting / retries
- Writing output CSV to `target_path`

The atom does NOT contain:
- Actual endpoint URLs (comes from config.json)
- Field names or business logic (comes from config.json)
- Credentials (comes from os.environ via env_file)

### config.json for API pipelines (pre-written by Claude Code)

```json
{
  "endpoint_path": "/attendance",
  "params": {"department": "engineering"},
  "data_path": "results.items",
  "field_mapping": {
    "employee": "name",
    "date": "attendance_date",
    "status": "status_code"
  }
}
```

### Shipped atom: api_fetch

A generic single-request fetcher for simple APIs. For complex APIs (OAuth2,
pagination, request signing), create a custom atom.

Params for api_fetch:
```json
{
  "endpoint": "https://api.example.com/data",
  "method": "GET",
  "headers": {"Authorization": "Bearer ${API_TOKEN}"},
  "params": {"limit": 100},
  "response_format": "json",
  "data_path": "results.items",
  "field_mapping": {"output_col": "response.nested.field"},
  "target_path": "..."
}
```

Note: `${VAR_NAME}` in headers is resolved from os.environ at runtime.

### Example: creating a custom API pipeline

1. Create `atoms/salesforce_fetch.py`:
```python
import csv, json, os
from urllib.request import Request, urlopen

def execute(params_json: str) -> str:
    params = json.loads(params_json)
    token = os.environ["SF_TOKEN"]
    base_url = os.environ["SF_BASE_URL"]

    # Custom OAuth2 refresh, SOQL query, pagination...
    # Write results to params["target_path"]
    return json.dumps({"success": True, "row_count": N, "message": "..."})
```

2. Pre-write `pipelines/sf_contacts/config.json`:
```json
{"query": "SELECT Name, Email FROM Contact WHERE Active__c = true"}
```

3. Create `pipelines/sf_contacts/manifest.yaml`:
```yaml
name: sf_contacts
atom: salesforce_fetch
form: passthrough
min_files: 0
env_file: ~/.etlai/secrets.env
requires_env:
  - SF_TOKEN
  - SF_BASE_URL
trigger:
  rules:
    - type: schedule
      cron: "0 6 * * 1"
```

4. User adds to `~/.etlai/secrets.env`:
```
SF_TOKEN=00D...
SF_BASE_URL=https://myorg.salesforce.com
```

5. Run `etlai sync` then `etlai run`.

## Example: adding a "filter rows" pipeline

1. Create `atoms/filter_rows.py`:
```python
import json
import pandas as pd

def execute(params_json: str) -> str:
    params = json.loads(params_json)
    df = pd.read_csv(params["input_file"])
    col = params["filter_column"]
    op = params["operator"]
    val = params["threshold"]
    # ... apply filter ...
    df_filtered.to_csv(params["target_path"], index=False)
    return json.dumps({"success": True, "row_count": len(df_filtered), "message": "..."})
```

2. Create `forms/filter_config.py`:
```python
def configure(file_paths, existing_config):
    if existing_config:
        return existing_config
    # Show Tkinter with column dropdown, operator dropdown, threshold input
    # Return: {"filter_column": "age", "operator": ">", "threshold": 18}
```

3. Create `pipelines/filter_by_age/manifest.yaml`:
```yaml
name: filter_by_age
atom: filter_rows
form: filter_config
min_files: 1
```

4. Run `etlai sync` then `etlai run`.
