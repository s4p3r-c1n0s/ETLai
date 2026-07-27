# Pipeline Creation Execution Plan

Two approaches for the 7-step pipeline creation workflow.

---

## Approach A: Privacy-First (Local + Graph RAG)

Uses cloud LLM only for atom code generation. Business knowledge never leaves the machine.

| Step | Executor | Input | Output |
|------|----------|-------|--------|
| 0 — Dejargon | Local LLM + company glossary RAG | User's request in domain jargon | Detailed ask without business jargon |
| 1 — Business Process Graph | Local LLM + Graph RAG over internal docs | Dejargoned ask | Step-wise graph of business operations (loops with user until complete) |
| 2 — Separation | Graph RAG + local LLM | Business process graph | Pure logical graph nodes + business-to-logic mapping + trigger definitions |
| 3 — Atomize | Local LLM / script | Logical graph nodes | Smallest possible operation chunks (one operation per node) |
| 4 — Match | Script (registry search) | Operation chunks | Matched existing atoms + unmatched operation specs |
| 5 — Create atom | Cloud LLM (receives only operation spec, no business context) | Generic operation description from step 3 | New generic atom code + tests |
| 6 — Assemble | Script / local LLM | Matched atoms + mapping + triggers | manifest.yaml + config.json + inject_as wiring |
| 7 — Rehydrate | Script (shipped atom or framework hook) | Generic output + business mapping from step 2 | Output with business-meaningful column names |

### Key properties

- Cloud LLM sees: "write an atom that evaluates a formula expression on two numeric columns"
- Cloud LLM never sees: "sku", "revenue", "Shopify", company names, thresholds, column names
- Graph RAG provides: company data relationships, existing schemas, field meanings, process flows
- Business mapping file is the single source of truth for domain ↔ generic translation

### Infrastructure needed

- Local LLM (7-14B minimum, 70B recommended for step 0-1 quality)
- Graph RAG over: ERDs, data catalogs, SOPs, existing pipeline specs, glossaries
- Atom registry (MCP or local catalog) for step 4 matching
- Company glossary file per project

---

## Approach B: Cloud-First (All Steps via Cloud LLM)

Maximum quality, simplest infrastructure. Suitable when data privacy is not a constraint.

| Step | Executor | Input | Output |
|------|----------|-------|--------|
| 0 — Dejargon | Cloud LLM | User's request in domain jargon | Detailed ask without business jargon |
| 1 — Business Process Graph | Cloud LLM | Dejargoned ask (loops with user until complete) | Step-wise graph of business operations |
| 2 — Separation | Cloud LLM | Business process graph | Pure logical graph nodes + business-to-logic mapping + trigger definitions |
| 3 — Atomize | Cloud LLM | Logical graph nodes | Smallest possible operation chunks |
| 4 — Match | Script (registry search) | Operation chunks | Matched existing atoms + unmatched operation specs |
| 5 — Create atom | Cloud LLM | Generic operation description | New generic atom code + tests |
| 6 — Assemble | Cloud LLM / script | Matched atoms + mapping + triggers | manifest.yaml + config.json + inject_as wiring |
| 7 — Rehydrate | Script (shipped atom or framework hook) | Generic output + business mapping from step 2 | Output with business-meaningful column names |

### Key properties

- Single LLM orchestrates the full flow conversationally
- Steps 0-1 are interactive (LLM asks user questions until graph is complete)
- Steps 2-7 execute sequentially once the graph is finalized
- Step 4 remains a script regardless (pure catalog lookup)
- Step 7 remains a script regardless (mechanical column rename)

### Infrastructure needed

- Cloud LLM API access (Claude with tool use)
- Atom registry (MCP or local catalog) for step 4 matching
- Scaffold CLAUDE.md with strict architecture rules for step 5

### Enforcement for cloud approach

Even with cloud doing everything, the architecture boundary must hold:
- Step 2 MUST produce the separation before step 5 runs
- Step 5 receives ONLY the operation spec from step 3, never the business mapping from step 2
- The LLM is instructed to treat steps 2-5 as separate contexts (no leakage between separation and atom creation)

---

## Shared: Output Formats Between Steps

Regardless of approach, the intermediate artifacts are identical:

**Step 0-1 output:** `pipeline_graph.yaml` — nodes with business operations, edges with data flow, gaps marked

**Step 2 output:**
- `logical_graph.yaml` — generic operation nodes (join, compute, group, filter, sort, rename)
- `business_mapping.json` — maps generic placeholders to real column names, formulas, thresholds
- `triggers.yaml` — schedule cron, folder watch patterns, API endpoints

**Step 3 output:** `atomic_operations.yaml` — one entry per smallest operation chunk

**Step 4 output:** `match_results.yaml` — each operation mapped to existing atom or marked "create"

**Step 5 output:** New atom files in shared pool (atoms/<name>.py + tests)

**Step 6 output:** `manifest.yaml` + `config.json` (pipeline ready to run)

**Step 7 output:** Final CSV with business column names restored

---

## Next Steps

1. Define the exact schema for each intermediate file format
2. Write scaffold CLAUDE.md instructions for cloud-first approach (Approach B)
3. Design the Graph RAG indexing strategy for Approach A
4. Ship missing generic atoms: `computed_column`, `groupby_aggregate`, `filter_flag`, `rename_columns`
5. Build atom registry MCP for step 4 matching
