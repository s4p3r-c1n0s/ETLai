# Pipeline Creation — Phase Dependency Graph

Artifact-centric dependency view of the 7-phase workflow (plus Phase 0).
Phases run **sequentially** for control/gates, but Phase 6 **reads artifacts from
multiple earlier phases** — not only its immediate predecessor.

```mermaid
flowchart TB
  %% Actors
  User([User])
  Orch([Orchestrator + gates])
  BA[Business Analyst]
  Sep[Separator]
  Smith[Atom Smith]
  Asm[Assembler]
  Sync([etlai sync])

  %% External inputs
  Req[/User request/]

  %% Artifacts
  PG[(pipeline_graph.yaml)]
  LG[(logical_graph.yaml)]
  BM[(business_mapping.json)]
  AO[(atomic_operations.yaml)]
  MR[(match_results.yaml)]
  Atoms[(atoms/*.py)]
  Man[(manifest.yaml)]
  Cfg[(config.json)]

  %% Phase 0–1
  Req --> BA
  User <-->|clarify / confirm| BA
  BA -->|Phase 0: dejargon<br/>Phase 1: business graph| PG
  PG --> Orch
  Orch -->|gate_1| Sep

  %% Phase 2–3
  PG -->|Phase 2 input| Sep
  Sep -->|Phase 2: separate domain| LG
  Sep -->|Phase 2: map placeholders| BM
  LG -->|Phase 3 input| Sep
  Sep -->|Phase 3: atomize DAG| AO
  LG --> Orch
  BM --> Orch
  AO --> Orch
  Orch -->|gates 2+3| Smith

  %% Phase 4–5 (firewall: no BM / no PG)
  AO -->|Phase 4–5 only allowed input| Smith
  Smith -->|Phase 4: match| MR
  Smith -->|Phase 5: create if needed| Atoms
  MR --> Orch
  Atoms --> Orch
  Orch -->|gates 4+5| Asm

  %% Phase 6–7 — multi-parent deps
  PG -->|data sources, triggers, outputs| Asm
  BM -->|real column/threshold values| Asm
  AO -->|step order + depends_on| Asm
  MR -->|atom assignment per op| Asm
  Atoms -.->|atoms must exist| Asm
  Asm -->|Phase 6: assemble| Man
  Asm -->|Phase 6: assemble| Cfg
  Asm -->|Phase 7: rehydrate<br/>final rename_columns| Man
  Asm --> Sync
  Man --> Sync
  Cfg --> Sync
  Sync -->|gate_6| Orch

  classDef actor fill:#e8f0fe,stroke:#3b82f6,color:#111
  classDef artifact fill:#fef3c7,stroke:#d97706,color:#111
  classDef gate fill:#f3e8ff,stroke:#9333ea,color:#111
  class User,BA,Sep,Smith,Asm,Orch,Sync actor
  class PG,LG,BM,AO,MR,Atoms,Man,Cfg,Req artifact
```

## Phase summary

| Phase | Does | Actor | Creates | Passes to |
|------:|------|-------|---------|-----------|
| 0 | Expand jargon, clarify request | Business Analyst (+ User) | Partial `pipeline_graph.yaml` | Phase 1 |
| 1 | Complete business process graph; user confirms | Business Analyst (+ User) | `pipeline_graph.yaml` (`owner_confirmed: true`) | Phase 2; later Phase 6 |
| 2 | Strip domain terms; split logic vs mapping | Separator | `logical_graph.yaml`, `business_mapping.json` | Phase 3 (`logical_graph`); Phase 6 (`business_mapping`) |
| 3 | Split into single-verb DAG ops | Separator | `atomic_operations.yaml` | Phase 4; Phase 6 |
| 4 | Match ops to shipped/custom atoms | Atom Smith | `match_results.yaml` | Phase 5 (unmatched); Phase 6 |
| 5 | Write new generic atoms (if needed) | Atom Smith | `atoms/<name>.py` (+ tests) | Phase 6 (runtime resolution) |
| 6 | Wire steps, inputs, triggers; translate placeholders → real config | Assembler | `manifest.yaml`, `config.json` | Phase 7; `etlai sync` / gate 6 |
| 7 | Ensure final `rename_columns` rehydration | Assembler | Updates final step in manifest + config mapping | Runnable pipeline |

## Artifact dependency edges (what Phase 6 actually reads)

```mermaid
flowchart LR
  P1[Phase 1<br/>pipeline_graph.yaml] --> P6[Phase 6 Assemble]
  P2[Phase 2<br/>business_mapping.json] --> P6
  P3[Phase 3<br/>atomic_operations.yaml] --> P6
  P4[Phase 4<br/>match_results.yaml] --> P6
  P5[Phase 5<br/>atoms/*.py] -.->|if create path| P6

  P1 --> P2
  P2 --> P3
  P3 --> P4
  P4 --> P5
```

## Is Phase 6 dependent on Phase 2 or Phase 1?

**Both — directly.**

- **Phase 1** → `pipeline_graph.yaml` (inputs/roles, triggers, outputs)
- **Phase 2** → `business_mapping.json` (placeholder → real column/threshold/source values)

Phase 6 also needs Phase 3 (`atomic_operations.yaml`) and Phase 4 (`match_results.yaml`).
Sequential control flow is 1→2→3→4→5→6, but the Assembler’s data dependencies fan in from 1, 2, 3, and 4 (and 5 when new atoms were created).

## Notes

- Phases 0–1 loop with the user; Phases 2–7 do not.
- Atom Smith is firewalled from `business_mapping.json` and `pipeline_graph.yaml`.
- Intermediate workflow artifacts live under `pipelines/<name>/workflow/`.
- Final runnable artifacts live under `pipelines/<name>/` (`manifest.yaml`, `config.json`).
