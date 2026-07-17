"""Tkinter-native file picker for selecting source CSV files."""

import tkinter as tk
from tkinter import filedialog


def pick_files(count: int = 2) -> list[str]:
    """Open file dialogs to select CSV files. Returns list of selected paths."""
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    selected = []
    for i in range(count):
        path = filedialog.askopenfilename(
            title=f"Select source file {i + 1} of {count}",
            filetypes=[("CSV files", "*.csv"), ("Excel files", "*.xlsx"), ("All files", "*.*")],
        )
        if not path:
            root.destroy()
            raise FileNotFoundError(f"File selection cancelled at file {i + 1}.")
        selected.append(path)

    root.destroy()
    return selected


if __name__ == "__main__":
    files = pick_files()
    for i, f in enumerate(files, 1):
        print(f"File {i}: {f}")
