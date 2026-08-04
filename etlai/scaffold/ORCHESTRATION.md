# Orchestration — how to call the Code control plane

**The control plane is Python**, not this document and not an LLM agent.

Source of truth: `etlai.orchestrator.Orchestrator` + `etlai create`  
Layer rule: `workflow/LAYERS.md` · TECH_DEBT #11

This file is a **transitional shim** for coding assistants (Claude Code, etc.).  
You **call** the APIs below. You do **not** invent the next phase, set `owner_confirmed`, or skip gates.

---

## Preferred path: CLI

```bash
etlai create "join sales with catalog"
# prints worker briefing for current task_id, then exits waiting for the worker

# after worker writes artifacts:
etlai create --resume --advance --name <pipeline> "join sales with catalog"

# confirm step (interactive TTY) or:
# Orchestrator.confirm_graph(True) then --resume
```

Flags:

| Flag | Meaning |
|------|---------|
| `--resume` | Continue `workflow/control_session.json` (do not reset) |
| `--advance` | `submit_worker()` + advance when artifacts ready |
| `--no-confirm` | Non-interactive; you must call `confirm_graph` yourself |
| `--name` | Pipeline name |

---

## Python API (same Code loop)

```python
from pathlib import Path
from etlai.orchestrator import Orchestrator, sanitize_pipeline_name

project_root = Path(".")
pipeline_name = sanitize_pipeline_name(user_request)
orch = Orchestrator(project_root=project_root, pipeline_name=pipeline_name)

orch.start_control_session(user_request)
# orch.current_task_id → "phase_0"
print(orch.worker_briefing())          # give to worker LLM
# ... worker writes artifacts ...
orch.submit_worker()
orch.advance()                         # → phase_1, etc.

# after phase_1 draft ready:
orch.confirm_graph(True)               # only Code may confirm
orch.advance()                         # → gate_1

result = orch.run_current_gate()
orch.advance_after_gate(result)        # advance or retry
```

### Rules (non-negotiable)

- Workers never set `owner_confirmed: true` — only `confirm_graph(True)`
- Workers never choose `current_task_id` — only `advance` / `advance_after_gate`
- Gate failures: `retry()` via `advance_after_gate`; max 3 then escalate to the user
- Firewall: Code activates on entering `phase_4`, deactivates after `gate_5` pass

---

## Task sequence (Code-owned)

```text
phase_0 → phase_1 → confirm → gate_1
→ phase_2 → phase_3 → gate_2 → gate_3
→ phase_4 → phase_5 → gate_4 → gate_5
→ phase_6 → phase_7 → gate_6 → done
```

One worker briefing = one task card (full `TaskPacket` lands in TECH_DEBT #10).

---

## Legacy note

Older revisions of this file told an “Orchestrator agent” to spawn subagents as the brain.  
That path is **deprecated**. Use `etlai create` / `Orchestrator` APIs above.
