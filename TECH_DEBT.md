# Tech Debt

Known structural issues that don't need fixing today but should be addressed before the codebase grows further.

## 1. `_execute_step` injection logic — extract into InputResolver

**File:** `etlai/registry.py:258-270`

**Problem:** The file/path injection logic in `_execute_step` has grown by accretion into a 5-branch conditional that handles:
- is_first + 2 files → left_file + right_file
- is_first + 1 file + right_file present → left_file
- is_first + 1 file → input_file
- not first + right_file present → left_file = prev_output
- not first → input_file = prev_output

Every new atom input pattern requires another branch. The logic is tested but hard to reason about in isolation.

**Fix:** Extract into a small `InputResolver` class with explicit methods (`resolve_first_step`, `resolve_continuation`) and a lookup table for atom signatures.

**When:** Before adding any atom that takes 3+ input files or has non-standard input patterns.

---

## 2. step_0 flat config special case

**File:** `etlai/registry.py:205-208`

**Problem:** Composite step 0 reads the ENTIRE flat `config.json` top-level dict. Steps 1+ read `step_N` keys. This means config.json has a hybrid structure: top-level params for step 0 + nested `step_1`, `step_2`, etc. for the rest. Gate 6 was updated to not require `step_0` but the asymmetry is confusing.

**Fix:** Unify to always use `step_N` keys (step 0 reads `step_0`). Requires migration of existing pipelines.

**When:** Next major version (breaking change). Needs migration script for existing config.json files.

---

## 3. Sensor doesn't enforce manifest `pattern:` at runtime

**File:** `etlai/sensors/hot_folder_sensor.py:11`

**Problem:** The sensor uses a hardcoded `^(.+)\.(csv|xlsx)$` regex for file detection. The manifest `inputs[].pattern` field (e.g., `"sales_*.csv"`) is only validated at `etlai sync` time, never at runtime. Any csv/xlsx file triggers the pipeline.

**Fix:** Pass the manifest pattern to the sensor factory and filter files by it before triggering.

**When:** If a user reports wrong files triggering a pipeline. Low priority since atoms will fail on wrong input anyway.

---

## 4. Alphabetical file assignment to left_file/right_file

**File:** `etlai/helpers/folders.py:116-119` (sorted), `etlai/registry.py:261-262`

**Problem:** When 2+ files are in inbox, they're assigned to `left_file`/`right_file` alphabetically. There's no way to guarantee which file is which except by naming convention. The manifest `inputs[].pattern` could be used to match files to roles but isn't.

**Fix:** Match inbox files to declared transient inputs by pattern, then assign to params by input order.

**When:** When a user has multiple transient inputs with different schemas that must not be swapped.

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
