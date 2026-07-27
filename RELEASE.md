# Release History

## v0.4.0 (2026-07-27)

### Architecture: The Fortress (7-Phase Workflow)

- **Mandatory 7-phase pipeline creation workflow** — Enforces strict atom privacy boundary
  - Phase 0: Dejargon user request (expand business jargon to plain language)
  - Phase 1: Build complete business process graph (loop with user until confirmed)
  - Phase 2: Separation (strip domain terms, produce logical_graph + business_mapping)
  - Phase 3: Atomize (split into single-verb operations, valid DAG)
  - Phase 4: Match (find existing atoms, mark new ones for creation)
  - Phase 5: Create atoms (write generic code, enforced info boundary)
  - Phase 6: Assemble (wire manifest.yaml + config.json from business_mapping)
  - Phase 7: Rehydrate (rename output columns to business names)
  - Each phase has deterministic structural validators (gate scripts)

- **Deterministic validators at each gate** — No more "did I do this right?"
  - `gate_1_graph_complete.py` — pipeline_graph structural completeness
  - `gate_2_no_leakage.py` — domain term scan (logical_graph vs business_mapping)
  - `gate_3_dag_valid.py` — single verbs, valid DAG, no cycles
  - `gate_4_match_coverage.py` — all ops matched, atoms exist on disk
  - `gate_5_atom_clean.py` — atom code has ZERO domain leakage, has execute()
  - `gate_6_manifest_valid.py` — manifest + config structurally sound

### New generic atoms (6 new shipped atoms)

- **`computed_column`** — Evaluate pandas expression on columns → new column
  - Params: `input_file, expression, output_column, target_path`
  - Supports: `col_a * col_b`, `(col_a - col_b) / col_a * 100`, any pandas expression

- **`group_aggregate`** — Group by column with flexible aggregations
  - Params: `input_file, group_column, aggregations: [{column, function, output_column}], target_path`
  - Functions: sum, mean, min, max, count, first, last
  - Replaces need for custom atoms with hardcoded aggregations

- **`filter_rows`** — Keep rows matching a condition (removes rows)
  - Params: `input_file, condition, target_path`
  - Condition: pandas query expression, e.g., `col_a > 10`

- **`flag_rows`** — Add boolean column from condition (keeps ALL rows)
  - Params: `input_file, condition, output_column, target_path`
  - Unlike filter, this preserves data while marking flagged rows

- **`rename_columns`** — Rename columns via mapping (Phase 7 rehydration step)
  - Params: `input_file, mapping: {old: new}, target_path`
  - Mandatory as final step in composite pipelines

- **`sort_rows`** — Sort by one or more columns
  - Params: `input_file, sort_columns: [], ascending, target_path`
  - Ascending can be bool (all columns) or list (per-column)

### Documentation: The Constitution

- **Rewritten scaffold CLAUDE.md** — Architecture principle + routing document
  - 3-sentence principle: atoms are generic, config is business logic, framework wires
  - Litmus test: rename columns to A/B/C — does atom still work?
  - Phase table with gates
  - Global DO NOTs (8 hard rules)
  - Routing to deeper docs (atoms/CLAUDE.md, pipelines/CLAUDE.md, workflow/)

- **New atoms/CLAUDE.md** — Atom creation law
  - Naming: `<verb>_<object>` only, no domain nouns
  - Contract: accept everything via params_json, nothing hardcoded
  - Testing rules: generic column names in tests (col_a, col_b)
  - Litmus test enforcement

- **New pipelines/CLAUDE.md** — Assembly law
  - Manifest structure for single + composite pipelines
  - How to translate business_mapping.json → config.json
  - inject_as rules for reference file wiring
  - rename_columns as mandatory final step

- **Complete workflow documentation**
  - `workflow/CLAUDE.md` — Phase protocol, sequencing rules, artifact storage
  - `phase_0_dejargon.md` through `phase_7_rehydrate.md` — Per-phase playbooks
  - `validators/` — Six gate validator scripts
  - `templates/` — Artifact schemas for each phase

### No breaking changes

- All existing atoms (vlookup, groupby, api_fetch, mock_generate) continue to work
- All existing manifests continue to work unchanged
- New phase workflow is for NEW pipeline creation only
- Scaffold templates include full workflow documentation

### Test coverage

- 18 new tests for 6 new atoms (computed_column, group_aggregate, filter_rows, flag_rows, rename_columns, sort_rows)
- All tests use generic column names, pass litmus test
- Total: 69 tests passing

---

## v0.3.5 (2026-07-22)

### New features

- **`inject_as` for reference file injection** — Manifests can declare reference files to be injected as specific atom params
  - New `inject_as` field in `inputs:` declarations: `{step: N, param: "param_name"}`
  - Framework resolves reference files by pattern and injects their paths into step config at runtime
  - Eliminates need for custom wrapper atoms — shipped generic atoms (vlookup, groupby) work directly
  - Reference file resolution is automatic and tested

### Documentation improvements

- **Atom Privacy Boundary** — Prominent new section in scaffold CLAUDE.md
  - Atoms must be domain-agnostic: no hardcoded column names, file names, or business rules
  - All business logic lives in config.json + inject_as declarations in manifest
  - Includes concrete anti-pattern/correct-pattern examples for cloud LLM clarity
  - Ensures atoms built by cloud LLM remain reusable across all projects

- Removed hardcoded test counts from CLAUDE.md, COMMIT_GUIDELINES.md, CONTRIBUTING.md, TESTS.md
  - Test counts always available via `pytest` — eliminates maintenance burden

### No breaking changes

- Manifests without `inject_as` continue to work exactly as before
- Existing atoms, forms, and pipelines unaffected
- New feature is purely additive

---

## v0.3.4 (2026-07-22)

### Fixed

- **NoneType crash in composite pipeline execution** — `context.op_config` can be None when no op config is provided, causing `AttributeError: 'NoneType' object has no attribute 'get'` in `_execute_step`. Now checks for None before accessing.

---

## v0.3.3 (2026-07-22)

### New features

- **Input role declarations** — Manifests can now declare inputs with explicit roles
  - New `inputs:` field in manifest.yaml: name, role (transient/reference), description, pattern
  - Transient inputs go to inbox/ (processed once, moved to processed/)
  - Reference inputs go to reference/ (permanent lookups, never moved)
  - AI agents and users can now distinguish file placement from the manifest alone

- **Auto-generated PIPELINE_README.md** — `etlai sync` generates per-pipeline documentation
  - Shows input table: name, folder, role, pattern, description
  - Folder layout explanation
  - Step-by-step workflow instructions
  - Regenerated on every sync (always current)

- **Input validation during sync** — `etlai sync` validates input declarations
  - Required fields: name, role, description
  - Warns if reference files missing from reference/ folder
  - Reports transient file pattern matches in inbox/
  - Errors on invalid role values

- **Auto min_files calculation** — When `min_files` not set, calculated from transient input count
  - Backward compatible: explicit min_files still takes precedence
  - Prevents misconfiguration (e.g., putting reference files in inbox)

- **Input metadata passed to atoms** — Atoms receive `input_metadata` in params
  - Allows atoms to identify which reference files to use by role
  - Enables smarter file resolution in composite pipelines

### Documentation fixes

- Fixed test counts across TESTS.md, RELEASE.md (now 47 tests)
- Fixed CICD.md contradictions (removed false README version check claim)
- Added NOT YET IMPLEMENTED warning to GitHub Actions section
- Updated GitHub Actions versions (v5, v4, v2)
- Fixed TODO.md misleading checkmarks on unimplemented phases
- Added all historical versions with correct dates from PyPI

### No breaking changes

- Manifests without `inputs:` continue to work exactly as before
- All existing atoms, forms, and pipelines unaffected

---

## v0.3.2 (2026-07-22)

### Improvements

- **Testing infrastructure** — Comprehensive pytest suite with 40 tests
  - `tests/test_atoms.py`: vlookup, groupby, mock_generate, api_fetch contract validation
  - `tests/test_forms.py`: passthrough form behavior
  - `tests/test_helpers.py`: config_store, env_loader, PipelineFolders file operations
  - `tests/test_registry.py`: manifest loading, atom/form resolution, trigger building
  - Fixtures for isolated file I/O with tmp_path
  - Coverage goals: 80%+ across all components

- **Documentation** — Complete CI/CD and testing guides
  - `TESTS.md`: How to run tests, conventions, coverage goals, testing checklist
  - `CICD.md`: Git hooks for pre-commit test validation, release workflow with PyPI publishing
  - `TODO.md`: Dagster decoupling design using Adapter pattern (future enhancement)
  - `ARCHITECTURE.md`: Added composite pipeline creation guide with 3+ step examples

- **Registry refactoring** — Cleaner code organization
  - Extracted `_execute_step()`: shared logic for single and composite jobs (eliminated 150+ lines duplication)
  - Extracted `_build_triggers()`: separated trigger building from job building
  - Extracted `_build_inbox_files_sensor()` and `_build_schedule_definition()`: per-trigger-type builders
  - Registry now more modular and easier to extend

- **Development dependencies** — Added pytest tooling
  - `pytest>=7.4`, `pytest-cov>=4.1`, `pytest-mock>=3.11` as optional `[dev]` extras

### No breaking changes

- All existing pipelines, atoms, forms continue to work unchanged
- API is backward compatible

---

## v0.3.1 (2026-07-21)

### Documentation

- **ARCHITECTURE.md** — Internal design documentation added
  - System overview diagram and core contracts
  - Data flow diagrams (file-based, API-based, composite pipelines)
  - Design decisions and security boundaries

### Status

- Internal release for design review and documentation
- Features from v0.3.0 included in this release
- Documentation cleanup and formatting

---

## v0.3.0 (2026-07-21)

### Major restructure

- **Package restructure** — All code now in `etlai/` pip-installable package
  - CLI: `etlai init`, `etlai sync`, `etlai run`, `etlai list` commands
  - Registry-driven: scans `pipelines/*/manifest.yaml` at startup
  - Dynamic Dagster job + sensor creation from manifests
  - Atom resolution: user `atoms/` → `etlai.atoms.<name>` (package)
  - Form resolution: user `forms/` → `etlai.forms.<name>` (package)
  - Scaffold templates with CLAUDE.md for AI-assisted pipeline creation

### New features

- **API pipeline support** — REST API data ingestion on schedules
  - Shipped `api_fetch` atom: generic HTTP fetcher (JSON/XML/CSV, field mapping, `${ENV_VAR}` resolution)
  - `env_file` + `requires_env` in manifests for credential management
  - `etlai sync` validates required env vars exist
  - Framework loads env file into `os.environ` before execution
  - `min_files: 0` for API-only pipelines with no inbox

- **Trigger abstraction** — Pipelines declare HOW they're triggered
  - `inbox_files`: hot folder sensor (default, existing behavior)
  - `schedule`: cron-based via Dagster ScheduleDefinition
  - Multiple rules can coexist (file sensor AND cron simultaneously)

- **Reference folder** — Permanent data across runs
  - `reference/` directory per pipeline
  - Framework passes `reference_files: [paths]` to atoms automatically
  - Use for: lookup tables, previous API snapshots, historical comparisons

- **`path: ask`** — Custom data folder locations per pipeline
  - Manifest `path: ask` triggers folder picker during `etlai sync`
  - Tkinter folder picker, chosen path written back to manifest
  - Each pipeline can store data anywhere independent of project

### Shipped atoms

- `vlookup` — Left join two CSVs on specified columns with dtype validation
- `groupby` — Group by column with count, sorted descending
- `mock_generate` — Generate synthetic data from file headers using Faker
- `api_fetch` — Generic REST API fetcher with auth and response parsing

### Shipped forms

- `vlookup_column_picker` — Tkinter join + output column multi-select
- `groupby_picker` — Tkinter single column selection
- `passthrough` — No UI, reads pre-written config.json

### Dependencies added

- `pyyaml>=6.0` (manifest parsing)
- `requests>=2.28` (available for custom API atoms)

### Breaking changes

- Package restructured: old `logic/`, `runners/`, `sensors/`, `pipeline.py`, `definitions.py` are legacy
- User projects now use `definitions.py` as 3-line loader: `from etlai.registry import build_definitions; defs = build_definitions()`

---

## v0.2.2 (2026-07-19)

### Fixed

- Config.json always stored in project directory, not data directory

---

## v0.2.1 (2026-07-19)

### Features

- Passthrough form reads config.json (no-UI pipeline support)

### Documentation

- Documentation updates

---

## v0.2.0 (2026-07-19)

### Major restructure

- Moved all code into `etlai/` pip-installable package
- Added `etlai` CLI: `init`, `sync`, `run`, `list` commands
- Registry-driven definitions (scans `pipelines/*/manifest.yaml`)
- Dynamic Dagster job + sensor creation from manifests
- Atom resolution: user `atoms/` → `etlai.atoms.*`
- Form resolution: user `forms/` → `etlai.forms.*`
- Scaffold templates with CLAUDE.md for AI-assisted pipeline creation

### Shipped atoms

- `vlookup` — left join two CSVs
- `groupby` — group by column with count
- `mock_generate` — Faker-based synthetic data

### Shipped forms

- `vlookup_column_picker` — Tkinter join/output column selection
- `groupby_picker` — Tkinter single column selection
- `passthrough` — no UI, reads config.json

---

## v0.1.1 (2026-07-19)

### Fixed

- Added `logic/atoms/mock_generate.py` (was missing, caused import error)

---

## v0.1.0 (2026-07-19)

### Initial release

- Flat module structure (pre-package)
- Static `definitions.py` with hardcoded jobs and sensors
- Hot folder sensors with file stability check and sweeper
- Config init pattern (first-run Tkinter UI, subsequent: saved config)
- Cross-platform notifications (macOS/Windows)
- Composite pipeline: vlookup → groupby
