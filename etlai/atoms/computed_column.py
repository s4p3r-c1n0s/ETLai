"""Atom: Compute a new column from a pandas expression."""

import json

import pandas as pd


def execute(params_json: str) -> str:
    """
    Evaluate an expression against existing columns, write result as a new column.

    Params: {"input_file", "expression", "output_column", "target_path"}
    Returns: {"success": bool, "row_count": int, "message": str}
    """
    try:
        params = json.loads(params_json)
        input_file = params["input_file"]
        expression = params["expression"]
        output_column = params["output_column"]
        target_path = params["target_path"]

        df = pd.read_csv(input_file)
        df[output_column] = df.eval(expression)
        df.to_csv(target_path, index=False)

        return json.dumps({
            "success": True,
            "row_count": len(df),
            "message": f"Computed '{output_column}' from expression '{expression}'. {len(df)} rows written.",
        })
    except KeyError as e:
        return json.dumps({"success": False, "row_count": 0, "message": f"Missing required param: {e}"})
    except Exception as e:
        return json.dumps({"success": False, "row_count": 0, "message": str(e)})
