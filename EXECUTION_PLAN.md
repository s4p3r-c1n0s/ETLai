# Pipeline Creation — Multi-Agent Execution Plan

## Architecture

Five agents collaborate to turn a user's business request into a running ETLai pipeline.

```
┌─────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR                              │
│  Drives sequence · Runs gate validators · Enforces firewalls    │
│  Routes artifacts between agents · Retries on FAIL              │
└────────┬──────────────┬──────────────┬──────────────┬───────────┘
         │              │              │              │
    ┌────▼────┐   ┌─────▼─────┐  ┌────▼────┐  ┌─────▼─────┐
    │ Business│   │ Separator │  │  Atom   │  │ Assembler │
    │ Analyst │   │           │  │  Smith  │  │           │
    │(Ph 0-1) │   │ (Ph 2-3)  │  │(Ph 4-5) │  │ (Ph 6-7)  │
    └─────────┘   └───────────┘  └─────────┘  └───────────┘
```

### Trust Boundary (The Firewall)

```
business_mapping.json ──► Separator produces it
                      ──► Assembler consumes it
                      ──✘ Atom Smith NEVER receives it
```

This is the entire architectural point. The orchestrator enforces it.

---

## Agents

### 1. Orchestrator

**Role:** Sequence controller. No domain knowledge.

**Responsibilities:**
- Start the pipeline creation flow
- Pass artifacts between agents (respecting firewalls)
- Run gate validator scripts between phases
- Retry on FAIL (pass errors back to the responsible agent)
- Report final status to user

**Does NOT:**
- Read or interpret business data
- Make domain decisions
- Touch atom code or config values

---

### 2. Business Analyst (Phases 0-1)

**Role:** Understand user's request, build the complete business process graph.

**Input:** User's raw request in domain jargon

**Output:** `pipeline_graph.yaml` (confirmed complete by user)

**Behavior:**
- Phase 0: Dejargon — expand abbreviations, clarify terms, ask questions
- Phase 1: Build full graph — nodes, edges, data sources, triggers, outputs
- Loops with user until `owner_confirmed: true`
- Once confirmed, hands off to orchestrator. Never called again.

**Context given:**
- `workflow/phase_0_dejargon.md`
- `workflow/phase_1_business_graph.md`
- `workflow/templates/pipeline_graph.yaml` (schema)

**Gate on exit:** `gate_1_graph_complete.py` → PASS

---

### 3. Separator (Phases 2-3)

**Role:** Strip domain terms and atomize into smallest operations.

**Input:** `pipeline_graph.yaml`

**Output:**
- `logical_graph.yaml` — generic operations only
- `business_mapping.json` — domain ↔ generic translation table
- `atomic_operations.yaml` — single-verb operations with DAG

**Behavior:**
- Phase 2: Replace every domain term with a generic placeholder. Produce the mapping.
- Phase 3: Split compound operations into single-verb atomic chunks. Build DAG.
- No user interaction. Mechanical translation.

**Context given:**
- `workflow/phase_2_separation.md`
- `workflow/phase_3_atomize.md`
- `workflow/templates/logical_graph.yaml` (schema)
- `workflow/templates/business_mapping.json` (schema)
- `workflow/templates/atomic_operations.yaml` (schema)

**Gates on exit:**
- After Phase 2: `gate_2_no_leakage.py` → PASS
- After Phase 3: `gate_3_dag_valid.py` → PASS

---

### 4. Atom Smith (Phases 4-5)

**Role:** Find or create generic atoms for each operation.

**Input:** `atomic_operations.yaml` (ONLY — no business_mapping, no pipeline_graph)

**Output:**
- `match_results.yaml` — each operation matched to shipped atom or marked "create"
- New atom files: `atoms/<verb>_<object>.py` + tests (Phase 5 only, if unmatched ops exist)

**Behavior:**
- Phase 4: Search shipped atoms list + user atoms/ directory. Match by operation verb.
- Phase 5: For unmatched operations, write new generic atoms. Apply litmus test.
- Never sees what the data represents. Only knows "join on two columns" not "join on SKU".

**Context given:**
- `workflow/phase_4_match.md`
- `workflow/phase_5_create_atom.md`
- `atoms/CLAUDE.md` (atom creation law)
- `workflow/templates/match_results.yaml` (schema)
- Shipped atoms list (from scaffold CLAUDE.md)

**FIREWALL:** Orchestrator strips `business_mapping.json` from this agent's context. If the agent requests it, orchestrator REFUSES.

**Gates on exit:**
- After Phase 4: `gate_4_match_coverage.py` → PASS
- After Phase 5: `gate_5_atom_clean.py` → PASS (scans for domain leakage)

---

### 5. Assembler (Phases 6-7)

**Role:** Wire atoms into a running pipeline with real business values.

**Input:**
- `match_results.yaml` — which atom per operation
- `business_mapping.json` — real column names, thresholds, formulas
- `atomic_operations.yaml` — execution order
- `pipeline_graph.yaml` — triggers, data source roles

**Output:**
- `pipelines/<name>/manifest.yaml`
- `pipelines/<name>/config.json`
- Final step: `rename_columns` with output mapping (Phase 7 rehydration)

**Behavior:**
- Phase 6: Translate generic placeholders → real values using business_mapping. Wire inject_as for reference files. Set `path: ask`. Set triggers.
- Phase 7: Add rename_columns as last step with output_columns from business_mapping.
- Run `etlai sync` to validate.

**Context given:**
- `workflow/phase_6_assemble.md`
- `workflow/phase_7_rehydrate.md`
- `pipelines/CLAUDE.md` (assembly law)

**Gate on exit:** `gate_6_manifest_valid.py` → PASS

---

## Execution Flow

```
User Request
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│ ORCHESTRATOR: Start                                     │
│   1. Spawn Business Analyst with user's request         │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ BUSINESS ANALYST: Phases 0-1                            │
│   - Dejargon user's request                             │
│   - Build pipeline_graph.yaml                           │
│   - Loop with user until confirmed                      │
│   - Return: pipeline_graph.yaml                         │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ ORCHESTRATOR: Gate 1                                    │
│   - Run gate_1_graph_complete.py                        │
│   - FAIL → send errors back to Business Analyst         │
│   - PASS → proceed                                      │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ SEPARATOR: Phases 2-3                                   │
│   - Input: pipeline_graph.yaml                          │
│   - Produce: logical_graph.yaml + business_mapping.json │
│   - Produce: atomic_operations.yaml                     │
│   - Return: all three artifacts                         │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ ORCHESTRATOR: Gates 2 + 3                               │
│   - Run gate_2_no_leakage.py                            │
│   - Run gate_3_dag_valid.py                             │
│   - FAIL → send errors back to Separator                │
│   - PASS → proceed                                      │
│   - FIREWALL: Remove business_mapping.json from context │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ ATOM SMITH: Phases 4-5                                  │
│   - Input: atomic_operations.yaml ONLY                  │
│   - Search shipped atoms, match operations              │
│   - Create new atoms if needed (generic, tested)        │
│   - Return: match_results.yaml + new atom files         │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ ORCHESTRATOR: Gates 4 + 5                               │
│   - Run gate_4_match_coverage.py                        │
│   - Run gate_5_atom_clean.py (if new atoms created)     │
│   - FAIL → send errors back to Atom Smith               │
│   - PASS → proceed                                      │
│   - RESTORE: Add business_mapping.json back to context  │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ ASSEMBLER: Phases 6-7                                   │
│   - Input: match_results + business_mapping +           │
│            atomic_operations + pipeline_graph            │
│   - Translate placeholders → real values                │
│   - Wire manifest.yaml + config.json                    │
│   - Add rename_columns final step                       │
│   - Run etlai sync                                      │
│   - Return: manifest.yaml + config.json                 │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ ORCHESTRATOR: Gate 6 + Done                             │
│   - Run gate_6_manifest_valid.py                        │
│   - FAIL → send errors back to Assembler                │
│   - PASS → Report success to user                       │
│   - Print: "Pipeline ready. Run `etlai sync` then       │
│             drop files into inbox/"                      │
└─────────────────────────────────────────────────────────┘
```

---

## Implementation Steps

### Step 1: Define Agent Interfaces

For each agent, specify:
- System prompt (what it knows, what it must not do)
- Tools available (file read/write, etlai CLI, gate validators)
- Input schema (what artifacts it receives)
- Output schema (what artifacts it must produce)
- Retry behavior (what happens on gate FAIL)

### Step 2: Build the Orchestrator

The orchestrator is the only stateful component:
- Holds the pipeline working directory path
- Tracks current phase
- Manages artifact handoff (passes files, not content in prompts where possible)
- Enforces the firewall (strips business_mapping from Atom Smith's context)
- Runs gate validators as subprocess calls
- Implements retry: on FAIL, passes error messages back to the agent with "fix these"

### Step 3: Build Business Analyst Agent

- System prompt: phase_0 + phase_1 playbooks
- Tools: read/write pipeline_graph.yaml, ask user questions
- Loop condition: user confirms graph is complete
- Exit: return path to pipeline_graph.yaml

### Step 4: Build Separator Agent

- System prompt: phase_2 + phase_3 playbooks
- Tools: read pipeline_graph.yaml, write logical_graph + business_mapping + atomic_operations
- No user interaction
- Exit: return paths to all three artifacts

### Step 5: Build Atom Smith Agent

- System prompt: phase_4 + phase_5 playbooks + atoms/CLAUDE.md
- Tools: read atomic_operations.yaml, search shipped atoms, write new atom files + tests
- CANNOT read: business_mapping.json, pipeline_graph.yaml, config.json
- Exit: return path to match_results.yaml + list of new atom files

### Step 6: Build Assembler Agent

- System prompt: phase_6 + phase_7 playbooks + pipelines/CLAUDE.md
- Tools: read all artifacts, write manifest.yaml + config.json, run `etlai sync`
- Exit: return paths to manifest.yaml + config.json

### Step 7: Integration Testing

Test the full flow with the sales reconciliation prompt:
- Input: "Build me a pipeline that takes weekly sales CSVs, enriches with product catalog, flags low-margin items, and produces a weekly summary"
- Expected: 5 agents cooperate, gates pass, pipeline created with zero domain leakage in atoms

### Step 8: Edge Case Handling

- What if gate FAIL persists after 3 retries? → Escalate to user with error context
- What if no shipped atom matches? → Atom Smith creates; gate_5 validates
- What if user abandons Phase 1? → Orchestrator cleans up partial artifacts
- What if a created atom fails gate_5 (domain leakage)? → Atom Smith gets specific leakage report, rewrites

---

## Technology Options

| Component | Option A (MCP) | Option B (Claude Code subagents) |
|-----------|----------------|----------------------------------|
| Orchestrator | MCP server with tool routing | Claude Code session with Agent tool |
| Business Analyst | Claude via API with tools | Subagent with user-facing I/O |
| Separator | Claude via API | Subagent (file-only, no user I/O) |
| Atom Smith | Claude via API (sandboxed) | Subagent (restricted file access) |
| Assembler | Claude via API | Subagent (full file access) |
| Gate validators | Subprocess calls | Bash tool calls |

**Recommended start:** Option B (Claude Code subagents). Simplest to prototype. The Agent tool already provides isolation. Firewall enforced by what we put in the agent's prompt (it doesn't receive business_mapping.json content).

---

## File Layout After Execution

```
pipelines/<name>/
├── workflow/
│   ├── pipeline_graph.yaml      ← Business Analyst output
│   ├── logical_graph.yaml       ← Separator output
│   ├── business_mapping.json    ← Separator output
│   ├── atomic_operations.yaml   ← Separator output
│   └── match_results.yaml       ← Atom Smith output
├── manifest.yaml                ← Assembler output
├── config.json                  ← Assembler output
├── inbox/
├── staging/
├── processed/
├── rejected/
├── output/
└── reference/

atoms/                           ← Atom Smith output (if new atoms created)
├── <new_atom>.py
└── ...

tests/
└── test_<new_atom>.py           ← Atom Smith output
```
