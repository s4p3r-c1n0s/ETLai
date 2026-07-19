# runners/

Dagster job assembly, execution lifecycle, and business-specific preprocessing.

## `pipeline_factory.py`

`build_business_pipeline(...)` creates a three-step job:

```text
load configured/inbox paths → prepare atom parameters → execute atom
```

If no preprocess op is supplied, the factory passes the first file as
`input_file`.

## `atom_runner.py`

- `build_load_files_op` reads sensor-provided paths or scans the inbox.
- `build_execute_atom_op` supplies a default output path, invokes an atom,
  records metadata, moves source files, and sends best-effort notifications.

## `ops.py`

- `vlookup_rollnumber_pre_process_op` loads saved choices or opens the Tkinter
  join/output picker.
- `groupby_religion_pre_process_op` loads a saved group column or opens its
  Tkinter picker.
- `mock_generator_pre_process_op` passes source paths and the pipeline output
  directory to the mock atom.

Delete a pipeline's `config.json` to force first-run configuration.

## `composite.py`

Defines the `vlookup_then_groupby` job without the generic factory. It owns
three ops: load two files, write `_vlookup_intermediate.csv`, then group that
intermediate result into `output.csv`. Lookup and group choices share one
pipeline config.
