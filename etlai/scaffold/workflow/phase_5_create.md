# Phase 5 — Create Atom

## Purpose

Write new generic atoms for operations marked "create" in match_results.yaml. Each atom is a reusable, domain-agnostic function that works for ANY dataset.

## Input

- `match_results.yaml` — specifically entries with `status: create`
- `atomic_operations.yaml` — for the operation spec (params, input/output columns)
- `atoms/CLAUDE.md` — for atom creation rules (READ IT BEFORE WRITING ANY CODE)

## Output

- New atom file(s) in `atoms/<name>.py`
- Corresponding test file(s) or test additions

## Process

1. Read `atoms/CLAUDE.md` for the atom creation contract and rules.
2. For each "create" entry in match_results.yaml:
   a. Read the operation spec from atomic_operations.yaml (id, operation verb, params, input/output columns).
   b. Write the atom as a GENERIC function that accepts all specifics via params_json.
   c. Use placeholder column names in tests (col_a, col_b) — never real business names.
   d. Verify the atom passes the litmus test: "rename all columns to A, B, C — does it still work?" YES.
3. Run the test to verify the atom works.

## Done When

- Every "create" entry has a corresponding atom file in `atoms/`
- Every atom passes its test
- Every atom passes the litmus test (no domain knowledge embedded)
- Every atom accepts ALL specifics via params_json — nothing hardcoded

## CRITICAL: Information Boundary

This phase receives ONLY:
- The operation verb (join, compute, filter, group, flag, etc.)
- The generic param structure (col_a, col_b, threshold_1)
- The expected behavior in abstract terms

This phase NEVER receives:
- `business_mapping.json`
- Real column names
- Real company/product/entity names
- Context about what the data represents

If you find yourself thinking "this column is revenue" or "this threshold is a margin percentage" — STOP. You are leaking. The atom does not know and must not know what the data means.

## Atom File Structure

```python
import json
import pandas as pd


def execute(params_json: str) -> str:
    """
    <One line: what generic operation this performs>

    Params: {list all accepted params}
    Returns: {"success": bool, "message": str, ...}
    """
    try:
        params = json.loads(params_json)

        # Read inputs from params (never hardcoded paths)
        # Perform ONE generic operation
        # Write output to params["target_path"]

        return json.dumps({"success": True, "message": "..."})
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)})
```

## Test Structure

```python
def test_<atom_name>_basic(tmp_path):
    # Create test data with GENERIC column names
    input_csv = tmp_path / "input.csv"
    input_csv.write_text("col_a,col_b,col_c\n1,2,3\n4,5,6\n")

    params = {
        "input_file": str(input_csv),
        # operation-specific params using generic names
        "target_path": str(tmp_path / "output.csv"),
    }

    result = json.loads(execute(json.dumps(params)))
    assert result["success"] is True
    # Verify output file contents
```

## DO

- Write ONE atom per "create" entry (unless two entries share the same operation — then one atom serves both)
- Accept every column name, threshold, formula via params
- Handle errors gracefully (missing columns, invalid types)
- Name the atom as `<verb>_<object>.py`: compute_column.py, filter_rows.py, group_aggregate.py, flag_rows.py
- Keep atoms small (under 50 lines of logic)
- Test with at least 2 test cases: success path + one error path

## DO NOT

- Read business_mapping.json inside the atom
- Hardcode ANY column name, file path, threshold, or formula
- Name the atom after what the data represents (no: profit_margin.py, sales_report.py)
- Write multi-operation atoms (no: "compute then flag" in one atom)
- Import or reference the pipeline that will use this atom
- Add parameters that assume data semantics ("revenue_column" → use "input_column" or "value_column")
- Make the atom aware of its position in a pipeline (no: "is_first_step", "upstream_output")

## Gate Validator

After writing all new atom files, run:
```bash
python workflow/validators/gate_5_atom_clean.py pipelines/<name>/ .
```

Must return PASS before proceeding to Phase 6. Checks: atom files exist, have execute() function, contain no business terms from business_mapping.json, don't hardcode paths.
