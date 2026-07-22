# Release History

## v0.3.2 (2026-07-22)

### Improvements

- **Testing infrastructure** — Comprehensive pytest suite with 36+ tests
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

## v0.3.0 (unreleased)

### New features

- **API pipeline support** — Pipelines can now ingest data from REST APIs
  - Shipped `api_fetch` atom: generic HTTP fetcher (JSON/XML/CSV response parsing, field mapping, `${ENV_VAR}` resolution in headers and params)
  - `env_file` + `requires_env` in manifests for credential management
  - `etlai sync` validates env files contain required variables
  - Framework loads env file into `os.environ` before atom execution
  - Example pipeline: `newsdata_fetch` (technology news from newsdata.io)

- **Trigger abstraction** — Pipelines declare how they're triggered
  - `inbox_files`: hot folder sensor (default, existing behavior)
  - `schedule`: cron-based via Dagster ScheduleDefinition
  - Multiple rules can coexist (e.g. both file sensor AND cron)
  - `min_files: 0` for API-only pipelines with no inbox

- **Reference folder** — Permanent data available to atoms across runs
  - `reference/` directory created per pipeline
  - Framework passes `reference_files: [paths]` to atoms automatically
  - Use for: lookup tables, previous API snapshots, historical comparisons

- **`path: ask`** — Custom data folder locations per pipeline
  - Manifest can set `path: ask` to prompt user during `etlai sync`
  - Tkinter folder picker opens, chosen path written back to manifest
  - Each pipeline can store data anywhere independent of the project

- **Config separation** — `config.json` stays in project directory
  - Even when `path` points elsewhere for data folders
  - Keeps business logic accessible to Claude Code

### Breaking changes

- Package restructured into `etlai/` namespace (was flat top-level modules)
- Old `logic/`, `runners/`, `sensors/`, `helpers/`, `pipeline.py`, `definitions.py` are legacy
- User projects now use `definitions.py` as a 3-line loader calling `etlai.registry.build_definitions()`

### Dependencies added

- `pyyaml>=6.0` (manifest parsing)
- `requests>=2.28` (available for custom API atoms)

---

## v0.2.2

- Config.json always stored in project directory, not data directory

## v0.2.1

- Passthrough form reads config.json (no-UI pipeline support)
- Documentation updates

## v0.2.0

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

## v0.1.1

- Added `logic/atoms/mock_generate.py` (was missing, caused import error)

## v0.1.0

- Initial release
- Flat module structure (pre-package)
- Static `definitions.py` with hardcoded jobs and sensors
- Hot folder sensors with file stability check and sweeper
- Config init pattern (first-run Tkinter UI, subsequent: saved config)
- Cross-platform notifications (macOS/Windows)
- Composite pipeline: vlookup → groupby
