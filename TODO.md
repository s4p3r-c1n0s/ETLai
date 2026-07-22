# TODO

**Priority:** Low (design exploration only)
**Status:** Not started
**Blocked by:** Nothing. Can start when needed.

## 1. Decouple Dagster dependencies

**Goal:** Abstract orchestration primitives behind interfaces so Dagster can be swapped with Airflow, Prefect, Temporal, or custom runners.

### Current Dagster coupling points

1. **registry.py**
   - Direct imports: `Definitions, In, Out, OpExecutionContext, ScheduleDefinition, job, op`
   - `build_definitions()` returns Dagster-specific `Definitions` object
   - `@op` and `@job` decorators used throughout

2. **hot_folder_sensor.py**
   - Direct imports: `RunRequest, SensorEvaluationContext, SkipReason, sensor`
   - `@sensor` decorator with Dagster-specific params
   - `RunRequest` with `run_config` structure specific to Dagster ops

3. **cli.py**
   - `etlai run` calls `dagster dev -m definitions` directly
   - Scaffold copies `dagster.yaml` and `definitions.py`

4. **scaffold/definitions.py**
   - Entry point that Dagster loads
   - Calls `build_definitions()` and exposes as `defs`

### Proposed architecture (Adapter pattern + Strategy pattern)

#### Step 1: Define orchestration interfaces

Create `etlai/orchestration/interfaces.py`:

```python
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List

class ExecutionContext(ABC):
    """Abstract execution context passed to steps."""
    @abstractmethod
    def log_info(self, message: str) -> None: ...
    
    @abstractmethod
    def get_config(self, key: str, default: Any = None) -> Any: ...


class StepDefinition(ABC):
    """Represents a single executable step."""
    @abstractmethod
    def execute(self, context: ExecutionContext, **kwargs) -> Any: ...


class JobDefinition(ABC):
    """Represents a workflow/pipeline/job."""
    name: str
    steps: List[StepDefinition]
    
    @abstractmethod
    def build(self) -> Any:
        """Return the orchestrator-specific job object."""


class TriggerDefinition(ABC):
    """Represents a trigger (sensor, schedule, webhook)."""
    @abstractmethod
    def build(self) -> Any:
        """Return the orchestrator-specific trigger object."""


class OrchestrationAdapter(ABC):
    """Main adapter interface for orchestration backends."""
    
    @abstractmethod
    def create_step(
        self, 
        name: str, 
        func: Callable,
        inputs: Dict[str, type],
        outputs: Dict[str, type]
    ) -> StepDefinition: ...
    
    @abstractmethod
    def create_job(self, name: str, steps: List[StepDefinition]) -> JobDefinition: ...
    
    @abstractmethod
    def create_file_sensor(
        self, 
        name: str, 
        job: JobDefinition,
        folder_path: str,
        min_files: int,
        **kwargs
    ) -> TriggerDefinition: ...
    
    @abstractmethod
    def create_schedule(
        self, 
        name: str,
        job: JobDefinition,
        cron: str
    ) -> TriggerDefinition: ...
    
    @abstractmethod
    def build_definitions(
        self,
        jobs: List[JobDefinition],
        sensors: List[TriggerDefinition],
        schedules: List[TriggerDefinition]
    ) -> Any:
        """Return the orchestrator's top-level definitions object."""


class OrchestrationRunner(ABC):
    """CLI runner interface for starting the orchestrator."""
    @abstractmethod
    def run_dev_server(self, module_path: str, port: int = 3000) -> None: ...
```

#### Step 2: Implement Dagster adapter

Create `etlai/orchestration/dagster_adapter.py`:

```python
from dagster import Definitions, In, Out, OpExecutionContext, ScheduleDefinition, job, op, sensor, RunRequest, SkipReason
from .interfaces import (
    ExecutionContext, StepDefinition, JobDefinition, 
    TriggerDefinition, OrchestrationAdapter, OrchestrationRunner
)

class DagsterExecutionContext(ExecutionContext):
    def __init__(self, dagster_context: OpExecutionContext):
        self._context = dagster_context
    
    def log_info(self, message: str) -> None:
        self._context.log.info(message)
    
    def get_config(self, key: str, default=None):
        return self._context.op_config.get(key, default) if self._context.op_config else default


class DagsterStepDefinition(StepDefinition):
    def __init__(self, op_func):
        self._op = op_func
    
    def execute(self, context: ExecutionContext, **kwargs):
        # Delegate to wrapped Dagster op
        pass


class DagsterJobDefinition(JobDefinition):
    def __init__(self, name: str, job_func):
        self.name = name
        self._job = job_func
    
    def build(self):
        return self._job


class DagsterTriggerDefinition(TriggerDefinition):
    def __init__(self, trigger_func):
        self._trigger = trigger_func
    
    def build(self):
        return self._trigger


class DagsterAdapter(OrchestrationAdapter):
    def create_step(self, name: str, func: Callable, inputs: Dict, outputs: Dict) -> StepDefinition:
        # Map generic inputs/outputs to Dagster In/Out
        dagster_ins = {k: In(v) for k, v in inputs.items()}
        dagster_outs = {k: Out() for k, v in outputs.items()}
        
        @op(name=name, ins=dagster_ins, out=dagster_outs)
        def _op(context: OpExecutionContext, **kwargs):
            wrapped_context = DagsterExecutionContext(context)
            return func(wrapped_context, **kwargs)
        
        return DagsterStepDefinition(_op)
    
    def create_job(self, name: str, steps: List[StepDefinition]) -> JobDefinition:
        dagster_ops = [s._op for s in steps]
        
        @job(name=name)
        def _job():
            # Wire ops together based on their inputs/outputs
            # This is simplified - real impl needs proper chaining
            for op_func in dagster_ops:
                op_func()
        
        return DagsterJobDefinition(name, _job)
    
    def create_file_sensor(self, name: str, job: JobDefinition, folder_path: str, min_files: int, **kwargs) -> TriggerDefinition:
        @sensor(name=name, job_name=job.name)
        def _sensor(context):
            # File watching logic (move from hot_folder_sensor.py)
            yield RunRequest(...)
        
        return DagsterTriggerDefinition(_sensor)
    
    def create_schedule(self, name: str, job: JobDefinition, cron: str) -> TriggerDefinition:
        sched = ScheduleDefinition(name=name, job=job.build(), cron_schedule=cron)
        return DagsterTriggerDefinition(sched)
    
    def build_definitions(self, jobs, sensors, schedules):
        return Definitions(
            jobs=[j.build() for j in jobs],
            sensors=[s.build() for s in sensors],
            schedules=[s.build() for s in schedules]
        )


class DagsterRunner(OrchestrationRunner):
    def run_dev_server(self, module_path: str, port: int = 3000):
        import subprocess, sys
        subprocess.run([sys.executable, "-m", "dagster", "dev", "-m", module_path, "-p", str(port)])
```

#### Step 3: Refactor registry to use adapter

Modify `etlai/registry.py`:

```python
from etlai.orchestration.interfaces import OrchestrationAdapter
from etlai.orchestration.dagster_adapter import DagsterAdapter

# Dependency injection: adapter chosen at module level
# Future: read from etlai.yaml {"orchestrator": "dagster|airflow|prefect"}
_adapter: OrchestrationAdapter = DagsterAdapter()

def build_definitions():
    """Orchestrator-agnostic registry."""
    # ... existing manifest scanning logic ...
    
    jobs = []
    for manifest_path in ...:
        manifest = _load_manifest(manifest_path)
        job_def = _build_job_generic(manifest, _adapter)
        jobs.append(job_def)
    
    sensors, schedules = _build_triggers_generic(manifests, jobs, _adapter)
    
    return _adapter.build_definitions(jobs, sensors, schedules)


def _build_job_generic(manifest: dict, adapter: OrchestrationAdapter) -> JobDefinition:
    """Build job using adapter, not direct Dagster calls."""
    pipeline_name = manifest["name"]
    
    # Create load_files step
    load_step = adapter.create_step(
        name=f"{pipeline_name}__load_files",
        func=_load_files_logic,  # pure function, no decorators
        inputs={},
        outputs={"file_paths": list}
    )
    
    # Create execute step
    execute_step = adapter.create_step(
        name=f"{pipeline_name}__execute",
        func=_execute_step_logic,  # refactored _execute_step without Dagster deps
        inputs={"file_paths": list},
        outputs={}
    )
    
    return adapter.create_job(pipeline_name, [load_step, execute_step])
```

#### Step 4: Add orchestrator selection to config

Modify `etlai.yaml`:

```yaml
pipelines_root: ./pipelines
orchestrator: dagster  # Options: dagster, airflow, prefect, custom
orchestrator_config:
  port: 3000
  storage: sqlite  # dagster-specific
```

Modify `etlai/cli.py`:

```python
def cmd_run():
    config = _load_etlai_config()
    orchestrator_type = config.get("orchestrator", "dagster")
    
    if orchestrator_type == "dagster":
        from etlai.orchestration.dagster_adapter import DagsterRunner
        runner = DagsterRunner()
    elif orchestrator_type == "airflow":
        from etlai.orchestration.airflow_adapter import AirflowRunner
        runner = AirflowRunner()
    # ... etc
    
    runner.run_dev_server("definitions", port=config.get("orchestrator_config", {}).get("port", 3000))
```

### Implementation order

1. ⬜ **Phase 1** (foundation): Create interfaces module
2. ⬜ **Phase 2** (extract): Refactor `_execute_step` to remove OpExecutionContext dependency (use generic context)
3. ⬜ **Phase 3** (wrap): Implement DagsterAdapter wrapping existing Dagster primitives
4. ⬜ **Phase 4** (migrate): Refactor registry.py to use adapter instead of direct Dagster imports
5. ⬜ **Phase 5** (CLI): Update cli.py to use runner interface
6. ⬜ **Phase 6** (test): Verify existing Dagster workflows still work
7. ⬜ **Phase 7** (alternative): Implement AirflowAdapter or PrefectAdapter as proof of portability

**Status:** Design complete. Implementation not started. No `etlai/orchestration/` directory exists yet.

### Benefits

- **Testability**: Can mock adapter for unit tests without needing Dagster runtime
- **Flexibility**: Swap orchestrators without touching atoms, forms, or business logic
- **Future-proof**: New orchestrators (Temporal, custom) are just new adapter implementations
- **Separation of concerns**: Pipeline logic (what to execute) decoupled from orchestration (how to schedule/run)

### Trade-offs

- **Initial complexity**: More indirection, more files
- **Lowest common denominator**: Interfaces can only expose features common to all orchestrators
- **Maintenance**: Need to keep adapters in sync when orchestrators update APIs

### Notes

- Keep Dagster as the default and primary supported backend
- Alternative adapters can be community-contributed or optional extras
- Atoms and forms remain completely orchestrator-agnostic (already achieved)
