# Architecture

Internal design document. Not shipped with the package.

## System overview

```
┌──────────────────────────────────────────────────────────────────┐
│ pip install ETLai                                                  │
│                                                                    │
│  etlai/                                                           │
│  ├── cli.py              CLI entry point (init/sync/run/list)     │
│  ├── registry.py         Manifest scanner → Dagster Definitions    │
│  ├── atoms/              Shipped reusable atoms                    │
│  ├── forms/              Shipped config UI forms                   │
│  ├── helpers/            Framework utilities                       │
│  │   ├── folders.py      PipelineFolders (lifecycle + reference)  │
│  │   ├── config_store.py JSON config persistence                   │
│  │   ├── env_loader.py   .env file loading + validation           │
│  │   └── notifier.py     OS toast notifications                    │
│  ├── sensors/            Hot folder sensor factory                  │
│  └── scaffold/           Templates for etlai init                  │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ User project (~/my-etl/)                                          │
│                                                                    │
│  CLAUDE.md               Teaches Claude Code how to create pipes  │
│  etlai.yaml              Project config (pipelines_root)           │
│  definitions.py          3-line Dagster loader                     │
│  dagster.yaml            Storage config                            │
│  atoms/                  User/AI-generated atoms                   │
│  forms/                  User/AI-generated forms                   │
│  pipelines/                                                        │
│    <name>/                                                         │
│      manifest.yaml       Pipeline wiring                           │
│      config.json         Business logic (params for atom)          │
│      inbox/              Transient input files                     │
│      staging/            In-flight (prevents double-trigger)       │
│      processed/          Successfully consumed                     │
│      rejected/           Failed + .error.txt                      │
│      output/             Transformation results                    │
│      reference/          Permanent data (lookups, snapshots)       │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ Secrets (outside project, e.g. ~/.etlai/secrets.env)              │
│  Never committed. Never visible to cloud LLMs.                    │
│  Framework loads into os.environ before atom execution.           │
└──────────────────────────────────────────────────────────────────┘
```

## Core contracts

### Atom

```python
def execute(params_json: str) -> str:
    """Single unit of work. Receives data + reference paths. Returns result."""
```

- Input: JSON string with all params (config values + file paths + reference paths + target_path)
- Output: JSON string `{"success": bool, "message": str, ...}`
- Rules:
  - One atom = one unit of work (fetch OR compare OR transform, not all three)
  - Domain-agnostic: no hardcoded endpoints, column names, business logic
  - Business logic comes from config.json (injected by framework)
  - Credentials come from os.environ (loaded by framework from env_file)
  - Reference files received as paths (permanent, read-only)
  - Input data for file-based pipelines: file paths injected by framework
  - Must handle errors gracefully and return success=false

### Form

```python
def configure(file_paths: list[str], existing_config: dict | None) -> dict:
    """First-run config UI. Returns params dict for the atom."""
```

- If existing_config is valid → return immediately (no UI)
- If first run → show Tkinter, return dict
- Raise RuntimeError → files go to rejected
- For no-UI pipelines: passthrough reads config.json

### Manifest

```yaml
name: pipeline_name
atom: atom_module_name
form: form_module_name        # default: passthrough
min_files: N                  # 0 for API-only pipelines
path: ask | /absolute/path    # optional, custom data location
env_file: path/to/env         # optional, for API credentials
requires_env: [VAR1, VAR2]   # validated during etlai sync
trigger:
  rules:
    - type: inbox_files       # hot folder sensor
      min_files: 2
      stability_seconds: 2
    - type: schedule          # cron
      cron: "0 8 * * *"
# OR for composites:
steps:
  - atom: first_atom
    form: first_form
  - atom: second_atom
    form: second_form
```

## Data flow

### File-based pipeline

```
1. User drops files in inbox/
2. Sensor detects stable files (size check over N seconds)
3. Files moved to staging/ (prevents double-trigger)
4. Job starts:
   a. load_files op: reads staged paths from RunConfig
   b. configure op: calls form.configure() → saves/loads config.json
   c. execute op: loads env, injects reference paths, calls atom.execute()
5. Success: files → processed/, output written, notification sent
6. Failure: files → rejected/ + .error.txt, notification sent
```

### API-based pipeline

```
1. Cron schedule fires (Dagster ScheduleDefinition)
2. Job starts:
   a. load_files op: returns [] (min_files=0)
   b. configure op: passthrough reads config.json
   c. execute op: loads env_file into os.environ, calls atom.execute()
3. Atom reads credentials from os.environ, makes API call
4. Atom writes CSV to target_path
5. Atom can also write to reference/ for next-run comparison
```

### Composite pipeline

```
1. Trigger fires (same as above)
2. load_files op runs once
3. For each step:
   a. configure: form reads step-specific config from config.json["step_N"]
   b. execute: atom receives prev step output as input_file
   c. Output becomes next step's input
4. Last step: files → processed/, final output, notification
```

## Resolution order

Framework resolves modules at job build time (Dagster startup):

```
Atoms:  project/atoms/<name>.py  →  etlai.atoms.<name>
Forms:  project/forms/<name>.py  →  etlai.forms.<name>
```

User files always win. This allows overriding shipped atoms/forms without
modifying the installed package.

## Trigger abstraction

Today: Dagster sensors and schedules implement triggers.
Tomorrow: could be OS cron, webhooks, cloud schedulers.

The manifest declares WHAT triggers a pipeline (rules). The registry maps rules
to Dagster primitives. Swapping the trigger backend means only changing the
registry, not the manifests or atoms.

Trigger types:
- `inbox_files` → Dagster sensor (file watcher with stability check + sweeper)
- `schedule` → Dagster ScheduleDefinition (cron expression)
- Future: `api_diff` (compare API response to reference), `webhook`, `manual`

## Security boundaries

| Layer | Contains | Visible to cloud LLM? |
|-------|----------|----------------------|
| Atom code | Generic logic (auth patterns, parsing, pagination) | Yes |
| Manifest | Pipeline wiring (atom name, form name, trigger rules) | Yes |
| Form code | Tkinter UI logic | Yes |
| config.json | Business logic (endpoints, field names, params) | Today: yes. Future: no (moved outside project) |
| secrets.env | Actual credentials | Never |
| reference/ | Historical data, lookup tables | No (in data path) |

### Future: local LLM as privacy firewall

```
User describes need → Local LLM strips PII/business logic
                    → Sanitized prompt to cloud LLM
                    → Cloud writes generic atom code
                    → Local LLM fills config.json with real values
```

This keeps atom code business-logic-free by design. The cloud LLM only ever
sees structural descriptions (auth type, response format, field count).

## Design decisions

### Why one atom per API (not a generic configurable fetcher)?

APIs vary too much: OAuth2 vs API key vs HMAC signing, cursor vs offset vs link-header
pagination, JSON vs XML vs protobuf, custom error formats, rate limiting strategies.
A generic atom becomes a mini-framework with its own config language. Per-API atoms
are simpler, testable, and the AI generates them trivially.

### Why config.json is separate from manifest?

- Manifest = structure (what to wire). Committed, visible to AI.
- Config = business logic (what values to use). May move outside project in future.
- Separation allows the same atom to serve multiple pipelines with different configs.

### Why forms are first-run only?

Config rarely changes. Showing UI every run blocks automation. The pattern:
save once, run forever, delete config.json to reconfigure. Simple mental model.

### Why reference/ instead of passing all data as params?

Reference files can be large (lookup tables, historical snapshots). Loading them
into a JSON param dict is impractical. Atoms get paths and read what they need.
They're permanent — never moved by the lifecycle system.

### Why framework handles file I/O for input but not reference?

Input files are transient (inbox → staging → processed/rejected). The framework
manages their lifecycle. Reference files are persistent and read-only from the
atom's perspective — no lifecycle management needed, just path access.
