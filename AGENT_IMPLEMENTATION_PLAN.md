# Agent Implementation Plan — Multi-Agent Pipeline Creation

## Overview

Build 5 specialized agents that collaborate through an orchestrator to create ETLai pipelines. Each agent is deeply scoped to a single task, has access to only the knowledge it needs, and is protected by firewalls that prevent it from accessing sensitive business logic where appropriate.

## Implementation Phases

### Phase 1: Orchestrator (Main Agent — runs in this session)

**Purpose:** Orchestrate the 5-agent pipeline creation flow. The only agent that runs continuously and routes work to specialized subagents.

**Responsibilities:**
1. Create `pipelines/<name>/workflow/` directory for artifacts
2. Spawn Business Analyst for Phases 0-1
3. On gate pass: spawn Separator for Phases 2-3
4. On gate pass: spawn Atom Smith for Phases 4-5 (with firewall enforcement)
5. On gate pass: spawn Assembler for Phases 6-7
6. On gate FAIL: retry agent with error feedback (up to 3 times)
7. On final success: print completion message

**Tools Available:**
- File read/write (all artifacts in `pipelines/<name>/workflow/`)
- Subprocess calls to gate validators (gate_1 through gate_6)
- Spawn subagents via `Agent` tool
- Report final status to user

**Key Logic:**
- Keep artifact paths stable: `pipelines/<name>/workflow/` is the single source of truth
- Firewall enforcement: before calling Atom Smith, strip `business_mapping.json` from context
- Retry on FAIL: extract error messages from gate validator output, send back to agent with "fix these specific errors"

---

### Phase 2: Business Analyst Agent (Subagent — Phases 0-1)

**Purpose:** Understand user's business request and produce a complete, user-confirmed process graph.

**Input:**
- User's raw request (text, may be in domain jargon)

**Output:**
- `pipelines/<name>/workflow/pipeline_graph.yaml` — complete business process graph
- `owner_confirmed: true` in the YAML

**System Prompt Components (from scaffold):**
1. `workflow/phase_0_dejargon.md` — How to expand jargon, ask clarifying questions
2. `workflow/phase_1_business_graph.md` — How to build nodes, edges, data sources, triggers, outputs
3. `workflow/templates/pipeline_graph.yaml` — Schema and examples
4. Instruction: **Loop with the user.** Ask for confirmation after each step. Do NOT exit Phase 1 until the user says "yes, this graph is complete and correct."

**Tools:**
- Read: phase playbooks, schema template
- Write: `pipeline_graph.yaml` (multiple iterations)
- Interact: ask user clarifying questions and for confirmation

**Loop Condition:**
```
while owner_confirmed != true:
  - Show current graph to user
  - Ask: "Is this complete and correct?"
  - On YES → set owner_confirmed: true and exit
  - On feedback → refine and loop
```

**Exit Criteria:**
- `pipeline_graph.yaml` exists
- `owner_confirmed: true` is set
- Ready for gate_1 validation

---

### Phase 3: Separator Agent (Subagent — Phases 2-3)

**Purpose:** Strip domain language and atomize into smallest single-verb operations.

**Input:**
- `pipeline_graph.yaml` from Business Analyst

**Output:**
- `logical_graph.yaml` — business operations → generic verbs (join, compute, group, filter, sort, rename, flag)
- `business_mapping.json` — domain term ↔ generic placeholder mapping
- `atomic_operations.yaml` — one verb per operation, DAG structure

**System Prompt Components:**
1. `workflow/phase_2_separation.md` — How to map domain terms to placeholders, build business_mapping
2. `workflow/phase_3_atomize.md` — How to split compound operations, build atomic DAG
3. `workflow/templates/logical_graph.yaml`, `business_mapping.json`, `atomic_operations.yaml` — Schemas
4. Instruction: **No user interaction.** All decisions are mechanical (follow the template schemas).

**Tools:**
- Read: pipeline_graph.yaml, phase playbooks, schemas
- Write: logical_graph.yaml, business_mapping.json, atomic_operations.yaml

**Key Constraints:**
- CANNOT write domain terms in logical_graph or atomic_operations
- MUST preserve all domain knowledge in business_mapping
- MUST produce valid DAG structure (no cycles, valid dependencies)

**Exit Criteria:**
- Three YAML files exist and conform to schemas
- Ready for gate_2 and gate_3 validation

---

### Phase 4: Atom Smith Agent (Subagent — Phases 4-5)

**Purpose:** Find or create generic atoms for each operation.

**Input:**
- `atomic_operations.yaml` ONLY (NO business_mapping.json, NO pipeline_graph.yaml)

**Output:**
- `match_results.yaml` — each operation → shipped atom or "create"
- New atom files: `atoms/<verb>_<object>.py` + `tests/test_<verb>_<object>.py` (Phase 5 only)

**System Prompt Components:**
1. `workflow/phase_4_match.md` — How to search and match operations to shipped atoms
2. `workflow/phase_5_create_atom.md` — How to write generic atoms with the litmus test
3. `atoms/CLAUDE.md` — Atom creation law (naming, structure, testing, litmus test)
4. `workflow/templates/match_results.yaml` — Schema
5. Shipped atoms list from `scaffold/CLAUDE.md` (10 atoms, query-able)
6. Instruction: **Never write domain knowledge.** The litmus test: "If I rename every column to A, B, C — does the atom still work?" YES → ship, NO → fix it.

**Tools:**
- Read: atomic_operations.yaml, phase playbooks, shipped atoms list, schema templates
- Write: match_results.yaml, new atom files, new test files
- CANNOT read: business_mapping.json (orchestrator enforces this via firewall)

**Key Constraints:**
- No access to business_mapping or any domain knowledge
- Every atom must pass the litmus test
- Tests must use generic column names (A, B, C) not real names
- All created atoms must be shipped to `atoms/` directory

**Exit Criteria:**
- `match_results.yaml` exists
- Every operation is mapped (shipped atom or "create")
- All new atoms have passing tests
- Ready for gate_4 and gate_5 validation

---

### Phase 5: Assembler Agent (Subagent — Phases 6-7)

**Purpose:** Wire atoms into a manifest.yaml + config.json pipeline with real business values.

**Input:**
- `match_results.yaml` — atom assignments
- `business_mapping.json` — real values to substitute
- `atomic_operations.yaml` — operation sequence
- `pipeline_graph.yaml` — triggers, data sources, outputs

**Output:**
- `pipelines/<name>/manifest.yaml` — complete pipeline definition
- `pipelines/<name>/config.json` — per-step configuration with real values

**System Prompt Components:**
1. `workflow/phase_6_assemble.md` — How to linearize DAG, translate placeholders, wire inject_as, set triggers
2. `workflow/phase_7_rehydrate.md` — How to add rename_columns final step with output mapping
3. `pipelines/CLAUDE.md` — Assembly law (manifest structure, config translation, inject_as rules, multiple outputs)
4. `workflow/templates/manifest.yaml`, `config.json` — Schemas
5. Instruction: **Translate generic → real.** Every col_a, threshold_1, formula_x becomes a real value from business_mapping. Final step is always rename_columns.

**Tools:**
- Read: match_results.yaml, business_mapping.json, atomic_operations.yaml, pipeline_graph.yaml, phase playbooks, schemas
- Write: manifest.yaml, config.json
- Execute: `etlai sync` via bash to validate

**Key Constraints:**
- No generic placeholders in final config.json
- Final step MUST be rename_columns with output_columns mapping
- `path: ask` MUST be set in manifest
- All reference files must have inject_as declarations
- min_files calculation must be correct

**Exit Criteria:**
- manifest.yaml and config.json exist
- `etlai sync` passes without errors
- Ready for gate_6 validation

---

## Knowledge Distribution — What Each Agent Knows

### Business Analyst
✅ User's business request (domain jargon)
✅ Phase 0-1 playbooks
✅ pipeline_graph.yaml schema
✅ User (for confirmation loops)

❌ Atom concepts, code, config
❌ Generic operations
❌ Technical pipeline structure

---

### Separator
✅ pipeline_graph.yaml (completed)
✅ Phase 2-3 playbooks
✅ All three output schemas (logical_graph, business_mapping, atomic_operations)
✅ Generic operation verbs (join, compute, group, etc.)

❌ Shipped atoms or user atoms
❌ manifest/config structure
❌ How pipelines run (Dagster, registry, etc.)

---

### Atom Smith
✅ atomic_operations.yaml
✅ Phase 4-5 playbooks
✅ atoms/CLAUDE.md (litmus test, naming, structure)
✅ match_results.yaml schema
✅ Shipped atoms list (10 atoms, their params, what they do)

❌ business_mapping.json (FIREWALL)
❌ pipeline_graph.yaml (FIREWALL)
❌ Real column names, thresholds, formulas, domain knowledge (FIREWALL)
❌ Config structure
❌ How atoms will be wired into pipelines

---

### Assembler
✅ match_results.yaml
✅ business_mapping.json
✅ atomic_operations.yaml
✅ pipeline_graph.yaml
✅ Phase 6-7 playbooks
✅ pipelines/CLAUDE.md
✅ manifest/config schemas
✅ Trigger definitions, input roles, inject_as rules

❌ Atom code (read-only, already created)
❌ How to write new atoms
❌ User interaction (no loops, no confirmations)

---

## Artifact Handoff Sequence

```
User Request
    │
    ├─→ Business Analyst
    │   └─→ pipeline_graph.yaml (owner_confirmed: true)
    │
    ├─→ Separator
    │   └─→ logical_graph.yaml
    │       business_mapping.json
    │       atomic_operations.yaml
    │
    ├─→ Atom Smith (FIREWALL: no business_mapping.json)
    │   Input: atomic_operations.yaml ONLY
    │   └─→ match_results.yaml
    │       atoms/*.py + tests/*.py (new ones)
    │
    ├─→ Assembler (FIREWALL LIFTED: business_mapping.json restored)
    │   Input: match_results.yaml + business_mapping.json + atomic_operations.yaml + pipeline_graph.yaml
    │   └─→ manifest.yaml
    │       config.json
    │
    └─→ Success: Pipeline ready
```

---

## Retry Logic

**On gate FAIL:**
1. Orchestrator extracts error messages from gate validator output
2. Sends error list back to the agent that produced the artifact
3. Agent re-reads the artifact, fixes errors, writes corrected version
4. Orchestrator re-runs gate
5. Max 3 retries per agent; after 3 FAILs, escalate to user

---

## Error Handling

**Gate Validation Errors (agent's job to fix):**
- gate_1: Incomplete graph, missing fields, undefined nodes
- gate_2: Domain leakage in logical_graph
- gate_3: Invalid DAG, cycles, missing dependencies
- gate_4: Unmatched operations, atoms don't exist
- gate_5: Domain leakage in atom code
- gate_6: Invalid manifest/config structure, etlai sync failures

**Escalation to User (orchestrator decides):**
- After 3 retries with same error, ask user for help
- If atom creation fails validation, ask user if they want to create a workaround
- If pipeline goals can't be met with shipped atoms, report what's needed

---

## Implementation Order

1. **Build Orchestrator** — The router and state manager
2. **Build Business Analyst** — Entry point, user interaction
3. **Build Separator** — Mechanical transformation
4. **Build Atom Smith** — Validation + creation
5. **Build Assembler** — Final wiring
6. **Integration Testing** — End-to-end with sales reconciliation prompt

---

## Success Criteria

✅ All 5 agents exist and are documented
✅ Orchestrator successfully routes between agents
✅ Firewall correctly strips/restores business_mapping.json for Atom Smith
✅ Gate validators run and feedback loops work
✅ End-to-end test: sales reconciliation prompt → complete, valid pipeline
✅ All agents refuse out-of-scope work (Business Analyst doesn't code, Atom Smith ignores domain knowledge)
✅ 73 tests passing (existing)
✅ New tests for agent orchestration (5+)
