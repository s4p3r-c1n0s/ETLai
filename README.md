# ETLai

A local, AI-assisted data transformation engine built on Dagster. Describe a
pipeline in plain English and ETLai builds it with AI — then runs it
deterministically, with no AI at runtime — from CSV transformations to API
ingestion.

## Install

```bash
pip install ETLai
```

Requires Python 3.10+ and Tkinter (ships with most Python installations).

## Quick start

```bash
etlai init ~/my-etl
cd ~/my-etl

# Option A: Create a pipeline with the build system
etlai create "join sales data with product catalog and compute revenue"

# Option B: Manual pipeline creation (see ARCHITECTURE.md)
etlai sync
etlai run
```

This starts a Dagster dev server at `http://localhost:3000`. Sensors run by
default — drop CSV files into `pipelines/<name>/inbox/` to trigger a pipeline
(run `etlai sync` to re-enable any sensor you've stopped).

## Commands

| Command | Purpose |
|---------|---------|
| `etlai init <dir>` | Scaffold project (templates, workflow, agents, example pipelines) |
| `etlai create "request"` | Create pipeline via the build system (4 LLM workers + Code control plane) |
| `etlai sync` | Validate manifests, create folders, prompt `path: ask`, check env files |
| `etlai run` | Start Dagster dev server |
| `etlai list` | Show registered pipelines with atoms and min_files |

## How it works

Each pipeline is defined by a **manifest** (`pipelines/<name>/manifest.yaml`)
that wires together:

- **Atoms** — reusable, single-unit-of-work transformations (domain-agnostic)
- **Triggers** — what causes the pipeline to run (file sensor, cron, or both)
- **Config** — business logic (column names, thresholds, expressions) in config.json

```text
Trigger fires → load files → read config.json → execute steps
                               ├→ processed/ + output/     (success)
                               └→ rejected/ + *.error.txt  (failure)
```

## Pipeline types

### Single atom (file-based)

Drop files into `inbox/`. Sensor detects stable files and triggers the pipeline.

```yaml
name: vlookup_rollnumber
atom: vlookup
min_files: 2
inputs_map:
  - param: left_file
  - param: right_file
```

Its parameters live in `pipelines/vlookup_rollnumber/config.json`.

### API-based (data ingestion)

Fetch data from REST APIs on a schedule. No inbox files needed.

```yaml
name: fetch_hr_data
atom: api_fetch
min_files: 0
env_file: ~/.etlai/secrets.env
requires_env: [HR_API_TOKEN]
trigger:
  rules:
    - type: schedule
      cron: "0 8 * * *"
```

### Composite (multi-step chains)

Chain multiple atoms with reference file injection and branching.

```yaml
name: sales_reconciliation
min_files: 1
inputs:
  - name: sales_data
    role: transient
    description: "Weekly sales CSV"
steps:
  - atom: vlookup                # step 0: join sales + catalog
    inputs_map:
      - param: left_file
      - param: right_file
        source: reference        # permanent lookup matched by pattern
        pattern: "catalog.csv"
  - atom: computed_column        # step 1: compute revenue
    inputs_map:
      - param: input_file
        source: prev_output
  - atom: group_aggregate        # step 2: aggregate by category
    input_from: 1                # reads step 1, not step 2 (branching)
    inputs_map:
      - param: input_file
        source: prev_output
  - atom: rename_columns         # final step: rehydrate column names
    inputs_map:
      - param: input_file
        source: prev_output
trigger:
  rules:
    - type: inbox_files
      min_files: 1
```

## Shipped atoms (10)

| Atom | Operation |
|------|-----------|
| `vlookup` | Left join two CSVs on a key column |
| `computed_column` | New column from expression (e.g. `price * qty`) |
| `group_aggregate` | Group + sum/mean/min/max/count aggregations |
| `filter_rows` | Keep rows matching a condition |
| `flag_rows` | Add boolean column from condition (keeps all rows) |
| `rename_columns` | Rename columns via mapping |
| `sort_rows` | Sort by one or more columns |
| `groupby` | Group by column with count |
| `api_fetch` | HTTP fetch → CSV (JSON/XML/CSV response parsing) |
| `mock_generate` | Generate synthetic data from CSV headers → single XLSX |

## Creating pipelines with AI

`etlai create` drives a build system of four LLM workers under a deterministic
**Code control plane**, with gate validators between each phase:

| Worker | Role |
|-------|------|
| Business Analyst | Drafts the requirements graph; proposes questions (user Q&A mediated by the control plane) |
| Separator | Strips domain terms, produces a generic operation graph |
| Atom Smith | Matches/creates atoms (firewalled from business data) |
| Assembler | Wires manifest + config with real business values |

The **control plane is Code** (`orchestrator.py`), not an LLM agent — it routes
tasks, owns the user channel, and enforces gates and the firewall.

The **firewall** physically hides `business_mapping.json` from Atom Smith,
ensuring atoms remain domain-agnostic by construction.

See [ARCHITECTURE.md](ARCHITECTURE.md) for full details on the build system.

## Key concepts

### reference (permanent lookup files)

Permanent lookup files in `reference/` bind to a step param via `source: reference`:
```yaml
steps:
  - atom: vlookup
    inputs_map:
      - param: left_file
      - param: right_file
        source: reference
        pattern: "catalog.csv"
```

### input_from (non-linear step routing)

Steps read the previous step's output by default. Use `input_from` to branch:
```yaml
steps:
  - atom: computed_column     # step 0
  - atom: rename_columns      # step 1 (reads step 0)
  - atom: group_aggregate     # step 2 reads step 0, NOT step 1
    input_from: 0
```

### config.json

Every step reads its `step_N` key (including `step_0`):
```json
{
  "step_0": {"left_column": "sku", "right_column": "sku"},
  "step_1": {"expression": "price * qty", "output_column": "revenue"},
  "step_2": {"mapping": {"revenue": "Total Revenue"}}
}
```

### Credentials

API credentials live in env files outside the project (e.g. `~/.etlai/secrets.env`).
`etlai sync` validates required vars are present without printing values.

## Resolution order

- Atoms: `./atoms/<name>.py` → `etlai.atoms.<name>` (package)

User atoms take precedence over shipped ones.

## Development

```bash
git clone <repo>
pip install -e ".[dev]"
pytest --cov=etlai
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for workflow, [ARCHITECTURE.md](ARCHITECTURE.md)
for internals, and [TESTS.md](TESTS.md) for testing guide.
