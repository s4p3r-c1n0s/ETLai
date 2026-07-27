"""Atom: Filter rows by a condition expression."""

import json

import pandas as pd


def execute(params_json: str) -> str:
    """
    Keep only rows where a condition evaluates to True.

    Params: {"input_file", "condition", "target_path"}
    condition: a pandas query expression (e.g., "col_a > 10", "col_b == 'active'")
    Returns: {"success": bool, "row_count": int, "rows_removed": int, "message": str}
    """
    try:
        params = json.loads(params_json)
        input_file = params["input_file"]
        condition = params["condition"]
        target_path = params["target_path"]

        df = pd.read_csv(input_file)
        original_count = len(df)

        filtered = df.query(condition)
        filtered.to_csv(target_path, index=False)

        removed = original_count - len(filtered)
        return json.dumps({
            "success": True,
            "row_count": len(filtered),
            "rows_removed": removed,
            "message": f"Filtered by '{condition}'. {len(filtered)} rows kept, {removed} removed.",
        })
    except KeyError as e:
        return json.dumps({"success": False, "row_count": 0, "rows_removed": 0, "message": f"Missing required param: {e}"})
    except Exception as e:
        return json.dumps({"success": False, "row_count": 0, "rows_removed": 0, "message": str(e)})
