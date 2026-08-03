# Architecture

Internal design document for contributors.

---

## System Overview

ETLai is a pip-installable package that provides a local, folder-driven CSV transformation engine. It has three layers: the **framework** (registry, sensors, lifecycle), the **pipeline creation system** (5-agent orchestration), and the **user project** (atoms, config, data).

```
┌─────────────────────────────────────────────────────────────────────┐
│ pip install ETLai                                                    │
│                                                                      │
│  etlai/                                                             │
│  ├── cli.py              CLI (init/create/sync/run/list)            │
│  ├── orchestrator.py     5-agent coordination (gates, firewall)     │
│  ├── registry.py         Manifest scanner → Dagster Definitions      │
│  ├── atoms/              10 shipped generic atoms                    │
│  ├── helpers/            Framework utilities                         │
│  │   ├── folders.py      PipelineFolders (lifecycle + reference)    │
│  │   ├── config_store.py JSON config persistence                     │
│  │   ├── env_loader.py   .env file loading + validation             │
│  │   └── notifier.py     OS toast notifications                      │
│  ├── sensors/            Hot folder sensor factory                    │
│  └── scaffold/           Templates for etlai init                    │
│      ├── CLAUDE.md       Constitution for LLM sessions               │
│      ├── ORCHESTRATION.md  Step-by-step agent coordination script   │
│      ├── HOW_TO_USE_AGENTS.md  End-user guide                       │
│      ├── workflow/       Phase playbooks + gate validators            │
│      │   ├── phase_0..7  Detailed instructions per phase             │
│      │   ├── templates/  YAML schemas for artifacts                  │
│      │   └── validators/ 6 deterministic gate scripts                │
│      └── agents/         System prompts for 5 agents                 │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ User project (scaffolded by `etlai init`)                           │
│                                                                      │
│  CLAUDE.md               LLM session constitution                    │
│  ORCHESTRATION.md        Agent coordination script                   │
│  etlai.yaml              Project config (pipelines_root)             │
│  definitions.py          3-line Dagster loader                       │
│  workflow/               Gate validators + phase playbooks            │
│  agents/                 Agent system prompts                         │
│  atoms/                  User/AI-created atoms                        │
│  pipelines/                                                          │
│    <name>/                                                           │
│      manifest.yaml       Pipeline wiring                             │
│      config.json         Business logic (params for atoms)           │
│      workflow/           Intermediate artifacts (pipeline_graph, etc) │
│      inbox/              Transient input files                        │
│      staging/            In-flight (prevents double-trigger)          │
│      processed/          Successfully consumed                        │
│      rejected/           Failed + .error.txt                         │
│      output/             Transformation results                       │
│      reference/          Permanent data (lookups, snapshots)          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Core Contracts

### Atom

```python
def execute(params_json: str) -> str:
    """Single unit of work. Domain-agnostic. Returns JSON result."""
```

- Input: JSON string with all params (config values + file paths + target_path)
- Output: JSON string `{"success": bool, "message": str}`
- Must be domain-agnostic (litmus test: rename columns to A,B,C — still works?)
- One verb per atom (join OR compute OR filter, never compound)
- Business logic comes from config.json, never hardcoded

### Config

Each pipeline's parameters live in a pre-written `config.json` under `step_N`
keys for every step (including `step_0`). Single-atom pipelines have only
`step_0`. The registry loads this config at runtime and injects file paths —
there is no interactive prompt. A missing config raises with a helpful message.

### Manifest (Single Atom)

```yaml
name: pipeline_name
atom: atom_module_name
min_files: 1
path: ask                        # Tkinter folder picker during sync
trigger:
  rules:
    - type: inbox_files
      min_files: 1
```

### Manifest (Composite Pipeline)

```yaml
name: sales_reconciliation
min_files: 1
path: ask
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
  - atom: flag_rows              # step 2: flag low margin
    input_from: 1                # reads step 1 output, not step 2's
  - name: detail_export          # named step → produces detail_export.csv
    atom: rename_columns
  - atom: group_aggregate        # step 4
    input_from: 2                # reads step 2, not step 3 (branch)
  - atom: rename_columns         # final step (always rename_columns)
trigger:
  rules:
    - type: inbox_files
      min_files: 1
```

### config.json Structure

```json
{
  "step_0": {
    "left_column": "sku",
    "right_column": "sku",
    "right_output_columns": ["category", "price"]
  },
  "step_1": {
    "expression": "price * quantity",
    "output_column": "revenue"
  },
  "step_2": {
    "condition": "revenue < 100",
    "output_column": "low_margin_flag"
  },
  "step_3": { "mapping": {"revenue": "Total Revenue"} },
  "step_4": {
    "group_column": "category",
    "aggregations": [{"column": "revenue", "function": "sum", "output_column": "total"}]
  },
  "step_5": { "mapping": {"total": "Category Total"} }
}
```

**Key:** Every step reads its `step_N` key — including `step_0`.

---

## Execution Engine (registry.py)

### File Injection Logic

The framework injects file paths into atom config before execution:

```
Step 0 (is_first=True):
  inject_as runs first (sets e.g. right_file from reference/)
  then auto-injection:
    2+ inbox files           → left_file + right_file
    1 file + right_file set  → left_file
    1 file alone             → input_file

Steps ≥ 1 (is_first=False):
  inject_as runs first (sets e.g. right_file from reference/)
  then auto-injection:
    right_file already set   → left_file = prev_output
    otherwise                → input_file = prev_output
```

### Target Path (Output Naming)

| Condition | Output file |
|-----------|------------|
| Last step | `output/output.csv` |
| Named step (`name: detail_export`) | `output/detail_export.csv` |
| Unnamed intermediate | `output/_intermediate_N.csv` |

Atoms MUST write to `target_path` for the chain to work.

### input_from (Non-Linear Routing)

Steps execute linearly by default (each reads prev step's output). For branching DAGs:

```yaml
steps:
  - atom: computed_column        # step 0
  - atom: rename_columns         # step 1 (reads step 0)
    name: export_a
  - atom: group_aggregate        # step 2 reads step 0, NOT step 1
    input_from: 0
```

### inject_as (Reference File Injection)

Reference files in `reference/` are injected into specific step params:

```yaml
inputs:
  - name: catalog
    role: reference
    pattern: "catalog.csv"
    inject_as:
      step: 0
      param: right_file
```

At runtime: fnmatch against `reference/` basenames → set config param.

---

## Pipeline Creation: 5-Agent System

### The Firewall Principle

Atoms must be domain-agnostic. The 5-agent system enforces this by construction:

```
business_mapping.json ──► Separator produces it
                      ──► Assembler consumes it
                      ──✘ Atom Smith NEVER receives it (file physically hidden)
```

### Agent Roles

| Agent | Phases | Loops with User? | Knows Domain? | Knows Atoms? |
|-------|--------|------------------|---------------|-------------|
| Orchestrator | All | YES (relay Q&A + confirmation only) | No | No |
| Business Analyst | 0-1 | No (worker turns; Orchestrator mediates) | YES | No |
| Separator | 2-3 | No | No | No |
| Atom Smith | 4-5 | No | No | YES |
| Assembler | 6-7 | No | YES | YES |

**Confirmation ownership:** Only `Orchestrator.confirm_graph(True)` may set `owner_confirmed: true` on `pipeline_graph.yaml` after explicit user assent. BA always writes `owner_confirmed: false`.

### Gate Validators

Deterministic scripts that validate artifacts between phases:

| Gate | Validates | Key Checks |
|------|-----------|------------|
| 1 | pipeline_graph.yaml | Complete, confirmed, all fields present |
| 2 | logical_graph.yaml | Zero domain terms (substring scan vs mapping) |
| 3 | atomic_operations.yaml | Valid DAG, single verbs, no cycles |
| 4 | match_results.yaml | All ops matched, atoms exist |
| 5 | New atom code | No domain leakage, has execute(), no hardcoded paths |
| 6 | manifest.yaml + config.json | Valid structure, no placeholders, last step = rename_columns |

### Orchestrator Module (etlai/orchestrator.py)

```python
from etlai.orchestrator import Orchestrator

orch = Orchestrator(project_root=Path("."), pipeline_name="sales_recon")
orch.initialize()
orch.start_ba_session("join sales with catalog")
orch.build_ba_turn_prompt()          # BA worker turn instructions
orch.confirm_graph(True)             # only Orchestrator may confirm
orch.prepare_gate1()                 # enforce confirmation ownership
orch.run_gate(1)                     # validate, returns GateResult
orch.activate_firewall()             # hide business_mapping.json
orch.build_agent_context("atom_smith")  # scoped file list
orch.deactivate_firewall()           # restore
orch.get_phase_status()              # which artifacts exist
```

---

## Runtime Data Flow

### File-Based Pipeline

```
1. User drops CSVs in inbox/
2. Sensor detects stable files (size unchanged over 2s)
3. Files moved to staging/ (prevents double-trigger)
4. Job starts:
   a. load_files: reads staged paths from RunConfig
   b. For each step:
      - read step config from config.json
      - inject reference files (inject_as)
      - inject input files (auto-injection)
      - atom.execute(params_json)
   c. Last step: files → processed/, output written
5. Failure at any step: all files → rejected/ + .error.txt
```

### API-Based Pipeline

```
1. Cron schedule fires (min_files: 0, no sensor)
2. load_files returns []
3. registry reads config.json
4. Atom reads credentials from os.environ (loaded from env_file)
5. Atom fetches data, writes to target_path
```

---

## Shipped Atoms (10)

| Atom | Operation | Key Params |
|------|-----------|-----------|
| `vlookup` | Join two tables on key | left_file, right_file, left/right_column |
| `computed_column` | New column from expression | input_file, expression, output_column |
| `group_aggregate` | Group + aggregate | input_file, group_column, aggregations[] |
| `filter_rows` | Keep matching rows | input_file, condition |
| `flag_rows` | Add boolean column | input_file, condition, output_column |
| `rename_columns` | Rename via mapping | input_file, mapping |
| `sort_rows` | Sort by columns | input_file, sort_columns, ascending |
| `groupby` | Group by count | input_file, group_column |
| `api_fetch` | HTTP → CSV | endpoint, method, headers, field_mapping |
| `mock_generate` | Synthetic data | input_files, rows |

---

## Module Resolution

```
Atoms:  project/atoms/<name>.py  →  etlai.atoms.<name>
```

User files take precedence. This allows overriding shipped atoms without modifying the package.

---

## CLI Commands

| Command | Purpose |
|---------|---------|
| `etlai init <dir>` | Scaffold project (copies workflow, agents, templates) |
| `etlai create "request"` | Create pipeline via 5-agent system |
| `etlai sync` | Validate manifests, create folders, handle `path: ask` |
| `etlai run` | Start Dagster dev server |
| `etlai list` | Show registered pipelines |

---

## Security Boundaries

| Layer | Contains | Visible to Cloud LLM? |
|-------|----------|----------------------|
| Atom code | Generic logic | Yes |
| Manifest | Pipeline wiring | Yes |
| config.json | Business logic (column names, thresholds) | Yes (local only) |
| secrets.env | Credentials | Never |
| reference/ | Lookup tables, historical data | No (in data path) |
| business_mapping.json | Domain ↔ placeholder map | Firewalled from Atom Smith |

---

## Design Decisions

### Why atoms must be domain-agnostic

If an atom knows column names, it can't be reused across pipelines. The same `computed_column` atom handles revenue calculations, interest rates, and margin formulas — because the expression comes from config, not code.

### Why config.json is separate from manifest

- Manifest = structure (what to wire). Committed, visible.
- Config = business values (what params to pass). May contain sensitive domain logic.
- Same atom serves multiple pipelines with different configs.

### Why every step uses `step_N` (including step_0)

One rule for all pipelines: step N reads `config.json["step_N"]`. Single-atom
pipelines are just `{ "step_0": { ... } }`. No hybrid flat/nested format.

### Why the firewall is physical (file rename, not access control)

LLM agents can read any file in the project. The only reliable way to prevent Atom Smith from seeing business_mapping.json is to physically remove it from the filesystem during Atom Smith's execution.

### Why gate validators are deterministic scripts (not LLM judgment)

LLMs can rationalize anything. A script that returns PASS/FAIL based on structural checks cannot be talked out of failing. If gate 5 finds "revenue" in atom code, it fails — no exceptions.

### Why `path: ask` uses Tkinter

Users may want pipeline data in a different location than the project directory (e.g., a shared network drive). `path: ask` opens a folder picker during `etlai sync`. The chosen path is written back to manifest.yaml permanently.
