"""Core atom: generates synthetic CSV data from real file headers. Zero domain knowledge."""

import csv
import json
import os

from faker import Faker

fake = Faker()

COLUMN_GENERATORS = {
    "name": fake.name,
    "first_name": fake.first_name,
    "first name": fake.first_name,
    "last_name": fake.last_name,
    "last name": fake.last_name,
    "middle_name": lambda: fake.first_name(),
    "middle name": lambda: fake.first_name(),
    "email": fake.email,
    "phone": fake.phone_number,
    "address": fake.address,
    "city": fake.city,
    "state": fake.state,
    "country": fake.country,
    "zip": fake.zipcode,
    "zipcode": fake.zipcode,
    "date": fake.date,
    "birth date": fake.date,
    "birth_date": fake.date,
    "company": fake.company,
    "id": lambda: fake.unique.random_int(min=1000, max=9999),
    "roll number": lambda: fake.random_int(min=100, max=999),
    "roll_number": lambda: fake.random_int(min=100, max=999),
    "religion": lambda: fake.random_element(["Hindu", "Muslim", "Christian", "Sikh", "Buddhist", "Jain"]),
    "gender": lambda: fake.random_element(["Male", "Female"]),
    "section": lambda: fake.random_element(["A", "B", "C", "D"]),
    "subject": lambda: fake.random_element(["Mathematics", "Science", "English", "History", "Geography"]),
    "marks": lambda: fake.random_int(min=30, max=100),
    "testtype": lambda: fake.random_element(["Midterm", "Final", "Quiz"]),
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


def execute(params_json: str) -> str:
    """
    Accepts JSON: {"input_files": [paths...], "target_path": str, "rows": int}
    Reads headers from each input file, generates mock data, writes to target_path dir.
    Returns JSON: {"success": bool, "message": str, "output_files": [paths...]}
    """
    try:
        params = json.loads(params_json)
        input_files = params["input_files"]
        target_dir = params["target_path"]
        rows = params.get("rows", 50)

        os.makedirs(target_dir, exist_ok=True)
        output_files = []

        for input_file in input_files:
            if not os.path.isfile(input_file):
                return json.dumps({
                    "success": False,
                    "message": f"File not found: {input_file}",
                    "output_files": [],
                })

            with open(input_file, "r", newline="") as f:
                reader = csv.reader(f)
                headers = [h.strip() for h in next(reader)]

            basename = os.path.basename(input_file)
            mock_name = f"mock_{basename}"
            output_path = os.path.join(target_dir, mock_name)

            with open(output_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                for _ in range(rows):
                    writer.writerow({col: _guess_generator(col)() for col in headers})

            output_files.append(output_path)

        return json.dumps({
            "success": True,
            "message": f"Generated {len(output_files)} mock files with {rows} rows each.",
            "output_files": output_files,
        })

    except Exception as e:
        return json.dumps({"success": False, "message": str(e), "output_files": []})
