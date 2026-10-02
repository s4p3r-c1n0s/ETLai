# Pipeline Assembly Law

This file governs manifest.yaml and config.json creation. Read it BEFORE assembling any pipeline.

## When This Applies

Phase 6 of the workflow. By this point you MUST have:
- `workflow/atomic_operations.yaml` — what operations to wire
- `workflow/match_results.yaml` — which atom handles each operation
- `workflow/business_mapping.json` — real values to populate config

If any of these are missing, STOP. Go back to the appropriate earlier phase.

## manifest.yaml Structure

### Single-atom pipeline

```yaml
name: <pipeline_name>
path: ask                           # Prompt user for data folder location during sync
atom: <atom_name>
min_files: <count of transient inputs>

inputs_map:                        # explicit file binding (see "inputs_map Rules")
  - param: input_file              # or left_file per atom contract
  - param: right_file              # optional: for join atoms
    source: reference              # permanent lookup matched by pattern
    pattern: "<filename_pattern>"  #   (omit source/pattern for a second inbox file)

inputs:
  - name: <source_name>
    role: transient
    description: "<what this data is>"
    pattern: "<filename_pattern>"

trigger:
  rules:
    - type: <schedule|inbox_files>
      cron: "<cron_expression>"        # if schedule
      min_files: <N>                   # if inbox_files
```

### Composite pipeline

```yaml
name: <pipeline_name>
path: ask                           # Prompt user for data folder location during sync
min_files: <count of transient inputs>
load_files_op_name: <pipeline_name>__load_files

inputs:
  - name: <source_1>
    role: transient
    description: "..."

steps:
  - name: enrich_data           # Optional: step produces <name>.csv as output
    atom: <atom_for_op_1>
    inputs_map:
      - param: left_file        # step 0 consumes inbox files (or prev_output)
      - param: right_file
        source: reference
        pattern: "..."          # permanent lookup, e.g. catalog.csv
  - atom: <atom_for_op_2>
    inputs_map:
      - param: input_file
        source: prev_output
  - name: detail_export         # Optional: named steps become first-class outputs
    atom: <atom_for_op_3>
    inputs_map:
      - param: input_file
        source: prev_output
  - atom: <atom_for_op_4>       # input_from: reads step 0's output instead of previous
    input_from: 0
    inputs_map:
      - param: input_file
        source: prev_output
  - atom: rename_columns        # ALWAYS last step (produces output.csv)
    inputs_map:
      - param: input_file
        source: prev_output

trigger:
  rules:
    - type: schedule
      cron: "0 8 * * 1"
```

## config.json Structure

### Single-atom

Params live under `step_0`:
```json
{
  "step_0": {
    "left_column": "actual_column_name",
    "right_column": "actual_column_name"
  }
}
```

### Composite

Per-step dict — every step has a `step_N` key, including `step_0`:
```json
{
  "step_0": {
    "left_column": "actual_column_name",
    "right_column": "actual_column_name"
  },
  "step_1": {
    "expression": "price * quantity",
    "output_column": "revenue"
  },
  "step_N": {
    "mapping": {
      "computed_1": "total_revenue",
      "flag_1": "low_margin_flag"
    }
  }
}
```

The last step (rename_columns) always has a `mapping` dict.

## Translating business_mapping.json → config.json

This is the core task of Phase 6. For each step:

1. Look up the atom's expected params (from its docstring or shipped atom reference)
2. For each param that needs a column name: find the placeholder in atomic_operations.yaml → look up its `real_name` in business_mapping.json → use that real name as the config value
3. For thresholds: look up `threshold_1` → get its `value` from business_mapping → use in config
4. For expressions/formulas: translate the generic expression to use real column names

### Example translation:

**atomic_operations.yaml says:** `params: {expression: "col_a * col_b", output_column: computed_1}`
**business_mapping.json says:** `col_a.real_name = "price"`, `col_b.real_name = "quantity"`, `computed_1.business_name = "revenue"`
**config.json becomes:** `{"expression": "price * quantity", "output_column": "revenue"}`

## inputs_map Rules

**Every step that reads a file MUST declare `inputs_map`.** File binding is
explicit — there is no heuristic fallback, and a missing `inputs_map` fails at
runtime.

Each entry is `{param, source}`:

| source            | binds                                            |
|-------------------|--------------------------------------------------|
| `inbox` (default) | the next unclaimed inbox file, in pipeline order |
| `prev_output`     | the previous step's output path                  |
| `inbox_all`       | the full list of inbox files (e.g. `input_files`) |
| `reference`       | first `reference/` file matching `pattern`        |

Rules:
1. Step 0 binds inbox files: joins declare `left_file` + `right_file`, others
   declare `input_file` (or `input_files` with `source: inbox_all`).
2. Steps ≥ 1 bind `prev_output`: declare `input_file` with `source: prev_output`
   (or `left_file` for a mid-pipeline join whose `right_file` is a reference).
3. Permanent lookups bind via `source: reference` + a filename `pattern`
   (matched against `reference/`). A reference param whose pattern matches
   nothing is left unset — `etlai sync` warns about it.
4. The param name must match what the atom reads (`input_file`, `left_file`,
   `right_file`, `input_files`). Check the atom's docstring.

```yaml
steps:
  - atom: vlookup               # step 0: join inbox + reference lookup
    inputs_map:
      - param: left_file
      - param: right_file
        source: reference
        pattern: "catalog.csv"
  - atom: group_aggregate       # step 1: reads step 0 output
    inputs_map:
      - param: input_file
        source: prev_output
```

## path: Field

**Always set `path: ask` in manifests.** This prompts the user during `etlai sync` to choose where the pipeline's data folders should live.

When `path: ask` is present:
1. Running `etlai sync` opens a Tkinter folder picker
2. User selects the data root location (e.g., `/Users/bob/Documents/my_pipeline_data`)
3. The manifest is updated: `path: /Users/bob/Documents/my_pipeline_data`
4. All lifecycle folders are created inside: `inbox/`, `staging/`, `processed/`, `rejected/`, `output/`, `reference/`

Without `path:`, the default is `pipelines/<pipeline_name>/` inside the project directory.

## min_files Calculation

```
min_files = count of inputs where role == "transient"
```

Reference files are NOT counted — they're permanent and already present.

## Trigger Rules

Map from pipeline_graph.yaml triggers:

| Graph trigger type | Manifest rule |
|-------------------|---------------|
| `schedule` with cron | `type: schedule`, `cron: "<expression>"` |
| `folder_watch` | `type: inbox_files`, `min_files: <N>` |
| Both | Two entries in `rules:` list |

## The Final Step: rename_columns

EVERY composite pipeline MUST end with `rename_columns`. This step:
- Reads the intermediate output from the previous step
- Renames generic/computed column names to business-meaningful names
- Gets its mapping from config.json's last step entry

The mapping comes from `business_mapping.json → output_columns`:
```json
"step_N": {
  "mapping": {
    "computed_1": "total_revenue",
    "computed_2": "profit_margin_pct",
    "flag_1": "low_margin_flag"
  }
}
```

## Config comes from config.json — Always

Pipelines have no runtime UI. Every step's parameters are pre-written into
`config.json` during assembly. The registry loads that config at runtime and
injects file paths — there is no interactive prompt. A missing config raises.

## Non-Linear Input (input_from)

By default, each step reads the **immediately previous step's** output. When a step needs input from a different predecessor (branching pipelines), use `input_from`:

```yaml
steps:
  - atom: vlookup               # step 0 → _intermediate_0.csv
  - atom: computed_column        # step 1, reads step 0 → _intermediate_1.csv
  - name: detail_export          # step 2, reads step 1 → detail_export.csv
    atom: rename_columns
  - atom: group_aggregate        # step 3, reads step 1 (NOT step 2!)
    input_from: 1
  - atom: flag_rows              # step 4, reads step 3
  - atom: rename_columns         # step 5 (final) → output.csv
```

**Rules:**
- `input_from` is a 0-indexed step number
- It must reference an earlier step (lower index)
- Without `input_from`, a step reads from step N-1 (default linear behavior)
- Use when a DAG branches: one branch produces a named export, the other continues processing from an earlier point

**When to use:** After a named step (like `detail_export`) that renames columns for export, the next step in the other branch needs the pre-renamed data. Point `input_from` at the step before the rename.

## Multiple Outputs (Named Steps)

Use `name:` on steps to produce multiple named outputs:

```yaml
steps:
  - name: transaction_detail    # Produces transaction_detail.csv
    atom: rename_columns
  - name: reconciliation_summary # Produces reconciliation_summary.csv (not final, will be output.csv)
    atom: rename_columns
```

All named intermediate steps produce `{name}.csv` in the output folder. The final step always produces `output.csv`.

## DO

- Set `path: ask` in every manifest — user chooses data folder location during sync
- Use `name:` for intermediate steps that are intentional outputs
- Use `input_from: N` when a step needs input from a non-adjacent predecessor (branching DAGs)
- Add `rename_columns` as the explicit last step
- Translate ALL placeholders to real values in config.json (col_a → real_name)
- Declare `inputs_map` on every file-reading step (see "inputs_map Rules"), wiring references via `source: reference`
- Include `load_files_op_name` for composite pipelines
- Verify step count in manifest matches step count in config.json
- Run `etlai sync` after assembly to validate and create folders

## DO NOT

- Leave generic placeholders (col_a, threshold_1) in config.json — they must be translated
- Skip the rename_columns final step
- Hardcode file paths in config — use `source: reference` for references, framework handles transient
- Add steps that don't correspond to an entry in match_results.yaml
- Change the step order vs what atomic_operations.yaml defines
- Put business logic in the manifest — it belongs in config.json
- Modify atom code to fit the pipeline — atoms are used as-is

## Gate Validator

After assembly, run:
```bash
python workflow/validators/gate_6_manifest_valid.py pipelines/<name>/ .
```

Must return PASS. Checks: all atoms exist, every step declares valid inputs_map (reference sources have a pattern), last step is rename_columns, no untranslated placeholders in config.
