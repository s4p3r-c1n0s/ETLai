# Atom Creation Law

This file governs ALL atom creation. Read it BEFORE writing any atom code.

## Contract

```python
def execute(params_json: str) -> str:
    """
    Accepts JSON params, performs ONE generic operation, returns JSON result.
    Returns: {"success": bool, "message": str, ...optional fields}
    """
```

Every atom is a single Python file in `atoms/` with one public function: `execute`.

## Naming

Atom names follow `<verb>_<object>` pattern:

| Allowed | Why |
|---------|-----|
| `compute_column` | Verb (compute) + generic object (column) |
| `filter_rows` | Verb (filter) + generic object (rows) |
| `group_aggregate` | Verb (group) + generic modifier (aggregate) |
| `join_tables` | Verb (join) + generic object (tables) |
| `flag_rows` | Verb (flag) + generic object (rows) |
| `rename_columns` | Verb (rename) + generic object (columns) |
| `sort_rows` | Verb (sort) + generic object (rows) |

| Forbidden | Why |
|-----------|-----|
| `sales_reconciliation` | Domain noun — tells you the industry |
| `profit_margin` | Business concept — not an operation |
| `inventory_tracker` | Domain noun — not a verb |
| `catalog_join` | Domain noun (catalog) — use `join_tables` |
| `margin_calculator` | Business concept — use `compute_column` |

**Test:** Could this atom name appear in a generic math textbook? If not, rename it.

## What Goes Into params_json

EVERYTHING specific. The atom receives all context via params:

| Always from params | Never hardcoded |
|-------------------|-----------------|
| Column names to operate on | Real column names in source code |
| File paths (input, output) | Path strings in source code |
| Formulas / expressions | Business logic in source code |
| Thresholds / limits | Magic numbers in source code |
| Aggregation functions | Fixed aggregation choices |
| Output column names | Hardcoded result column names |

## What the Atom Does NOT Know

- What the data represents (revenue? temperature? inventory?)
- What industry it's for (finance? healthcare? retail?)
- Why a threshold is that number (margin below 15%? defect rate above 5%?)
- Which pipeline will use it
- What columns the file actually has (beyond what params declares)
- Where in the pipeline it runs (first step? last step?)

## Litmus Test

Before committing any atom, answer this question:

> "If I rename every column in the test data to A, B, C, D — does the atom still work identically?"

If YES → atom is generic. Ship it.
If NO → atom knows something about the data semantics. Fix it.

## Structure Template

```python
import json
import pandas as pd


def execute(params_json: str) -> str:
    """<One line: generic operation description>

    Params: {<list every param the atom accepts>}
    Returns: {"success": bool, "message": str}
    """
    try:
        params = json.loads(params_json)

        # 1. Read input from params (never hardcoded)
        # 2. Perform ONE operation
        # 3. Write output to params["target_path"]

        return json.dumps({
            "success": True,
            "message": "...",
        })
    except KeyError as e:
        return json.dumps({
            "success": False,
            "message": f"Missing required param: {e}",
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "message": str(e),
        })
```

## One Operation Per Atom

An atom does ONE thing:

| One atom | NOT one atom |
|----------|-------------|
| Join two tables on a key | Join then filter then compute |
| Compute one new column from expression | Compute revenue AND compute margin |
| Flag rows matching a condition | Flag then group then sort |
| Group and aggregate (sum/avg/count) | Group then flag low values |
| Sort by a column | Sort then take top N then rename |
| Rename columns | Rename then write to a special format |

If your atom has two distinct logical steps, split it into two atoms.

## Testing Rules

Every atom MUST have a test. The test:

1. Uses generic column names: `col_a`, `col_b`, `value_1`, `group_col`
2. Creates temporary test data (never reads real business files)
3. Tests success path AND at least one error path
4. Verifies output file contents, not just success flag
5. Never imports business_mapping.json or any pipeline-specific file

```python
def test_compute_column_basic(tmp_path):
    input_csv = tmp_path / "input.csv"
    input_csv.write_text("col_a,col_b\n10,5\n20,3\n")
    output_csv = tmp_path / "output.csv"

    params = {
        "input_file": str(input_csv),
        "expression": "col_a * col_b",
        "output_column": "result",
        "target_path": str(output_csv),
    }

    result = json.loads(execute(json.dumps(params)))
    assert result["success"] is True

    df = pd.read_csv(output_csv)
    assert "result" in df.columns
    assert df["result"].tolist() == [50, 60]
```

## DO

- Accept every column name, threshold, formula, file path via params_json
- Return clear error messages for missing params (KeyError handling)
- Write output to `params["target_path"]`
- Keep atoms under 50 lines of core logic
- Use pandas for CSV operations (it's a project dependency)
- Handle edge cases: empty files, missing columns, type mismatches

## DO NOT

- Import or read `business_mapping.json`
- Import or read `config.json` directly (framework passes config as params)
- Reference any pipeline by name
- Hardcode ANY string that identifies a column, file, threshold, or domain concept
- Use semantic param names: `revenue_column` → use `value_column` or `input_column`
- Know about other atoms or pipeline position
- Write to locations other than `target_path`
- Print to stdout (return results in JSON)
- Import Dagster (atoms are pure Python)

## Relationship to Phases

- Atoms are created ONLY during Phase 5
- Phase 5 receives ONLY the operation description (from atomic_operations.yaml)
- Phase 5 NEVER receives business_mapping.json
- After creation, Gate 5 validator scans atom code for domain leakage:
  ```bash
  python workflow/validators/gate_5_atom_clean.py pipelines/<name>/ .
  ```
- If the validator FAILs, the atom has leaked domain terms. Fix and re-run.
