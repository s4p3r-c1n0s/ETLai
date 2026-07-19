"""Composite pipelines using Dagster graph composition — chain atoms in a single job."""

import json
import os

from dagster import In, OpExecutionContext, Out, graph, job, op

from helpers.config_store import config_exists, load_config, save_config
from helpers.folders import PipelineFolders
from helpers.notifier import notify
from logic.atoms import groupby, vlookup


PIPELINE_NAME = "vlookup_then_groupby"
_folders = PipelineFolders(PIPELINE_NAME)


@op(name="vtg__load_files", out={"file_paths": Out()})
def vtg_load_files_op(context: OpExecutionContext) -> list[str]:
    """Load files from config or scan inbox."""
    import re
    config_paths = context.op_config.get("file_paths") if context.op_config else None
    if config_paths:
        return config_paths
    pattern = re.compile(r"^(.+)\.(csv|xlsx)$", re.IGNORECASE)
    paths = _folders.list_inbox_files(pattern)
    if len(paths) < 2:
        raise RuntimeError(f"Need 2 files in {_folders.inbox}, found {len(paths)}.")
    return paths[:2]


@op(name="vtg__vlookup", ins={"file_paths": In(list)}, out={"vlookup_output": Out()})
def vtg_vlookup_op(context: OpExecutionContext, file_paths: list[str]) -> str:
    """Run vlookup atom using saved config, output intermediate file."""
    from helpers.column_picker import pick_columns

    reconfigure = bool(context.op_config.get("reconfigure")) if context.op_config else False

    if not reconfigure and config_exists(_folders):
        config = load_config(_folders)
        context.log.info(f"Loaded config: {config}")
    else:
        context.log.info("Opening column picker for vlookup config...")
        try:
            mapping = pick_columns(file_paths[0], file_paths[1])
        except Exception as e:
            _folders.move_to_rejected(file_paths, f"Config cancelled: {e}")
            notify(title=f"{PIPELINE_NAME} — Failed", message=str(e)[:200])
            raise

        config = {
            "left_column": mapping["left_column"],
            "right_column": mapping["right_column"],
            "left_output_columns": mapping["left_output_columns"],
            "right_output_columns": mapping["right_output_columns"],
        }
        save_config(_folders, config)

    intermediate_path = os.path.join(_folders.output, "_vlookup_intermediate.csv")
    params = {
        "left_file": file_paths[0],
        "right_file": file_paths[1],
        "left_column": config["left_column"],
        "right_column": config["right_column"],
        "left_output_columns": config["left_output_columns"],
        "right_output_columns": config["right_output_columns"],
        "target_path": intermediate_path,
    }

    result = json.loads(vlookup.execute(json.dumps(params)))
    if not result["success"]:
        _folders.move_to_rejected(file_paths, f"VLOOKUP failed: {result['message']}")
        notify(title=f"{PIPELINE_NAME} — Failed", message=result["message"][:200])
        raise RuntimeError(f"VLOOKUP failed: {result['message']}")

    context.log.info(f"VLOOKUP step: {result['message']}")
    return intermediate_path


@op(name="vtg__groupby", ins={"file_paths": In(list), "vlookup_output": In(str)})
def vtg_groupby_op(context: OpExecutionContext, file_paths: list[str], vlookup_output: str) -> None:
    """Run groupby on the vlookup output, using a saved group_column or picking one."""
    import tkinter as tk
    from tkinter import ttk

    import pandas as pd

    config = load_config(_folders) or {}
    reconfigure = bool(context.op_config.get("reconfigure")) if context.op_config else False
    group_column = config.get("group_column")

    if not group_column or reconfigure:
        df = pd.read_csv(vlookup_output, nrows=5)
        columns = list(df.columns)
        result = {}

        root = tk.Tk()
        root.title("Select Group By Column (Composite)")
        root.attributes("-topmost", True)
        root.resizable(False, False)

        frame = ttk.Frame(root, padding=20)
        frame.grid(row=0, column=0)
        ttk.Label(frame, text="Select column to group by:", font=("TkDefaultFont", 11, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 5))
        listbox = tk.Listbox(frame, width=40, height=10, exportselection=False)
        for col in columns:
            listbox.insert(tk.END, f"{col}  ({df[col].dtype})")
        listbox.grid(row=1, column=0)

        status_label = ttk.Label(frame, text="", foreground="red")
        status_label.grid(row=2, column=0, pady=(10, 0))

        def on_confirm():
            sel = listbox.curselection()
            if not sel:
                status_label.config(text="Please select a column.")
                return
            result["group_column"] = columns[sel[0]]
            root.destroy()

        def on_cancel():
            root.destroy()

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, pady=(15, 0))
        ttk.Button(btn_frame, text="Confirm", command=on_confirm).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=on_cancel).pack(side="left", padx=5)
        root.mainloop()

        if not result:
            _folders.move_to_rejected(file_paths, "GroupBy config cancelled.")
            notify(title=f"{PIPELINE_NAME} — Failed", message="GroupBy cancelled.")
            raise RuntimeError("GroupBy column selection cancelled.")

        group_column = result["group_column"]
        config["group_column"] = group_column
        save_config(_folders, config)

    final_output = _folders.output_path("output.csv")
    params = {
        "input_file": vlookup_output,
        "group_column": group_column,
        "target_path": final_output,
    }

    gb_result = json.loads(groupby.execute(json.dumps(params)))
    if not gb_result["success"]:
        _folders.move_to_rejected(file_paths, f"GroupBy failed: {gb_result['message']}")
        notify(title=f"{PIPELINE_NAME} — Failed", message=gb_result["message"][:200])
        raise RuntimeError(f"GroupBy failed: {gb_result['message']}")

    context.log.info(f"GroupBy step: {gb_result['message']}")

    _folders.move_to_processed(file_paths)
    notify(
        title=f"{PIPELINE_NAME} — Success",
        message=gb_result["message"][:200],
        open_folder=_folders.output,
    )


@job(name=PIPELINE_NAME)
def vlookup_then_groupby():
    """Composite: VLOOKUP by roll number → GroupBy on result."""
    file_paths = vtg_load_files_op()
    vlookup_output = vtg_vlookup_op(file_paths)
    vtg_groupby_op(file_paths, vlookup_output)
