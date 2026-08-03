# Tech Debt

Known structural issues that don't need fixing today but should be addressed before the codebase grows further.

## 1. ~~`_execute_step` injection logic — extract into InputResolver~~ RESOLVED v0.5.2

**Fixed in:** `etlai/helpers/input_resolver.py`

Extracted to `InputResolver` class with `resolve()` method. Supports explicit `inputs_map` for N-file atoms and retains fallback heuristic for backward compat.

---

## 2. ~~step_0 flat config special case~~ RESOLVED v0.6.0

**Fixed in:** `etlai/registry.py:_execute_step` + `gate_6_manifest_valid.py`

Every step — including step 0 — reads `config.json["step_N"]`. Single-atom
pipelines use only `step_0`. Gate 6 requires `step_0` for all pipelines.

---

## 3. ~~Sensor doesn't enforce manifest `pattern:` at runtime~~ RESOLVED v0.5.2

**Fixed in:** `etlai/sensors/hot_folder_sensor.py:_filter_by_patterns()` + `etlai/registry.py:_build_inbox_files_sensor()`

Sensor now accepts `input_patterns` param. Registry extracts transient input patterns from manifest and passes to sensor factory. Only files matching declared patterns trigger the pipeline.

---

## 4. ~~Alphabetical file assignment to left_file/right_file~~ RESOLVED v0.5.2

**Fixed in:** `etlai/helpers/input_resolver.py:order_files_by_pattern()`

Inbox files are reordered to match declared `inputs[].pattern` before assignment. Unmatched files append at end. Falls back to alphabetical when no patterns declared.

---

## 5. Multi-backend AI execution layer (`etlai/ai/`)

**Status:** Design complete, not implemented.

**Problem:** The current orchestrator assumes a single capable cloud model runs all agents. This means user business data (column names, sample rows, domain logic) leaves the device during the Business Analyst phase. Users with sensitive data need local-first execution.

**Design:** Decompose the BA into narrow steps that small local models (Gemma 4, Qwen 3.6) can handle, while keeping atom creation on cloud models (where no domain data is sent). The execution layer needs four backend types:

### Backend types

| Backend | Purpose | Example models |
|---------|---------|----------------|
| `CodeBackend` | Deterministic Python, no model | File profiling, gate validators, template fill |
| `EmbeddingBackend` | Vector similarity search | bge-small-en (~33M params) for intent classification, column matching |
| `LocalLLMBackend` | Small local model with constrained output | Gemma 4 / Qwen 3.6 for slot filling, ambiguity detection |
| `CloudBackend` | Capable cloud model (domain-free data only) | Claude / GPT-4 for atom creation, DAG optimization |

### Privacy boundary

```
LOCAL (user data stays on device):        CLOUD (domain-stripped, safe to send):
  - File inspection (Code)                  - Atom search (Embedding)
  - Intent classification (Embedding)       - Atom creation (Cloud)
  - Slot filling (LocalLLM)                 - DAG optimization (Cloud, optional)
  - Ambiguity detection (LocalLLM+Code)
  - User interaction (Code)
  - Requirements assembly (LocalLLM)
  - Separator / term stripping (LocalLLM)
  - Assembler / manifest wiring (LocalLLM)
```

### Decomposed Business Analyst (6 steps replacing monolithic BA)

| Step | Name | Backend | What it does |
|------|------|---------|-------------|
| 0 | File Inspector | `Code` | Read CSV headers + sample rows, detect dtypes/nulls/row count. Use DuckDB/Polars for profile enrichment (distinct counts, regex pattern detection, auto header-row detection) |
| 1 | Intent Classifier | `Embedding` | Map user sentence to 1 of ~8 canonical intents (join, aggregate, filter, pivot, compute, deduplicate, reshape, multi-step) via cosine similarity against canonical descriptions |
| 2 | Slot Filler | `LocalLLM` | For each intent, fill a fixed question template (3-6 slots) by selecting from closed sets derived from file profile. Semantic RAG pre-filters wide tables to top-5 candidate columns. AST formula builder for computed columns: `[Col_A] [Operator] [Col_B]` |
| 3 | Ambiguity Detector | `Code + LocalLLM` | Deterministic rules first (if top-2 column similarity within 15% → flag). Model handles edge cases only. Never asks the LLM "are you confident?" |
| 4 | User Answers | `Code` (UI) | Present clarifying questions as multiple-choice with sample value previews (e.g., `CUST_ID (e.g. "C-1024", "C-1025")`). Merge into slot dict |
| 5 | Requirements Doc | `LocalLLM` | Pydantic grammar-constrained decoding (Outlines/SGLang) to generate strictly valid JSON requirements from completed slot dict |

### Pre-processing: Clause Splitter (before Step 1)

Multi-intent user queries (e.g., "join sales with catalog then filter last 30 days and sum by region") need decomposition into sequential intent steps before classification. Lightweight rule-based/regex splitter on connectors ("then", "and", comma). Must preserve ordering awareness — "filter then aggregate" ≠ "aggregate then filter".

### Router contract (proposed)

```python
class TaskRouter:
    """Routes each pipeline creation step to the appropriate backend."""

    def __init__(self, config: RouterConfig):
        # config specifies: which local model, embedding model path,
        # cloud API key, escalation thresholds

    def execute(self, task: Task) -> TaskResult:
        # Pick backend based on task.type
        # Run with retry on gate failure
        # Escalate to cloud if local fails 3x (with user consent dialog)
```

### Escalation path

If intent classifier confidence is below threshold or ambiguity detector fires 3+ times, offer user explicit consent: "This pipeline is complex. Send a summary to cloud for help? [Yes / No, I'll simplify]"

### Key constraints

- `LocalLLMBackend` must support constrained/grammar-guided decoding (Outlines, SGLang, llama.cpp grammars)
- `EmbeddingBackend` runs bge-small-en or similar (~33M params) — loads once, stays resident
- No domain data crosses the privacy boundary without explicit user consent
- All backends implement the same `execute(task) -> TaskResult` interface for uniform retry/gate logic

**Dependencies:** `outlines` or `sglang` for constrained decoding, `sentence-transformers` for embeddings, `duckdb` or `polars` for profiling, `ollama` or `llama-cpp-python` for local LLM serving.

**When:** Next major feature cycle. Requires: choosing a local model serving stack, building intent/slot schemas for 8 pipeline types, collecting training examples for embedding calibration.

---

## 6. Aider support — decouple orchestration from Claude Code

**Status:** Design complete, not implemented.

**Problem:** The scaffold currently ships `ORCHESTRATION.md` and `HOW_TO_USE_AGENTS.md` that assume the user runs Claude Code with the "Agent tool" for subagent spawning. Users who prefer Aider (or any other coding assistant) cannot use the 5-agent pipeline creation system. The system should be tool-agnostic so any LLM-powered editor can drive it.

### Current Claude Code coupling points

| File | Coupling |
|------|----------|
| `ORCHESTRATION.md` | References "Agent tool", subagent spawning, parallel agents |
| `HOW_TO_USE_AGENTS.md` | "When a Claude Code session opens this repository..." |
| `scaffold/CLAUDE.md` | `etlai create` assumes Claude Code session |
| Agent system prompts | Written as context for Claude's multi-agent model |

### How Aider differs

| Concept | Claude Code | Aider |
|---------|-------------|-------|
| Agent spawning | Built-in `Agent tool`, parallel subagents | Single conversation, sequential |
| Context control | System prompts per agent, firewall via file hiding | `/add` files to context, `/drop` to remove |
| Orchestration | Model-driven (orchestrator agent picks next step) | Script-driven or user-driven (one step per message) |
| File editing | `Edit` tool, `Write` tool | Unified diff, whole-file, or architect mode |
| Conventions file | `CLAUDE.md` (auto-loaded) | `.aider/conventions.md` or repo-level instructions |

### Design: File-driven step protocol

The key insight: **make each step a self-contained file-in/file-out operation that any coding assistant can execute.** The orchestration becomes a CLI script that tells the user (or Aider) what to do next.

#### Proposed `etlai create` flow for Aider

```bash
etlai create "join sales with catalog and compute margins"
# → Creates pipelines/<name>/workflow/ directory
# → Writes NEXT_STEP.md with instructions for current phase
# → Prints: "Open this project in Aider and follow NEXT_STEP.md"
```

Each `NEXT_STEP.md` contains:
1. What role the assistant plays this step (BA, Separator, etc.)
2. Which files to `/add` to context
3. What artifact to produce (and where to write it)
4. The gate command to run when done

```markdown
# Current Step: Business Analyst (Phase 0-1)

## Context files (add these)
- workflow/phase_0_dejargon.md
- workflow/phase_1_graph.md
- workflow/templates/pipeline_graph.yaml

## Your task
Interview the user about their pipeline needs. Build pipeline_graph.yaml.
Write it to: pipelines/<name>/workflow/pipeline_graph.yaml

## When done, run:
etlai gate 1
```

After each gate pass, `etlai gate N` rewrites `NEXT_STEP.md` with the next phase's instructions.

#### Firewall enforcement for Aider

Claude Code hides files by renaming. For Aider, the equivalent is:
- `NEXT_STEP.md` explicitly says "DO NOT /add business_mapping.json"
- `.aiderignore` file updated per-phase to exclude firewalled files
- `etlai gate 4` writes `.aiderignore` blocking `business_mapping.json` before Atom Smith phase
- `etlai gate 5` removes the block

#### Aider conventions file (`.aider/conventions.md`)

```markdown
# Aider Conventions for ETLai

- Follow NEXT_STEP.md in the pipeline workflow directory
- Only read/write files listed in NEXT_STEP.md
- Run `etlai gate N` after completing each step
- Never add business_mapping.json during atom creation phases
- Atoms must pass litmus test: rename columns to A,B,C → still works
```

#### CLI additions needed

| Command | Purpose |
|---------|---------|
| `etlai create "<request>"` | Initialize pipeline, write first NEXT_STEP.md |
| `etlai gate <N>` | Run gate validator, advance NEXT_STEP.md on pass |
| `etlai status` | Show current phase, what's done, what's next |
| `etlai firewall on/off` | Manually toggle business_mapping.json visibility |

### What stays the same

- Gate validators (deterministic Python scripts — tool-agnostic)
- Artifact schemas (YAML/JSON files — tool-agnostic)
- Agent system prompts (usable as context regardless of tool)
- The orchestrator Python class (still used by CLI under the hood)
- Privacy boundary and multi-backend AI layer (item #5 above)

### What changes

- `ORCHESTRATION.md` → Split into tool-specific guides: `ORCHESTRATION_CLAUDE_CODE.md` and `ORCHESTRATION_AIDER.md`
- `HOW_TO_USE_AGENTS.md` → Rewrite as tool-agnostic "Pipeline Creation Guide"
- `etlai create` → No longer assumes Claude Code; becomes a step-file generator
- Scaffold ships both `.aider/` conventions and `CLAUDE.md`
- `.aiderignore` becomes a managed file (written/modified by `etlai gate`)

### Aider-specific optimizations

1. **Architect mode for BA phase:** Aider's `/architect` mode lets a smarter model plan while a cheaper one edits — maps well to the BA (needs judgment) producing artifacts (structured YAML)
2. **`/add` as context boundary:** Each NEXT_STEP.md lists exactly which files to add — this is the Aider equivalent of the Claude Code agent's `readable_files` list
3. **`/run` for gates:** Aider's `/run` command executes shell commands inline — users can `/run etlai gate 1` without leaving the session
4. **Model selection per step:** Aider supports `--model` flag — users can use a capable model for BA and a local model for Separator/Assembler within the same session by restarting with a different model flag

### Migration path

1. Ship `etlai gate` CLI command (thin wrapper around `Orchestrator.run_gate()`)
2. Ship `NEXT_STEP.md` template generation (one template per phase)
3. Add `.aider/conventions.md` to scaffold
4. Write `ORCHESTRATION_AIDER.md` (step-by-step guide for Aider users)
5. Update README/HOW_TO_USE_AGENTS.md to mention both tools
6. Test end-to-end with Aider + DeepSeek/Qwen (local models)

**Dependencies:** Aider 0.50+ (supports conventions files, `/run` command, `.aiderignore`).

**When:** After item #5 (multi-backend layer). The file-driven step protocol is the prerequisite for both Aider support AND the local model decomposition — they share the "each step is self-contained with explicit inputs/outputs" property.

---

## 7. Orchestrator-mediated user channel (BA is not an independent session actor)

**Status:** Design decision made; not implemented.

**Problem:** Phases 0–1 currently treat the Business Analyst as an independent entity that talks to the user directly while the Orchestrator waits. That splits session ownership: BA owns the conversational loop and self-sets `owner_confirmed`, while Orchestrator still owns gates/retries/routing. In CLI and subagent runtimes there is one user channel — so either BA *is* the session (Orchestrator isn’t orchestrating), or handoff is fragile. It also doesn’t scale when later phases need rare user questions (e.g. inbox filename patterns).

**Target design:** Orchestrator owns the user channel and phase state machine. BA remains a domain specialist (propose questions, draft/revise `pipeline_graph.yaml`) but does not hold a direct user session. Orchestrator alone sets `owner_confirmed` after explicit user assent, then runs gate 1.

```
Current:  User ↔ BA (independent loop) → artifact → Orchestrator (gate)
Target:   User ↔ Orchestrator ↔ BA (worker turns) → Orchestrator sets confirmed → gate
```

### What needs changing

#### Control / code

| Area | Change |
|------|--------|
| `etlai/orchestrator.py` | Add BA turn API: accept user request/feedback → invoke BA context → return proposed questions + draft graph diff; add `confirm_graph(user_said_yes)` that writes `owner_confirmed: true` (BA must not write this flag). Track phase-0/1 loop state (round count, pending questions). |
| `etlai create` / CLI wiring | Orchestrator drives the interactive loop for phases 0–1 (print BA questions, collect answers, re-invoke BA). After confirmation, run gate 1 and continue Separator → … as today. |
| Gate / retry path | On gate 1 FAIL, Orchestrator re-prompts BA with validator errors (no user loop inside BA). Optionally surface a short summary to the user if retries exhaust. |
| Future rare questions (post–phase 1) | Same channel: Orchestrator may ask user; never spawn Separator/Atom Smith/Assembler as user-facing agents. |

#### Agent contracts (scaffold prompts)

| File | Change |
|------|--------|
| `etlai/scaffold/agents/ORCHESTRATOR_SYSTEM_PROMPT.md` | Own user I/O for phases 0–1; present BA questions/graph; collect answers; set `owner_confirmed` only on explicit yes; do not invent domain answers. Update “Loops with User?” to YES for confirmation/Q&A relay (still NO for domain decisions). |
| `etlai/scaffold/agents/BUSINESS_ANALYST_SYSTEM_PROMPT.md` | Remove direct user loop. Inputs: user request + Orchestrator-relayed answers. Outputs: clarifying questions (structured) and/or updated `pipeline_graph.yaml` with `owner_confirmed: false`. Explicitly forbid setting `owner_confirmed: true`. |
| `etlai/scaffold/ORCHESTRATION.md` | Replace “BA interacts with the user directly” with mediated turn protocol; document confirmation as Orchestrator step before gate 1. |
| `etlai/scaffold/HOW_TO_USE_AGENTS.md` | User-facing flow: talk to Orchestrator/`etlai create`; BA works behind it. |
| `etlai/scaffold/workflow/phase_0_dejargon.md` | Questions are *proposed* for Orchestrator to ask, not asked by BA in-session. |
| `etlai/scaffold/workflow/phase_1_graph.md` | Remove “BA sets `owner_confirmed`”; confirmation is Orchestrator-owned after user yes. |
| `etlai/scaffold/workflow/CLAUDE.md` + `etlai/scaffold/CLAUDE.md` | Agent table: Orchestrator relays user Q&A; BA does not loop with user as session owner. |

#### Docs / architecture tables

| File | Change |
|------|--------|
| `ARCHITECTURE.md` | Agent table: Orchestrator loops with user (relay only); BA loops with user = No (specialist turns only). Document confirmation ownership. |
| `docs/AGENT_IMPLEMENTATION_PLAN.md` | BA section: no Interact-with-user tool; Orchestrator phase owns loop + `owner_confirmed`. |
| `docs/AGENT_BUILD_ROADMAP.md` | Same; “Only Business Analyst talks to user” → “Only Orchestrator talks to user; BA is invoked as worker”. |
| `docs/PHASE_DEPENDENCY_GRAPH.md` | Show User ↔ Orchestrator, Orchestrator → BA (not User ↔ BA). |
| `README.md` / `CHANGELOG.md` | When implemented: describe mediated BA under pipeline creation. |

#### Tests

| Area | Change |
|------|--------|
| `tests/test_orchestrator.py` | Cover: BA turn without `owner_confirmed`; `confirm_graph` sets flag; BA prompt/context never instructed to confirm; gate 1 retry does not require BA↔user session. |
| New contract tests (optional) | Snapshot/assert BA system prompt forbids `owner_confirmed: true`; Orchestrator prompt requires mediated confirmation. |

### What stays the same

- BA still owns domain understanding and graph content (sources, nodes, edges, triggers).
- Separator / Atom Smith / Assembler stay non-interactive.
- Firewall, gate validators, and artifact schemas unchanged.
- Phase ordering and artifact paths unchanged.

### Interaction with other tech debt

- **Item #5 (multi-backend):** Decomposed BA steps (slot fill, ambiguity, user answers) already assume a Code/UI “User Answers” step outside the model — aligns with Orchestrator-owned channel; implement mediation before or with that decomposition.
- **Item #6 (Aider / NEXT_STEP.md):** File-driven flow should describe Orchestrator/`etlai create` as the interviewer; BA role in `NEXT_STEP.md` = produce questions + draft graph, not “interview the user” as session owner.

**When:** Before hardening `etlai create` as the primary user entrypoint (before or alongside item #6 step protocol). Do not ship a polished interactive create UX while BA still owns the session.
