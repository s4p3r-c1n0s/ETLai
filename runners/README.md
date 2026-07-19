# runners/

Pipeline assembly infrastructure and business-specific ops.

## Modules

### pipeline_factory.py

`build_business_pipeline(pipeline_name, atom_module, atom_label, pre_process_op)` — Assembles a Dagster job with: load files → pre-process (config init) → execute atom (with file lifecycle + notifications).

### atom_runner.py

Generic ops factories:
- `build_load_files_op` — Loads files from sensor config or scans inbox
- `build_execute_atom_op` — Runs atom, moves to processed/rejected, sends OS notification

### ops.py

Business-specific pre-processing ops with the **config init pattern**:
- `vlookup_rollnumber_pre_process_op` — First run: Tkinter column picker, saves config. Future runs: loads config.
- `groupby_religion_pre_process_op` — First run: Tkinter column picker, saves config. Future runs: loads config.

Set `reconfigure: true` in op config to force the UI to reappear.
