# Tech Debt

Known structural issues that don't need fixing today but should be addressed before the codebase grows further.

## 1. `_execute_step` injection logic — extract into InputResolver

**File:** `etlai/registry.py:258-270`

**Problem:** The file/path injection logic in `_execute_step` has grown by accretion into a 5-branch conditional that handles:
- is_first + 2 files → left_file + right_file
- is_first + 1 file + right_file present → left_file
- is_first + 1 file → input_file
- not first + right_file present → left_file = prev_output
- not first → input_file = prev_output

Every new atom input pattern requires another branch. The logic is tested but hard to reason about in isolation.

**Fix:** Extract into a small `InputResolver` class with explicit methods (`resolve_first_step`, `resolve_continuation`) and a lookup table for atom signatures.

**When:** Before adding any atom that takes 3+ input files or has non-standard input patterns.

---

## 2. step_0 flat config special case

**File:** `etlai/registry.py:205-208`

**Problem:** Composite step 0 reads the ENTIRE flat `config.json` top-level dict. Steps 1+ read `step_N` keys. This means config.json has a hybrid structure: top-level params for step 0 + nested `step_1`, `step_2`, etc. for the rest. Gate 6 was updated to not require `step_0` but the asymmetry is confusing.

**Fix:** Unify to always use `step_N` keys (step 0 reads `step_0`). Requires migration of existing pipelines.

**When:** Next major version (breaking change). Needs migration script for existing config.json files.

---

## 3. Sensor doesn't enforce manifest `pattern:` at runtime

**File:** `etlai/sensors/hot_folder_sensor.py:11`

**Problem:** The sensor uses a hardcoded `^(.+)\.(csv|xlsx)$` regex for file detection. The manifest `inputs[].pattern` field (e.g., `"sales_*.csv"`) is only validated at `etlai sync` time, never at runtime. Any csv/xlsx file triggers the pipeline.

**Fix:** Pass the manifest pattern to the sensor factory and filter files by it before triggering.

**When:** If a user reports wrong files triggering a pipeline. Low priority since atoms will fail on wrong input anyway.

---

## 4. Alphabetical file assignment to left_file/right_file

**File:** `etlai/helpers/folders.py:116-119` (sorted), `etlai/registry.py:261-262`

**Problem:** When 2+ files are in inbox, they're assigned to `left_file`/`right_file` alphabetically. There's no way to guarantee which file is which except by naming convention. The manifest `inputs[].pattern` could be used to match files to roles but isn't.

**Fix:** Match inbox files to declared transient inputs by pattern, then assign to params by input order.

**When:** When a user has multiple transient inputs with different schemas that must not be swapped.
