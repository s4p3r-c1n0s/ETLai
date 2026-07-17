"""Air-Gap Shield: generates synthetic data from real CSV headers without exposing actual data."""

import csv
import os
import sys
from pathlib import Path

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


def read_headers(file_path: str) -> list[str]:
    with open(file_path, "r", newline="") as f:
        reader = csv.reader(f)
        headers = next(reader)
    return [h.strip() for h in headers]


def generate_mock(headers: list[str], output_path: str, rows: int = 20) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for _ in range(rows):
            writer.writerow({col: _guess_generator(col)() for col in headers})


def main():
    if len(sys.argv) != 3:
        print("Usage: python -m helpers.mock_generator <path_to_file_A.csv> <path_to_file_B.csv>")
        sys.exit(1)

    file_a, file_b = sys.argv[1], sys.argv[2]

    for path in (file_a, file_b):
        if not Path(path).exists():
            print(f"ERROR: File not found: {path}")
            sys.exit(1)

    headers_a = read_headers(file_a)
    headers_b = read_headers(file_b)

    output_a = "data/mock_file_A.csv"
    output_b = "data/mock_file_B.csv"

    generate_mock(headers_a, output_a)
    generate_mock(headers_b, output_b)

    print("=" * 60)
    print("AIR-GAP MOCK GENERATION COMPLETE")
    print("=" * 60)
    print(f"\nFile A columns ({Path(file_a).name}):")
    print(f"  {headers_a}")
    print(f"\nFile B columns ({Path(file_b).name}):")
    print(f"  {headers_b}")
    print(f"\nMock outputs written to:")
    print(f"  → {output_a}")
    print(f"  → {output_b}")
    print("\n📋 Copy the column lists above and share them with Claude.")


if __name__ == "__main__":
    main()
