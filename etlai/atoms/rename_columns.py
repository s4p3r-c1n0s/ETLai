"""Atom: Rename columns using a provided mapping."""

import json

import pandas as pd


def execute(params_json: str) -> str:
    """
    Rename columns in a CSV using a mapping dict.

    Params: {"input_file", "mapping": {"old_name": "new_name", ...}, "target_path"}
    Returns: {"success": bool, "row_count": int, "columns_renamed": int, "message": str}
    """
    try:
        params = json.loads(params_json)
        input_file = params["input_file"]
        mapping = params["mapping"]
        target_path = params["target_path"]

        df = pd.read_csv(input_file)
        renamed_count = sum(1 for col in mapping if col in df.columns)
        df = df.rename(columns=mapping)
        df.to_csv(target_path, index=False)

        return json.dumps({
            "success": True,
            "row_count": len(df),
            "columns_renamed": renamed_count,
            "message": f"Renamed {renamed_count} columns. {len(df)} rows written.",
        })
    except KeyError as e:
        return json.dumps({"success": False, "row_count": 0, "columns_renamed": 0, "message": f"Missing required param: {e}"})
    except Exception as e:
        return json.dumps({"success": False, "row_count": 0, "columns_renamed": 0, "message": str(e)})
