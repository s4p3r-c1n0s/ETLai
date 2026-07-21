"""Atom: generate synthetic CSV data from source file headers using Faker."""

import csv
import json
import os

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


def execute(params_json: str) -> str:
    """
    Params: {"input_files": [paths], "target_path": dir, "rows": int (optional, default 20)}
    Returns: {"success": bool, "message": str, "output_files": [paths]}
    """
    try:
        params = json.loads(params_json)
        input_files = params["input_files"]
        target_path = params["target_path"]
        rows = params.get("rows", 20)

        generated = []
        for file_path in input_files:
            headers = _read_headers(file_path)
            basename = os.path.basename(file_path)
            output_path = os.path.join(target_path, f"mock_{basename}")
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                for _ in range(rows):
                    writer.writerow({col: _guess_generator(col)() for col in headers})
            generated.append(output_path)

        return json.dumps({"success": True, "message": f"Generated {len(generated)} mock file(s) with {rows} rows each.", "output_files": generated})
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)})
