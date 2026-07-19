# Air-Gapped Desktop Automation Engine

A modular, factory-based Dagster system for local data operations. No data leaves your machine.

## Core Concepts

| Term | Meaning |
|------|---------|
| **Atom** | A generic, reusable pure function (JSON-in, JSON-out). No domain knowledge. E.g. "vlookup", "groupby". |
| **Business Pipeline** | An atom applied to specific domain data with its own folder lifecycle, config, and sensor. E.g. "vlookup on roll number", "groupby religion". |
| **Config Init** | First-run UI step that captures user selections (columns, params) and saves them. Subsequent runs are fully automated. |

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  definitions.py              Dagster entry point              │
│  pipeline.py                 Business pipeline definitions    │
├──────────────────────────────────────────────────────────────┤
│  logic/atoms/                Core atoms (generic, reusable)   │
│  ├── vlookup.py             Left-join atom                   │
│  └── groupby.py             Group-by-count atom              │
├──────────────────────────────────────────────────────────────┤
│  runners/                    Pipeline assembly infrastructure │
│  ├── pipeline_factory.py    Job builder                      │
│  ├── atom_runner.py         File lifecycle + notifications   │
│  └── ops.py                 Business-specific pre-process ops│
├──────────────────────────────────────────────────────────────┤
│  sensors/                    Hot folder sensors               │
│  └── hot_folder_sensor.py   Stability check + sweeper        │
├──────────────────────────────────────────────────────────────┤
│  helpers/                    Cross-cutting utilities          │
│  ├── folders.py             Per-pipeline folder lifecycle    │
│  ├── config_store.py        Per-pipeline config persistence  │
│  ├── column_picker.py       Tkinter column selection UI      │
│  ├── notifier.py            Cross-platform OS notifications  │
│  └── mock_generator.py      Synthetic test data              │
├──────────────────────────────────────────────────────────────┤
│  pipelines/                  Business pipeline folders        │
│  ├── vlookup_rollnumber/    VLOOKUP by roll number           │
│  │   ├── inbox/  staging/  processed/  rejected/  output/   │
│  │   └── config.json                                         │
│  └── groupby_religion/      GroupBy religion                 │
│      ├── inbox/  staging/  processed/  rejected/  output/   │
│      └── config.json                                         │
└──────────────────────────────────────────────────────────────┘
```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

### Start Dagster

```bash
DAGSTER_HOME=$(pwd) dagster dev -m definitions
```

Open **http://localhost:3000**. Enable sensors for the pipelines you want.

### Business Pipelines

#### VLOOKUP by Roll Number

Drop 2 CSV/Excel files into `pipelines/vlookup_rollnumber/inbox/`.

- **First run:** Tkinter column picker appears. Select join columns (roll number) and output columns. Config is saved.
- **Subsequent runs:** Fully automated — no UI, uses saved config.
- **Reconfigure:** Delete `pipelines/vlookup_rollnumber/config.json` or set `reconfigure: true` in RunConfig.

#### GroupBy Religion

Drop 1 CSV/Excel file into `pipelines/groupby_religion/inbox/`.

- **First run:** Tkinter picker for the group-by column. Config is saved.
- **Subsequent runs:** Fully automated.
- **Output:** CSV with each unique value and its count, sorted descending.

### Manual Trigger via Launchpad

```yaml
ops:
  vlookup_rollnumber__load_files:
    config:
      file_paths:
        - /path/to/left.csv
        - /path/to/right.csv
  vlookup_rollnumber__pre_process:
    config:
      reconfigure: true    # force UI again
```

### CLI

```bash
DAGSTER_HOME=$(pwd) dagster job execute -m definitions -j vlookup_rollnumber
```

## File Lifecycle

```
inbox/ → [sensor detects stable files] → staging/ → [pipeline runs]
    → processed/ (on success, + output written to output/)
    → rejected/  (on failure, with .error.txt reason)
```

Files that don't match `*.csv`/`*.xlsx` are swept to `rejected/` after 3 minutes.

## Config Init Pattern

1. First run: pre-process op detects no `config.json` → shows Tkinter UI → saves selections
2. Future runs: loads config silently, no user interaction needed
3. To reconfigure: delete `config.json` or pass `reconfigure: true` in op config

## Adding a New Business Pipeline

1. **Choose or create an atom** in `logic/atoms/` (pure function, no domain knowledge)
2. **Create a pre-process op** in `runners/ops.py` (with config init pattern)
3. **Register in `pipeline.py`:**
   ```python
   my_pipeline = build_business_pipeline(
       pipeline_name="my_pipeline",
       atom_module=my_atom,
       atom_label="My Pipeline",
       pre_process_op=my_pre_process_op,
   )
   ```
4. **Add sensor in `definitions.py`:**
   ```python
   my_sensor = build_hot_folder_sensor("my_pipeline", "my_pipeline", min_files=1)
   ```
5. Folders `pipelines/my_pipeline/{inbox,staging,processed,rejected,output}/` are created automatically.

## Notifications

Native OS toast on success/failure. On success, opens the output folder:
- **macOS** — AppleScript + `open`
- **Windows** — PowerShell toast + `explorer.exe`

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Sensor not triggering | Enable it in UI; check correct inbox folder |
| Config UI appears every run | Verify `config.json` was saved in pipeline folder |
| Files stuck in staging | Pipeline may have crashed — check Dagster logs, move files manually |
| Wrong columns in output | Delete `config.json`, re-run to reconfigure |
