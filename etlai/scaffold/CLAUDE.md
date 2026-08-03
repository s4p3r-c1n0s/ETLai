# CLAUDE.md — ETLai Project

This is an ETLai project. Pipelines are created through a **7-phase workflow** that enforces strict separation between generic operations (atoms) and business logic (config).

---

## The Architecture Principle

Three sentences. Non-negotiable.

1. **Atoms are generic reusable operations.** They perform one verb (join, compute, filter, group, flag, sort, rename) on whatever columns/files params_json tells them to. They have zero knowledge of what the data represents.

2. **Business logic lives ONLY in config.json.** Column names, thresholds, formulas, file patterns — all domain specifics are in config, never in atom code.

3. **The framework wires them together.** manifest.yaml declares the pipeline structure. `inject_as` maps reference files to atom params. The registry executes steps in order, passing config as params.

---

## The Litmus Test

Before shipping ANY atom, answer:

> "If I rename every column in the test data to A, B, C, D — does the atom still work identically?"

**YES → ship it.** The atom is generic.
**NO → it knows something about the data. Fix it.**

---

## Creating a Pipeline: The 7-Phase Workflow

Pipelines are NOT created ad-hoc. Every pipeline goes through this mandatory sequence:

| Phase | What happens | Artifact produced | Gate validator |
|-------|-------------|-------------------|----------------|
| 0 | Dejargon user's request into plain language | `pipeline_graph.yaml` (partial) | — |
| 1 | Build complete business process graph | `pipeline_graph.yaml` (complete) | `gate_1_graph_complete.py` |
| 2 | Separate: strip domain terms from operations | `logical_graph.yaml` + `business_mapping.json` | `gate_2_no_leakage.py` |
| 3 | Atomize: split into smallest single-verb operations | `atomic_operations.yaml` | `gate_3_dag_valid.py` |
| 4 | Match: find existing atoms for each operation | `match_results.yaml` | `gate_4_match_coverage.py` |
| 5 | Create: write new atoms (for unmatched operations only) | `atoms/<name>.py` | `gate_5_atom_clean.py` |
| 6 | Assemble: wire manifest.yaml + config.json | `manifest.yaml` + `config.json` | `gate_6_manifest_valid.py` |
| 7 | Rehydrate: rename output columns to business names | Final step in manifest | — |

**Detailed instructions for each phase:** `workflow/phase_N_<name>.md`
**Artifact schemas:** `workflow/templates/`
**Gate validators:** `workflow/validators/gate_N_<name>.py`

### Phase Rules

- Phases are **strictly sequential**. No skipping.
- Each phase produces an artifact file. The next phase cannot start until the artifact exists AND its gate validator passes.
- Phases 0-1 loop with the user **via the Orchestrator** (BA proposes questions; Orchestrator confirms).
- Phases 2-7 do NOT loop back to the user. All ambiguity is resolved in 0-1.
- Gate validators are deterministic scripts. If they return FAIL, fix errors before proceeding.

---

## DO NOT (Global)

- **NEVER** write atom code that references real column names, file names, or domain concepts
- **NEVER** skip phases — even for "simple" pipelines, the full workflow runs
- **NEVER** create an atom named after a business concept (no: `sales_reconciliation`, `profit_margin`)
- **NEVER** put two operations in one atom (join + compute = two atoms, not one)
- **NEVER** proceed past a gate validator that returns FAIL
- **NEVER** send `business_mapping.json` to the phase that creates atoms (Phase 5)
- **NEVER** leave generic placeholders (col_a, threshold_1) in the final config.json
- **NEVER** skip the rename_columns final step in composite pipelines

---

## Deeper Instructions (Read When Needed)

| When you are... | Read this |
|----------------|-----------|
| Creating a pipeline via agents | `ORCHESTRATION.md` (the full script, follow step by step) |
| Creating a new pipeline (manual) | `workflow/CLAUDE.md` → then the relevant `phase_N.md` |
| Understanding agent roles | `HOW_TO_USE_AGENTS.md` |
| Writing atom code | `atoms/CLAUDE.md` |
| Assembling manifest + config | `pipelines/CLAUDE.md` |
| Running a gate check | `workflow/validators/gate_N_<name>.py` |

---

## 5-Agent Pipeline Creation System

For complex pipelines, a 5-agent system automates the 7-phase workflow:

| Agent | Phases | Role |
|-------|--------|------|
| **Orchestrator** | All | Owns user channel; relays BA Q&A; confirms graph; gates/firewall |
| **Business Analyst** | 0-1 | Worker turns (no user session); drafts graph + proposes questions |
| **Separator** | 2-3 | Mechanical; strips domain; builds generic DAG |
| **Atom Smith** | 4-5 | Firewalled from business data; finds/creates atoms |
| **Assembler** | 6-7 | Wires manifest + config with real values |

Agent system prompts: `agents/`
End-user guide: `HOW_TO_USE_AGENTS.md`

**Status:** System prompts complete. Agent orchestration code is planned (see `docs/AGENT_BUILD_ROADMAP.md`).

---

## How It Works (Runtime)

1. User drops CSV files into `pipelines/<name>/inbox/`
2. A sensor detects stable files, moves them to `staging/`, triggers a job
3. The job runs: load files → read config.json → execute atom → notify
4. On success: files → `processed/`, output → `output/`
5. On failure: files → `rejected/` with error reason

---

## Shipped Atoms (Search These First — Phase 4)

| Atom | Operation | Params |
|------|-----------|--------|
| `vlookup` | Join two tables on a key | `left_file, right_file, left_column, right_column, left_output_columns, right_output_columns, target_path` |
| `computed_column` | Create new column from expression | `input_file, expression, output_column, target_path` |
| `group_aggregate` | Group by column with sum/mean/min/max/count | `input_file, group_column, aggregations: [{column, function, output_column}], target_path` |
| `filter_rows` | Keep rows matching condition | `input_file, condition, target_path` |
| `flag_rows` | Add boolean column from condition (keeps all rows) | `input_file, condition, output_column, target_path` |
| `rename_columns` | Rename columns via mapping | `input_file, mapping: {old: new}, target_path` |
| `sort_rows` | Sort by columns | `input_file, sort_columns: [], ascending, target_path` |
| `groupby` | Group by column with count only | `input_file, group_column, target_path` |
| `api_fetch` | HTTP fetch, parse response to CSV | `endpoint, method, headers, params, response_format, data_path, field_mapping, target_path` |
| `mock_generate` | Generate synthetic data from headers | `input_files, target_path, rows` |

If a shipped atom handles the operation, USE IT. Do not create a new one.

---

## Configuration

Pipelines have no runtime UI. Every parameter (column names, thresholds,
expressions, mappings) is pre-written into `config.json` during assembly. The
registry loads it at runtime and injects file paths. A missing config raises.

---

## Key Concepts

### inject_as

Declares that a reference file should be injected as a specific atom param at runtime:
```yaml
inputs:
  - name: lookup_table
    role: reference
    pattern: "lookup.csv"
    inject_as:
      step: 0
      param: right_file
```

### input_from

Steps execute linearly by default (each reads prev step's output). For branching DAGs, use `input_from` to read from a non-adjacent predecessor:
```yaml
steps:
  - atom: computed_column        # step 0
  - name: detail_export          # step 1 (named output, reads step 0)
    atom: rename_columns
  - atom: group_aggregate        # step 2 reads step 0, NOT step 1
    input_from: 0
  - atom: rename_columns         # step 3 (final, reads step 2)
```

### config.json

Single source of business config. Written during Phase 6 by translating `business_mapping.json` into atom params:
```json
{
  "step_0": {"left_column": "sku", "right_column": "sku", "right_output_columns": ["category"]},
  "step_1": {"expression": "price * quantity", "output_column": "revenue"},
  "step_2": {"mapping": {"revenue": "total_revenue", "flag_1": "low_margin"}}
}
```

### Reference folder

`pipelines/<name>/reference/` — permanent data (lookup tables, price lists). Never moved or consumed. Wired to atoms via `inject_as`.

### Triggers

```yaml
trigger:
  rules:
    - type: inbox_files       # watch for new files
      min_files: 1
    - type: schedule          # cron-based
      cron: "0 8 * * 1"
```

---

## Resolution Order

- Atoms: `./atoms/<name>.py` → `etlai.atoms.<name>` (shipped package)

User-created atoms take precedence over shipped ones.

---

## API Pipelines

For data fetched from APIs:
- Use `api_fetch` atom (shipped) for simple single-request APIs
- Create custom atom for complex APIs (OAuth2, pagination, request signing)
- Store credentials in `~/.etlai/secrets.env` (never committed)
- Declare `env_file` and `requires_env` in manifest
- Set `min_files: 0` and use `schedule` trigger

---

## Constraints

- Python 3.10+ required
- CSV files only for processing
- All step params come from a pre-written `config.json` (no runtime UI)
- Do not commit: `pipelines/*/inbox/`, `staging/`, `processed/`, `rejected/`, `output/`, `config.json`
- Reference files are permanent — do not gitignore `reference/`

---

## Common Commands

```bash
etlai create "request"  # create pipeline via 5-agent system (orchestrator + gates)
etlai sync              # validate manifests, create folders
etlai run               # start Dagster dev server
etlai list              # show registered pipelines
```
