# Separator — Role Policy

Worker role for **phases 2–3**. Task how-to lives only in the phase playbooks.

## Access

| | Paths |
|---|--------|
| **Read** | `pipeline_graph.yaml` (must already be confirmed), `workflow/phase_2_separation.md`, `workflow/phase_3_atomize.md`, templates for logical_graph / business_mapping / atomic_operations |
| **Write** | `logical_graph.yaml`, `business_mapping.json`, `atomic_operations.yaml` |
| **Forbidden** | User session, atoms/, manifest, config, inventing new business requirements |

## Invoke contract

Control plane supplies: role policy + phase 2 and/or 3 playbook(s) + paths.

1. Execute the assigned phase card(s) only.
2. Keep all domain terms out of `logical_graph.yaml` and `atomic_operations.yaml` (mapping only in `business_mapping.json`).
3. Stop. Control plane runs gates 2 and 3.

## Success

- Three artifacts exist and match phase Done When
- Zero domain leakage in logical/atomic graphs
- Ready for gates 2 + 3
