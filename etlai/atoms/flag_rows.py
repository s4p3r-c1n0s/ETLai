"""Atom: Add a boolean flag column based on a condition."""

import json

import pandas as pd


def execute(params_json: str) -> str:
    """
    Add a boolean column where a condition is True. Keeps ALL rows.

    Params: {"input_file", "condition", "output_column", "target_path"}
    condition: a pandas eval expression (e.g., "col_a < 15", "col_b > col_c")
    Returns: {"success": bool, "row_count": int, "flagged_count": int, "message": str}
    """
    try:
        params = json.loads(params_json)
        input_file = params["input_file"]
        condition = params["condition"]
        output_column = params["output_column"]
        target_path = params["target_path"]

        df = pd.read_csv(input_file)
        df[output_column] = df.eval(condition)
        flagged = df[output_column].sum()
        df.to_csv(target_path, index=False)

        return json.dumps({
            "success": True,
            "row_count": len(df),
            "flagged_count": int(flagged),
            "message": f"Flagged {int(flagged)}/{len(df)} rows where '{condition}'.",
        })
    except KeyError as e:
        return json.dumps({"success": False, "row_count": 0, "flagged_count": 0, "message": f"Missing required param: {e}"})
    except Exception as e:
        return json.dumps({"success": False, "row_count": 0, "flagged_count": 0, "message": str(e)})
