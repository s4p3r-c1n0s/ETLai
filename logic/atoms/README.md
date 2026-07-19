# logic/atoms/

Core atoms — generic, reusable, pure functions with zero domain knowledge.

## Protocol

```python
def execute(params_json: str) -> str
```

Input: JSON parameters. Output: JSON with `{"success": bool, "message": str, ...}`.

## Available Atoms

| Atom | File | Purpose |
|------|------|---------|
| vlookup | `vlookup.py` | Left join two CSVs on specified columns |
| groupby | `groupby.py` | Group by a column, return counts |
