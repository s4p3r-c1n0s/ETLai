# Phase 3 — Atomize

## Purpose

Break each logical graph node into the smallest possible single-operation chunks. Each chunk maps to exactly one atom. No chunk performs more than one verb.

## Input

- `logical_graph.yaml` from Phase 2

## Output

- `atomic_operations.yaml` — ordered list of single-operation chunks with dependencies

## Process

1. For each node in logical_graph.yaml, ask: "Does this node contain more than one verb?"
2. If yes, split it. Repeat until every entry has exactly ONE operation verb.
3. Assign sequential IDs: op_1, op_2, op_3, etc.
4. For each operation, define: input_columns (what it reads), output_columns (what it produces/modifies).
5. Set depends_on: which prior operation IDs must complete before this one can run.
6. Verify the DAG: no cycles, every input_column is either from a data source or a prior operation's output.
7. Verify the final operation's output_columns cover everything the pipeline is expected to produce.

## Done When

- Every entry has exactly ONE operation verb
- The split test passes for every entry: "Can this be split further?" → No
- The DAG is valid: no cycles, no orphan columns
- Every input_column traces back to either a source or a prior output_column
- Total output covers the pipeline's expected result

## Splitting Rules

These operations are ATOMIC (one verb, cannot split further):
- `join` — merge two datasets on a key
- `compute` — create one new column from an expression
- `group` — group rows by a column with one aggregation function per output
- `filter` — remove rows that don't match a condition
- `flag` — add a boolean column based on a condition (keeps all rows)
- `sort` — reorder rows by a column
- `rename` — change column names (one batch operation is fine)
- `aggregate` — reduce grouped rows to summary (sum, avg, count, min, max) for ONE metric

These are COMPOUND (must split):
- "compute margin and flag low margin" → `compute` + `flag`
- "group by category and calculate sum of revenue and sum of cost" → `aggregate(revenue)` + `aggregate(cost)` OR one `group` with multiple aggregations if the atom supports it
- "join and then filter" → `join` + `filter`
- "compute revenue, compute margin, flag" → `compute` + `compute` + `flag`

## DO

- Split aggressively — two simple operations are better than one complex one
- Preserve column lineage: op_1 creates col_x, op_2 reads col_x → depends_on: [op_1]
- Keep operations in execution order (op_1 before op_2 before op_3)
- If an aggregation has multiple functions on multiple columns, check if one atom can handle it (groupby_aggregate with list of aggregations) — if so, keep as one entry

## DO NOT

- Create compound operations ("join and compute" is NEVER one entry)
- Use domain language — this file uses the same generic placeholders as logical_graph.yaml
- Add operations that weren't in the logical graph (don't optimize or add steps)
- Remove operations that were in the logical graph (don't skip steps)
- Assume an atom exists for this operation yet — that's Phase 4's job
- Add a rename/rehydration step here — that's Phase 7's job (it will be added during Phase 6)

## Dependency Example

```yaml
operations:
  - id: op_1
    operation: join
    params: {left_key: col_a, right_key: col_b, select_from_right: [col_c]}
    input_columns: [col_a, col_b, col_c]
    output_columns: [col_a, col_c, col_d, col_e]
    depends_on: []

  - id: op_2
    operation: compute
    params: {expression: "col_d * col_e", output_column: computed_1}
    input_columns: [col_d, col_e]
    output_columns: [computed_1]
    depends_on: [op_1]

  - id: op_3
    operation: flag
    params: {condition: "computed_1 < threshold_1", output_column: flag_1}
    input_columns: [computed_1]
    output_columns: [flag_1]
    depends_on: [op_2]
```

Each op has ONE verb. Each depends_on is clear. Column lineage is traceable.

## Gate Validator

After producing atomic_operations.yaml, run:
```bash
python workflow/validators/gate_3_dag_valid.py pipelines/<name>/
```

Must return PASS before proceeding to Phase 4. Checks: single verbs, valid DAG (no cycles), no domain leakage, valid depends_on references.
