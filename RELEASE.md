# Release History

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
