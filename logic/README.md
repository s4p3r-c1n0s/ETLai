# logic/

## Concept

**Atoms** are generic, reusable, pure core functions. They have zero domain knowledge — they don't know *which* column to join on or *which* field to group by. That's the business pipeline's job.

## Protocol

Every atom module must implement:

```python
def execute(params_json: str) -> str
```

- **Input:** JSON string with atom-specific parameters
- **Output:** JSON string with at minimum `{"success": bool, "message": str}`

## Atoms

### atoms/vlookup.py

Left join between two CSV files on user-specified columns.

**Parameters:** `left_file`, `right_file`, `left_column`, `right_column`, `left_output_columns`, `right_output_columns`, `target_path`

### atoms/groupby.py

Group by a column and count occurrences.

**Parameters:** `input_file`, `group_column`, `target_path`

## Atom vs Business Logic

| | Atom | Business Pipeline |
|---|------|-------------------|
| **Knows which column?** | No | Yes (via config) |
| **Has folder lifecycle?** | No | Yes (inbox → staging → processed/rejected) |
| **Has sensor?** | No | Yes |
| **Reusable across domains?** | Yes | No — specific to one use case |
| **Location** | `logic/atoms/` | `pipeline.py` + `runners/ops.py` + `pipelines/<name>/` |
