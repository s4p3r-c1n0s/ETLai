"""Business pipeline pre-processing ops with config init pattern.
First run: shows Tkinter UI, saves config.
Subsequent runs: loads from config, skips UI.
Set reconfigure=true in op config to force UI again."""

from dagster import In, OpExecutionContext, Out, op

from helpers.column_picker import pick_columns
from helpers.config_store import config_exists, load_config, save_config
from helpers.folders import PipelineFolders
from helpers.notifier import notify


def _should_reconfigure(context: OpExecutionContext) -> bool:
    return bool(context.op_config.get("reconfigure")) if context.op_config else False


@op(name="vlookup_rollnumber__pre_process", ins={"file_paths": In(list)}, out={"params": Out()})
def vlookup_rollnumber_pre_process_op(context: OpExecutionContext, file_paths: list[str]) -> dict:
    """Config init for vlookup on roll number. Shows column picker on first run only."""
    folders = PipelineFolders("vlookup_rollnumber")
    reconfigure = _should_reconfigure(context)

    if not reconfigure and config_exists(folders):
        config = load_config(folders)
        context.log.info(f"Loaded saved config: {config}")
        config["left_file"] = file_paths[0]
        config["right_file"] = file_paths[1]
        return config

    context.log.info("No config found or reconfigure requested. Opening column picker...")
    try:
        column_mapping = pick_columns(file_paths[0], file_paths[1])
    except Exception as e:
        folders.move_to_rejected(file_paths, f"Config init cancelled: {e}")
        notify(title="VLOOKUP Roll Number — Failed", message=f"Config cancelled: {e}"[:200])
        raise

    config = {
        "left_column": column_mapping["left_column"],
        "right_column": column_mapping["right_column"],
        "left_output_columns": column_mapping["left_output_columns"],
        "right_output_columns": column_mapping["right_output_columns"],
    }
    save_config(folders, config)
    context.log.info(f"Saved config: {config}")

    config["left_file"] = file_paths[0]
    config["right_file"] = file_paths[1]
    return config


@op(name="groupby_religion__pre_process", ins={"file_paths": In(list)}, out={"params": Out()})
def groupby_religion_pre_process_op(context: OpExecutionContext, file_paths: list[str]) -> dict:
    """Config init for groupby on religion column. Shows picker on first run only."""
    import tkinter as tk
    from tkinter import ttk

    import pandas as pd

    folders = PipelineFolders("groupby_religion")
    reconfigure = _should_reconfigure(context)

    if not reconfigure and config_exists(folders):
        config = load_config(folders)
        context.log.info(f"Loaded saved config: {config}")
        config["input_file"] = file_paths[0]
        return config

    context.log.info("No config found or reconfigure requested. Opening column picker...")
    df = pd.read_csv(file_paths[0], nrows=5)
    columns = list(df.columns)

    result = {}

    root = tk.Tk()
    root.title("Select Group By Column")
    root.attributes("-topmost", True)
    root.resizable(False, False)

    frame = ttk.Frame(root, padding=20)
    frame.grid(row=0, column=0)

    ttk.Label(frame, text="Select column to group by:", font=("TkDefaultFont", 11, "bold")).grid(
        row=0, column=0, sticky="w", pady=(0, 5)
    )

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
        folders.move_to_rejected(file_paths, "Config init cancelled by user.")
        notify(title="GroupBy Religion — Failed", message="Config cancelled by user.")
        raise RuntimeError("Column selection cancelled by user.")

    config = {"group_column": result["group_column"]}
    save_config(folders, config)
    context.log.info(f"Saved config: {config}")

    config["input_file"] = file_paths[0]
    return config


@op(name="mock_generator__pre_process", ins={"file_paths": In(list)}, out={"params": Out()})
def mock_generator_pre_process_op(context: OpExecutionContext, file_paths: list[str]) -> dict:
    """Passthrough for mock generator — passes all input files."""
    folders = PipelineFolders("mock_generator")
    return {"input_files": file_paths, "target_path": folders.output}
