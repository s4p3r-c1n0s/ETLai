# logic/

Contains the `atoms/` package — domain-agnostic CSV transformation modules.

## Atom vs Business Pipeline

| | Atom | Business Pipeline |
|---|------|-------------------|
| **Knows which column?** | No | Yes (via saved config) |
| **Has folder lifecycle?** | No | Yes (inbox → staging → processed/rejected) |
| **Has sensor?** | No | Yes |
| **Reads/writes files?** | Yes | Yes (delegates to atom) |
| **Reusable across domains?** | Yes | No — specific to one use case |
| **Location** | `logic/atoms/` | `pipeline.py` + `runners/ops.py` + `pipelines/<name>/` |

Atoms are not pure functions — they perform file I/O. "Atom" means a reusable
orchestration unit that a business pipeline can compose.

See `atoms/README.md` for per-module documentation.
