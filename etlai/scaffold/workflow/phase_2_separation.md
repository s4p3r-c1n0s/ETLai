# Phase 2 — Separation

## Purpose

Split the business process graph into two artifacts:
1. A **logical graph** containing only generic operations (no domain terms)
2. A **business mapping** that translates between generic placeholders and real business terms

This is the privacy boundary. After this step, atom creation (Phase 5) receives ONLY the logical graph — never the business mapping.

## Input

- Complete `pipeline_graph.yaml` with `owner_confirmed: true`

## Output

- `logical_graph.yaml` — generic operations with placeholder column names
- `business_mapping.json` — maps every placeholder back to its real business meaning

## Process

1. For each data_source in pipeline_graph.yaml, assign a placeholder: `source_1`, `source_2`, etc.
2. For each field/column referenced anywhere, assign a placeholder: `col_a`, `col_b`, `col_c`, etc. Record the mapping.
3. For each threshold or magic number, assign a placeholder: `threshold_1`, `threshold_2`, etc. Record the mapping.
4. For each formula that uses real column names, rewrite it with placeholders: `price * quantity` → `col_a * col_b`. Record the mapping.
5. For each node in pipeline_graph.yaml, rewrite it as a logical_graph node using only placeholders and generic operation verbs.
6. Determine trigger type from pipeline_graph.yaml triggers (schedule → cron, folder_watch → pattern). Keep trigger spec generic (cron string is fine, but don't reference real folder paths).
7. Write `logical_graph.yaml` with the sanitized nodes.
8. Write `business_mapping.json` with every placeholder-to-real mapping.
9. Validate: read `logical_graph.yaml` as if you've never seen the business context. Can you tell what industry this is for? If yes, separation FAILED — find and replace the leaked term.

## Done When

- `logical_graph.yaml` contains ZERO business terms, column names, product names, company names, or industry indicators
- `business_mapping.json` has an entry for EVERY placeholder used in logical_graph.yaml
- The two files together can perfectly reconstruct the original pipeline_graph.yaml meaning
- The litmus test passes: "A reader of logical_graph.yaml cannot identify the business domain"

## DO

- Replace ALL real names systematically: columns → col_a/col_b, sources → source_1/source_2, thresholds → threshold_1
- Keep operation verbs generic: join, compute, group, filter, flag, sort, rename, aggregate
- Preserve the graph structure (edges, dependencies) — only strip the domain semantics
- Verify completeness: every placeholder in logical_graph has exactly one entry in business_mapping
- Use consistent placeholder naming: col_ prefix for columns, source_ for data sources, threshold_ for numbers

## DO NOT

- Leave ANY real column name in logical_graph.yaml (e.g., "sku", "revenue", "customer_id")
- Leave business entity names (company names, product names, department names)
- Leave industry-specific verbs ("reconcile", "invoice", "onboard") — use generic verbs only
- Modify the LOGIC — separation changes NAMES, not BEHAVIOR
- Skip threshold extraction — hardcoded numbers like "15%" become "threshold_1" with value in mapping
- Combine this step with Phase 3 — separation is about NAMING, atomization is about SPLITTING

## Validation Script (Mental Model)

```
for each word in logical_graph.yaml:
    if word is a noun AND word is not in [node, edge, operation, join, compute, 
       group, filter, flag, sort, rename, aggregate, col_, source_, threshold_,
       computed_, flag_, schedule, folder_watch]:
        FAIL — this word is likely domain leakage
```

## Example

**Before (from pipeline_graph.yaml):**
```
node: "Join sales transactions with product catalog on SKU to get category"
```

**After (logical_graph.yaml):**
```
node:
  operation: join
  params:
    left_key: col_a
    right_key: col_b
    select_from_right: [col_c]
```

**In business_mapping.json:**
```
"col_a": {"real_name": "sku", "source": "sales_transactions", ...}
"col_b": {"real_name": "sku", "source": "product_catalog", ...}
"col_c": {"real_name": "category", "source": "product_catalog", ...}
```

## Gate Validator

After producing both files, run:
```bash
python workflow/validators/gate_2_no_leakage.py pipelines/<name>/
```

Must return PASS before proceeding to Phase 3. The validator scans logical_graph.yaml for ANY real name found in business_mapping.json. A single match = FAIL.
