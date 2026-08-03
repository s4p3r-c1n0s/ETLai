# How to Use Agents — End User Guide

## Quick Start

When a Claude Code session runs in this project, it can now create pipelines using a 5-agent system.

### Example: Creating a Sales Reconciliation Pipeline

```
User: "Build me a pipeline that takes weekly sales data, enriches it with product catalog 
       and supplier prices, computes margins, flags low-margin items, and produces a 
       summary report."
```

**What happens internally:**

1. **Orchestrator** mediates phases 0–1 (owns the user channel):
   - Spawns Business Analyst as a **worker** that proposes questions + drafts the graph
   - Relays clarifying questions to you (e.g. threshold, catalog cadence, multi-output needs)
   - Alone confirms the graph after you say yes (`confirm_graph`)

2. **Separator** (Agent 2) mechanically translates:
   - "sales_data" → "source_1"
   - "product_catalog" → "source_2"
   - "supplier_prices" → "source_3"
   - "margin" → "col_a * col_b" (generic)
   - "low_margin_threshold" → "threshold_1"
   - Produces: `logical_graph.yaml`, `business_mapping.json`, `atomic_operations.yaml`

3. **Atom Smith** (Agent 3) finds/creates atoms (NEVER sees real column names):
   - "join on key" → shipped `vlookup` atom
   - "compute formula" → shipped `computed_column` atom
   - "flag rows where margin < threshold" → shipped `flag_rows` atom
   - "group by category, sum revenue" → shipped `group_aggregate` atom
   - All atoms are generic, domain-free
   - Produces: `match_results.yaml`

4. **Assembler** (Agent 4) wires the pipeline:
   - Translates col_a → "price", col_b → "quantity", threshold_1 → 15.0
   - Creates `manifest.yaml` with steps, inputs, triggers, inject_as
   - Creates `config.json` with real values: {"price": "price", "quantity": "qty", "threshold": 15.0}
   - Adds final `rename_columns` step
   - Runs `etlai sync` to validate

5. **Orchestrator** continues routing gates/firewall for agents 2–4.

**Result:**
```
pipelines/weekly_sales_reconciliation/
├── manifest.yaml (valid, ready to run)
├── config.json (business values, no generics)
├── inbox/ (drop CSV files here)
├── staging/
├── processed/
├── rejected/
├── output/ (results appear here)
└── reference/ (permanent lookup tables)
```

---

## When Claude Sees This Code

When a Claude Code session opens this repository and you ask it to build a pipeline, it sees:

**From `scaffold/CLAUDE.md`:**
- 7-phase workflow overview
- Shipped atoms table (10 atoms)
- Key concepts (inject_as, config.json, triggers)
- DO/DO NOT rules

**From `workflow/CLAUDE.md`:**
- Gate validator commands
- Phase sequence and rules
- Artifact storage paths

**From individual phase files** (e.g., `workflow/phase_0_dejargon.md`):
- Detailed playbook for that phase
- Input/output contracts
- Process steps and examples

**From scaffold/agents/ directory:**
- System prompts for all 5 agents
- Clear role, responsibilities, tools for each
- Knowledge boundaries (what each agent knows/doesn't know)

---

## Agent Behavior

### Business Analyst (Phases 0-1) — worker under Orchestrator

```
Orchestrator: "I'll help you build a pipeline. A few clarifying questions first…"
              [relays BA-proposed questions]

User: [answers]

Orchestrator: [BA worker turn revises draft]
              "Here's the business process graph. Is this complete and correct?"

User: "Yes, perfect."

Orchestrator: [confirm_graph(True) — alone sets owner_confirmed]
```

**BA worker refuses:**
- ❌ Writing code or atoms
- ❌ Talking to the user directly / setting `owner_confirmed: true`
- ❌ Producing generic operations (that's Separator's job)

---

### Separator (Phases 2-3)

```
Claude: [Silent. Reading pipeline_graph.yaml]
         [Extracting operations: join, compute, filter, group, rename]
         [Creating placeholders: col_a, col_b, threshold_1, formula_1]
         [Building mappings: col_a → "sku", threshold_1 → 15.0]
         [Writing three YAMLs]

Result: logical_graph.yaml, business_mapping.json, atomic_operations.yaml
```

**Agent refuses:**
- ❌ Asking user questions
- ❌ Writing atoms or config
- ❌ Including domain terms in output

---

### Atom Smith (Phases 4-5)

```
Claude: [Reads atomic_operations.yaml — ONLY. No business_mapping.json!]
        [Sees: "operation: join on two columns"]
        [Searches shipped atoms]
        [Finds: vlookup atom exists]
        
        [Sees: "operation: compute col_a * col_b"]
        [Searches shipped atoms]
        [Finds: computed_column atom exists]
        
        [All operations matched to existing atoms]

Result: match_results.yaml (no new atoms needed)
```

**If a new atom was needed:**
```
Claude: [Sees unmatched operation]
        [Writes atoms/join_with_custom_logic.py]
        [Uses generic column names: col_a, col_b, computed_1]
        [Writes tests using columns A, B, C]
        [Checks litmus test: "Rename to A,B,C — still works? YES"]

Result: match_results.yaml + new atom files
```

**Agent refuses:**
- ❌ Reading business_mapping.json (firewall blocks it)
- ❌ Looking at real column names
- ❌ Writing domain-specific code
- ❌ Making routing decisions (not its job)

---

### Assembler (Phases 6-7)

```
Claude: [Reads all four inputs]
        [Sees: col_a → "sku" from business_mapping]
        [Sees: threshold_1 → 15.0 from business_mapping]
        [Creates manifest.yaml with real values]
        [Creates config.json with real values]
        [Adds final rename_columns step]
        [Runs etlai sync → SUCCESS]

Result: manifest.yaml, config.json, folders created
```

**Agent refuses:**
- ❌ Writing atom code (that's done; use as-is)
- ❌ Asking user questions (too late; use confirmed graph)
- ❌ Generic values in config (translate everything to real)

---

## When an Agent Gets Stuck

**Example: Atom Smith stuck because a new atom is needed**

```
Orchestrator: [Runs gate_4_match_coverage.py]
              [FAIL: "operation_7 (custom_aggregate) is unmatched"]

[Routes back to Atom Smith with error]

Atom Smith: [Reads error]
            [Finds operation_7: "Aggregate by category with custom logic"]
            [No shipped atom handles this]
            [Writes atoms/aggregate_custom.py]
            [Writes tests/test_aggregate_custom.py]
            [Applies litmus test: "Rename to A,B,C — still works? YES"]

Orchestrator: [Re-runs gate_4]
              [PASS: All operations matched]
              [Proceeds to gate_5]

Orchestrator: [Runs gate_5_atom_clean.py on new atom]
              [Scans for domain leakage]
              [FAIL: "Found real term 'category' in atom code"]

[Routes back to Atom Smith with error]

Atom Smith: [Reads error]
            [Finds 'category' in code]
            [Replaces with col_a]
            [Updates tests to use column A]
            [Re-writes file]

Orchestrator: [Re-runs gate_5]
              [PASS: No domain leakage]
              [Proceeds to Assembler]
```

**Max retries: 3 per agent. After 3 FAILs on same gate:**
```
Orchestrator: [Reports to user]
              "I tried 3 times to fix this, but it's still failing. 
               Here's the error: [gate output]
               You may need to adjust the pipeline request or provide more guidance."
```

---

## What Agents See vs. Don't See

### Business Analyst
✅ User's request (raw, with jargon)
✅ Orchestrator-relayed answers (`ba_session.json`)
✅ Phase playbooks
✅ Draft graph + `ba_questions.json` (write)
❌ Direct user session / setting `owner_confirmed: true`
❌ Atoms, code, manifest
❌ Other agents' work
❌ Technical framework details

### Separator
✅ pipeline_graph.yaml (confirmed via Orchestrator.confirm_graph)
✅ Phase playbooks
✅ Schemas (logical_graph, business_mapping, atomic_operations)
❌ User
❌ Atoms or code
❌ Manifest/config structure

### Atom Smith
✅ atomic_operations.yaml (generic operations only)
✅ Phase playbooks
✅ Shipped atoms list
✅ atoms/CLAUDE.md (litmus test, structure)
❌ **business_mapping.json** ← FIREWALL BLOCKS
❌ **pipeline_graph.yaml** ← FIREWALL BLOCKS
❌ Real column names, thresholds, formulas
❌ How atoms will be wired
❌ Config or manifest

### Assembler
✅ match_results.yaml (atom assignments)
✅ business_mapping.json (real values)
✅ atomic_operations.yaml (operations + order)
✅ pipeline_graph.yaml (triggers, data sources)
✅ pipelines/CLAUDE.md (assembly law)
❌ Atom code (use as-is, don't modify)
❌ User (no interaction)

### Orchestrator
✅ User request (to name pipeline)
✅ Gate validator outputs
✅ Artifact paths
✅ Firewall state (what to strip/restore)
✅ Retry logic (max 3 attempts)
❌ Domain knowledge
❌ Code or technical decisions

---

## Integration Checklist (Planned — Not Yet Implemented)

The agent system prompts are complete. The orchestration code that spawns agents, enforces the firewall, and runs gates is planned for a future release. Track progress in `docs/AGENT_BUILD_ROADMAP.md`.

**Validation criteria for when implementation ships:**

- [ ] Orchestrator entry point exists (CLI or Python script)
- [ ] Orchestrator successfully spawns all 5 agents in sequence
- [ ] Orchestrator mediates BA turns and alone confirms the graph
- [ ] Separator produces three valid YAMLs (zero domain leakage)
- [ ] Atom Smith finds/creates atoms without seeing business_mapping.json
- [ ] Gate validators catch errors; agents retry and fix
- [ ] Assembler produces manifest.yaml + config.json with zero placeholders
- [ ] Final pipeline passes `etlai sync` and is executable
- [ ] End-to-end test with sales reconciliation prompt succeeds
- [ ] Tests suite: 73 → 80+ (new agent tests)
- [ ] No domain knowledge in atoms or core framework
- [ ] Each agent refuses out-of-scope work gracefully

---

## FAQ

**Q: Can I use one agent for multiple phases?**
A: Not recommended. Each agent's system prompt assumes it's doing only its phases. Mixing phases would require cross-cutting knowledge.

**Q: What if Atom Smith needs to create 5 new atoms?**
A: It writes all 5 to atoms/ with tests. Each must pass the litmus test and gates 4 + 5. If any fails, orchestrator retries with error message.

**Q: Can Separator ask the user clarifying questions?**
A: No. The Business Analyst should have resolved all ambiguities in phases 0-1. By phase 2, the graph is final.

**Q: What if the final pipeline has bugs?**
A: The gates validate structure (gates 1-6), not correctness. If config has wrong values or logic is flawed, that's a content error, not a structure error. Encourage the user to start over with clearer requirements (Orchestrator will relay better BA questions).

**Q: Can I manually edit manifest.yaml after assembly?**
A: Yes, but then you're not using the agent system. If you find yourself manually editing, file an issue so the Assembler can be improved.

**Q: How do I know an atom has domain leakage?**
A: The litmus test: rename every column to A, B, C — does it still work? If no, it knows something about the data. gate_5_atom_clean.py scans for real terms; if it finds any, the atom fails.

---

## Summary

The 5-agent system is your pipeline creation assistant. Each agent does one job well and refuses to go beyond scope. The firewall ensures atoms stay generic. Gates validate at each step. Retries fix issues automatically. You get a production-ready pipeline.

**When you build a pipeline:**
1. Describe your business need (user jargon welcome)
2. Orchestrator clarifies with you (relaying BA questions)
3. Three mechanical agents transform your request
4. Assembler wires it all together
5. Your pipeline is ready to run

**The magic:** Atoms are completely generic. Same `computed_column` atom works for revenue calculations, margin formulas, interest rates, anything — as long as the formula is passed in config. Business logic stays in config.json. Atoms never know what the data means.

That's the fortress.
