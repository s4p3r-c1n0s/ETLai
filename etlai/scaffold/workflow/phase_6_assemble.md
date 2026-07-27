# Phase 6 — Assemble Pipeline

## Purpose

Wire together matched/created atoms into a working ETLai pipeline: manifest.yaml + config.json. This is where the business mapping gets applied — translating generic placeholders into real config values.

## Input

- `match_results.yaml` — which atom handles each operation
- `business_mapping.json` — real column names, thresholds, formulas
- `atomic_operations.yaml` — execution order and dependencies
- `pipeline_graph.yaml` — trigger definitions and data source roles

## Output

- `pipelines/<name>/manifest.yaml` — pipeline manifest with steps, inputs, inject_as, triggers
- `pipelines/<name>/config.json` — per-step config with real column names and values from business_mapping
- A `rename_columns` step as the final step (rehydration from Phase 7)

## Multiple Outputs (Named Steps)

Steps can declare a `name:` field to produce intentional outputs:
- Step with `name: detail_export` produces `detail_export.csv`
- Step without `name:` uses default naming `_intermediate_N.csv`
- Final step always produces `output.csv`

Use this to design pipelines with multiple outputs: place strategic steps (rename_columns for export snapshots) at intermediate positions and give them `name:` fields.

## Process

1. Read `pipelines/CLAUDE.md` for manifest assembly rules.
2. Determine step order from atomic_operations.yaml depends_on chain.
3. **Linearize the DAG:** Steps execute in a single linear sequence. If the DAG branches (multiple operations depend on the same parent), flatten into a linear order:
   - Place the shorter branch first (typically the named export with rename_columns)
   - Then continue the longer branch
   - On the first step of the longer branch, add `input_from: <step_index>` pointing to the shared parent step
   - Example: ops A→B→C(export)→D(groups from B) becomes steps [A, B, C(named), D(input_from:1)]
4. Map each operation to its atom (from match_results.yaml).
5. Identify which intermediate steps should be named outputs (assign `name:` fields).
6. Build manifest.yaml:
   a. Set pipeline `name` from pipeline_graph.yaml.
   b. Build `steps:` list in linearized order, each referencing its atom and `form: passthrough`.
   c. For any step that needs non-adjacent input, add `input_from: <step_index>`.
   d. Build `inputs:` declarations from pipeline_graph.yaml data_sources:
      - role: reference for permanent data, role: transient for incoming data
      - Add `inject_as:` for each reference source (map to the step + param that needs it)
   e. Build `trigger:` from pipeline_graph.yaml triggers.
   f. Add a final step: `atom: rename_columns`, `form: passthrough` (rehydration).
7. Build config.json:
   a. For each step, translate generic params into real values using business_mapping.json:
      - `col_a` → look up real_name in business_mapping.columns → use that as param value
      - `threshold_1` → look up value in business_mapping.thresholds → use that as param value
      - Formulas: translate generic expression to real column names
   b. Structure as `{"step_0": {...}, "step_1": {...}, ...}` for composite pipelines.
   c. Final step (rename_columns) gets its mapping from business_mapping.output_columns.
   d. **Important:** Steps with `input_from` receive the output of the referenced step. Their config must use column names as they exist at that point in the chain (not after any subsequent renames).
8. Run `etlai sync` to validate the manifest and create folders.

## Done When

- `manifest.yaml` passes `etlai sync` without errors
- `config.json` has entries for every step
- Every atom in the steps list actually exists (shipped or in atoms/)
- Every reference file has an `inject_as` declaration pointing to the correct step + param
- The final step is `rename_columns` with output mapping from business_mapping
- Trigger rules match what was defined in pipeline_graph.yaml

## Config Translation Example

**From business_mapping.json:**
```json
{
  "columns": {
    "col_a": {"real_name": "sku", "source": "sales_transactions"},
    "col_b": {"real_name": "sku", "source": "product_catalog"},
    "col_c": {"real_name": "category", "source": "product_catalog"}
  },
  "thresholds": {
    "threshold_1": {"value": 15.0}
  }
}
```

**Becomes config.json step_0:**
```json
{
  "step_0": {
    "left_column": "sku",
    "right_column": "sku",
    "left_output_columns": ["*"],
    "right_output_columns": ["category"]
  }
}
```

The atom receives real column names via config — it doesn't know what "sku" means, it just joins on it.

## DO

- Use `form: passthrough` for every step (no UI — config.json is pre-written)
- Wire `inject_as` for every reference data source (never leave reference file discovery to the atom)
- Add `rename_columns` as the explicit final step
- Set `min_files` based on count of transient inputs
- Include `load_files_op_name` for composite pipelines
- Use the trigger type from pipeline_graph.yaml (schedule → cron rule, folder_watch → inbox_files rule)

## DO NOT

- Put generic placeholder names (col_a, threshold_1) in config.json — translate them to real values
- Create forms other than passthrough (all config is pre-written by this phase)
- Skip the rename_columns final step (output must have business-meaningful column names)
- Hardcode file paths in config — use inject_as for reference files, framework handles transient
- Create steps that don't map to an entry in match_results.yaml
- Modify any atom code during this phase — assembly uses atoms as-is

## Gate Validator

After assembling manifest.yaml and config.json, run:
```bash
python workflow/validators/gate_6_manifest_valid.py pipelines/<name>/ .
```

Must return PASS. Checks: required fields present, all atoms exist, reference inputs have inject_as, last step is rename_columns, no un-translated placeholders in config.json.
