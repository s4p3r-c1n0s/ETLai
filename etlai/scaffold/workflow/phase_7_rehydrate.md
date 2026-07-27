# Phase 7 — Rehydrate

## Purpose

Ensure the pipeline's final output uses business-meaningful column names. The generic column names produced by atoms (computed_1, flag_1, col_a) are renamed to what the user expects to see (revenue, low_margin_flag, category).

## Input

- `business_mapping.json` — output_columns section maps generic → business names
- Pipeline assembled in Phase 6 (manifest.yaml + config.json already include rename_columns as final step)

## Output

- The `rename_columns` step in the manifest is configured with correct mappings in config.json
- Output CSV will have business-meaningful column headers

## Process

1. Read `business_mapping.json` → `output_columns` section.
2. For each output column the pipeline produces (from atomic_operations.yaml final operation's output_columns):
   a. Find its entry in business_mapping.output_columns.
   b. Map: generic name → business_name.
3. Also include any pass-through columns that kept their business names from config.json (e.g., columns from reference files that were already real names after Phase 6 translation).
4. Write the mapping into config.json under the final step's config:
   ```json
   "step_N": {
     "mapping": {
       "computed_1": "total_revenue",
       "flag_1": "low_margin_flag"
     }
   }
   ```
5. Verify: the final output CSV will have column names that match what the user described in Phase 1's output section.

## Done When

- Every generic output column has a business-meaningful name in the rename mapping
- The rename_columns step is the LAST step in the manifest
- config.json's final step section contains the complete mapping
- Expected output columns (from pipeline_graph.yaml → output → fields) are all present in the mapping's values

## The rename_columns Atom

This is a shipped atom (or to be created if not yet shipped):

```python
# atoms/rename_columns.py
def execute(params_json: str) -> str:
    """Rename columns in a CSV using a provided mapping."""
    params = json.loads(params_json)
    df = pd.read_csv(params["input_file"])
    df = df.rename(columns=params["mapping"])
    df.to_csv(params["target_path"], index=False)
    return json.dumps({"success": True, "message": f"Renamed {len(params['mapping'])} columns"})
```

Params: `input_file`, `mapping` (dict of old_name → new_name), `target_path`

## DO

- Map EVERY generic/computed column name to a business-meaningful name
- Use names from business_mapping.json — don't invent new ones
- Include this as the explicit final step (not a post-processing hack)
- Verify the output column names match what the user expects (from Phase 1 output section)

## DO NOT

- Skip this step if columns "already have good names" — always include it for consistency
- Rename inside other atoms — rehydration is always a separate final step
- Use this step for anything other than column renaming (no filtering, no computation)
- Add columns that don't exist in the input (rename only, don't create)
