# Air-Gapped Desktop Automation Engine

A modular, 4-layer Dagster pipeline that performs Excel-style VLOOKUP operations entirely on your local machine — no data ever leaves your desktop.

## Architecture

```
Layer 1: pipeline.py          → Dagster @job (UI & orchestration)
Layer 2: logic/vlookup_atom.py → Pure business logic (JSON-in, JSON-out)
Layer 3: runners/ops.py       → Dagster @op adapters (bridge UI ↔ logic)
Layer 4: helpers/              → Input harvesters & air-gap utilities
```

**Why 4 layers?** Business logic in Layer 2 is completely decoupled from frameworks and file I/O details. It can be unit-tested and audited by an AI without ever touching your real data.

## Quick Start

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Generate mock data (air-gap step)

Before running the pipeline, generate safe synthetic test data from your real files:

```bash
python -m helpers.mock_generator path/to/your_file_A.csv path/to/your_file_B.csv
```

This reads ONLY the column headers from your files, then creates `data/mock_file_A.csv` and `data/mock_file_B.csv` with 20 rows of realistic fake data.

### 3. Launch the Dagster dashboard

```bash
dagster dev -f pipeline.py
```

Open your browser to **http://localhost:3000**. You will see the `vlookup_pipeline` job.

### 4. Configure and run

In the Dagster Launchpad, configure the job:

```yaml
ops:
  vlookup_op:
    config:
      lookup_column: "id"              # Column to join on
      output_columns: ["name", "email"] # Columns to pull from the right file
      target_path: "data/output.csv"   # Where to save results
```

Click **Launch Run**. A file picker dialog will appear — select your two source CSVs.

### 5. Check results

- The Dagster UI shows run status, logs, and metadata (row count, output path).
- Your merged output is saved to the configured `target_path`.
- If a column is missing, the error trace appears directly in the Dagster run log.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| "Column not found" error | Check the column name in your config matches the CSV header exactly (case-sensitive) |
| File picker doesn't appear | Ensure you're running on a desktop environment with display access |
| Import errors | Verify you activated the `.venv` and ran `pip install -r requirements.txt` |

## File Structure

```
├── .gitignore
├── .claudeignore           # Prevents AI from reading real data files
├── requirements.txt
├── pipeline.py             # Layer 1: Dagster job definition
├── logic/
│   └── vlookup_atom.py    # Layer 2: Pure VLOOKUP function
├── runners/
│   └── ops.py             # Layer 3: Dagster @op wrappers
├── helpers/
│   ├── file_picker.py     # Layer 4: Tkinter file dialog
│   └── mock_generator.py  # Layer 4: Synthetic data generator
└── data/                   # Output directory (git-ignored via .claudeignore)
```
