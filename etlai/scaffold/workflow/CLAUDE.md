# Workflow — Phase Protocol

This folder holds **phase task cards** (what to produce). Who runs them, who talks to the user, and when gates fire belong to the **control plane** — see [LAYERS.md](LAYERS.md).

## Layer reminder

| Concern | Where |
|---------|--------|
| What (task contract) | `phase_N_*.md`, `templates/` |
| Access policy (optional role) | `../agents/*_SYSTEM_PROMPT.md` |
| When / user channel / gates | Orchestrator + `../ORCHESTRATION.md` + `etlai/orchestrator.py` |

## Phase Sequence

| Phase | Name | Artifact Produced | Gate |
|------:|------|-------------------|------|
| 0 | Dejargon | `pipeline_graph.yaml` (partial) + optional `ba_questions.json` | Open questions resolved via control plane |
| 1 | Business Process Graph | `pipeline_graph.yaml` (complete, then confirmed) | `gate_1` after `owner_confirmed: true` |
| 2 | Separation | `logical_graph.yaml` + `business_mapping.json` | `gate_2` |
| 3 | Atomize | `atomic_operations.yaml` | `gate_3` |
| 4 | Match | `match_results.yaml` | `gate_4` |
| 5 | Create Atom | `atoms/<name>.py` (+ tests) | `gate_5` |
| 6 | Assemble | `manifest.yaml` + `config.json` | (with phase 7) |
| 7 | Rehydrate | Final `rename_columns` mapping | `gate_6` |

## Sequencing Rules (control plane)

1. Phases are **strictly sequential**. Do not start phase N until phase N−1 artifacts exist and prior gates pass.
2. Phases 0–1 may require clarifying answers. The **control plane** collects those answers and re-invokes the phase card; phase cards never own a user session.
3. Only the control plane sets `owner_confirmed: true` (via `confirm_graph`) after explicit user assent.
4. Phase 2 onward does not request user input. Ambiguity must already be resolved.
5. Each invoke should load **one** `phase_N_*.md` (plus its template), not a bundle of agent + all phases.
6. Artifacts write under `pipelines/<name>/workflow/` (final manifest/config under `pipelines/<name>/`).
7. Never send `business_mapping.json` into atom-creation invokes (firewall).

## DO NOT

- Run phases in parallel.
- Produce atom or pipeline code before Phase 4 match is complete.
- Put agent names, spawn/retry policy, or confirmation ownership inside `phase_N_*.md`.
- Duplicate phase process steps inside role system prompts.
- Backtrack to Phase 0–1 from Phase 3+ (treat as failure / restart).
- Skip Phase 4.

## Gate Validators

Deterministic scripts — structural only. Run before advancing.

```bash
python workflow/validators/gate_1_graph_complete.py pipelines/<name>/
python workflow/validators/gate_2_no_leakage.py pipelines/<name>/
python workflow/validators/gate_3_dag_valid.py pipelines/<name>/
python workflow/validators/gate_4_match_coverage.py pipelines/<name>/ .
python workflow/validators/gate_5_atom_clean.py pipelines/<name>/ .
python workflow/validators/gate_6_manifest_valid.py pipelines/<name>/ .
```

Exit 0 = PASS, 1 = FAIL. On FAIL, fix artifacts before proceeding.

## Artifact Storage

```
pipelines/<pipeline_name>/workflow/
├── ba_session.json          # control-plane mediation state
├── ba_questions.json        # clarifying questions artifact (phases 0–1)
├── pipeline_graph.yaml
├── logical_graph.yaml
├── business_mapping.json
├── atomic_operations.yaml
└── match_results.yaml
```

Schemas: `workflow/templates/`.

## Role packaging (optional)

Roles are a **routing convenience**, not the unit of work. Default packaging:

| Phases | Role wrapper |
|--------|----------------|
| 0–1 | Business Analyst (worker) |
| 2–3 | Separator |
| 4–5 | Atom Smith (firewalled) |
| 6–7 | Assembler |
| All | Orchestrator (control plane) |

Tomorrow’s multi-backend router may invoke phase/sub-steps without these role names. Phase cards stay the source of truth.
