# Architecture

Internal design document for contributors.

---

## 1. What ETLai Is

**ETLai turns a plain-English business request into a running, auditable,
deterministic data pipeline — using AI to *build* the pipeline, never to *run*
it.**

Someone says *"join my weekly sales file with the catalog and flag any product
with margin under 20%."* ETLai produces a folder-driven pipeline that does
exactly that, every time a file lands in the right folder, with:

- **deterministic** execution — no AI at runtime, only tested code + declarative
  config;
- **auditable** structure — read the manifest and see exactly what happens;
- **reusable** building blocks — atoms that outlive any single pipeline.

### The one idea

Everything hangs on a single separation of concerns. A pipeline is **three
things that must never be conflated**:

| Piece | Holds | Example | Domain knowledge? | AI may see it? |
|-------|-------|---------|-------------------|----------------|
| **Atom** | the *verb* (code) | `vlookup`, `computed_column` | no — generic | yes (cloud) |
| **Manifest** | the *wiring* (structure) | `vlookup → groupby → rename_columns` | no — structure | yes |
| **Config** | the *logic* (business values) | `left_column: sku`, `margin < 0.2` | **yes** | local only |

- An **atom** is a single, domain-agnostic operation — one verb, reusable across
  every pipeline. Litmus test: *"rename columns to A, B, C — still works?"*
  Business values never appear in atom code.
- The **manifest** describes *structure*: which atoms, in what order, and how
  files flow between them.
- The **config** holds the *business logic*: column names, expressions,
  thresholds. Same atom + different config = a different pipeline.

This split is what makes the system both safe and auditable: **generic code can
be shown to a cloud AI; domain logic stays on your machine.** (Full visibility
table in §6.)

### Two axes, two planes

ETLai is two machines bolted together, and most confusion comes from mixing
them:

1. **The runtime** — deterministic. Atoms execute against config, orchestrated by
   the registry on Dagster (sensors/schedules), moving files through a lifecycle.
   *No AI at runtime.*
2. **The build** — AI-assisted. LLM workers, gated at each step, turn your
   request into the manifest + config + atoms the runtime needs.
   *AI only at build time.*

```
        BUILD (AI-assisted, one-time)              RUN (deterministic, every time)
 ┌─────────────────────────────────────┐   ┌──────────────────────────────────────┐
 │ request ──► workers ──► gates       │   │ drop file ──► sensor ──► job          │
 │   └──► manifest.yaml                │   │   └──► atom ▸ atom ▸ atom ──► output  │
 │        config.json                  │   │        (config.json drives params)    │
 │        atoms/*.py                   │   └──────────────────────────────────────┘
 └─────────────────────────────────────┘
```

The rest of this document covers the two planes (§2), the contracts between
them (§3), the runtime (§4) and build (§5) systems, the security model (§6), and
the rationale (§7).

---

## 2. The Two Planes

ETLai deliberately splits itself into two planes that are **decoupled except at
one well-defined seam** (the filesystem). They run on different timelines, have
different failure models, and demand different levels of trust.

| | **Runtime plane** | **Build plane** |
|---|---|---|
| **When** | every time a file lands | once, when creating a pipeline |
| **What runs it** | Dagster + deterministic code | `etlai create` (AI-assisted) |
| **Intelligence** | none — code + config | LLM workers, gated |
| **Failure model** | deterministic (same input → same result) | must be caught *before* runtime (gates) |
| **Trust** | trusted library code + local config | untrusted AI output → gated → trusted |
| **Artifacts** | reads manifests, config, atoms | writes manifests, config, atoms |

### The runtime plane — deterministic

The runtime plane is an ordinary, deterministic ETL engine. It has no idea AI
exists:

- **Registry** (`registry.py`) — scans `pipelines/*/manifest.yaml` and builds
  Dagster `Definitions` (jobs + sensors + schedules) from them.
- **Atoms** (`etlai/atoms/*`, `project/atoms/*`) — the reusable, domain-agnostic
  verbs, each an `execute(json) -> json` function.
- **Config** (`config.json`) — per-step business params, read at execution time.
- **Helpers** — the file lifecycle (`PipelineFolders`: `inbox/`, `staging/`,
  `processed/`, `rejected/`, `output/`, `reference/`), explicit file→param
  binding (`InputResolver`), env loading, notifications.
- **Triggers** — a hot-folder sensor (`inbox_files`) and/or a cron schedule
  (`schedule`).
- **Dagster** — the orchestrator that runs jobs, evaluates sensors, and records
  runs.

Flow: *file lands → sensor fires → job runs → atoms execute in order, each
reading its `step_N` config → output written, inputs moved to
`processed/` or `rejected/`.*

### The build plane — AI-assisted

The build plane is a one-time, AI-assisted factory that produces the runtime's
inputs:

- **`etlai create "request"`** — the entry point.
- **Code control plane** (`orchestrator.py`) — a deterministic Python state
  machine that routes tasks and enforces gates. *Not* an LLM.
- **Four LLM workers** — Business Analyst (understand the request), Separator
  (strip domain terms → generic DAG), Atom Smith (find or create domain-free
  atoms), Assembler (wire manifest + config with real values).
- **Six gates** — deterministic validators that check artifacts between phases
  (structure, domain leakage, atom validity, …).
- **The firewall** — physically hides `business_mapping.json` from Atom Smith so
  domain knowledge can never leak into atom code.

Flow: *request → Business Analyst (with user Q&A) → Separator (logical graph) →
Atom Smith (atoms) → Assembler (manifest + config) — with a gate after each
phase.*

### The seam: build writes, runtime reads

The two planes communicate **only through the filesystem**. Build writes three
kinds of files; runtime reads exactly those:

```
            BUILD plane                                       RUNTIME plane
 ┌──────────────────────────────────┐           ┌─────────────────────────────────┐
 │ etlai create "..."               │           │ etlai run (Dagster)             │
 │   ├─ Business Analyst            │           │   registry scans                 │
 │   ├─ Separator                   │   files   │   pipelines/*/manifest.yaml      │
 │   ├─ Atom Smith                  │ ────────► │   → jobs + sensors + schedules   │
 │   └─ Assembler                   │  on disk  │                                  │
 │      │                           │           │   atoms execute(config.json)     │
 │      ▼ writes                    │           │   files move through lifecycle   │
 │   pipelines/<name>/manifest.yaml │           └─────────────────────────────────┘
 │   pipelines/<name>/config.json   │
 │   atoms/<name>.py   (if new)     │
 └──────────────────────────────────┘
```

Three consequences fall out of this seam:

1. **No runtime dependency on the build plane.** A pipeline, once built, runs
   forever without the AI system. You can even hand-write the manifest and config
   and never invoke `etlai create` at all.
2. **The files are the source of truth** — ordinary YAML/JSON/Python, so they're
   auditable, diffable, and reviewable *before* anything executes.
3. **Gates are the trust boundary.** AI output is untrusted until gates pass;
   gates are deterministic precisely so they can't be talked out of failing.

## 3. Core Contracts

Three artifacts define a pipeline: the **atom** (verb), the **config** (logic),
and the **manifest** (wiring). Each has a precise shape. This section is the
*schema*; how they execute is §4, and how they are produced is §5.

### 3.1 The Atom Contract

```python
def execute(params_json: str) -> str:
    """Single unit of work. Domain-agnostic. Returns JSON result."""
```

- **Input** — a JSON string carrying every param: config values, file paths, and
  `target_path`.
- **Output** — a JSON string that **must** include `success` (bool) and `message`
  (str), and **may** include diagnostics (`row_count`, `rows_removed`,
  `flagged_count`, `columns_renamed`, …). The registry reads only
  `success`/`message`, and only on the failure path.

Invariants (enforced by the litmus test and gate 5):

- **Domain-agnostic** — rename every column to `A, B, C`; if the atom stops
  making sense, it's leaking domain. Business values never appear in code.
- **One verb** — join *or* compute *or* filter, never a compound.
- **Logic from config, never hardcoded.**

### 3.2 The Config Contract

Business parameters live in `config.json` under `step_N` keys — for **every**
step, including `step_0`:

```json
{
  "step_0": { "left_column": "sku", "right_column": "sku", "right_output_columns": ["category", "price"] },
  "step_1": { "expression": "price * quantity", "output_column": "revenue" }
}
```

Rules:

- Single-atom pipelines have only `step_0`.
- One rule for all pipelines: **step N reads `config.json["step_N"]`** — no hybrid
  flat/nested format.
- Loaded at execution time with file paths injected — **no interactive prompt**.
  A missing config raises with a helpful message.

### 3.3 The Manifest Contract

The manifest wires atoms together. Minimal single-atom shape:

```yaml
name: pipeline_name
atom: atom_module_name        # single verb
min_files: 1
inputs_map:                   # which params receive which files
  - param: input_file
path: ask                     # optional: external data root (folder picker)
trigger:
  rules:
    - type: inbox_files       # hot-folder sensor
      min_files: 1
```

Composite pipelines replace `atom:` with an ordered `steps:` list:

```yaml
name: sales_reconciliation
min_files: 1
steps:
  - atom: vlookup             # step 0
    inputs_map:
      - param: left_file
      - param: right_file
        source: reference     # permanent lookup, never consumed
        pattern: "catalog.csv"
  - atom: computed_column     # step 1 (reads step 0)
    inputs_map:
      - param: input_file
        source: prev_output
  - atom: flag_rows           # step 2
    input_from: 1             # branch: read step 1, not step 2
    inputs_map:
      - param: input_file
        source: prev_output
  - name: detail_export       # named step → detail_export.csv
    atom: rename_columns
    inputs_map:
      - param: input_file
        source: prev_output
trigger:
  rules:
    - type: inbox_files
      min_files: 1
```

Key fields:

| Field | Meaning |
|---|---|
| `name` | pipeline name (also the job/sensor name) |
| `atom` / `steps` | one verb, or an ordered list of them |
| `min_files` | how many inbox files must be present to trigger |
| `inputs_map` | explicit file→param binding per step (resolution in §4.2) |
| `source` | `inbox` (default) / `prev_output` / `inbox_all` / `reference` |
| `input_from` | non-linear routing — read a non-adjacent step's output |
| `trigger.rules` | `inbox_files` (sensor) and/or `schedule` (cron) |
| `path` | optional external data root for lifecycle folders |

Invariants:

- Every file-consuming step must declare `inputs_map`; a step with inbound files
  but no `inputs_map` fails loudly at runtime.
- The final step is always `rename_columns`.
- A `trigger` with no `rules` defaults to an `inbox_files` sensor when
  `min_files > 0`.

## 4. Runtime Execution

This is the deterministic plane in action. One run is
*trigger → load → bind → execute → write → move*.

### 4.1 Triggers

A run starts one of three ways:

| Trigger | Manifest | Behavior |
|---|---|---|
| **Hot-folder sensor** | `trigger.rules: [{type: inbox_files, min_files: N}]` | polls `inbox/`; fires when N matching files are stable |
| **Cron schedule** | `trigger.rules: [{type: schedule, cron: "0 * * * *"}]` | fires on a schedule (`min_files: 0`) |
| **Manual** | — (Dagster UI or direct) | runs the job with no file config |

- **Sensor** adds *stability* and *staging*: a file counts only after its size is
  unchanged over a short window, then it's moved to `staging/` (preventing a
  double-trigger) and the staged paths are handed to the job.
- **Manual** runs skip staging and stability — the job reads `inbox/` directly.

### 4.2 Input Binding

`InputResolver` maps files to atom params, explicitly, per step via `inputs_map`.
Nothing is guessed:

| `source` | Binds the param to |
|---|---|
| `inbox` (default) | the next unclaimed inbox file, in pipeline order |
| `prev_output` | the previous step's output path |
| `inbox_all` | the full list of inbox files (e.g. `input_files`) |
| `reference` | the first `reference/` file matching `pattern` |

Rules:

- A step with inbound files but no `inputs_map` **fails loudly**.
- A `source: reference` whose `pattern` matches nothing leaves the param unset —
  the atom fails at runtime (and `etlai sync` warns about it).
- A param already set by an explicit `config.json` value is left untouched.

Steps execute linearly by default, each reading the previous step's output.
`input_from: N` overrides this for branching DAGs — the step reads step N's
output instead of its predecessor's.

### 4.3 Output Naming

Every atom writes to `target_path`, assigned by the registry:

| Condition | Output file |
|---|---|
| Last step | `output/output.csv` |
| Named step (`name: detail_export`) | `output/detail_export.csv` |
| Unnamed intermediate | `output/_intermediate_N.csv` |

### 4.4 File Lifecycle

The folders implement a simple state machine:

```
inbox/ ──► staging/ ──► [run] ──► processed/     on success
                        │
                        └───────► rejected/      on failure (+ .error.txt)

reference/   permanent lookups — never moved
output/      transformation results
```

(`staging/` is used only on the sensor path; manual runs go straight from
`inbox/`.)

- **File pipelines** (sensor or manual): inputs are consumed on success
  (`processed/`) and quarantined on failure (`rejected/` + an `.error.txt`).
- **API pipelines** (`min_files: 0`, schedule trigger): `load_files` returns `[]`;
  the atom reads credentials from the env file, fetches data, and writes
  `target_path` — no files move.

## 5. The Build System

The build plane is AI-assisted but not AI-autonomous. A deterministic **Code
control plane** drives four LLM workers through a fixed phase sequence, with
deterministic gates between phases. The design trades a little flexibility for a
lot of *verifiability*: the LLM does the thinking, but nothing it produces runs
until a script has checked it.

### 5.1 The Shape

`etlai create "request"` walks a fixed sequence of phases:

```
request ─► Business Analyst ─► Separator ─► Atom Smith ─► Assembler ─► manifest + config + atoms
```

Each phase is owned by one worker; six deterministic gates validate the
artifact(s) a phase produces before the next phase may begin.

### 5.2 Agents: four workers + Code control plane

There is no "orchestrator agent." The **control plane is Code** — a
deterministic Python state machine (`etlai/orchestrator.py`). Four LLM workers
do the thinking:

| Role | Phases | Knows domain? | Knows atoms? |
|---|---|---|---|
| **Business Analyst** (LLM) | 0–1 | yes | no |
| **Separator** (LLM) | 2–3 | no | no |
| **Atom Smith** (LLM) | 4–5 | no | yes |
| **Assembler** (LLM) | 6–7 | yes | yes |
| **Orchestrator** (Code) | all | no | no |

- **Business Analyst** understands the request. User Q&A is relayed *through the
  Orchestrator*, and only the Orchestrator may set `owner_confirmed: true` (the
  BA always writes `owner_confirmed: false`).
- **Separator** strips domain terms and produces a generic logical DAG.
- **Atom Smith** finds existing atoms or authors new, domain-free ones.
- **Assembler** wires the manifest + config with real values.

**Layer separation:** phase playbooks are *task contracts* (what to produce);
role prompts are *access policies* (what each worker may see); the *control
plane* is Code — not an LLM, not a markdown script.

### 5.3 Gates

Deterministic scripts that validate artifacts between phases:

| Gate | Validates | Key checks |
|---|---|---|
| 1 | `pipeline_graph.yaml` | complete, confirmed, all fields present |
| 2 | `logical_graph.yaml` | zero domain terms (vs `business_mapping.json`), valid verbs |
| 3 | `atomic_operations.yaml` | valid DAG, single verbs, no cycles, no domain leakage |
| 4 | `match_results.yaml` | all ops matched, atoms exist |
| 5 | new atom code | no domain leakage, has `execute()`, no hardcoded paths |
| 6 | `manifest.yaml` + `config.json` | valid structure, no placeholders, last step `rename_columns`, `inputs_map` everywhere needed |

Gates are deterministic *precisely because* LLMs can rationalize anything — a
script that returns PASS/FAIL cannot be talked out of failing.

### 5.4 The Firewall

Atoms must be domain-agnostic, and the system enforces this **by construction**:

```
business_mapping.json ──► Separator produces it
                      ──► Assembler consumes it
                      ──✘ Atom Smith NEVER sees it   (file physically hidden)
```

An LLM agent can read any file in the project, so the only reliable way to keep
`business_mapping.json` away from Atom Smith is to **physically move it out of
the filesystem** during Atom Smith's turn, then restore it. Access-control
tricks don't work — the file itself is gone.

## 6. Security & Privacy Boundaries

The privacy model follows the same domain ↔ generic split as everything else:
**generic structure may be shared with a cloud LLM; domain knowledge and
credentials never leave the machine.** The boundary is drawn per artifact:

| Artifact | Contains | Cloud LLM may see it? |
|---|---|---|
| Atom code | generic logic | yes |
| Manifest | pipeline wiring (structure) | yes |
| `config.json` | business logic (column names, thresholds) | no — local only |
| env file (`manifest.env_file`) | credentials / secrets | **never** |
| `reference/` | lookup tables, historical data | no — in the data path |
| `business_mapping.json` | domain ↔ placeholder map | no — firewalled from Atom Smith |

Notes:

- **Credentials are the hard line.** The env file is loaded into `os.environ`
  *before* any atom runs; its contents never appear in an artifact an agent can
  read. Atoms reach secrets only via `os.environ` at runtime.
- **`config.json` is local-only by convention.** It's a plain project file, but
  it carries the business values (real column names, thresholds), so it is never
  shared with a cloud LLM.
- **`reference/` is data, not code.** It holds permanent lookups and never enters
  the build plane.
- **`business_mapping.json`** is the domain dictionary used to strip/restore
  domain terms; it's physically hidden from Atom Smith (§5.4) so domain names
  can't leak into atom code.

The invariant in one line: **an LLM may see the *shape* of a pipeline, never the
*content* of the business's data.**

## 7. Why It's Built This Way

The design is a chain of decisions, each answering a specific "why." Read
together, they explain the whole system.

### Why AI builds the pipeline but never runs it

An LLM is good at *generating* and bad at *guaranteeing*. Running data through an
LLM on every file drop would be non-deterministic (same input, different
output), expensive, and unauditable. So AI is used exactly once — at build time,
where its output is gated and reviewed — and the runtime is plain deterministic
code + config. You get the LLM's flexibility with the reliability of a script.

### Why the atom / manifest / config split

- **Why atoms are domain-agnostic** — if an atom knows column names, it can't be
  reused. The same `computed_column` handles revenue, interest rates, and margins
  because the expression comes from config, not code.
- **Why config is separate from manifest** — the manifest is *structure* (what to
  wire), committed and shareable; the config is *business values* (what params),
  which may be sensitive. Keeping them apart lets one atom serve many pipelines
  with different configs, and keeps domain logic out of the generic parts.
- **Why `step_N` everywhere (including `step_0`)** — one rule for all pipelines. A
  single-atom pipeline is just `{ "step_0": { … } }`; there's no hybrid
  flat/nested special case to remember.

### Why the trust boundary is physical and deterministic

- **Why the firewall moves the file, not its permissions** — an LLM agent can read
  any file in the project, so the only reliable way to keep
  `business_mapping.json` from Atom Smith is to physically remove it from the
  filesystem during its turn. Access control is theatre against a process that
  can read everything.
- **Why gates are deterministic scripts** — an LLM can rationalize anything, so an
  LLM's judgment is not a gate. A script returns PASS/FAIL and cannot be talked
  out of failing.

### Why `path: ask` uses Tkinter

Users may want pipeline data outside the project directory (e.g. a shared network
drive). `path: ask` opens a native folder picker during `etlai sync` and writes
the chosen absolute path back into the manifest.

---

## Appendix A: CLI Commands

<!-- TODO -->

## Appendix B: Module Resolution

<!-- TODO -->

## Appendix C: Shipped Atoms

<!-- TODO -->

## Appendix D: Directory Layout & `path:` Mechanics

<!-- TODO -->
