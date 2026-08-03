# Phase 1 — Business Process Graph

## Purpose

Build the complete data flow graph: what goes in, what operations happen in what order, and what comes out. Produce a draft for the Orchestrator to confirm with the user until every node and edge is defined with zero unknowns.

## Input

- Partial `pipeline_graph.yaml` from Phase 0 (expanded description, initial data sources)
- Orchestrator-relayed user answers (`ba_session.json` / turn feedback)

## Output

- Complete `pipeline_graph.yaml` with all sections filled and **`owner_confirmed: false`**
- `ba_questions.json` — remaining clarifying questions, or `{"questions": []}` when ready for Orchestrator to ask the user to confirm

## Process

1. From the dejargoned description (Phase 0), identify each distinct operation as a node.
2. For each node, define: what data it reads (inputs), what it produces (outputs), what rules it applies (business_rules).
3. For each data source, fill ALL fields: name, retrieval method, frequency, format, fields with types, role.
4. Draw edges: which node feeds into which. Verify no orphan nodes.
5. Define triggers: what starts this pipeline running.
6. Define output: what the final result looks like, where it goes.
7. Write the complete draft with `owner_confirmed: false`. If gaps remain, write questions to `ba_questions.json` for the Orchestrator to relay. If complete, write an empty questions list so the Orchestrator can ask: "Is this complete and correct?"
8. **Do not** set `owner_confirmed: true`. The Orchestrator calls `confirm_graph(True)` only after explicit user yes.

## Done When

- ALL of these are true simultaneously:
  - Every node has non-empty: id, operation, inputs, outputs, description
  - Every data source has non-empty: name, retrieval, frequency, format, fields, role
  - Every edge connects valid node IDs
  - No field contains "unknown", "tbd", "tbc", or empty string
  - Triggers section is filled
  - Output section is filled
  - Draft is ready for Orchestrator-mediated confirmation (`owner_confirmed` still false until then)

## DO

- Propose questions about EVERY gap for the Orchestrator to ask
- Verify field types via proposed questions
- Confirm trigger and data roles via Orchestrator-relayed answers
- Number nodes sequentially (node_1, node_2) to show execution order

## DO NOT

- Set `owner_confirmed: true` — only Orchestrator.confirm_graph may do that
- Ask the user directly — you have no user session
- Leave any field empty or placeholder — if unknown, propose a question
- Assume column names or types — wait for relayed confirmation
- Proceed to Phase 2 with any "tbd" entries
- Add operations the user didn't ask for (don't optimize prematurely)
- Guess data formats — propose "is it CSV, JSON, or something else?"

## Gap Detection Questions

When reviewing the graph for completeness, check:

1. **Data gaps:** Does every node have all required input data sourced from either a data_source or a prior node?
2. **Field gaps:** Does every operation reference columns that actually exist in its input?
3. **Logic gaps:** Are all thresholds, conditions, and formulas stated with exact values?
4. **Output gaps:** Are all expected output fields producible from the defined operations?
5. **Trigger gaps:** Is it clear WHEN and HOW this pipeline starts?
6. **Error gaps:** What happens if input data is missing or malformed? (note in business_rules)

## Looping Rules (Orchestrator-mediated)

- Orchestrator invokes BA turns until gaps are filled (max 5 rounds)
- Orchestrator presents the graph summary after each round
- If still incomplete after 5 rounds, Orchestrator presents what's missing as a bulleted list
- Accept "I don't care / use default" (relayed) as valid for non-critical fields

## Gate Validator

After Orchestrator.confirm_graph(True), run:
```bash
python workflow/validators/gate_1_graph_complete.py pipelines/<name>/
```

Must return PASS before proceeding to Phase 2. Fix any structural errors the validator reports (BA fix turns keep `owner_confirmed: false` until Orchestrator re-confirms if needed).
