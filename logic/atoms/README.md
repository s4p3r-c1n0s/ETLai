# logic/atoms/

Domain-agnostic CSV transformations. Every module implements
`execute(params_json: str) -> str` and catches execution errors into a JSON
result. These functions read and write files; "atom" means a reusable
orchestration unit, not a side-effect-free function.

## `vlookup.py`

Performs a pandas left join and writes selected columns.

Required parameters: `left_file`, `right_file`, `left_column`,
`right_column`, `left_output_columns`, `right_output_columns`, and
`target_path`.

## `groupby.py`

Groups a CSV by one column, counts rows, sorts descending, and writes CSV.

Required parameters: `input_file`, `group_column`, and `target_path`.

## `mock_generate.py`

Reads headers from each input CSV, chooses Faker generators from header names,
and writes `mock_<source-name>` files into the target directory.

Required parameters: `input_files` and `target_path`. Optional `rows` defaults
to 50.
