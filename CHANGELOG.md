# Changelog

All notable changes to ETLai are documented here.

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

### Note
This release contains the complete agent architecture (system prompts, contracts, firewall rules). Orchestration code that spawns agents is planned for a future release.

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
- New generic atoms: `filter_rows`, `flag_rows`, `rename_columns`, `sort_rows`, `computed_column`, `group_aggregate`
- Scaffold system with CLAUDE.md constitution
- Phase playbooks, artifact templates, validator scripts
- `passthrough` form for automated pipelines
- `inject_as` for reference file injection
- Hot folder sensors with configurable triggers
