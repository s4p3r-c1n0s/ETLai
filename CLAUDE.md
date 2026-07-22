# CLAUDE.md

Guidance for coding agents working in this repository.

## ⚠️ CRITICAL: Read Before Any Commit

**[COMMIT_GUIDELINES.md](COMMIT_GUIDELINES.md)** — MUST follow for every commit:
- Short titles (max 70 chars) with type prefix
- Bullet points explaining WHY, not what
- **NO AI attribution** — Never include "Co-Authored-By:", "Authored by Claude"
- Imperative mood (add, not added)

**[CONTRIBUTING.md](CONTRIBUTING.md)** — Development workflow, testing, PRs

## Quick Links

- **Tests:** [TESTS.md](TESTS.md) — coverage goals, how to run
- **CI/CD:** [CICD.md](CICD.md) — Git hooks, release workflow, tagging
- **Publishing:** [PUBLISH.md](PUBLISH.md) — Building and publishing to PyPI
- **Architecture:** [ARCHITECTURE.md](ARCHITECTURE.md) — Internal design, composite pipelines

## Project overview

ETLai is a pip-installable Python package that provides a local, folder-driven
Dagster CSV transformation engine. Users run `etlai init` to scaffold a project,
then use Claude Code to create new pipelines.

The package ships reusable atoms, forms, sensors, helpers, and a CLI. User
projects contain manifests, custom atoms/forms, and data folders.

## Package structure

```
etlai/
  cli.py              ← etlai init/sync/run/list commands
  registry.py         ← scans manifests, dynamically builds Dagster Definitions
  atoms/              ← shipped atoms (vlookup, groupby, mock_generate)
  forms/              ← shipped forms (vlookup_column_picker, groupby_picker, passthrough)
  helpers/            ← folders, config_store, notifier
  sensors/            ← hot_folder_sensor factory
  runners/            ← (reserved for future use)
  scaffold/           ← templates copied by etlai init
```

## Common commands

```bash
pip install -e .                    # install in dev mode
etlai init /tmp/test && cd /tmp/test
etlai sync                          # validate manifests, create folders
etlai run                           # start Dagster dev server
```

## Architecture

- `registry.py` scans `pipelines/*/manifest.yaml` and builds all Dagster jobs +
  sensors dynamically. No static imports.
- Each manifest wires: atom + form + min_files + optional path
- Atoms: `execute(params_json: str) -> str` returning `{"success": bool, "message": str}`
- Forms: `configure(file_paths: list[str], existing_config: dict | None) -> dict`
- Resolution: user `atoms/`/`forms/` → package `etlai.atoms`/`etlai.forms`
- `PipelineFolders` reads the manifest `path` field or falls back to `pipelines/<name>/`
- `config.json` is the single source of business config — written by form UI or by Claude Code

## Key conventions

- Atoms are domain-agnostic. Business logic lives in `config.json`.
- Forms are first-run UI only. For no-UI pipelines, use `passthrough` and pre-write `config.json`.
- `path: ask` in manifests triggers a folder picker during `etlai sync`.
- Scaffold CLAUDE.md teaches end-user Claude Code sessions how to add pipelines.

## Important constraints

- Python 3.10+ required
- CSV only for processing (sensors accept .xlsx filenames but atoms use CSV readers)
- Tkinter required for first-run config forms
- Do not commit pipeline runtime data (inbox, staging, processed, rejected, output, config.json)
- The old top-level `logic/`, `runners/`, `sensors/`, `helpers/`, `pipeline.py`, `definitions.py`
  are legacy — all active code lives under `etlai/`
