"""Atom: VLOOKUP-equivalent left join between two CSV files."""

import json

import pandas as pd


def execute(params_json: str) -> str:
    """
    Params: {"left_file", "right_file", "left_column", "right_column",
             "left_output_columns", "right_output_columns", "target_path"}
    Returns: {"success": bool, "row_count": int, "message": str}
    """
    try:
        params = json.loads(params_json)
        left_file = params["left_file"]
        right_file = params["right_file"]
        left_column = params["left_column"]
        right_column = params["right_column"]
        left_output_columns = params["left_output_columns"]
        right_output_columns = params["right_output_columns"]
        target_path = params["target_path"]

        left_df = pd.read_csv(left_file)
        right_df = pd.read_csv(right_file)

        if left_column not in left_df.columns:
            return json.dumps({"success": False, "row_count": 0, "message": f"Column '{left_column}' not found in left file."})

        if right_column not in right_df.columns:
            return json.dumps({"success": False, "row_count": 0, "message": f"Column '{right_column}' not found in right file."})

        if left_df[left_column].dtype != right_df[right_column].dtype:
            return json.dumps({
                "success": False, "row_count": 0,
                "message": f"Data type mismatch: left '{left_column}' is {left_df[left_column].dtype}, right '{right_column}' is {right_df[right_column].dtype}.",
            })

        right_merge_cols = [right_column] + [c for c in right_output_columns if c in right_df.columns]
        right_subset = right_df[list(dict.fromkeys(right_merge_cols))]
        merged = left_df.merge(right_subset, left_on=left_column, right_on=right_column, how="left")

        if right_column != left_column:
            merged = merged.drop(columns=[right_column], errors="ignore")

        final_cols = [c for c in left_output_columns if c in merged.columns]
        final_cols += [c for c in right_output_columns if c in merged.columns and c not in final_cols]
        merged = merged[final_cols]
        merged.to_csv(target_path, index=False)

        return json.dumps({"success": True, "row_count": len(merged), "message": f"VLOOKUP complete. {len(merged)} rows written to {target_path}."})
    except Exception as e:
        return json.dumps({"success": False, "row_count": 0, "message": str(e)})
