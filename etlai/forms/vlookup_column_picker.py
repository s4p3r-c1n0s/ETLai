"""Form: join column + output column selection for vlookup pipelines."""

import tkinter as tk
from tkinter import messagebox, ttk

import pandas as pd


def configure(file_paths: list[str], existing_config: dict | None) -> dict:
    """Show column picker UI or return existing config if valid."""
    if existing_config and _is_valid(existing_config, file_paths):
        return existing_config

    left_file, right_file = file_paths[0], file_paths[1]
    left_df = pd.read_csv(left_file, nrows=5)
    right_df = pd.read_csv(right_file, nrows=5)

    left_cols = list(left_df.columns)
    right_cols = list(right_df.columns)
    left_dtypes = {col: str(left_df[col].dtype) for col in left_cols}
    right_dtypes = {col: str(right_df[col].dtype) for col in right_cols}

    result = {}

    root = tk.Tk()
    root.title("Select Lookup Columns")
    root.attributes("-topmost", True)
    root.resizable(False, False)

    frame = ttk.Frame(root, padding=20)
    frame.grid(row=0, column=0, sticky="nsew")

    ttk.Label(frame, text="Join column (left file):", font=("TkDefaultFont", 11, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 5))
    left_listbox = tk.Listbox(frame, width=35, height=8, exportselection=False)
    for col in left_cols:
        left_listbox.insert(tk.END, f"{col}  ({left_dtypes[col]})")
    left_listbox.grid(row=1, column=0, padx=(0, 10))

    ttk.Label(frame, text="Join column (right file):", font=("TkDefaultFont", 11, "bold")).grid(row=0, column=1, sticky="w", pady=(0, 5))
    right_listbox = tk.Listbox(frame, width=35, height=8, exportselection=False)
    for col in right_cols:
        right_listbox.insert(tk.END, f"{col}  ({right_dtypes[col]})")
    right_listbox.grid(row=1, column=1)

    ttk.Separator(frame, orient="horizontal").grid(row=2, column=0, columnspan=2, sticky="ew", pady=(15, 10))

    ttk.Label(frame, text="Output columns from left file:", font=("TkDefaultFont", 11, "bold")).grid(row=3, column=0, sticky="w", pady=(0, 5))
    left_output_listbox = tk.Listbox(frame, width=35, height=8, selectmode=tk.MULTIPLE, exportselection=False)
    for col in left_cols:
        left_output_listbox.insert(tk.END, f"{col}  ({left_dtypes[col]})")
    left_output_listbox.grid(row=4, column=0, padx=(0, 10))

    ttk.Label(frame, text="Output columns from right file:", font=("TkDefaultFont", 11, "bold")).grid(row=3, column=1, sticky="w", pady=(0, 5))
    right_output_listbox = tk.Listbox(frame, width=35, height=8, selectmode=tk.MULTIPLE, exportselection=False)
    for col in right_cols:
        right_output_listbox.insert(tk.END, f"{col}  ({right_dtypes[col]})")
    right_output_listbox.grid(row=4, column=1)

    status_label = ttk.Label(frame, text="", foreground="red")
    status_label.grid(row=5, column=0, columnspan=2, pady=(10, 0))

    def on_confirm():
        left_sel = left_listbox.curselection()
        right_sel = right_listbox.curselection()
        left_out_sel = left_output_listbox.curselection()
        right_out_sel = right_output_listbox.curselection()

        if not left_sel or not right_sel:
            status_label.config(text="Please select a join column from each list.")
            return
        if not left_out_sel and not right_out_sel:
            status_label.config(text="Please select at least one output column.")
            return

        left_col = left_cols[left_sel[0]]
        right_col = right_cols[right_sel[0]]

        if left_dtypes[left_col] != right_dtypes[right_col]:
            messagebox.showerror("Data Type Mismatch",
                f"Cannot join: left '{left_col}' is {left_dtypes[left_col]}, right '{right_col}' is {right_dtypes[right_col]}.")
            return

        result["left_column"] = left_col
        result["right_column"] = right_col
        result["left_output_columns"] = [left_cols[i] for i in left_out_sel]
        result["right_output_columns"] = [right_cols[i] for i in right_out_sel]
        root.destroy()

    def on_cancel():
        root.destroy()

    btn_frame = ttk.Frame(frame)
    btn_frame.grid(row=6, column=0, columnspan=2, pady=(15, 0))
    ttk.Button(btn_frame, text="Confirm", command=on_confirm).pack(side="left", padx=5)
    ttk.Button(btn_frame, text="Cancel", command=on_cancel).pack(side="left", padx=5)

    root.mainloop()

    if not result:
        raise RuntimeError("Column selection cancelled by user.")

    return result


def _is_valid(config: dict, file_paths: list[str]) -> bool:
    required = ["left_column", "right_column", "left_output_columns", "right_output_columns"]
    return all(k in config for k in required)
