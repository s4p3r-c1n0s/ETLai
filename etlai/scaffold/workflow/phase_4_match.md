# Phase 4 — Match

## Purpose

For each atomic operation, search the existing atom registry to find a matching implementation. Only operations with NO existing match proceed to Phase 5 (creation).

## Input

- `atomic_operations.yaml` from Phase 3

## Output

- `match_results.yaml` — every operation mapped to an existing atom or marked "create"

## Process

1. Load the list of shipped atoms from `etlai.atoms` (vlookup, groupby, api_fetch, mock_generate).
2. Load any user-created atoms from `atoms/` folder in the project.
3. For each operation in atomic_operations.yaml:
   a. Read the operation verb and params.
   b. Search shipped atoms: does any atom perform this exact operation?
   c. Search user atoms: does any project-specific atom perform this operation?
   d. If found: mark as "matched", record atom name and source.
   e. If not found: mark as "create", propose a generic atom name.
4. For "create" entries, verify the proposed name is a generic operation verb — not a domain term.
5. Check for duplicates: if two operations need the same new atom, they share one "create" entry.

## Done When

- Every operation from atomic_operations.yaml has an entry in match_results.yaml
- All "matched" entries reference atoms that ACTUALLY EXIST (file verified)
- All "create" entries have a generic verb name (no domain terms)
- No unnecessary "create" entries (an existing atom could handle it with different config)

## Matching Logic

An existing atom MATCHES an operation if:
1. The atom performs the same core verb (join, group, filter, compute, etc.)
2. The atom accepts the required parameters via its params_json interface
3. The atom's output format is compatible with downstream operations

An existing atom does NOT match if:
1. The atom performs multiple operations (compound) but the operation needs only one
2. The atom requires params that don't map to the operation's needs
3. The atom has hardcoded behavior that conflicts with the operation's requirements

## Shipped Atom Reference

### vlookup
- **Operation:** join
- **Params:** left_file, right_file, left_column, right_column, left_output_columns, right_output_columns
- **Matches:** Any two-table join on a key column with column selection

### groupby
- **Operation:** group (count only)
- **Params:** input_file, group_column
- **Matches:** Group by one column with count aggregation ONLY
- **Does NOT match:** Group with sum, avg, min, max, or multiple aggregations

### api_fetch
- **Operation:** fetch external data
- **Params:** endpoint, method, headers, params, response_format, data_path, field_mapping
- **Matches:** Single HTTP request with JSON/XML/CSV response parsing

### mock_generate
- **Operation:** generate synthetic data
- **Params:** input_files, rows
- **Matches:** Creating test data from file headers

## DO

- Check shipped atoms FIRST, then user atoms
- Verify the match by comparing param signatures, not just operation names
- Mark partial matches with confidence "partial" and explain what needs adaptation
- Group duplicate creation needs (two operations needing `compute_column` = one creation task)
- Propose atom names using the pattern: `<verb>_<object>` (compute_column, filter_rows, group_aggregate, flag_rows)

## DO NOT

- Mark "create" if an existing atom can do the job — even if config needs adaptation
- Mark "matched" if the atom only PARTIALLY covers the operation (e.g., groupby for sum when it only does count)
- Propose atom names with domain terms (no: margin_calculator, sales_aggregator, inventory_filter)
- Skip the search — even if you "know" no atom exists, document the search
- Modify existing atoms to fit — if they don't match, mark "create" for a new one
- Create multiple atoms for the same generic operation (one `compute_column` serves all compute needs)

## Gate Validator

After producing match_results.yaml, run:
```bash
python workflow/validators/gate_4_match_coverage.py pipelines/<name>/ .
```

Must return PASS before proceeding to Phase 5. Checks: full coverage, matched atoms exist on disk, create names are generic verbs.
