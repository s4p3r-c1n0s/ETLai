# Assembler — Role Policy

Worker role for **phases 6–7**. Task how-to lives only in the phase playbooks + `pipelines/CLAUDE.md`.

## Access

| | Paths |
|---|--------|
| **Read** | `match_results.yaml`, `business_mapping.json`, `atomic_operations.yaml`, `pipeline_graph.yaml`, phase 6/7 playbooks, `pipelines/CLAUDE.md` |
| **Write** | `manifest.yaml`, `config.json` |
| **Forbidden** | User session, modifying atom source code, inventing placeholders (translate all via business_mapping) |

## Invoke contract

Control plane supplies: role policy + phase 6/7 playbooks + paths (firewall already lifted).

1. Execute assemble then rehydrate per those phase cards.
2. No placeholders left in `config.json`; final step is `rename_columns`.
3. Optionally run `etlai sync`; stop for control plane gate 6.

## Success

- Valid `manifest.yaml` + fully translated `config.json`
- `path: ask`, inject_as / input_from as required by phase cards
- Ready for gate 6
