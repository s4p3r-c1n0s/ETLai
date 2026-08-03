# Changelog

All notable changes to ETLai are documented here.

## [Unreleased]

### Changed
- Orchestrator owns the user channel for phases 0–1; Business Analyst is a worker (TECH_DEBT #7)
- `owner_confirmed` may only be set via `Orchestrator.confirm_graph()` after explicit user assent
- `etlai create` prints BA turn prompts, relays questions, and confirms interactively when a TTY is available

### Added
- BA mediation APIs: `start_ba_session`, `build_ba_turn_prompt`, `record_ba_questions`, `record_user_answers`, `confirm_graph`, `prepare_gate1`

## [0.6.0] — 2026-08-03

### Removed
- Forms concept entirely (`etlai/forms/`, manifest `form:` field, runtime configure step)
- Tkinter column pickers (`vlookup_column_picker`, `groupby_picker`); params come only from config.json
- `path: ask` folder picker during `etlai sync` is retained

### Changed
- **Breaking:** `config.json` always uses `step_N` keys, including `step_0` (no flat top-level step-0 params)
- Gate 6 requires `step_0` for single-atom and composite pipelines
- Scaffold example configs (`groupby_religion`, `vlookup_rollnumber`, `newsdata_fetch`) ship under `step_0`

### Fixed
- TECH_DEBT #2: step_0 flat config special case eliminated

## [0.5.2] — 2026-08-03

### Added
- `InputResolver` class (`etlai/helpers/input_resolver.py`): replaces inline file injection heuristic
- `inputs_map` field in manifest steps: explicit mapping of inbox files to atom params (supports N files)
- `vlookup_then_groupby` scaffold example: full 7-phase workflow artifacts included

### Changed
- Extracted file/path injection logic from `registry.py:_execute_step` into `InputResolver`
- `vlookup_then_groupby` pipeline: added manifest.yaml, fixed config.json structure, added rehydration step

## [0.5.1] — 2026-07-31

### Added
- `etlai create` CLI command: drives the 5-agent pipeline creation flow
- `etlai/orchestrator.py`: gate runner, firewall enforcement, agent context builder, phase tracking
- ORCHESTRATION.md: step-by-step script for Claude Code sessions
- TECH_DEBT.md: documented known structural issues (InputResolver, step_0 config, sensor patterns)

### Fixed
- Mid-pipeline join injection: steps >= 1 now correctly set `left_file = prev_output` when `right_file` already present via inject_as
- Gate 6 no longer requires `step_0` key in config.json (step 0 reads flat top-level config)
- Gate 5 domain leakage threshold aligned with gate 2 (both use > 2 chars)

### Changed
- `etlai init` now copies workflow/, agents/, ORCHESTRATION.md, HOW_TO_USE_AGENTS.md
- Documentation fully rewritten: ARCHITECTURE.md, README.md, CONTRIBUTING.md, CLAUDE.md
- CHANGELOG.md now contains full release history (merged from RELEASE.md, which is removed)
- Removed EXECUTION_PLAN.md (superseded by docs/AGENT_IMPLEMENTATION_PLAN.md)
- Moved docs to docs/: DAGSTER_DECOUPLING_DESIGN.md (was TODO.md), RCA_BRANCHING_STUCK.md
- Mandatory changelog check added to publish and release checklists

## [0.5.0] — 2026-07-27

### Added
- 5-agent pipeline creation system (architecture + system prompts)
  - Orchestrator: routes work, enforces firewall, validates gates
  - Business Analyst: loops with user for phases 0-1
  - Separator: strips domain terms, builds generic DAG (phases 2-3)
  - Atom Smith: finds/creates domain-free atoms, firewalled (phases 4-5)
  - Assembler: wires manifest + config with real values (phases 6-7)
- Agent implementation plan and build roadmap
- End-user guide for the agent system

## [0.4.3] — 2026-07-27

### Added
- `input_from` field for non-linear step routing in composite pipelines
  - Steps can read from any predecessor, not just the adjacent one
  - Solves branching DAG linearization problem

### Fixed
- `inject_as` now resolves BEFORE auto-injection
  - Previously, when a reference file set `right_file` via inject_as, auto-injection didn't know and would set `input_file` instead of `left_file`
  - Reordered: inject_as first, then check what's already in config

## [0.4.2] — 2026-07-27

### Fixed
- `path: ask` now included in all manifest templates and documented in DO list
  - LLM agents were omitting it, causing pipelines to miss user folder selection

## [0.4.1] — 2026-07-27

### Added
- Option B (Named Steps) for multiple pipeline outputs
  - Steps with `name:` field produce `{name}.csv`
  - Steps without name use `_intermediate_N.csv`
  - Final step always produces `output.csv`

### Fixed
- `gate_1_graph_complete.py` updated to validate plural `outputs:` list (was checking singular `output:`)

## [0.4.0] — 2026-07-27

### Added
- Architecture fortress: 7-phase workflow with gate validators
  - 6 deterministic gate scripts validating artifacts between phases
  - Phase playbooks (phase_0 through phase_7) with step-by-step instructions
  - Artifact schemas in workflow/templates/
- New generic atoms (6): `computed_column`, `group_aggregate`, `filter_rows`, `flag_rows`, `rename_columns`, `sort_rows`
- Scaffold system with CLAUDE.md constitution (3-sentence principle, litmus test, DO NOTs)
- `passthrough` form for automated pipelines
- `inject_as` for reference file injection
- Hot folder sensors with configurable triggers

### Test coverage
- 18 new tests for 6 new atoms
- Total: 69 tests passing

## [0.3.5] — 2026-07-22

### Added
- `inject_as` for reference file injection
  - New field in `inputs:` declarations: `{step: N, param: "param_name"}`
  - Framework resolves reference files by pattern and injects paths into step config at runtime
- Atom Privacy Boundary documented in scaffold CLAUDE.md

### Changed
- Removed hardcoded test counts from documentation (always available via `pytest`)

## [0.3.4] — 2026-07-22

### Fixed
- NoneType crash in composite pipeline execution (`context.op_config` can be None)

## [0.3.3] — 2026-07-22

### Added
- Input role declarations (`inputs:` field in manifest.yaml: name, role, description, pattern)
- Auto-generated PIPELINE_README.md from `etlai sync`
- Input validation during sync (required fields, reference file warnings)
- Auto `min_files` calculation from transient input count
- Input metadata passed to atoms (`input_metadata` in params)

### Fixed
- Test counts across documentation
- CICD.md contradictions (removed false README version check claim)
- TODO.md misleading checkmarks on unimplemented phases

## [0.3.2] — 2026-07-22

### Added
- Testing infrastructure: comprehensive pytest suite (40 tests)
- Documentation: TESTS.md, CICD.md, TODO.md (Dagster decoupling design)
- Development dependencies: pytest, pytest-cov, pytest-mock as `[dev]` extras

### Changed
- Registry refactored: extracted `_execute_step()`, `_build_triggers()`, per-trigger-type builders

## [0.3.1] — 2026-07-21

### Added
- ARCHITECTURE.md: system overview, core contracts, data flow diagrams, design decisions

## [0.3.0] — 2026-07-21

### Added
- Package restructure: all code in `etlai/` pip-installable package
- CLI: `etlai init`, `etlai sync`, `etlai run`, `etlai list`
- Registry-driven: scans `pipelines/*/manifest.yaml`, dynamic Dagster job + sensor creation
- API pipeline support: `api_fetch` atom, `env_file` + `requires_env`, schedule triggers
- Trigger abstraction: `inbox_files` (sensor) and `schedule` (cron) rules
- Reference folder: `reference/` per pipeline for permanent lookup data
- `path: ask`: Tkinter folder picker during sync
- Dependencies: `pyyaml>=6.0`, `requests>=2.28`

### Breaking
- Package restructured: old `logic/`, `runners/`, `sensors/`, `pipeline.py`, `definitions.py` are legacy
- User projects now use `definitions.py` as 3-line loader

## [0.2.2] — 2026-07-19

### Fixed
- Config.json always stored in project directory, not data directory

## [0.2.1] — 2026-07-19

### Added
- Passthrough form reads config.json (no-UI pipeline support)

## [0.2.0] — 2026-07-19

### Added
- Moved all code into `etlai/` pip-installable package
- CLI: `init`, `sync`, `run`, `list` commands
- Registry-driven definitions
- Shipped atoms: `vlookup`, `groupby`, `mock_generate`
- Shipped forms: `vlookup_column_picker`, `groupby_picker`, `passthrough`

## [0.1.1] — 2026-07-19

### Fixed
- Added missing `logic/atoms/mock_generate.py` (import error)

## [0.1.0] — 2026-07-19

### Added
- Initial release
- Flat module structure with static `definitions.py`
- Hot folder sensors with file stability check and sweeper
- Config init pattern (first-run Tkinter UI, subsequent: saved config)
- Cross-platform notifications (macOS/Windows)
- Composite pipeline: vlookup → groupby
