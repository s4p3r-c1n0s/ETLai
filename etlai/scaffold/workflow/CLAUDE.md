# Workflow — Phase Protocol

This folder governs the 7-phase pipeline creation process. Phases are **strictly sequential**. No phase may begin until the previous phase's artifact file exists and passes its validation checklist.

## Phase Sequence

| Phase | Name | Artifact Produced | Gate |
|-------|------|-------------------|------|
| 0 | Dejargon | `pipeline_graph.yaml` (partial) | User's request fully expanded |
| 1 | Business Process Graph | `pipeline_graph.yaml` (complete) | `owner_confirmed: true` set by user |
| 2 | Separation | `logical_graph.yaml` + `business_mapping.json` | Zero domain terms in logical_graph |
| 3 | Atomize | `atomic_operations.yaml` | One verb per entry, valid DAG |
| 4 | Match | `match_results.yaml` | Every operation mapped |
| 5 | Create Atom | New atom files in `atoms/` | Only for operations marked "create" |
| 6 | Assemble | `manifest.yaml` + `config.json` | Pipeline passes `etlai sync` |
| 7 | Rehydrate | Final step wired in manifest | Output columns use business names |

## Sequencing Rules

1. Phases 0 and 1 LOOP with the user. Do not exit Phase 1 until the user explicitly confirms the graph.
2. Phase 2 onward does NOT loop back to the user. All ambiguity must be resolved in Phases 0-1.
3. Each phase reads its detailed instructions from `workflow/phase_N_<name>.md`.
4. Each phase writes its artifact to the pipeline's working directory: `pipelines/<name>/workflow/`.
5. Before starting any phase, validate that the previous artifact exists and passes its checklist.

## DO NOT

- Run phases in parallel.
- Produce code (atom or pipeline) before Phase 4 is complete.
- Ask the user questions after Phase 1 is confirmed complete.
- Backtrack to Phase 0-1 from Phase 3+. If something is unclear, the graph was incomplete — this is a failure state, not a normal flow.
- Skip Phase 4 (match). Even if you "know" no atom exists, the search must be performed and documented.
- Send `business_mapping.json` content to any step that creates atom code.

## Gate Validators

Each phase transition has a deterministic validator script. Run BEFORE proceeding to the next phase.
These are structural checks — they catch missing fields, domain leakage, broken DAGs, and missing files.
They do NOT replace semantic judgment (that's the LLM's job during each phase).

```bash
# After Phase 1 (before starting Phase 2):
python workflow/validators/gate_1_graph_complete.py pipelines/<name>/

# After Phase 2 (before starting Phase 3):
python workflow/validators/gate_2_no_leakage.py pipelines/<name>/

# After Phase 3 (before starting Phase 4):
python workflow/validators/gate_3_dag_valid.py pipelines/<name>/

# After Phase 4 (before starting Phase 5):
python workflow/validators/gate_4_match_coverage.py pipelines/<name>/ .

# After Phase 5 (before starting Phase 6):
python workflow/validators/gate_5_atom_clean.py pipelines/<name>/ .

# After Phase 6 (final check):
python workflow/validators/gate_6_manifest_valid.py pipelines/<name>/ .
```

**Rule: If a gate validator returns FAIL, do NOT proceed. Fix all errors first.**

Validators return exit code 0 (PASS) or 1 (FAIL) with specific error messages.

## Artifact Storage

All intermediate artifacts live in:
```
pipelines/<pipeline_name>/workflow/
├── pipeline_graph.yaml
├── logical_graph.yaml
├── business_mapping.json
├── atomic_operations.yaml
└── match_results.yaml
```

Final outputs (manifest.yaml, config.json) go in `pipelines/<pipeline_name>/` as normal.
New atoms go in `atoms/` at project root.

## Template Reference

Schema definitions for all artifacts: `workflow/templates/`

Every artifact MUST conform to its template schema. Missing required fields = incomplete artifact = gate not passed.

## 5-Agent Mode

The 7-phase workflow can be executed manually (one LLM session doing all phases) or via the **5-agent system** where specialized agents handle specific phases:

- Phases 0-1 → Business Analyst agent (loops with user)
- Phases 2-3 → Separator agent (mechanical, no user interaction)
- Phases 4-5 → Atom Smith agent (firewalled from business_mapping.json)
- Phases 6-7 → Assembler agent (wires final pipeline)
- Orchestrator routes between agents and validates gates

Agent system prompts: `../agents/`

The phase files, gate validators, and artifact schemas are identical in both modes. The agents simply automate who-does-what and enforce the firewall.
