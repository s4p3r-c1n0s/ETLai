# Agent Build Roadmap — Next Steps

## Status: ✅ Foundation Complete

All system prompts written. Each agent knows exactly what it does, what it knows, and what it doesn't know. Firewall rules documented. Artifact handoff sequence clear.

**Files created:**
- `AGENT_IMPLEMENTATION_PLAN.md` — Detailed design for 5 agents
- `etlai/scaffold/agents/ORCHESTRATOR_SYSTEM_PROMPT.md` — Main routing agent
- `etlai/scaffold/agents/BUSINESS_ANALYST_SYSTEM_PROMPT.md` — User-facing, phases 0-1
- `etlai/scaffold/agents/SEPARATOR_SYSTEM_PROMPT.md` — Mechanical, phases 2-3
- `etlai/scaffold/agents/ATOM_SMITH_SYSTEM_PROMPT.md` — Firewalled, phases 4-5
- `etlai/scaffold/agents/ASSEMBLER_SYSTEM_PROMPT.md` — Wiring, phases 6-7

---

## Next: Build the Agents (6 Implementation Steps)

### Step 1: Orchestrator CLI Entry Point

**Where:** Create a new command or modify existing CLI to invoke the orchestrator flow.

**What it does:**
1. Accept user's business request
2. Create `pipelines/<name>/workflow/` directory
3. Spawn Business Analyst subagent
4. Run gates and route between agents
5. Report final status

**Inputs:**
- User request (text)
- Optional: pipeline_name

**Key code to write:**
- Gate validator runner (subprocess calls)
- Agent spawning logic (use `Agent` tool)
- Firewall enforcement (strip/restore business_mapping.json)
- Retry logic (max 3 attempts per agent)
- Error extraction from gate output

**Tests needed:**
- Orchestrator routes successfully between phases
- Firewall correctly blocks Atom Smith from seeing business_mapping
- Gate validators run and failures trigger retries
- Final status message printed correctly

---

### Step 2: Business Analyst Implementation

**Where:** Scaffoldable worker agent (no user session).

**What it does:**
1. Read phase_0_dejargon.md / phase_1_graph.md
2. **Propose** clarifying questions to `ba_questions.json` (Orchestrator relays)
3. Build `pipeline_graph.yaml` with `owner_confirmed: false`
4. Exit turn; Orchestrator loops with user and alone calls `confirm_graph(True)`

**Inputs:**
- User request + Orchestrator-relayed answers (`ba_session.json`)

**Key code to write:**
- Question proposals based on incomplete graph
- Draft graph writes (never set owner_confirmed true)
- Orchestrator APIs: `start_ba_session`, `build_ba_turn_prompt`, `confirm_graph`, `prepare_gate1`

**Tests needed:**
- BA turn prompt forbids owner_confirmed true
- confirm_graph alone sets the flag
- prepare_gate1 strips BA-self-confirmed graphs
- record_user_answers feeds next turn prompt

---

### Step 3: Separator Implementation

**Where:** Non-interactive, mechanical translation.

**What it does:**
1. Read pipeline_graph.yaml
2. Extract business operations
3. Create generic placeholders (col_a, threshold_1, etc.)
4. Build business_mapping.json (domain ↔ placeholder)
5. Build logical_graph.yaml (zero domain terms)
6. Build atomic_operations.yaml (single-verb DAG)

**Inputs:**
- pipeline_graph.yaml

**Key code to write:**
- Placeholder generation strategy
- Domain term detection and mapping
- Operation splitting (compound → single-verb)
- DAG validation (no cycles, valid dependencies)
- Three YAML writers

**Tests needed:**
- No domain terms in output YAMLs
- All domain terms in business_mapping
- DAG is valid and acyclic
- Placeholders are consistent

---

### Step 4: Atom Smith Implementation

**Where:** Firewalled, no business knowledge.

**What it does:**
1. Read atomic_operations.yaml (ONLY)
2. For each operation: search shipped atoms + user atoms/
3. If found: add to match_results.yaml
4. If not found: write new atom + tests
5. Apply litmus test (rename to A,B,C → still works?)

**Inputs:**
- atomic_operations.yaml

**Key code to write:**
- Shipped atoms search/match logic
- Atom code template writer (follows atoms/CLAUDE.md)
- Test code generator (generic column names A, B, C)
- Litmus test application (domain knowledge detector)
- match_results.yaml writer

**Tests needed:**
- Shipped atoms correctly matched
- New atoms created with generic names only
- Tests use A, B, C columns
- Litmus test catches domain leakage

---

### Step 5: Assembler Implementation

**Where:** Wires manifest + config from all inputs.

**What it does:**
1. Read all four inputs (match_results, business_mapping, atomic_operations, pipeline_graph)
2. Linearize DAG (convert branching to linear steps)
3. Translate col_a → real_name for config.json
4. Build manifest.yaml with steps, inputs, triggers, inject_as
5. Set path: ask, write config.json, final rename_columns
6. Run etlai sync

**Inputs:**
- match_results.yaml
- business_mapping.json
- atomic_operations.yaml
- pipeline_graph.yaml

**Key code to write:**
- DAG linearization (branches → input_from)
- Placeholder → real value translation
- manifest.yaml builder
- config.json builder
- inject_as wirer
- etlai sync runner

**Tests needed:**
- Zero placeholders in final config.json
- All real values translated correctly
- manifest.yaml passes etlai sync
- Folders created: inbox/, staging/, processed/, rejected/, output/, reference/

---

### Step 6: End-to-End Integration Test

**Where:** Test the full 5-agent pipeline.

**What to test:**
1. Orchestrator spawns all 5 agents in sequence
2. All gates pass
3. Firewall correctly enforces/lifts for Atom Smith
4. Final pipeline is valid and runnable
5. No domain knowledge in atoms or manifest

**Test input:**
- Sales reconciliation prompt (or similar)

**Expected output:**
- `pipelines/weekly_sales_reconciliation/manifest.yaml` (valid)
- `pipelines/weekly_sales_reconciliation/config.json` (real values)
- All folders created
- `etlai sync` passes
- Tests suite: 73 → 80+ (new agent tests)

---

## Build Order

**Recommended sequence:**

1. **Business Analyst** — Easiest entry point (user-facing loop)
2. **Separator** — Mechanical, no surprises
3. **Atom Smith** — Trickiest (firewall enforcement, litmus test)
4. **Assembler** — Complex but deterministic
5. **Orchestrator** — Ties everything together
6. **Integration test** — Validates the whole system

## Architecture Review

Before building, verify:

✅ **Firewall Logic** — Orchestrator must STRIP business_mapping.json before calling Atom Smith
✅ **Gate Validators** — All 6 gates exist and work correctly
✅ **Artifact Paths** — All agents write to `pipelines/<name>/workflow/` by default
✅ **Error Extraction** — Gate output can be parsed for error messages
✅ **Retry Logic** — Agents can fix and re-run on gate FAIL
✅ **User Interaction** — Only Orchestrator talks to user; BA is a worker; others are silent

## Testing Strategy

- **Unit tests** — Each agent tested in isolation (mock inputs/outputs)
- **Integration test** — Full 5-agent pipeline with real artifacts
- **Regression test** — Ensure existing 73 tests still pass
- **Edge cases** — Branching pipelines, reference files, multiple outputs, input_from

## Success Criteria

- ✅ All 5 agents built and documented
- ✅ Orchestrator successfully routes between agents
- ✅ Firewall enforced correctly
- ✅ Gates validate and provide actionable errors
- ✅ Retry logic works (agent fixes issues, gate passes)
- ✅ End-to-end test: sales reconciliation prompt → valid pipeline
- ✅ No domain knowledge in atoms
- ✅ 80+ tests passing
- ✅ Each agent refuses out-of-scope work

---

## File Locations Summary

```
Prompts (done):
├── etlai/scaffold/agents/ORCHESTRATOR_SYSTEM_PROMPT.md
├── etlai/scaffold/agents/BUSINESS_ANALYST_SYSTEM_PROMPT.md
├── etlai/scaffold/agents/SEPARATOR_SYSTEM_PROMPT.md
├── etlai/scaffold/agents/ATOM_SMITH_SYSTEM_PROMPT.md
├── etlai/scaffold/agents/ASSEMBLER_SYSTEM_PROMPT.md
├── etlai/scaffold/HOW_TO_USE_AGENTS.md
├── docs/AGENT_IMPLEMENTATION_PLAN.md
└── docs/AGENT_BUILD_ROADMAP.md (this file)

To be created:
├── etlai/cli.py (or new entry point) — Orchestrator caller
├── etlai/agents/ — Agent code (if modularized)
├── tests/test_orchestrator.py — Gate runner, firewall enforcement, retry logic
├── tests/test_business_analyst.py — Loop, graph building, confirmation
├── tests/test_separator.py — Placeholder generation, DAG building, mapping
├── tests/test_atom_smith.py — Matching, creation, litmus test, firewall compliance
├── tests/test_assembler.py — Linearization, translation, manifest/config building
└── tests/test_agents_integration.py — End-to-end (sales reconciliation prompt)
```

---

## Quick Reference: Agent Responsibilities

| Agent | Phases | Loops? | Knows Domain? | Knows Atoms? | Firewall? |
|-------|--------|--------|---------------|-------------|-----------|
| **Orchestrator** | All | YES (relay + confirm) | No | No | Enforcer |
| **Business Analyst** | 0-1 | No (worker) | YES | No | — |
| **Separator** | 2-3 | No | No | No | — |
| **Atom Smith** | 4-5 | No | No | YES | ❌ BLOCKED |
| **Assembler** | 6-7 | No | YES | YES | ✅ ALLOWED |

---

## Questions to Clarify Before Building

1. **Where should Orchestrator code live?** 
   - Option A: New command in `etlai/cli.py` (e.g., `etlai create-pipeline`)
   - Option B: Separate `etlai/orchestrator.py` module
   - Option C: Python script that users invoke directly

2. **Should agents be modularized?**
   - Option A: All in main context (simplest)
   - Option B: Separate modules in `etlai/agents/` (cleaner)
   - Option C: Standalone scripts in `etlai/scaffold/agents/` (most isolated)

3. **How to pass firewall state to orchestrator?**
   - Option A: Orchestrator tracks state internally
   - Option B: Write state to a file between agent calls
   - Option C: Pass as environment variable to subprocess agents

Pick options that match your architecture preference before building.

---

## Next Session Handoff

If continuing later:

1. Read this roadmap (you're reading it now ✓)
2. Read `docs/AGENT_IMPLEMENTATION_PLAN.md` for detailed architecture
3. Read the 5 system prompts in `etlai/scaffold/agents/`
4. Read `etlai/scaffold/HOW_TO_USE_AGENTS.md` for end-user perspective
5. Pick Build Step 1 (Business Analyst) and start coding
6. Test incrementally (unit tests for one agent at a time)
7. When all agents work, wire orchestrator
8. Run end-to-end integration test

The foundation is solid. The agents know their jobs. Now build them.
