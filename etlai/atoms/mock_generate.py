"""Atom: generate synthetic data from source CSV headers, written as a single XLSX."""

import csv
import json
import os

import pandas as pd
from faker import Faker

fake = Faker()

COLUMN_GENERATORS = {
    "name": fake.name,
    "first_name": fake.first_name,
    "last_name": fake.last_name,
    "email": fake.email,
    "phone": fake.phone_number,
    "address": fake.address,
    "city": fake.city,
    "state": fake.state,
    "country": fake.country,
    "zip": fake.zipcode,
    "zipcode": fake.zipcode,
    "date": fake.date,
    "company": fake.company,
    "id": lambda: fake.unique.random_int(min=1000, max=9999),
    "price": lambda: round(fake.pyfloat(min_value=1, max_value=999, right_digits=2), 2),
    "amount": lambda: round(fake.pyfloat(min_value=1, max_value=9999, right_digits=2), 2),
    "quantity": lambda: fake.random_int(min=1, max=100),
}


def _guess_generator(column_name: str):
    col_lower = column_name.lower().strip()
    for key, gen in COLUMN_GENERATORS.items():
        if key in col_lower:
            return gen
    return fake.word


def _read_headers(file_path: str) -> list[str]:
    with open(file_path, "r", newline="") as f:
        reader = csv.reader(f)
        headers = next(reader)
    return [h.strip() for h in headers]


def _sanitize_sheet_name(name: str, fallback: str) -> str:
    """Excel sheet names must be <= 31 chars and free of : \\ / ? * [ ]."""
    invalid = set(':\\/?*[]')
    cleaned = "".join(c for c in name if c not in invalid).strip()
    cleaned = cleaned or fallback
    return cleaned[:31]


def execute(params_json: str) -> str:
    """
    Params: {"input_files": [paths], "target_path": str, "rows": int (optional, default 20)}
    Returns: {"success": bool, "message": str, "row_count": int, "output_file": str}

    Writes a single .xlsx to target_path (extension corrected from .csv), with
    one sheet per input header file. Respects the one-file-per-atom contract.
    """
    try:
        params = json.loads(params_json)
        input_files = params["input_files"]
        target_path = params["target_path"]
        rows = params.get("rows", 20)

        # Always produce a single XLSX file, regardless of the target extension.
        xlsx_path = os.path.splitext(target_path)[0] + ".xlsx"
        os.makedirs(os.path.dirname(xlsx_path), exist_ok=True)

        total_rows = 0
        with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
            for idx, file_path in enumerate(input_files):
                headers = _read_headers(file_path)
                data = [
                    {col: _guess_generator(col)() for col in headers}
                    for _ in range(rows)
                ]
                df = pd.DataFrame(data, columns=headers)
                base = os.path.splitext(os.path.basename(file_path))[0]
                sheet_name = _sanitize_sheet_name(base, f"sheet_{idx}")
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                total_rows += len(df)

        return json.dumps({
            "success": True,
            "message": f"Generated {len(input_files)} sheet(s), {total_rows} row(s) total → {xlsx_path}.",
            "row_count": total_rows,
            "output_file": xlsx_path,
        })
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)})