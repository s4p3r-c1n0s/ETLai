# Pipeline Creation Orchestration Script

**When a user asks you to create a pipeline, follow this script exactly.**

You are the orchestrator. You coordinate 4 subagents, validate gates between them, and enforce the firewall. You do NOT write atoms, config, or business logic yourself.

---

## Prerequisites

```python
from pathlib import Path
from etlai.orchestrator import Orchestrator, sanitize_pipeline_name

project_root = Path(".")  # or wherever etlai.yaml lives
```

---

## Step 1: Initialize

```python
pipeline_name = sanitize_pipeline_name(user_request)  # or ask user for name
orch = Orchestrator(project_root=project_root, pipeline_name=pipeline_name)
workflow_dir = orch.initialize()
```

Tell the user: "Creating pipeline `{pipeline_name}`. I'll ask you some questions to understand what you need."

---

## Step 2: Spawn Business Analyst (Phases 0-1)

Use the **Agent tool** to spawn a subagent with this prompt:

```
You are the Business Analyst agent for ETLai pipeline creation.

Read the system prompt at: {orch.build_agent_context("business_analyst")["system_prompt"]}
Read the phase playbooks at:
- workflow/phase_0_dejargon.md
- workflow/phase_1_graph.md

The user's request is: "{user_request}"

Your job:
1. Ask the user clarifying questions about their data pipeline needs
2. Build a pipeline_graph.yaml incrementally
3. Show the user the graph after each update
4. Loop until user confirms: "Is this complete and correct?"
5. On confirmation, write the YAML to: {workflow_dir}/pipeline_graph.yaml
   with owner_confirmed: true

Write ONLY pipeline_graph.yaml. Do not proceed to other phases.
```

**IMPORTANT:** The BA agent interacts with the user directly. Wait for it to complete and produce `pipeline_graph.yaml`.

---

## Step 3: Validate Gate 1

```python
result = orch.run_gate(1)
if not result:
    # Send errors back to BA agent for fixing (max 3 retries)
    print(f"Gate 1 FAIL: {result.error_summary()}")
    # Re-prompt BA with: "Fix these errors in pipeline_graph.yaml: {result.errors}"
```

Only proceed when gate 1 passes.

---

## Step 4: Spawn Separator (Phases 2-3)

Use the **Agent tool** to spawn a subagent with this prompt:

```
You are the Separator agent for ETLai pipeline creation.

Read the system prompt at: {orch.build_agent_context("separator")["system_prompt"]}
Read the phase playbooks at:
- workflow/phase_2_separation.md
- workflow/phase_3_atomize.md

Read the confirmed pipeline graph at: {workflow_dir}/pipeline_graph.yaml

Your job:
1. Extract all business terms and create generic placeholders (col_a, threshold_1, etc.)
2. Write THREE files to {workflow_dir}/:
   - logical_graph.yaml (zero domain terms)
   - business_mapping.json (placeholder ↔ real value mapping)
   - atomic_operations.yaml (single-verb DAG)

Rules:
- NO domain terms in logical_graph or atomic_operations
- ALL domain terms go in business_mapping.json
- Each operation is a single verb (join, compute, group, filter, sort, rename, flag, aggregate)
- Valid DAG structure (no cycles)

Do NOT ask the user questions. This is mechanical.
```

**This agent does NOT interact with the user.** Wait for completion.

---

## Step 5: Validate Gates 2 + 3

```python
for gate_num in (2, 3):
    result = orch.run_gate(gate_num)
    if not result:
        # Re-prompt Separator: "Fix these errors: {result.errors}"
        # Max 3 retries
```

---

## Step 6: Activate Firewall + Spawn Atom Smith (Phases 4-5)

**CRITICAL: Activate firewall BEFORE spawning Atom Smith.**

```python
orch.activate_firewall()  # hides business_mapping.json
```

Use the **Agent tool** to spawn a subagent with this prompt:

```
You are the Atom Smith agent for ETLai pipeline creation.

Read the system prompt at: {orch.build_agent_context("atom_smith")["system_prompt"]}
Read the phase playbooks at:
- workflow/phase_4_match.md
- workflow/phase_5_create.md

Read ONLY: {workflow_dir}/atomic_operations.yaml
(You have NO access to business_mapping.json or pipeline_graph.yaml — this is enforced.)

Your job:
1. For each operation, search the shipped atoms list:
   vlookup, computed_column, group_aggregate, filter_rows, flag_rows,
   rename_columns, sort_rows, groupby, api_fetch, mock_generate
2. Match operations to existing atoms where possible
3. For unmatched operations: write new atoms to atoms/<verb>_<object>.py
   - Generic column names only (col_a, col_b, never real names)
   - Must pass litmus test: "rename columns to A,B,C — still works?"
   - Include tests in tests/test_<verb>_<object>.py
4. Write match_results.yaml to {workflow_dir}/

Do NOT read business_mapping.json. Do NOT ask the user questions.
```

---

## Step 7: Validate Gates 4 + 5 + Deactivate Firewall

```python
for gate_num in (4, 5):
    result = orch.run_gate(gate_num)
    if not result:
        # Re-prompt Atom Smith: "Fix these errors: {result.errors}"
        # Max 3 retries

orch.deactivate_firewall()  # restore business_mapping.json
```

---

## Step 8: Spawn Assembler (Phases 6-7)

Use the **Agent tool** to spawn a subagent with this prompt:

```
You are the Assembler agent for ETLai pipeline creation.

Read the system prompt at: {orch.build_agent_context("assembler")["system_prompt"]}
Read the phase playbooks at:
- workflow/phase_6_assemble.md
- workflow/phase_7_rehydrate.md

Read ALL four inputs:
- {workflow_dir}/match_results.yaml
- {workflow_dir}/business_mapping.json
- {workflow_dir}/atomic_operations.yaml
- {workflow_dir}/pipeline_graph.yaml

Also read: pipelines/CLAUDE.md (assembly rules)

Your job:
1. Linearize the DAG into sequential steps (use input_from for non-linear reads)
2. Translate ALL generic placeholders to real values from business_mapping.json
3. Write manifest.yaml to pipelines/{pipeline_name}/manifest.yaml with:
   - steps (each with atom, form: passthrough)
   - inputs (with inject_as for reference files)
   - trigger rules
   - path: ask
   - min_files
4. Write config.json to pipelines/{pipeline_name}/config.json with:
   - Top-level params for step 0
   - step_1, step_2, etc. for subsequent steps
   - ZERO placeholders (everything translated to real values)
5. Final step MUST be rename_columns (rehydration)
6. Run: etlai sync

Do NOT ask the user questions. Do NOT modify atom code.
```

---

## Step 9: Validate Gate 6

```python
result = orch.run_gate(6)
if not result:
    # Re-prompt Assembler: "Fix these errors: {result.errors}"
    # Max 3 retries
```

---

## Step 10: Report Success

Tell the user:

```
Pipeline '{pipeline_name}' created successfully!

Files:
  pipelines/{pipeline_name}/manifest.yaml
  pipelines/{pipeline_name}/config.json

Next steps:
  1. Run: etlai sync (creates folders, validates)
  2. Place reference files in pipelines/{pipeline_name}/reference/
  3. Drop transient CSVs into pipelines/{pipeline_name}/inbox/
  4. Run: etlai run
```

---

## Error Handling

### Gate Failure (max 3 retries per agent)

```python
MAX_RETRIES = 3
for attempt in range(MAX_RETRIES):
    result = orch.run_gate(gate_num)
    if result:
        break
    # Send errors back to the SAME agent:
    # "Gate {gate_num} FAIL. Fix these errors:\n{result.error_summary()}"
    # Agent re-reads artifact, fixes, writes corrected version
else:
    # Escalate to user after 3 failures
    print(f"Gate {gate_num} failed after {MAX_RETRIES} attempts.")
    print(f"Errors: {result.error_summary()}")
    print("Please review the artifact and provide guidance.")
```

### Agent Refuses / Produces Wrong Artifact

If an agent produces an artifact that doesn't match expectations:
1. Check the system prompt was loaded correctly
2. Check the input files exist
3. Re-spawn with more explicit instructions
4. After 3 failures, ask the user for help

### Firewall Breach Attempt

If Atom Smith somehow references `business_mapping.json`:
- Gate 5 will catch domain leakage in atom code
- The file is physically renamed, so it can't be read even if attempted

---

## Retry Flow Diagram

```
                  ┌──────────────┐
                  │ Spawn Agent  │
                  └──────┬───────┘
                         │
                         ▼
                  ┌──────────────┐
                  │  Run Gate    │
                  └──────┬───────┘
                         │
                    ┌────┴────┐
                    │         │
                  PASS      FAIL
                    │         │
                    ▼         ▼
              ┌─────────┐  ┌─────────────┐
              │ Next     │  │ Retry < 3?  │
              │ Phase    │  └──────┬──────┘
              └─────────┘    YES   │   NO
                              │    │    │
                              ▼    │    ▼
                        ┌─────────┐│ ┌───────────┐
                        │Re-prompt││ │ Escalate  │
                        │ Agent   ││ │ to User   │
                        └────┬────┘│ └───────────┘
                             │     │
                             └─────┘
```

---

## Config.json Structure for Assembler

The Assembler must write config.json in this format:

```json
{
  "left_column": "sku",
  "right_column": "sku",
  "left_output_columns": ["name"],
  "right_output_columns": ["category", "price"],
  "step_1": {
    "expression": "price * quantity",
    "output_column": "revenue"
  },
  "step_2": {
    "condition": "revenue < 100",
    "output_column": "low_revenue_flag"
  },
  "step_3": {
    "mapping": {
      "revenue": "Total Revenue",
      "low_revenue_flag": "Low Revenue Alert"
    }
  }
}
```

- Top-level params → step 0 (the runtime reads flat config for step 0)
- `step_N` keys → steps 1, 2, 3, etc.
- Zero placeholders — all real business values

---

## Quick Reference: What Each Agent Writes

| Agent | Output Files | Location |
|-------|-------------|----------|
| Business Analyst | `pipeline_graph.yaml` | `pipelines/<name>/workflow/` |
| Separator | `logical_graph.yaml`, `business_mapping.json`, `atomic_operations.yaml` | `pipelines/<name>/workflow/` |
| Atom Smith | `match_results.yaml` + optional atom/test files | `pipelines/<name>/workflow/` + `atoms/` + `tests/` |
| Assembler | `manifest.yaml`, `config.json` | `pipelines/<name>/` |
