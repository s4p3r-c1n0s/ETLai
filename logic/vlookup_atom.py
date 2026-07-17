"""Pure business logic atom: performs a VLOOKUP-equivalent left join. Zero framework dependencies."""

import json

import pandas as pd


def vlookup(params_json: str) -> str:
    """
    Accepts JSON: {"left_file", "right_file", "lookup_column", "output_columns", "target_path"}
    Returns JSON: {"success": bool, "row_count": int, "message": str}
    """
    try:
        params = json.loads(params_json)
        left_file = params["left_file"]
        right_file = params["right_file"]
        lookup_column = params["lookup_column"]
        output_columns = params["output_columns"]
        target_path = params["target_path"]

        left_df = pd.read_csv(left_file)
        right_df = pd.read_csv(right_file)

        for col_name in [lookup_column] + output_columns:
            if col_name not in left_df.columns and col_name not in right_df.columns:
                return json.dumps({
                    "success": False,
                    "row_count": 0,
                    "message": f"Column '{col_name}' not found in either file.",
                })

        if lookup_column not in left_df.columns:
            return json.dumps({
                "success": False,
                "row_count": 0,
                "message": f"Lookup column '{lookup_column}' not found in left file.",
            })

        if lookup_column not in right_df.columns:
            return json.dumps({
                "success": False,
                "row_count": 0,
                "message": f"Lookup column '{lookup_column}' not found in right file.",
            })

        right_subset = right_df[[lookup_column] + [c for c in output_columns if c in right_df.columns]]
        merged = left_df.merge(right_subset, on=lookup_column, how="left")

        keep_cols = list(left_df.columns) + [c for c in output_columns if c not in left_df.columns]
        merged = merged[[c for c in keep_cols if c in merged.columns]]

        merged.to_csv(target_path, index=False)

        return json.dumps({
            "success": True,
            "row_count": len(merged),
            "message": f"VLOOKUP complete. {len(merged)} rows written to {target_path}.",
        })

    except Exception as e:
        return json.dumps({"success": False, "row_count": 0, "message": str(e)})
