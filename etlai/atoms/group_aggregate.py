"""Atom: Group by a column and aggregate with specified functions."""

import json

import pandas as pd


def execute(params_json: str) -> str:
    """
    Group rows by a column, apply aggregation functions to specified columns.

    Params: {
        "input_file", "group_column",
        "aggregations": [{"column": str, "function": str, "output_column": str}, ...],
        "target_path"
    }
    Supported functions: sum, mean, min, max, count, first, last
    Returns: {"success": bool, "row_count": int, "message": str}
    """
    try:
        params = json.loads(params_json)
        input_file = params["input_file"]
        group_column = params["group_column"]
        aggregations = params["aggregations"]
        target_path = params["target_path"]

        df = pd.read_csv(input_file)

        if group_column not in df.columns:
            return json.dumps({
                "success": False,
                "row_count": 0,
                "message": f"Group column '{group_column}' not found in file.",
            })

        agg_dict = {}
        rename_map = {}
        for agg in aggregations:
            col = agg["column"]
            func = agg["function"]
            out_col = agg.get("output_column", f"{col}_{func}")

            if col not in df.columns:
                return json.dumps({
                    "success": False,
                    "row_count": 0,
                    "message": f"Aggregation column '{col}' not found in file.",
                })

            agg_dict[col] = func
            rename_map[col] = out_col

        grouped = df.groupby(group_column).agg(agg_dict).reset_index()
        grouped.rename(columns=rename_map, inplace=True)
        grouped.to_csv(target_path, index=False)

        return json.dumps({
            "success": True,
            "row_count": len(grouped),
            "message": f"Grouped by '{group_column}'. {len(grouped)} groups written.",
        })
    except KeyError as e:
        return json.dumps({"success": False, "row_count": 0, "message": f"Missing required param: {e}"})
    except Exception as e:
        return json.dumps({"success": False, "row_count": 0, "message": str(e)})
