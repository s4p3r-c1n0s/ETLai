# CLAUDE.md

Guidance for coding agents working in this repository.

## Project overview

A local, folder-driven Dagster application for CSV transformations. Four
registered jobs: `vlookup_rollnumber`, `groupby_religion`, `mock_generator`,
and the composite `vlookup_then_groupby`.

The `package.json` dependency on Claude Code is optional tooling unrelated to the
Python/Dagster runtime.

## Common commands

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
DAGSTER_HOME="$(pwd)" dagster dev -m definitions
```

Execute one job without the web UI:

```bash
DAGSTER_HOME="$(pwd)" dagster job execute -m definitions -j <job-name>
```

No automated tests, formatter, or linter are currently configured.

## Architecture

- `definitions.py` registers all jobs and sensors.
- `pipeline.py` builds the three single-atom business jobs via the factory.
- `logic/atoms/` contains JSON-in/JSON-out file transformation modules (atoms).
- `runners/` assembles jobs, preprocesses parameters, executes atoms, and
  defines the composite job.
- `sensors/hot_folder_sensor.py` stages stable inbox files and launches jobs.
- `helpers/` owns folder lifecycle, saved config, Tkinter UIs, notifications,
  and standalone utilities.
- `pipelines/` contains runtime data (inbox/staging/processed/rejected/output
  and per-job config.json). These are not Python modules.

## Key conventions

- **Atoms** are domain-agnostic reusable transformations. They read/write files
  but have zero knowledge of which columns or business context they serve.
- **Business pipelines** apply atoms to specific domain data with their own
  folder lifecycle, sensor, and saved configuration.
- When given a new data task, separate the generic transformation (atom) from
  the domain-specific application (business pipeline).

## Important constraints

- Python 3.10+ required (type annotations use `X | None` syntax).
- Sensor accepts `.csv` and `.xlsx` filenames but atoms use CSV readers only.
  Use CSV for end-to-end processing.
- Two-file jobs assign left/right by lexical filename order.
- First-run config opens Tkinter — process needs desktop access.
- Saved configs and generated outputs are gitignored.
- Do not inspect or commit user CSV/Excel/output/processed/rejected/staging
  content or Dagster storage.
- Notifications are best-effort; Linux has no implementation.
- On success, macOS/Windows notifications open the output folder immediately
  (not a click action).
