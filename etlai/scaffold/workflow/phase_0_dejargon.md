# Phase 0 — Dejargon

## Purpose

Transform the user's request from domain jargon into precise, plain-language operations that any engineer could understand without industry knowledge.

## Input

- User's raw request (conversational, may use abbreviations, acronyms, assumed knowledge)

## Output

- Partial `pipeline_graph.yaml` — specifically the `description` field and initial `data_sources` and `nodes` entries written in plain language

## Process

1. Read the user's request. Identify every domain-specific term (acronyms, industry jargon, product names, role titles, process names).
2. For each term, expand it into a plain-language definition. If unsure what a term means, ASK the user.
3. Rewrite the request as a sequence of concrete operations using only generic vocabulary: "join", "filter", "compute", "group", "flag", "sort", "rename".
4. Identify what data goes in and what data comes out. Write initial `data_sources` entries.
5. Present the expanded version to the user for confirmation: "Is this what you mean?"

## Done When

- Every domain term in the original request has been expanded
- The user has confirmed the expanded description is accurate
- No term remains that requires industry knowledge to understand

## DO

- Ask clarification questions for EVERY ambiguous term
- Use concrete verbs: "join file A with file B on column X" not "reconcile"
- State units explicitly: "percentage", "count", "sum in dollars"
- Distinguish between "happens once" vs "happens per row" vs "happens per group"

## DO NOT

- Assume you know what an acronym means — ask
- Proceed if any term is unclear — loop back
- Use the user's jargon in your expanded version — that defeats the purpose
- Write any code or create any files beyond pipeline_graph.yaml
- Make assumptions about data format, frequency, or retrieval method — ask

## Examples of Dejargoning

| User says | You expand to |
|-----------|---------------|
| "reconcile POS against suppliers" | "join transaction records with supplier price records on shared product identifier, compute difference between transaction amount and supplier cost per row" |
| "flag low-margin SKUs" | "for each product identifier, compute (revenue - cost) / revenue as a percentage, mark rows where this percentage is below a threshold" |
| "roll up by category" | "group rows by the category column, compute sum of specified numeric columns per group" |
| "drop dupes" | "remove rows where all column values are identical to a previous row" |

## Questions to Always Ask

1. What data arrives and how? (file drop, API, manual upload)
2. How often does it arrive? (daily, weekly, on-demand)
3. What stays the same across runs? (reference/lookup data)
4. What changes every run? (transient/incoming data)
5. What does the output look like? (which columns, what format)
6. What thresholds or conditions matter? (get exact numbers, not "low" or "high")
