# ETLai

A local, AI-assisted data transformation engine built on Dagster. Install it,
scaffold a project, and let Claude Code create new pipelines — from CSV
transformations to API ingestion.

## Install

```bash
pip install ETLai
```

Requires Python 3.10+ and Tkinter (ships with most Python installations).

## Quick start

```bash
etlai init ~/my-etl
cd ~/my-etl
etlai sync
etlai run
```

This starts a Dagster dev server at `http://localhost:3000`. Enable sensors in
the UI, then drop CSV files into `pipelines/<name>/inbox/`.

## Commands

| Command | Purpose |
|---------|---------|
| `etlai init <dir>` | Scaffold a new project with example pipelines |
| `etlai sync` | Validate manifests, create folders, prompt for `path: ask`, check env files |
| `etlai run` | Start the Dagster dev server |
| `etlai list` | Show all registered pipelines |

## How it works

Each pipeline is defined by a **manifest** (`pipelines/<name>/manifest.yaml`)
that wires together:

- **Atom** — a reusable, single-unit-of-work transformation
- **Form** — first-run Tkinter UI that collects config (or passthrough for no-UI)
- **Trigger** — what causes the pipeline to run (file sensor, cron schedule, or both)

```text
Trigger fires → load files (if any) → configure (form/config.json) → execute atom
                                        ├→ processed/ + output/     (success)
                                        └→ rejected/ + *.error.txt  (failure)
```

## Pipeline types

### File-based (CSV transformation)

Drop files into `inbox/`. Sensor detects stable files and triggers the pipeline.

```yaml
name: vlookup_rollnumber
atom: vlookup
form: vlookup_column_picker
min_files: 2
```

### API-based (data ingestion)

Fetch data from REST APIs on a schedule. No inbox files needed.

```yaml
name: fetch_hr_data
atom: hr_api_fetch
form: passthrough
min_files: 0
env_file: ~/.etlai/secrets.env
requires_env:
  - HR_API_TOKEN
trigger:
  rules:
    - type: schedule
      cron: "0 8 * * *"
```

### Composite (multi-step chains)

Chain multiple atoms. Output of each step feeds into the next.

```yaml
name: vlookup_then_groupby
min_files: 2
steps:
  - atom: vlookup
    form: vlookup_column_picker
  - atom: groupby
    form: groupby_picker
```

## Shipped atoms

| Atom | Description |
|------|-------------|
| `vlookup` | Left join two CSVs on specified columns with dtype validation |
| `groupby` | Group by column with count, sorted descending |
| `mock_generate` | Generate synthetic data from file headers using Faker |
| `api_fetch` | Generic REST API fetcher (JSON/XML/CSV, field mapping, env-based auth) |

## Shipped forms

| Form | Description |
|------|-------------|
| `vlookup_column_picker` | Join + output column multi-select with dtype validation |
| `groupby_picker` | Single column selection |
| `passthrough` | No UI — reads config.json and passes to atom |

## Key concepts

### Reference folder

`reference/` holds permanent data used across runs (lookup tables, previous API
snapshots). The framework passes reference file paths to atoms automatically.

### Custom data paths

`path: ask` in a manifest prompts the user (via folder picker) during `etlai sync`
to choose where data folders live. Each pipeline can have its own location.

### Credentials

API credentials live in env files outside the project (e.g. `~/.etlai/secrets.env`).
The framework loads them before atom execution. `etlai sync` validates required
vars are present without printing values.

### Adding pipelines with Claude Code

Open your project in Claude Code. The scaffolded `CLAUDE.md` teaches it to:
1. Create atoms (or reuse shipped ones)
2. Create forms (or use passthrough with pre-written config.json)
3. Write manifest.yaml
4. Run `etlai sync`

## Resolution order

- Atoms: `./atoms/<name>.py` → `etlai.atoms.<name>` (package)
- Forms: `./forms/<name>.py` → `etlai.forms.<name>` (package)

User files take precedence over shipped ones.

## Development

```bash
git clone <repo>
pip install -e .
etlai init /tmp/test-project
cd /tmp/test-project
etlai run
```
