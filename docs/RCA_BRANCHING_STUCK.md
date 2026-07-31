# RCA: Pipeline Creation Agent Stuck on Branching Structures

## Symptom

Every time a business request implies multiple outputs or a branching data flow (e.g., "produce a detail export AND a summary"), the LLM enters a deliberation loop:

1. It correctly identifies the DAG has a fork (ops 1-4 linear → split to detail vs. summary)
2. It reads the framework code and discovers `_composite_job` is strictly linear (each step receives prev_output)
3. It spends 1-2 minutes trying to reconcile "DAG with fan-out" against "linear step chain"
4. Eventually works around it, but the workaround is fragile and burns time

## Root Cause

**The architecture has a fundamental mismatch between what it models and what it executes.**

### Layer 1: The DAG Lie

`atomic_operations.yaml` declares a **`depends_on` field per operation** — this models a directed acyclic graph. Multiple operations can depend on the same upstream operation:

```yaml
operations:
  - id: op_1  # join
  - id: op_2  # compute, depends_on: [op_1]
  - id: op_3  # compute, depends_on: [op_2]
  - id: op_4  # rename (detail export), depends_on: [op_3]  ← BRANCH A
  - id: op_5  # group, depends_on: [op_3]                   ← BRANCH B (same parent!)
  - id: op_6  # flag, depends_on: [op_5]
  - id: op_7  # rename (summary), depends_on: [op_6]
```

This is a valid DAG. Gate 3 passes it. The instructions say "determine step order from depends_on chain."

### Layer 2: The Linear Reality

`registry.py` `_composite_job()` (line 459-464):

```python
def _composite_job():
    file_paths = _load_files()
    prev_output = step_ops[0](file_paths)
    for step_op in step_ops[1:]:
        prev_output = step_op(file_paths, prev_output)
```

**Every step receives the PREVIOUS step's output.** There is no mechanism to:
- Read from step N-2 (skip step N-1's output)
- Fork: have two steps read from the same parent
- Merge: have one step read from two parents

### Layer 3: The Gap in Instructions

Phase 6 instruction says:
> "2. Determine step order from atomic_operations.yaml depends_on chain."

But it never addresses the case where the DAG has a fan-out. It implicitly assumes the `depends_on` chain is always linear (each op depends on exactly one predecessor, in sequence).

The template `atomic_operations.yaml` allows `depends_on: []` as a list — implying DAGs with multiple parents are possible. But the execution engine can't run them.

### The Collision Point

When the LLM reaches Phase 6 with a branching DAG:
1. It has `atomic_operations.yaml` with a valid fan-out
2. It reads `registry.py` and discovers it's strictly linear
3. It tries to "linearize" the DAG, but branch B needs to read from an earlier step (not the previous step)
4. It realizes `prev_output` is always step N-1, not "whichever step I depend on"
5. It gets stuck in a loop trying to figure out the workaround

## Why It's Always This Pattern

The mismatch only surfaces when the pipeline has **multiple outputs** or **diverging branches**. For simple linear pipelines (A→B→C→D), the DAG IS linear, and everything works. The problem is structural — it appears on every non-trivial pipeline.

## Contributing Factors

### 1. `pipeline_graph.yaml` template allows `outputs:` (plural, list)
The template explicitly models multiple outputs. This signals to the LLM during Phases 0-1 that branching is supported.

### 2. `atomic_operations.yaml` has `depends_on: []`
The DAG validation (gate 3) allows fan-outs. The LLM has no reason to think it must produce a linear chain.

### 3. Phase 6 instruction has no "linearization" step
There's no instruction that says: "If the DAG has branches, flatten them into a linear sequence by X strategy."

### 4. No `input_from` field in manifest steps
The manifest step schema is:
```yaml
steps:
  - name: ...
    atom: ...
    form: ...
```

There's no way to say "this step reads from step 2's output" vs. "this step reads from the previous step's output." The only implicit contract is: each step gets `prev_output` from step N-1.

### 5. Named steps (Option B) partially solved it but didn't close the loop
We added `name:` to produce named output files, but we didn't add a corresponding `input_from:` that lets a step choose which previous output to read. The named file exists in the output folder, but the framework always feeds `prev_output` (the immediately preceding step's output path).

## The Actual Execution Problem

For the sales reconciliation pipeline, the correct data flow is:

```
step 0: vlookup         → _intermediate_0.csv
step 1: vlookup         → _intermediate_1.csv
step 2: computed_column → _intermediate_2.csv
step 3: computed_column → _intermediate_3.csv
step 4: rename_columns  → detailed_transactions.csv  (BRANCH A: detail export)
step 5: group_aggregate → _intermediate_5.csv        (needs _intermediate_3.csv, NOT detailed_transactions.csv)
step 6: flag_rows       → _intermediate_6.csv
step 7: rename_columns  → output.csv                 (BRANCH B: summary)
```

**Step 5 needs input from step 3, not step 4.** But the framework gives it step 4's output.

The LLM eventually realizes: "Oh, if I put step 4 before step 5, step 5 will get step 4's renamed output which has different column names." Then it tries to reorder, realizes it can't without breaking the detail export, and loops.

## Fix Options

### Option 1: Add `input_from` field to manifest steps (Minimal)

Allow steps to declare which step's output they read:

```yaml
steps:
  - atom: vlookup                        # step 0
  - atom: vlookup                        # step 1
  - atom: computed_column                # step 2
  - atom: computed_column                # step 3
  - name: detailed_transactions          # step 4 (named output)
    atom: rename_columns
  - atom: group_aggregate                # step 5
    input_from: 3                        # reads step 3's output, NOT step 4's
  - atom: flag_rows                      # step 6
  - atom: rename_columns                 # step 7 (final)
```

**Registry change:** In `_execute_step`, if `input_from` is declared, look up that step's output path instead of using `prev_output`.

**Scope:** Small code change (~10 lines in registry), update to pipelines/CLAUDE.md template, update to Phase 6 instructions.

### Option 2: Split into separate pipelines (No code change)

Document that branching pipelines must be split into independent pipelines sharing reference files:
- Pipeline A: join→compute→rename (detail export)
- Pipeline B: join→compute→group→flag→rename (summary)

**Problem:** Duplicates the join + compute steps. Less efficient, more maintenance.

### Option 3: Full DAG execution engine (Large)

Rewrite `_composite_job()` to do topological execution:
- Track which step produces which file
- Each step declares its `depends_on` in the manifest
- Steps execute when all dependencies are met

**Problem:** Major refactor. Overkill for the current pipeline complexity. Breaks the simple mental model.

## Recommended Fix

**Option 1 (`input_from` field).** It's the minimal change that:
- Preserves the linear-by-default mental model
- Allows explicit non-linear reads where needed
- Requires no architectural overhaul
- Directly solves the agent's stuck point

The LLM will see: "If a step needs input from a non-adjacent predecessor, declare `input_from: <step_index>`." No more deliberation loops.

## Also Required: Documentation Fixes

1. **Phase 6 playbook** — Add instruction: "If the DAG has branches, linearize by placing the shorter branch first, then use `input_from` for steps that need to read from a non-adjacent predecessor."

2. **pipelines/CLAUDE.md** — Add `input_from` to the composite manifest template.

3. **atomic_operations.yaml template** — Add a comment: "The depends_on graph will be linearized during Phase 6. Non-linear dependencies use `input_from` in the manifest."

4. **Gate 3 validator** — Add a warning (not error) when the DAG has fan-outs, noting that Phase 6 will need `input_from` declarations.

## Prevention

This is a systemic pattern: features are modeled in the artifact schemas (DAGs, multiple outputs) but never checked against the execution engine's actual capabilities. Future architecture changes should:

1. Start from what the engine CAN DO
2. Model only what can be executed
3. If the model allows more than the engine, document the linearization strategy
