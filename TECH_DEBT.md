# Tech Debt

Known structural issues that don't need fixing today but should be addressed before the codebase grows further.

## Open-item execution sequence

Do **not** implement multi-backend (#5) or Aider step files (#6) before the Code control plane and task packets exist.

```text
DONE:  #1–#4 runtime fixes
DONE:  #7 BA mediation (Orchestrator owns user channel)
DONE:  #8 Layer detangle (phase vs role vs control docs)

NEXT:  #11 Code-first control plane     ← state machine in Python, not LLM/markdown
 THEN: #10 Task-card router             ← one TaskPacket / one playbook per invoke
 WITH: #9  Atom Smith firewall          ← parallel with #11/#10; before sensitive create
 THEN: #5  Multi-backend AI layer       ← workers on packets (LocalLLM/Cloud); CP stays Code
 THEN: #6  Aider / tool-agnostic UX     ← NEXT_STEP.md generated from TaskSpec
```

**Rule:** “Local LLM orchestration” means **workers** run on local models. Phase advance, confirmation, gates, firewall, and packet assembly stay on **`CodeBackend`**. `ORCHESTRATION.md` is a transitional Claude Code shim that *calls* Python APIs — it is not the control plane.

---

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
| `CodeBackend` | Deterministic Python, no model | **Control plane** (phase advance, confirm, gates, firewall, packet build), file profiling, template fill |
| `EmbeddingBackend` | Vector similarity search | bge-small-en (~33M params) for intent classification, column matching |
| `LocalLLMBackend` | Small local model with constrained output | Gemma 4 / Qwen 3.6 for **worker** tasks: slot filling, ambiguity, separation — never phase routing |
| `CloudBackend` | Capable cloud model (domain-free data only) | Claude / GPT-4 for atom creation, DAG optimization |

### Privacy boundary

```
LOCAL (user data stays on device):        CLOUD (domain-stripped, safe to send):
  - Control plane / phase routing (Code)    - Atom search (Embedding)
  - File inspection (Code)                  - Atom creation (Cloud)
  - Intent classification (Embedding)       - DAG optimization (Cloud, optional)
  - Slot filling (LocalLLM)
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

**When:** After items **#11** (Code control plane) and **#10** (`TaskPacket` / one card per invoke). Backends must receive task cards from a Python state machine — not agent personas or an LLM orchestrator. Then: choose local model serving stack, build intent/slot schemas for 8 pipeline types, calibrate embeddings.

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

**When:** After items **#11** + **#10** (Code control plane owns the loop; `TaskSpec` can generate `NEXT_STEP.md`). Multi-backend (#5) may land in parallel once packets exist, but Aider UX should not reintroduce markdown-as-orchestrator.

---

## 7. ~~Orchestrator-mediated user channel (BA is not an independent session actor)~~ RESOLVED

**Fixed in:** `etlai/orchestrator.py` (BA turn APIs + `confirm_graph` / `prepare_gate1`), `etlai/cli.py` (`etlai create` mediation), scaffold agent prompts + phase playbooks, docs.

Orchestrator owns the user channel for phases 0–1. BA is a worker that drafts `pipeline_graph.yaml` with `owner_confirmed: false` and proposes questions in `ba_questions.json`. Only `Orchestrator.confirm_graph(True)` may set confirmation after explicit user assent. `prepare_gate1()` strips BA-self-confirmed graphs.

---

## 8. ~~Detangle phase playbooks from role prompts~~ RESOLVED

**Fixed in:** `etlai/scaffold/workflow/LAYERS.md`, thinned `agents/*_SYSTEM_PROMPT.md`, purified `phase_0`/`phase_1`.

**Rule:** phases = *what* (task I/O); roles = access policy only; **control plane = Code** (see item #11). Compose turn packets at runtime — required for small-model / multi-backend (item #5).

---

## 9. Atom Smith firewall gaps

**Files:** `etlai/orchestrator.py` (`activate_firewall` / `deactivate_firewall`), `etlai/cli.py` (`etlai create`), `etlai/scaffold/workflow/validators/gate_5_atom_clean.py`, `etlai/scaffold/ORCHESTRATION.md`

**How it works today:** Three layers — (1) physical rename of `business_mapping.json` → `.business_mapping.json.firewalled` during Atom Smith, (2) soft allowlist via `build_agent_context("atom_smith")` + prompt instructions, (3) Gate 5 post-check for domain terms in new atom source.

**Problems:**

1. **`pipeline_graph.yaml` is not physically firewalled.** Docs claim Atom Smith is blocked from both mapping and pipeline graph, but only the mapping is renamed. The graph stays on disk; soft allowlist/prompt is the only barrier.
2. **Gate 5 runs while the firewall is still active.** Gate 5 needs `business_mapping.json` to collect real names for leakage detection. `etlai create` and ORCHESTRATION run gates 4+5 before `deactivate_firewall()`, so when the mapping is hidden Gate 5 skips the leakage scan (`if mapping_path.exists()` → empty `real_names`).
3. **Crash leaves mapping hidden.** `_firewall_active` is in-memory; a crash between activate and deactivate leaves `.business_mapping.json.firewalled` with no restored `business_mapping.json`.
4. **Dotfile hide is shallow.** Renaming in the same directory does not stop tools that list/open hidden files; it is not a sandbox.

**Fix:**
- Physically hide (or move out of project tree) both `business_mapping.json` and `pipeline_graph.yaml` during Atom Smith — or teach Gate 5 to read the firewalled path.
- Deactivate firewall before Gate 5, **or** point Gate 5 at `.business_mapping.json.firewalled` while the firewall is up.
- Add crash-safe restore (try/finally in CLI + `etlai create --restore-firewall` / status check on startup).

**When:** Parallel with #11/#10; must land before relying on `etlai create` for domain-sensitive pipelines. Related to privacy goals in item #5.

---

## 10. Task-card router — one phase (or sub-step) per invoke

**Status:** Design only; not implemented.

**Depends on:** Item **#11** (Code-first control plane). Packets are built and advanced by Python — not by `ORCHESTRATION.md` or an LLM orchestrator agent.

**Problem:** Layers are detangled in docs (#8) and BA mediation exists (#7), but runtime still thinks in **role bundles** (BA = phases 0–1, Separator = 2–3, …). `build_ba_turn_prompt()` still attaches *both* phase 0 and 1 playbooks. Small local models and item #5 backends need **one invoke = one task card**, with roles optional packaging—not the unit of work.

**Goal:** Code control plane builds a `TaskPacket` per invoke and routes it to a worker backend. Role system prompts become optional allowlist overlays; phase/sub-step cards + schemas are mandatory.

### Target packet

```text
TaskPacket:
  task_id: phase_0 | phase_1 | phase_2 | … | ba_slot_fill | …
  playbook_path: workflow/phase_N_*.md   # exactly one
  template_paths: [...]
  readable_paths: [...]                 # from allowlist table, not persona prose
  writable_paths: [...]
  inputs: { prior answers, gate_errors, artifact snippets as needed }
  backend: Code | Embedding | LocalLLM | Cloud   # wired in item #5
```

### Work breakdown

#### A. Catalog & contracts

| # | Task | Notes |
|---|------|--------|
| A1 | Define `TaskSpec` registry (id → playbook, templates, default reads/writes, gate after) | Single source; replace hard-coded role→phases maps in `build_agent_context` |
| A2 | Split oversized phases into sub-step cards where needed for local models | Start with BA: align with item #5 steps (file inspect, intent, slot fill, ambiguity, requirements)—each card ≤ one schema out |
| A3 | Keep phase_2…7 as one card each until measured too large; document max token/complexity budget per card | Avoid premature split |
| A4 | Machine-readable allowlists (YAML/JSON) derived from today’s role tables | Role `.md` files become human docs or generated from allowlists |

#### B. Packet API (on top of #11 state machine)

| # | Task | Notes |
|---|------|--------|
| B1 | `build_task_packet(task_id, **inputs) -> TaskPacket` | Replaces / generalizes `build_ba_turn_prompt`; **exactly one** playbook path |
| B2 | Wire packets into #11 advance loop | After artifact + gate → next `task_id`; mediation loops stay on 0/1 only |
| B3 | `etlai create` runs **per `task_id`** | “Separator” = two sequential packets (2 then 3); no persona spawn |
| B4 | Retry packet = same `task_id` + `gate_errors` in inputs | No re-bundle of sibling phases |
| B5 | Optional `--task phase_3` for resume/debug | Feeds item #6 `NEXT_STEP.md` later |

#### C. Deprecate role-as-unit-of-work

| # | Task | Notes |
|---|------|--------|
| C1 | Ensure CLI/docs don’t re-fat multi-phase role essays | Roles already thinned (#8) |
| C2 | Map legacy role names → list of `task_id`s for UX only | `business_analyst → [phase_0, phase_1]`; packaging, not invoke |
| C3 | Update HOW_TO_USE_AGENTS / PHASE_DEPENDENCY_GRAPH to show task packets | Avoid teaching “agent owns phases” as the runtime model |

#### D. Bridge to multi-backend (item #5)

| # | Task | Notes |
|---|------|--------|
| D1 | Attach `backend` hint on each `TaskSpec` | Code for inspect/gates/user answers; LocalLLM for slot fill/separation; Cloud for atom create |
| D2 | `TaskRouter.execute(packet)` stub that today only assembles prompt text / invokes worker | Real backends land in #5; packet shape must not change |
| D3 | Constrained-output schema path per task (JSON Schema / Pydantic) | Required for LocalLLM; place next to templates |

#### E. Tests & gates

| # | Task | Notes |
|---|------|--------|
| E1 | Assert every built packet references exactly one `phase_*.md` (or one sub-step card) | |
| E2 | Assert no packet for Atom Smith tasks includes mapping/graph paths (with #9 firewall) | |
| E3 | Contract test: role markdown does not restate phase Process sections | Drift guard from #8 |

### Out of scope (this item)

- Code control-plane state machine ownership (item #11)
- Implementing LocalLLM/Embedding/Cloud backends (item #5)
- Aider `NEXT_STEP.md` UX (item #6)
- Firewall physical hardening (item #9)

**When:** Immediately after #11 (or overlapping once the Code loop owns create). Before #5 model serving.

---

## 11. Code-first control plane (not an LLM orchestrator)

**Status:** Design complete; not implemented (docs/sequence locked here).

**Problem:** Today’s wording treats `ORCHESTRATION.md` + `ORCHESTRATOR_SYSTEM_PROMPT.md` + `etlai/orchestrator.py` as co-equal “control plane.” That fits a strong Claude Code driver, but **fails if orchestration also runs on small local models**. Prose agents are bad at phase advance, retries, confirmation ownership, and exact packet assembly.

**Target rule:** Control plane = **deterministic Python (`CodeBackend`)**. LLMs execute **worker** task cards only. “Local LLM orchestration” ≠ “local LLM decides the state machine.”

```text
User ↔ Code control plane ↔ TaskPacket → worker backend → artifacts → gate (Code)
                │                              ↑
                └──── next / retry task_id ────┘
```

| Concern | Owner | Why |
|---------|--------|-----|
| Next `task_id`, loops, max retries | **Code** (`orchestrator.py` → `TaskRouter`) | Small LLMs fail at state machines |
| Build packet (one playbook + paths + inputs) | **Code** `build_task_packet` (#10) | Exactness; no sibling-phase drift |
| User channel / `confirm_graph` | **Code** (+ CLI/UI) | Contract, not model judgment |
| Gates / firewall | **Code** | Already deterministic |
| Slot fill / separation / atom write | **LocalLLM or Cloud** worker on one packet | Narrow constrained I/O |
| `ORCHESTRATION.md` / orchestrator system prompt | **Transitional shim only** | Calls Python APIs until `etlai create` owns the loop |

### Hierarchy

1. **Source of truth:** `etlai/orchestrator.py` (+ `TaskSpec` / `TaskRouter` from #10/#11)
2. **Worker payloads:** phase cards + templates + allowlists
3. **Transitional drivers:** `ORCHESTRATION.md` / Claude prompts — must *call* APIs, not *be* the state machine

`build_ba_turn_prompt()` is the right *shape* (code builds the packet) but incomplete until #10 (one phase only; generalize beyond BA).

### Work breakdown

| # | Task | Notes |
|---|------|--------|
| CP0 | **Non-goal:** LLM agent that freely chooses next phase / sets `owner_confirmed` | Optional later: tiny helper that picks among a **fixed** enum of next-actions, always validated by Code |
| CP1 | ~~Update `LAYERS.md`: control plane = Python; markdown = shim~~ | Done with this tech-debt lock-in |
| CP2 | `etlai create` owns the full phase loop in process | Print/relay user Q&A; call `confirm_graph`, `run_gate`, firewall; do not wait for a prose orchestrator |
| CP3 | State machine API: `current_task_id` / `advance()` / `retry()` | Persisted under `workflow/` (extend `ba_session.json` → `control_session.json`) |
| CP4 | Demote `ORCHESTRATION.md` to “how to call the CLI/APIs” | No longer the runtime brain; split/tool-agnostic under #6 later |
| CP5 | Demote `ORCHESTRATOR_SYSTEM_PROMPT.md` | Document Code ownership; Claude shim only if needed |
| CP6 | Tests: advance/retry/confirm cannot be skipped by worker artifacts alone | Mirror #7 `prepare_gate1` pattern for later phases |

### Interaction with other items

| Item | Relationship |
|------|----------------|
| #7 (done) | Mediation APIs stay; become methods on the Code loop |
| #8 (done) | Layers stay; control-plane *location* corrected to Code |
| #10 | Implements `TaskPacket` on top of this state machine |
| #9 | Firewall activate/deactivate called from Code loop around phase_4/5 |
| #5 | Worker backends only; control plane row stays `CodeBackend` |
| #6 | `NEXT_STEP.md` / Aider are UIs over the same Code state machine |

### Dependency order (canonical)

```text
#7 #8 (done)
  → #11 Code-first control plane
  → #10 Task-card router (TaskSpec + build_task_packet)
  → #9  firewall (parallel OK with #11/#10)
  → #5  multi-backend workers
  → #6  Aider / tool-agnostic step UX
```

**When:** Next — before #10 implementation and before any #5 local-model serving work.

---
