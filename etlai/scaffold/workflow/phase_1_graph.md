# Phase 1 — Business Process Graph

## Purpose

Build the complete data flow graph: what goes in, what operations happen in what order, and what comes out. Loop with the user until every node and edge is defined with zero unknowns.

## Input

- Partial `pipeline_graph.yaml` from Phase 0 (expanded description, initial data sources)

## Output

- Complete `pipeline_graph.yaml` with all sections filled, `owner_confirmed: true`

## Process

1. From the dejargoned description (Phase 0), identify each distinct operation as a node.
2. For each node, define: what data it reads (inputs), what it produces (outputs), what rules it applies (business_rules).
3. For each data source, fill ALL fields: name, retrieval method, frequency, format, fields with types, role.
4. Draw edges: which node feeds into which. Verify no orphan nodes.
5. Define triggers: what starts this pipeline running.
6. Define output: what the final result looks like, where it goes.
7. Present the complete graph to the user. Ask: "Is this complete and correct?"
8. Set `owner_confirmed: true` ONLY after the user explicitly says yes.

## Done When

- ALL of these are true simultaneously:
  - Every node has non-empty: id, operation, inputs, outputs, description
  - Every data source has non-empty: name, retrieval, frequency, format, fields, role
  - Every edge connects valid node IDs
  - No field contains "unknown", "tbd", "tbc", or empty string
  - Triggers section is filled
  - Output section is filled
  - User has explicitly confirmed (`owner_confirmed: true`)

## DO

- Ask the user about EVERY gap: "You mentioned X arrives weekly — what columns does it contain?"
- Verify field types: "Is quantity always a whole number or can it have decimals?"
- Confirm the trigger: "This runs every Monday at 8am — correct?"
- Verify data roles: "The product catalog stays the same across runs — it's reference data, correct?"
- Number nodes sequentially (node_1, node_2) to show execution order
- Verify the chain: "So node_1's output feeds into node_2's input — correct?"

## DO NOT

- Set `owner_confirmed: true` without explicit user confirmation
- Leave any field empty or placeholder — if unknown, ask
- Assume column names or types — ask the user to confirm
- Proceed to Phase 2 with any "tbd" entries
- Add operations the user didn't ask for (don't optimize prematurely)
- Guess data formats — ask "is it CSV, JSON, or something else?"

## Gap Detection Questions

When reviewing the graph for completeness, check:

1. **Data gaps:** Does every node have all required input data sourced from either a data_source or a prior node?
2. **Field gaps:** Does every operation reference columns that actually exist in its input?
3. **Logic gaps:** Are all thresholds, conditions, and formulas stated with exact values?
4. **Output gaps:** Are all expected output fields producible from the defined operations?
5. **Trigger gaps:** Is it clear WHEN and HOW this pipeline starts?
6. **Error gaps:** What happens if input data is missing or malformed? (note in business_rules)

## Looping Rules

- Keep asking until ALL gaps are filled
- Present the graph summary after each round of questions
- Maximum 5 question rounds — if still incomplete after 5, present what's missing as a bulleted list and ask the user to fill it
- Accept "I don't care / use default" as valid answers for non-critical fields (e.g., output destination defaults to output/ folder)

## Gate Validator

After user confirms, run:
```bash
python workflow/validators/gate_1_graph_complete.py pipelines/<name>/
```

Must return PASS before proceeding to Phase 2. Fix any structural errors the validator reports.
