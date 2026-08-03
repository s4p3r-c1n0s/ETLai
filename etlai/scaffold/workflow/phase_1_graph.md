# Phase 1 — Business Process Graph

## Purpose

Build the complete data flow graph: inputs, operations, edges, triggers, and outputs — with zero unknowns left as invented guesses.

## Input

- Partial `pipeline_graph.yaml` from Phase 0 (expanded description, initial sources/nodes)
- Optional: answered clarifying questions from prior turns (provided with this invoke)

## Output

- Complete `pipeline_graph.yaml` with all sections filled and `owner_confirmed: false`
- `ba_questions.json` — remaining clarifying questions, or `{"questions": []}` when the draft has no open gaps

## Process

1. From the Phase 0 description, identify each distinct operation as a node.
2. For each node, define: inputs, outputs, description, business_rules.
3. For each data source, fill: name, retrieval, frequency, format, fields (with types), role.
4. Draw edges between sources/nodes. Verify no orphan nodes.
5. Define triggers (what starts the pipeline).
6. Define outputs (final result shape and destination).
7. If any required field is unknown, add a clarifying question to `ba_questions.json` instead of inventing a value.
8. Write the draft with `owner_confirmed: false`. This phase never sets `owner_confirmed: true`.
9. When there are no open gaps, write `ba_questions.json` as `{"questions": []}`.

## Done When

All of the following hold:

- Every node has non-empty: id, operation, inputs, outputs, description
- Every data source has non-empty: name, retrieval, frequency, format, fields, role
- Every edge connects valid node IDs or data source names
- No field contains "unknown", "tbd", "tbc", or empty string (unless covered by an open question)
- Triggers and outputs sections are filled
- `owner_confirmed` is still `false`
- Either `ba_questions.json` lists remaining gaps, or it is empty because the draft is complete

## DO

- Emit a clarifying question for every gap
- Number nodes sequentially (`node_1`, `node_2`, …)
- Keep descriptions plain-language and concrete
- Preserve branches and multiple outputs when the request requires them

## DO NOT

- Set `owner_confirmed: true`
- Leave placeholders without a corresponding clarifying question
- Assume column names or types without answered evidence
- Add operations not implied by the request
- Guess formats (CSV vs JSON, etc.)
- Proceed to later phases from this playbook (stop after writing artifacts)

## Gap detection checklist

1. **Data:** Does every node input come from a data_source or prior node?
2. **Fields:** Does every operation reference columns that exist on its inputs?
3. **Logic:** Are thresholds, conditions, and formulas stated with exact values?
4. **Output:** Are expected output fields producible from defined operations?
5. **Trigger:** Is WHEN/HOW the pipeline starts specified?
6. **Errors:** Note missing/malformed input behavior in business_rules when known

## Gate Validator

Structural check after the control plane has set `owner_confirmed: true`:

```bash
python workflow/validators/gate_1_graph_complete.py pipelines/<name>/
```

Must return PASS before Phase 2. On FAIL, revise the graph (still with `owner_confirmed: false`) using the listed errors as input.
