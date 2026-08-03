# Phase 0 — Dejargon

## Purpose

Transform a raw request from domain jargon into precise, plain-language operations that any engineer could understand without industry knowledge.

## Input

- Raw request text (conversational; may use abbreviations, acronyms, assumed knowledge)
- Optional: answered clarifying questions from a prior turn (provided with this invoke)

## Output

- Partial `pipeline_graph.yaml` — at least `description`, initial `data_sources`, and initial `nodes` in plain language
- `ba_questions.json` — clarifying questions still needed, or `{"questions": []}` if none

## Process

1. Read the request. Identify every domain-specific term (acronyms, industry jargon, product names, role titles, process names).
2. For each term, expand it into a plain-language definition. If meaning is uncertain, add a clarifying question to `ba_questions.json` instead of guessing.
3. Rewrite the request as a sequence of concrete operations using only generic vocabulary: join, filter, compute, group, flag, sort, rename.
4. Identify what data goes in and what data comes out. Write initial `data_sources` entries.
5. Set `owner_confirmed: false` on the draft graph (this phase never sets it to true).

## Done When

- Every domain term in the original request has been expanded **or** has an open clarifying question
- No expanded term still requires industry knowledge to understand
- Draft graph fields that are known are filled; unknowns are represented as questions, not invented facts

## DO

- Emit a clarifying question for every ambiguous term
- Use concrete verbs: "join file A with file B on column X" not "reconcile"
- State units explicitly: percentage, count, sum in dollars
- Distinguish "happens once" vs "happens per row" vs "happens per group"

## DO NOT

- Assume acronym meanings without evidence or an answered question
- Invent data format, frequency, or retrieval method
- Use the requester's jargon in the expanded description
- Set `owner_confirmed: true`
- Write code, atoms, manifest, or config
- Write files other than `pipeline_graph.yaml` and `ba_questions.json`

## Examples

| Request fragment | Expand to |
|------------------|-----------|
| "reconcile POS against suppliers" | "join transaction records with supplier price records on shared product identifier, compute difference between transaction amount and supplier cost per row" |
| "flag low-margin SKUs" | "for each product identifier, compute (revenue - cost) / revenue as a percentage, mark rows where this percentage is below a threshold" |
| "roll up by category" | "group rows by the category column, compute sum of specified numeric columns per group" |
| "drop dupes" | "remove rows where all column values are identical to a previous row" |

## Clarifying questions checklist

If not already answered in the input, prefer questions covering:

1. What data arrives and how? (file drop, API, manual upload)
2. How often does it arrive? (daily, weekly, on-demand)
3. What stays the same across runs? (reference/lookup data)
4. What changes every run? (transient/incoming data)
5. What does the output look like? (which columns, what format)
6. What thresholds or conditions matter? (exact numbers)
7. What filename patterns identify each inbox file? (e.g. `sales_*.csv` vs `catalog_*.csv`)
