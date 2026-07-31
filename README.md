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

# Option A: Create a pipeline with the 5-agent system
etlai create "join sales data with product catalog and compute revenue"

# Option B: Manual pipeline creation (see ARCHITECTURE.md)
etlai sync
etlai run
```

This starts a Dagster dev server at `http://localhost:3000`. Enable sensors in
the UI, then drop CSV files into `pipelines/<name>/inbox/`.

## Commands

| Command | Purpose |
|---------|---------|
| `etlai init <dir>` | Scaffold project (templates, workflow, agents, example pipelines) |
| `etlai create "request"` | Create pipeline via 5-agent system with gate validation |
| `etlai sync` | Validate manifests, create folders, prompt `path: ask`, check env files |
| `etlai run` | Start Dagster dev server |
| `etlai list` | Show registered pipelines with atoms and min_files |

## How it works

Each pipeline is defined by a **manifest** (`pipelines/<name>/manifest.yaml`)
that wires together:

- **Atoms** — reusable, single-unit-of-work transformations (domain-agnostic)
- **Forms** — first-run config UI or `passthrough` (no-UI, reads config.json)
- **Triggers** — what causes the pipeline to run (file sensor, cron, or both)
- **Config** — business logic (column names, thresholds, expressions) in config.json

```text
Trigger fires → load files → configure (form/config.json) → execute steps
                               ├→ processed/ + output/     (success)
                               └→ rejected/ + *.error.txt  (failure)
```

## Pipeline types

### Single atom (file-based)

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
atom: api_fetch
form: passthrough
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
  - name: product_catalog
    role: reference
    pattern: "catalog.csv"
    inject_as:
      step: 0
      param: right_file
steps:
  - atom: vlookup                # step 0: join sales + catalog
  - atom: computed_column        # step 1: compute revenue
  - atom: group_aggregate        # step 2: aggregate by category
    input_from: 1                # reads step 1, not step 2 (branching)
  - atom: rename_columns         # final step: rehydrate column names
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
| `mock_generate` | Generate synthetic data from CSV headers |

## Shipped forms

| Form | Description |
|------|-------------|
| `passthrough` | No UI — reads config.json and passes to atom |
| `vlookup_column_picker` | Join column multi-select (Tkinter) |
| `groupby_picker` | Single column selection (Tkinter) |

## Creating pipelines with AI

The 5-agent system (`etlai create`) orchestrates pipeline creation through 7
phases with deterministic gate validators between each:

| Agent | Role |
|-------|------|
| Business Analyst | Loops with user to capture pipeline requirements |
| Separator | Strips domain terms, produces generic operation graph |
| Atom Smith | Matches/creates atoms (firewalled from business data) |
| Assembler | Wires manifest + config with real business values |

The **firewall** physically hides `business_mapping.json` from Atom Smith,
ensuring atoms remain domain-agnostic by construction.

See [ARCHITECTURE.md](ARCHITECTURE.md) for full details on the agent system.

## Key concepts

### inject_as (reference file injection)

Reference files in `reference/` are injected into specific atom params at runtime:
```yaml
inputs:
  - name: catalog
    role: reference
    pattern: "catalog.csv"
    inject_as: {step: 0, param: right_file}
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

Step 0 reads flat top-level config. Steps 1+ read `step_N` keys:
```json
{
  "left_column": "sku",
  "right_column": "sku",
  "step_1": {"expression": "price * qty", "output_column": "revenue"},
  "step_2": {"mapping": {"revenue": "Total Revenue"}}
}
```

### Credentials

API credentials live in env files outside the project (e.g. `~/.etlai/secrets.env`).
`etlai sync` validates required vars are present without printing values.

## Resolution order

- Atoms: `./atoms/<name>.py` → `etlai.atoms.<name>` (package)
- Forms: `./forms/<name>.py` → `etlai.forms.<name>` (package)

User files take precedence over shipped ones.

## Development

```bash
git clone <repo>
pip install -e ".[dev]"
pytest --cov=etlai
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for workflow, [ARCHITECTURE.md](ARCHITECTURE.md)
for internals, and [TESTS.md](TESTS.md) for testing guide.
