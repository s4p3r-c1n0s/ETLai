"""Core atom: performs a GROUP BY with count on a specified column. Zero domain knowledge."""

import json

import pandas as pd


def execute(params_json: str) -> str:
    """
    Accepts JSON: {"input_file", "group_column", "target_path"}
    Returns JSON: {"success": bool, "row_count": int, "message": str}
    """
    try:
        params = json.loads(params_json)
        input_file = params["input_file"]
        group_column = params["group_column"]
        target_path = params["target_path"]

        df = pd.read_csv(input_file)

        if group_column not in df.columns:
            return json.dumps({
                "success": False,
                "row_count": 0,
                "message": f"Column '{group_column}' not found in file.",
            })

        grouped = df.groupby(group_column).size().reset_index(name="count")
        grouped = grouped.sort_values("count", ascending=False)
        grouped.to_csv(target_path, index=False)

        return json.dumps({
            "success": True,
            "row_count": len(grouped),
            "message": f"GROUP BY complete. {len(grouped)} groups written to {target_path}.",
        })

    except Exception as e:
        return json.dumps({"success": False, "row_count": 0, "message": str(e)})
