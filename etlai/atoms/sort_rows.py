"""Atom: Sort rows by one or more columns."""

import json

import pandas as pd


def execute(params_json: str) -> str:
    """
    Sort a CSV by specified columns.

    Params: {"input_file", "sort_columns": [str], "ascending": bool|[bool], "target_path"}
    ascending defaults to True if not provided.
    Returns: {"success": bool, "row_count": int, "message": str}
    """
    try:
        params = json.loads(params_json)
        input_file = params["input_file"]
        sort_columns = params["sort_columns"]
        ascending = params.get("ascending", True)
        target_path = params["target_path"]

        df = pd.read_csv(input_file)

        for col in sort_columns:
            if col not in df.columns:
                return json.dumps({
                    "success": False,
                    "row_count": 0,
                    "message": f"Sort column '{col}' not found in file.",
                })

        df = df.sort_values(by=sort_columns, ascending=ascending).reset_index(drop=True)
        df.to_csv(target_path, index=False)

        return json.dumps({
            "success": True,
            "row_count": len(df),
            "message": f"Sorted by {sort_columns}. {len(df)} rows written.",
        })
    except KeyError as e:
        return json.dumps({"success": False, "row_count": 0, "message": f"Missing required param: {e}"})
    except Exception as e:
        return json.dumps({"success": False, "row_count": 0, "message": str(e)})
