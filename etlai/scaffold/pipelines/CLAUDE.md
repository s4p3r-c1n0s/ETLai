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
form: passthrough
min_files: <count of transient inputs>

inputs:
  - name: <source_name>
    role: transient
    description: "<what this data is>"
    pattern: "<filename_pattern>"

  - name: <reference_name>
    role: reference
    description: "<what this lookup table provides>"
    pattern: "<filename_pattern>"
    inject_as:
      step: 0
      param: <param_name_atom_expects>

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
  - name: <ref_1>
    role: reference
    description: "..."
    pattern: "..."
    inject_as:
      step: 0
      param: right_file

steps:
  - name: enrich_data           # Optional: step produces <name>.csv as output
    atom: <atom_for_op_1>
    form: passthrough
  - name: detail_export         # Optional: named steps become first-class outputs
    atom: <atom_for_op_2>
    form: passthrough
  - atom: rename_columns        # ALWAYS last step (produces output.csv)
    form: passthrough

trigger:
  rules:
    - type: schedule
      cron: "0 8 * * 1"
```

## config.json Structure

### Single-atom

Flat dict with params the atom expects:
```json
{
  "left_column": "actual_column_name",
  "right_column": "actual_column_name",
  "target_path": "..."
}
```

### Composite

Per-step dict:
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

## inject_as Rules

Every reference file MUST have an `inject_as` declaration:

```yaml
inject_as:
  step: <0-indexed step number>
  param: <param name the atom expects for this file>
```

How to determine the correct step and param:
1. Find which atomic operation uses this reference source (from atomic_operations.yaml)
2. That operation maps to a step index (same order as steps list)
3. The atom for that step expects the file as a specific param (typically `right_file` for joins, `input_file` for single-input atoms)

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

## form: passthrough — Always

All pipelines assembled by this workflow use `form: passthrough` for EVERY step.

Why: config.json is pre-written during assembly. There is no first-run UI needed. The form just reads config.json and passes it to the atom.

NEVER use any other form in an automated pipeline. Forms with Tkinter UI are for human-interactive pipelines only.

## Multiple Outputs (Named Steps)

Use `name:` on steps to produce multiple named outputs:

```yaml
steps:
  - name: transaction_detail    # Produces transaction_detail.csv
    atom: rename_columns
    form: passthrough
  - name: reconciliation_summary # Produces reconciliation_summary.csv (not final, will be output.csv)
    atom: rename_columns
    form: passthrough
```

All named intermediate steps produce `{name}.csv` in the output folder. The final step always produces `output.csv`.

## DO

- Set `path: ask` in every manifest — user chooses data folder location during sync
- Set `form: passthrough` on every step
- Use `name:` for intermediate steps that are intentional outputs
- Add `rename_columns` as the explicit last step
- Translate ALL placeholders to real values in config.json (col_a → real_name)
- Wire `inject_as` for every reference input
- Include `load_files_op_name` for composite pipelines
- Verify step count in manifest matches step count in config.json
- Run `etlai sync` after assembly to validate and create folders

## DO NOT

- Leave generic placeholders (col_a, threshold_1) in config.json — they must be translated
- Skip the rename_columns final step
- Create forms other than passthrough
- Hardcode file paths in config — use inject_as for references, framework handles transient
- Add steps that don't correspond to an entry in match_results.yaml
- Change the step order vs what atomic_operations.yaml defines
- Put business logic in the manifest — it belongs in config.json
- Modify atom code to fit the pipeline — atoms are used as-is

## Gate Validator

After assembly, run:
```bash
python workflow/validators/gate_6_manifest_valid.py pipelines/<name>/ .
```

Must return PASS. Checks: all atoms exist, reference inputs have inject_as, last step is rename_columns, no untranslated placeholders in config.
