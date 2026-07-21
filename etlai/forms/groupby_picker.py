"""Form: single column selection for group-by pipelines."""

import tkinter as tk
from tkinter import ttk

import pandas as pd


def configure(file_paths: list[str], existing_config: dict | None) -> dict:
    """Show group column picker UI or return existing config if valid."""
    if existing_config and "group_column" in existing_config:
        return existing_config

    df = pd.read_csv(file_paths[0], nrows=5)
    columns = list(df.columns)

    result = {}

    root = tk.Tk()
    root.title("Select Group By Column")
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
        raise RuntimeError("Column selection cancelled by user.")

    return result
