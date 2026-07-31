# CLAUDE.md

Guidance for coding agents working in this repository.

## CRITICAL: Read Before Any Commit

**[COMMIT_GUIDELINES.md](COMMIT_GUIDELINES.md)** — MUST follow for every commit:
- Short titles (max 70 chars) with type prefix
- Bullet points explaining WHY, not what
- **NO AI attribution** — Never include "Co-Authored-By:", "Authored by Claude"
- Imperative mood (add, not added)

**[CONTRIBUTING.md](CONTRIBUTING.md)** — Development workflow, testing, PRs

## Quick Links

- **Architecture:** [ARCHITECTURE.md](ARCHITECTURE.md) — System design, contracts, 5-agent system, execution engine
- **Tests:** [TESTS.md](TESTS.md) — Coverage goals, how to run
- **CI/CD:** [CICD.md](CICD.md) — Git hooks, release workflow, tagging
- **Publishing:** [PUBLISH.md](PUBLISH.md) — Building and publishing to PyPI
- **Changelog:** [CHANGELOG.md](CHANGELOG.md) — Release history
- **Tech debt:** [TECH_DEBT.md](TECH_DEBT.md) — Known structural issues

### Agent System Docs (in docs/)

- [Agent Build Roadmap](docs/AGENT_BUILD_ROADMAP.md) — 6-step implementation plan
- [Agent Implementation Plan](docs/AGENT_IMPLEMENTATION_PLAN.md) — Detailed agent contracts

### Design Explorations (in docs/)

- [Dagster Decoupling](docs/DAGSTER_DECOUPLING_DESIGN.md) — Adapter pattern for orchestrator portability
- [RCA: Branching Stuck](docs/RCA_BRANCHING_STUCK.md) — Historical: how input_from was designed

## Project overview

ETLai is a pip-installable Python package that provides a local, folder-driven
Dagster CSV transformation engine. Users run `etlai init` to scaffold a project,
then use `etlai create` or Claude Code to create new pipelines.

The package ships reusable atoms, forms, sensors, helpers, an orchestrator, and
a CLI. User projects contain manifests, custom atoms/forms, and data folders.

## Package structure

```
etlai/
  cli.py              ← etlai init/create/sync/run/list commands
  orchestrator.py     ← 5-agent coordination (gates, firewall, context)
  registry.py         ← scans manifests, dynamically builds Dagster Definitions
  atoms/              ← 10 shipped atoms (vlookup, computed_column, group_aggregate, ...)
  forms/              ← shipped forms (passthrough, vlookup_column_picker, groupby_picker)
  helpers/            ← folders, config_store, env_loader, notifier
  sensors/            ← hot_folder_sensor factory
  scaffold/           ← templates copied by etlai init (workflow, agents, docs)
```

## Common commands

```bash
pip install -e ".[dev]"             # install in dev mode with test deps
pytest --cov=etlai                  # run all tests with coverage
etlai init /tmp/test && cd /tmp/test
etlai create "join sales with catalog"  # 5-agent pipeline creation
etlai sync                          # validate manifests, create folders
etlai run                           # start Dagster dev server
```

## Architecture (summary)

- `registry.py` scans `pipelines/*/manifest.yaml` and builds all Dagster jobs +
  sensors dynamically. No static imports.
- `orchestrator.py` coordinates the 5-agent pipeline creation: gate validation,
  firewall enforcement, agent context building.
- Each manifest wires: atoms + config + triggers + optional inputs (inject_as, input_from)
- Atoms: `execute(params_json: str) -> str` returning `{"success": bool, "message": str}`
- Forms: `configure(file_paths: list[str], existing_config: dict | None) -> dict`
- Resolution: user `atoms/`/`forms/` → package `etlai.atoms`/`etlai.forms`
- config.json: step 0 reads flat top-level, steps 1+ read `step_N` keys

See [ARCHITECTURE.md](ARCHITECTURE.md) for full details.

## Key conventions

- Atoms are domain-agnostic. Business logic lives in `config.json`.
- Forms are first-run UI only. For no-UI pipelines, use `passthrough` and pre-write `config.json`.
- `path: ask` in manifests triggers a folder picker during `etlai sync`.
- Final step in composite pipelines must be `rename_columns` (rehydration).
- Scaffold CLAUDE.md teaches end-user Claude Code sessions how to add pipelines.

## Important constraints

- Python 3.10+ required
- CSV only for processing (sensors accept .xlsx filenames but atoms use CSV readers)
- Tkinter required for first-run config forms
- Do not commit pipeline runtime data (inbox, staging, processed, rejected, output, config.json)
- Secrets in `~/.etlai/secrets.env`, never committed
- The old top-level `logic/`, `runners/`, `sensors/`, `helpers/`, `pipeline.py`, `definitions.py`
  are legacy — all active code lives under `etlai/`
