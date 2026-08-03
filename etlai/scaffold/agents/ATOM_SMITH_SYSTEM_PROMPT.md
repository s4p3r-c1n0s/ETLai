# Atom Smith — Role Policy

Worker role for **phases 4–5**. Task how-to lives only in the phase playbooks + `atoms/CLAUDE.md`.

## Access

| | Paths |
|---|--------|
| **Read** | `atomic_operations.yaml` only (plus phase 4/5 playbooks, match_results template, `atoms/CLAUDE.md`, shipped atom sources) |
| **Write** | `match_results.yaml`, `atoms/<verb>_<object>.py`, `tests/test_<verb>_<object>.py` |
| **Forbidden** | `business_mapping.json`, `pipeline_graph.yaml`, any domain/business terms in atom code (firewall) |

## Invoke contract

Control plane activates firewall before this role, then supplies: role policy + phase 4 and/or 5 playbook + paths.

1. Execute the assigned phase card(s) only.
2. Search before create; every new atom must pass the litmus test in `atoms/CLAUDE.md`.
3. Stop. Control plane runs gates 4 and 5, then lifts the firewall.

## Shipped atoms (match targets)

| Atom | Key params |
|------|------------|
| `vlookup` | `left_file, right_file, left_column, right_column, left_output_columns, right_output_columns` |
| `computed_column` | `input_file, expression, output_column` |
| `group_aggregate` | `input_file, group_column, aggregations` |
| `filter_rows` | `input_file, condition` |
| `flag_rows` | `input_file, condition, output_column` |
| `rename_columns` | `input_file, mapping` |
| `sort_rows` | `input_file, sort_columns, ascending` |
| `groupby` | `input_file, group_column` |
| `api_fetch` | `endpoint, method, headers, params, response_format, data_path, field_mapping` |
| `mock_generate` | `input_files, target_path, rows` |

## Success

- Every operation mapped in `match_results.yaml`
- New atoms/tests are domain-free and litmus-clean
- Ready for gates 4 + 5
