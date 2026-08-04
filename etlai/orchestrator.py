"""Orchestrator — Code control plane for pipeline creation (TECH_DEBT #11).

Deterministic Python owns phase advance, confirmation, gates, firewall, and
packet assembly. LLMs execute worker task cards only — they do not choose the
next task_id.

Usage from CLI:
    etlai create "Build me a pipeline that..."

Usage from Python:
    from etlai.orchestrator import Orchestrator
    orch = Orchestrator(project_root=Path("."), pipeline_name="my_pipeline")
    orch.start_control_session(user_request="Build me a pipeline that...")
    # Code loop: briefing → worker/gate → advance() / retry()
"""

import json
import subprocess
import sys
from pathlib import Path

import yaml

BA_SESSION_FILE = "ba_session.json"
BA_QUESTIONS_FILE = "ba_questions.json"
CONTROL_SESSION_FILE = "control_session.json"
MAX_BA_ROUNDS = 5

# Code control-plane task graph (TECH_DEBT #11). LLMs never choose the next id.
CONTROL_TASK_SEQUENCE = [
    "phase_0",
    "phase_1",
    "confirm",
    "gate_1",
    "phase_2",
    "phase_3",
    "gate_2",
    "gate_3",
    "phase_4",
    "phase_5",
    "gate_4",
    "gate_5",
    "phase_6",
    "phase_7",
    "gate_6",
    "done",
]

GATE_TASK_NUMBERS = {
    "gate_1": 1,
    "gate_2": 2,
    "gate_3": 3,
    "gate_4": 4,
    "gate_5": 5,
    "gate_6": 6,
}

WORKER_TASKS = {
    "phase_0",
    "phase_1",
    "phase_2",
    "phase_3",
    "phase_4",
    "phase_5",
    "phase_6",
    "phase_7",
}

ROLE_FOR_TASK = {
    "phase_0": "business_analyst",
    "phase_1": "business_analyst",
    "phase_2": "separator",
    "phase_3": "separator",
    "phase_4": "atom_smith",
    "phase_5": "atom_smith",
    "phase_6": "assembler",
    "phase_7": "assembler",
}


class GateResult:
    """Result of running a gate validator."""

    def __init__(self, gate_num: int, passed: bool, errors: list[str], raw_output: str):
        self.gate_num = gate_num
        self.passed = passed
        self.errors = errors
        self.raw_output = raw_output

    def __bool__(self):
        return self.passed

    def error_summary(self) -> str:
        if not self.errors:
            return ""
        return "\n".join(f"  - {e}" for e in self.errors)


class BATurnResult:
    """Snapshot of one Business Analyst mediation turn (Orchestrator-owned channel)."""

    def __init__(
        self,
        round_number: int,
        questions: list,
        graph: dict | None,
        graph_path: Path | None,
        ready_for_confirm: bool,
        owner_confirmed: bool,
        confirmed_by_orchestrator: bool,
    ):
        self.round_number = round_number
        self.questions = questions
        self.graph = graph
        self.graph_path = graph_path
        self.ready_for_confirm = ready_for_confirm
        self.owner_confirmed = owner_confirmed
        self.confirmed_by_orchestrator = confirmed_by_orchestrator


class Orchestrator:
    """Code control plane for pipeline creation.

    Responsibilities:
    1. Persist and advance control_session.json (task_id / retries)
    2. Own the user channel for phases 0-1 (relay questions; confirm_graph)
    3. Run gate validators; enforce firewall around Atom Smith phases
    4. Emit worker briefings (packets) — never invent domain answers

    Worker LLMs are invoked by the caller with briefings from this class.
    They must not choose the next task_id.
    """

    MAX_RETRIES = 3

    def __init__(self, project_root: Path, pipeline_name: str):
        self.project_root = project_root.resolve()
        self.pipeline_name = pipeline_name
        self.pipeline_dir = self.project_root / "pipelines" / pipeline_name
        self.workflow_dir = self.pipeline_dir / "workflow"
        self.validators_dir = self._find_validators_dir()
        self._firewall_active = False

    def _find_validators_dir(self) -> Path:
        """Locate gate validators — check project scaffold first, then package."""
        project_validators = self.project_root / "workflow" / "validators"
        if project_validators.is_dir():
            return project_validators

        from etlai import __file__ as pkg_init
        pkg_validators = Path(pkg_init).parent / "scaffold" / "workflow" / "validators"
        if pkg_validators.is_dir():
            return pkg_validators

        raise FileNotFoundError(
            "Cannot find gate validators. Ensure project was scaffolded with 'etlai init'."
        )

    def initialize(self) -> Path:
        """Create pipeline and workflow directories. Returns workflow_dir path."""
        self.pipeline_dir.mkdir(parents=True, exist_ok=True)
        self.workflow_dir.mkdir(parents=True, exist_ok=True)
        return self.workflow_dir

    # ------------------------------------------------------------------
    # Code control plane state machine (TECH_DEBT #11)
    # ------------------------------------------------------------------

    @property
    def control_session_path(self) -> Path:
        return self.workflow_dir / CONTROL_SESSION_FILE

    def start_control_session(self, user_request: str) -> dict:
        """Start or reset the Code-owned creation loop. Also starts BA mediation."""
        self.initialize()
        self.start_ba_session(user_request)
        session = {
            "user_request": user_request,
            "current_task_id": CONTROL_TASK_SEQUENCE[0],
            "retry_count": 0,
            "max_retries": self.MAX_RETRIES,
            "worker_submitted_for": None,
            "history": [],
        }
        self._write_control_session(session)
        return session

    def _default_control_session(self) -> dict:
        return {
            "user_request": "",
            "current_task_id": CONTROL_TASK_SEQUENCE[0],
            "retry_count": 0,
            "max_retries": self.MAX_RETRIES,
            "worker_submitted_for": None,
            "history": [],
        }

    def _read_control_session(self) -> dict:
        if not self.control_session_path.is_file():
            return self._default_control_session()
        with open(self.control_session_path) as f:
            data = json.load(f)
        base = self._default_control_session()
        base.update(data)
        return base

    def _write_control_session(self, session: dict) -> None:
        self.workflow_dir.mkdir(parents=True, exist_ok=True)
        with open(self.control_session_path, "w") as f:
            json.dump(session, f, indent=2)
            f.write("\n")

    def _append_history(self, session: dict, event: str, detail: str = "") -> None:
        history = list(session.get("history") or [])
        history.append({
            "task_id": session.get("current_task_id"),
            "event": event,
            "detail": detail,
        })
        session["history"] = history

    @property
    def current_task_id(self) -> str:
        return self._read_control_session().get("current_task_id", CONTROL_TASK_SEQUENCE[0])

    def control_status(self) -> dict:
        """Snapshot of Code control-plane state for CLI / drivers."""
        session = self._read_control_session()
        task_id = session.get("current_task_id", CONTROL_TASK_SEQUENCE[0])
        return {
            "user_request": session.get("user_request", ""),
            "current_task_id": task_id,
            "retry_count": int(session.get("retry_count", 0)),
            "max_retries": int(session.get("max_retries", self.MAX_RETRIES)),
            "is_worker": task_id in WORKER_TASKS,
            "is_gate": task_id in GATE_TASK_NUMBERS,
            "is_confirm": task_id == "confirm",
            "is_done": task_id == "done",
            "role": ROLE_FOR_TASK.get(task_id),
            "can_advance": self.can_advance()[0],
            "advance_block_reason": self.can_advance()[1],
        }

    def can_advance(self) -> tuple[bool, str]:
        """Whether Code may move past the current task_id."""
        task_id = self.current_task_id
        if task_id == "done":
            return False, "already done"

        if task_id == "confirm":
            ba = self._read_ba_session()
            graph = self.read_artifact("pipeline_graph") or {}
            if ba.get("confirmed_by_orchestrator") and graph.get("owner_confirmed"):
                return True, "ok"
            return False, "call confirm_graph(True) after explicit user assent"

        if task_id in GATE_TASK_NUMBERS:
            return False, "use advance_after_gate(result) after run_current_gate()"

        # Worker tasks: require explicit submit_worker() + expected artifacts
        checks = {
            "phase_0": self._artifact_exists("pipeline_graph"),
            "phase_1": self._artifact_exists("pipeline_graph"),
            "phase_2": self._artifact_exists("logical_graph") and self._artifact_exists("business_mapping"),
            "phase_3": self._artifact_exists("atomic_operations"),
            "phase_4": self._artifact_exists("match_results"),
            "phase_5": self._artifact_exists("match_results"),
            "phase_6": self._artifact_exists("manifest") and self._artifact_exists("config"),
            "phase_7": self._artifact_exists("manifest") and self._artifact_exists("config"),
        }
        if task_id in WORKER_TASKS:
            session = self._read_control_session()
            if session.get("worker_submitted_for") != task_id:
                return False, "call submit_worker() after the worker finishes this task"
            if task_id in checks and not checks[task_id]:
                return False, f"worker artifacts for {task_id} not ready"
            return True, "ok"
        return False, f"unknown task_id: {task_id}"

    def submit_worker(self) -> None:
        """Declare that the worker finished the current task (artifacts should exist)."""
        session = self._read_control_session()
        task_id = session.get("current_task_id")
        if task_id not in WORKER_TASKS:
            raise RuntimeError(f"submit_worker only valid on worker tasks, got {task_id!r}")
        session["worker_submitted_for"] = task_id
        self._append_history(session, "submit_worker", task_id)
        self._write_control_session(session)

    def _artifact_exists(self, name: str) -> bool:
        return self.read_artifact(name) is not None

    def advance(self, *, from_gate_pass: bool = False) -> str:
        """Move to the next task_id after preconditions pass. Returns new task_id."""
        if not from_gate_pass:
            ok, reason = self.can_advance()
            if not ok:
                raise RuntimeError(f"Cannot advance from {self.current_task_id}: {reason}")

        session = self._read_control_session()
        current = session["current_task_id"]
        if current not in CONTROL_TASK_SEQUENCE:
            raise RuntimeError(f"Unknown task_id in session: {current!r}")
        idx = CONTROL_TASK_SEQUENCE.index(current)
        if idx >= len(CONTROL_TASK_SEQUENCE) - 1:
            raise RuntimeError("Already at end of control sequence")

        nxt = CONTROL_TASK_SEQUENCE[idx + 1]
        self._append_history(session, "advance", f"→ {nxt}")
        session["current_task_id"] = nxt
        session["retry_count"] = 0
        session["worker_submitted_for"] = None
        self._write_control_session(session)

        # Firewall side effects owned by Code
        if nxt == "phase_4":
            self.activate_firewall()
        if current == "gate_5" and nxt == "phase_6":
            self.deactivate_firewall()

        return nxt

    def retry(self) -> tuple[bool, int]:
        """Record a failed attempt on the current task. False if max retries exceeded."""
        session = self._read_control_session()
        count = int(session.get("retry_count", 0)) + 1
        max_retries = int(session.get("max_retries", self.MAX_RETRIES))
        session["retry_count"] = count
        self._append_history(session, "retry", f"attempt {count}/{max_retries}")
        self._write_control_session(session)
        return count <= max_retries, count

    def run_current_gate(self) -> GateResult:
        """Run the gate validator for the current gate_* task."""
        task_id = self.current_task_id
        if task_id not in GATE_TASK_NUMBERS:
            raise RuntimeError(f"current_task_id {task_id!r} is not a gate task")
        if task_id == "gate_1":
            ready, reason = self.prepare_gate1()
            if not ready:
                return GateResult(
                    gate_num=1,
                    passed=False,
                    errors=[reason],
                    raw_output=reason,
                )
        return self.run_gate(GATE_TASK_NUMBERS[task_id])

    def advance_after_gate(self, result: GateResult) -> str | None:
        """Advance on gate pass; retry on fail. Returns new task_id, or None if retries exhausted."""
        if self.current_task_id not in GATE_TASK_NUMBERS:
            raise RuntimeError("advance_after_gate only valid on gate_* tasks")
        if result:
            return self.advance(from_gate_pass=True)
        ok, count = self.retry()
        if not ok:
            session = self._read_control_session()
            self._append_history(session, "fail", f"max retries ({count})")
            self._write_control_session(session)
            if self.current_task_id in ("gate_4", "gate_5") or self._firewall_active:
                self.deactivate_firewall()
            return None
        return self.current_task_id

    def worker_briefing(self, user_feedback: str | None = None, gate_errors: list[str] | None = None) -> str:
        """Emit instructions for the current worker task (Code-assembled packet)."""
        task_id = self.current_task_id
        if task_id not in WORKER_TASKS:
            raise RuntimeError(f"No worker briefing for task {task_id!r}")

        if task_id in ("phase_0", "phase_1"):
            return self.build_ba_turn_prompt(
                user_feedback=user_feedback,
                gate_errors=gate_errors,
            )

        role = ROLE_FOR_TASK[task_id]
        ctx = self.build_agent_context(role)
        scaffold = self._find_scaffold_workflow_dir()
        phase_file = {
            "phase_2": "phase_2_separation.md",
            "phase_3": "phase_3_atomize.md",
            "phase_4": "phase_4_match.md",
            "phase_5": "phase_5_create.md",
            "phase_6": "phase_6_assemble.md",
            "phase_7": "phase_7_rehydrate.md",
        }[task_id]

        lines = [
            f"You are executing worker task {task_id} (Code control plane).",
            "Follow ONLY the assigned phase playbook. Do not talk to the user.",
            "Do not choose the next phase — write artifacts and stop.",
            "",
            f"Role policy: {ctx['system_prompt']}",
            f"Phase playbook: {scaffold / phase_file}",
            f"Layers: {scaffold / 'LAYERS.md'}",
            "",
            "Readable:",
            *[f"  - {p}" for p in ctx["readable_files"]],
            "Writable:",
            *[f"  - {p}" for p in ctx["writable_paths"]],
        ]
        if gate_errors:
            lines.append("")
            lines.append("Gate reported these errors — fix artifacts then stop:")
            for err in gate_errors:
                lines.append(f"  - {err}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # BA mediation (Orchestrator owns the user channel for phases 0-1)
    # ------------------------------------------------------------------

    @property
    def ba_session_path(self) -> Path:
        return self.workflow_dir / BA_SESSION_FILE

    @property
    def ba_questions_path(self) -> Path:
        return self.workflow_dir / BA_QUESTIONS_FILE

    def start_ba_session(self, user_request: str) -> dict:
        """Initialize or reset BA mediation state for phases 0-1."""
        self.initialize()
        session = {
            "user_request": user_request,
            "round": 0,
            "pending_questions": [],
            "answer_history": [],
            "confirmed_by_orchestrator": False,
            "max_rounds": MAX_BA_ROUNDS,
        }
        self._write_ba_session(session)
        return session

    def _read_ba_session(self) -> dict:
        if not self.ba_session_path.is_file():
            return {
                "user_request": "",
                "round": 0,
                "pending_questions": [],
                "answer_history": [],
                "confirmed_by_orchestrator": False,
                "max_rounds": MAX_BA_ROUNDS,
            }
        with open(self.ba_session_path) as f:
            return json.load(f)

    def _write_ba_session(self, session: dict) -> None:
        self.workflow_dir.mkdir(parents=True, exist_ok=True)
        with open(self.ba_session_path, "w") as f:
            json.dump(session, f, indent=2)
            f.write("\n")

    def build_ba_turn_prompt(
        self,
        user_feedback: str | None = None,
        gate_errors: list[str] | None = None,
    ) -> str:
        """Build a control-plane turn packet for one BA worker invoke.

        Composes: thin role policy + phase playbook paths + artifact paths.
        Worker must never set owner_confirmed; only confirm_graph() may.
        """
        session = self._read_ba_session()
        next_round = int(session.get("round", 0)) + 1
        ctx = self.build_agent_context("business_analyst")
        workflow_dir_scaffold = self._find_scaffold_workflow_dir()
        graph_path = self.workflow_dir / "pipeline_graph.yaml"
        questions_path = self.ba_questions_path

        lines = [
            "You are executing one Business Analyst worker turn (control-plane mediated).",
            "You do NOT talk to the user. Follow ONLY the assigned phase playbook for task how-to.",
            "",
            f"Role policy: {ctx['system_prompt']}",
            "Phase playbooks (execute the relevant one for this turn — prefer a single phase):",
            f"  - {workflow_dir_scaffold / 'phase_0_dejargon.md'}",
            f"  - {workflow_dir_scaffold / 'phase_1_graph.md'}",
            f"Template: {workflow_dir_scaffold / 'templates' / 'pipeline_graph.yaml'}",
            f"Layers: {workflow_dir_scaffold / 'LAYERS.md'}",
            f"User request: {session.get('user_request', '')}",
            f"Turn / round: {next_round} (max {session.get('max_rounds', MAX_BA_ROUNDS)})",
            "",
            "Write:",
            f"  - {graph_path}  (always owner_confirmed: false)",
            f"  - {questions_path}  (JSON list or {{\"questions\": [...]}}; empty when ready to confirm)",
            "",
            "FORBIDDEN:",
            "- Do NOT set owner_confirmed: true (control plane confirm_graph only).",
            "- Do NOT ask the user questions directly.",
            "- Do NOT proceed to phase 2+ or write atoms/manifest/config.",
            "- Do NOT restate a custom process — use the phase playbook.",
        ]

        if user_feedback:
            lines.extend(["", "Answered questions / feedback (from control plane):", user_feedback])

        history = session.get("answer_history") or []
        if history and not user_feedback:
            lines.append("")
            lines.append("Prior answer history:")
            for i, entry in enumerate(history, 1):
                lines.append(f"  Round {i}: {entry}")

        if gate_errors:
            lines.append("")
            lines.append("Gate 1 reported these errors — fix the graph (still keep owner_confirmed: false):")
            for err in gate_errors:
                lines.append(f"  - {err}")

        return "\n".join(lines)

    def begin_ba_turn(self) -> int:
        """Increment BA round counter. Returns the new round number."""
        session = self._read_ba_session()
        session["round"] = int(session.get("round", 0)) + 1
        self._write_ba_session(session)
        return session["round"]

    def record_ba_questions(self, questions: list) -> Path:
        """Persist questions proposed by BA for Orchestrator to relay to the user."""
        self.workflow_dir.mkdir(parents=True, exist_ok=True)
        payload = {"questions": list(questions)}
        with open(self.ba_questions_path, "w") as f:
            json.dump(payload, f, indent=2)
            f.write("\n")
        session = self._read_ba_session()
        session["pending_questions"] = list(questions)
        self._write_ba_session(session)
        return self.ba_questions_path

    def get_pending_questions(self) -> list:
        """Load pending clarifying questions (from file or session)."""
        if self.ba_questions_path.is_file():
            with open(self.ba_questions_path) as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return list(data.get("questions") or [])
        session = self._read_ba_session()
        return list(session.get("pending_questions") or [])

    def record_user_answers(self, answers: str) -> None:
        """Store Orchestrator-relayed user answers for the next BA turn."""
        session = self._read_ba_session()
        history = list(session.get("answer_history") or [])
        history.append(answers)
        session["answer_history"] = history
        session["pending_questions"] = []
        self._write_ba_session(session)
        if self.ba_questions_path.is_file():
            self.ba_questions_path.unlink()

    def strip_owner_confirmed(self) -> bool:
        """Clear owner_confirmed if BA (or anyone) set it outside confirm_graph.

        Returns True if the flag was cleared.
        """
        graph_path = self.workflow_dir / "pipeline_graph.yaml"
        if not graph_path.is_file():
            return False
        with open(graph_path) as f:
            graph = yaml.safe_load(f) or {}
        if not graph.get("owner_confirmed"):
            return False
        graph["owner_confirmed"] = False
        with open(graph_path, "w") as f:
            yaml.safe_dump(graph, f, sort_keys=False)
        session = self._read_ba_session()
        session["confirmed_by_orchestrator"] = False
        self._write_ba_session(session)
        return True

    def confirm_graph(self, user_said_yes: bool) -> bool:
        """Set owner_confirmed only after explicit user assent via Orchestrator.

        Returns True if the graph is now confirmed.
        """
        if not user_said_yes:
            self.strip_owner_confirmed()
            return False

        graph_path = self.workflow_dir / "pipeline_graph.yaml"
        if not graph_path.is_file():
            raise FileNotFoundError(
                f"Cannot confirm: {graph_path} does not exist. Run a BA turn first."
            )

        with open(graph_path) as f:
            graph = yaml.safe_load(f) or {}
        graph["owner_confirmed"] = True
        with open(graph_path, "w") as f:
            yaml.safe_dump(graph, f, sort_keys=False)

        session = self._read_ba_session()
        session["confirmed_by_orchestrator"] = True
        session["pending_questions"] = []
        self._write_ba_session(session)
        if self.ba_questions_path.is_file():
            self.ba_questions_path.unlink()
        return True

    def prepare_gate1(self) -> tuple[bool, str]:
        """Ensure confirmation was Orchestrator-owned before running gate 1.

        If YAML has owner_confirmed but session was not confirmed by Orchestrator,
        strip the flag and return (False, reason).
        """
        graph_path = self.workflow_dir / "pipeline_graph.yaml"
        if not graph_path.is_file():
            return False, "pipeline_graph.yaml missing"

        with open(graph_path) as f:
            graph = yaml.safe_load(f) or {}

        session = self._read_ba_session()
        orch_confirmed = bool(session.get("confirmed_by_orchestrator"))

        if graph.get("owner_confirmed") and not orch_confirmed:
            self.strip_owner_confirmed()
            return (
                False,
                "owner_confirmed was set without Orchestrator.confirm_graph(); "
                "flag cleared. Relay the draft to the user, then call confirm_graph(True).",
            )

        if not graph.get("owner_confirmed"):
            return (
                False,
                "Graph not confirmed. Present draft to user, then call confirm_graph(True).",
            )

        return True, "ok"

    def get_ba_turn_status(self) -> BATurnResult:
        """Snapshot current BA mediation state for the Orchestrator loop."""
        session = self._read_ba_session()
        graph_path = self.workflow_dir / "pipeline_graph.yaml"
        graph = None
        if graph_path.is_file():
            with open(graph_path) as f:
                graph = yaml.safe_load(f)

        questions = self.get_pending_questions()
        orch_confirmed = bool(session.get("confirmed_by_orchestrator"))
        owner_confirmed = bool(graph and graph.get("owner_confirmed"))
        ready = (
            graph is not None
            and not questions
            and not owner_confirmed
            and not orch_confirmed
        )

        return BATurnResult(
            round_number=int(session.get("round", 0)),
            questions=questions,
            graph=graph,
            graph_path=graph_path if graph_path.is_file() else None,
            ready_for_confirm=ready,
            owner_confirmed=owner_confirmed,
            confirmed_by_orchestrator=orch_confirmed,
        )

    def run_gate(self, gate_num: int) -> GateResult:
        """Run a gate validator and return structured result.

        Gates 1-3 take only pipeline_dir.
        Gates 4-6 take pipeline_dir and project_root.
        """
        script_names = {
            1: "gate_1_graph_complete.py",
            2: "gate_2_no_leakage.py",
            3: "gate_3_dag_valid.py",
            4: "gate_4_match_coverage.py",
            5: "gate_5_atom_clean.py",
            6: "gate_6_manifest_valid.py",
        }

        if gate_num not in script_names:
            raise ValueError(f"Invalid gate number: {gate_num}. Must be 1-6.")

        script = self.validators_dir / script_names[gate_num]
        if not script.is_file():
            return GateResult(
                gate_num=gate_num,
                passed=False,
                errors=[f"Validator script not found: {script}"],
                raw_output="",
            )

        cmd = [sys.executable, str(script), str(self.pipeline_dir)]
        if gate_num >= 4:
            cmd.append(str(self.project_root))

        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=str(self.project_root)
        )

        raw_output = result.stdout + result.stderr
        passed = result.returncode == 0
        errors = self._parse_gate_errors(raw_output)

        return GateResult(
            gate_num=gate_num,
            passed=passed,
            errors=errors,
            raw_output=raw_output.strip(),
        )

    def run_gates(self, *gate_nums: int) -> list[GateResult]:
        """Run multiple gates in sequence. Stops on first failure."""
        results = []
        for num in gate_nums:
            result = self.run_gate(num)
            results.append(result)
            if not result:
                break
        return results

    def activate_firewall(self) -> bool:
        """Hide business_mapping.json from Atom Smith by renaming it.

        Returns True if firewall was activated, False if file doesn't exist.
        """
        mapping_path = self.workflow_dir / "business_mapping.json"
        hidden_path = self.workflow_dir / ".business_mapping.json.firewalled"

        if not mapping_path.is_file():
            return False

        mapping_path.rename(hidden_path)
        self._firewall_active = True
        return True

    def deactivate_firewall(self) -> bool:
        """Restore business_mapping.json after Atom Smith completes.

        Returns True if firewall was deactivated, False if nothing to restore.
        """
        hidden_path = self.workflow_dir / ".business_mapping.json.firewalled"
        mapping_path = self.workflow_dir / "business_mapping.json"

        if not hidden_path.is_file():
            self._firewall_active = False
            return False

        hidden_path.rename(mapping_path)
        self._firewall_active = False
        return True

    @property
    def firewall_active(self) -> bool:
        return self._firewall_active

    def get_phase_status(self) -> dict:
        """Check which artifacts exist to determine current progress."""
        artifacts = {
            "pipeline_graph": self.workflow_dir / "pipeline_graph.yaml",
            "logical_graph": self.workflow_dir / "logical_graph.yaml",
            "business_mapping": self.workflow_dir / "business_mapping.json",
            "atomic_operations": self.workflow_dir / "atomic_operations.yaml",
            "match_results": self.workflow_dir / "match_results.yaml",
            "manifest": self.pipeline_dir / "manifest.yaml",
            "config": self.pipeline_dir / "config.json",
        }

        status = {}
        for name, path in artifacts.items():
            status[name] = path.is_file()

        # Determine current phase
        if not status["pipeline_graph"]:
            status["current_phase"] = 0
        elif not status["logical_graph"] or not status["business_mapping"]:
            status["current_phase"] = 2
        elif not status["atomic_operations"]:
            status["current_phase"] = 3
        elif not status["match_results"]:
            status["current_phase"] = 4
        elif not status["manifest"] or not status["config"]:
            status["current_phase"] = 6
        else:
            status["current_phase"] = 7

        return status

    def read_artifact(self, name: str) -> dict | list | None:
        """Read a workflow artifact by name. Returns parsed content or None."""
        paths = {
            "pipeline_graph": self.workflow_dir / "pipeline_graph.yaml",
            "logical_graph": self.workflow_dir / "logical_graph.yaml",
            "business_mapping": self.workflow_dir / "business_mapping.json",
            "atomic_operations": self.workflow_dir / "atomic_operations.yaml",
            "match_results": self.workflow_dir / "match_results.yaml",
            "manifest": self.pipeline_dir / "manifest.yaml",
            "config": self.pipeline_dir / "config.json",
        }

        path = paths.get(name)
        if not path or not path.is_file():
            return None

        with open(path) as f:
            if path.suffix == ".json":
                return json.load(f)
            return yaml.safe_load(f)

    def build_agent_context(self, agent_role: str) -> dict:
        """Build the context/file list for a specific agent role.

        Returns a dict with:
        - system_prompt: path to the agent's system prompt
        - readable_files: list of files the agent may read
        - writable_paths: list of paths the agent may write to
        - phase_playbooks: list of relevant phase playbook paths
        """
        agents_dir = self._find_agents_dir()
        workflow_dir_scaffold = self._find_scaffold_workflow_dir()

        contexts = {
            "business_analyst": {
                "system_prompt": agents_dir / "BUSINESS_ANALYST_SYSTEM_PROMPT.md",
                "readable_files": [
                    workflow_dir_scaffold / "LAYERS.md",
                    workflow_dir_scaffold / "phase_0_dejargon.md",
                    workflow_dir_scaffold / "phase_1_graph.md",
                    workflow_dir_scaffold / "templates" / "pipeline_graph.yaml",
                    self.ba_session_path,
                ],
                "writable_paths": [
                    self.workflow_dir / "pipeline_graph.yaml",
                    self.ba_questions_path,
                ],
            },
            "separator": {
                "system_prompt": agents_dir / "SEPARATOR_SYSTEM_PROMPT.md",
                "readable_files": [
                    self.workflow_dir / "pipeline_graph.yaml",
                    workflow_dir_scaffold / "phase_2_separation.md",
                    workflow_dir_scaffold / "phase_3_atomize.md",
                    workflow_dir_scaffold / "templates" / "logical_graph.yaml",
                    workflow_dir_scaffold / "templates" / "business_mapping.json",
                    workflow_dir_scaffold / "templates" / "atomic_operations.yaml",
                ],
                "writable_paths": [
                    self.workflow_dir / "logical_graph.yaml",
                    self.workflow_dir / "business_mapping.json",
                    self.workflow_dir / "atomic_operations.yaml",
                ],
            },
            "atom_smith": {
                "system_prompt": agents_dir / "ATOM_SMITH_SYSTEM_PROMPT.md",
                "readable_files": [
                    self.workflow_dir / "atomic_operations.yaml",
                    workflow_dir_scaffold / "phase_4_match.md",
                    workflow_dir_scaffold / "phase_5_create.md",
                    workflow_dir_scaffold / "templates" / "match_results.yaml",
                ],
                "writable_paths": [
                    self.workflow_dir / "match_results.yaml",
                    self.project_root / "atoms",
                    self.project_root / "tests",
                ],
            },
            "assembler": {
                "system_prompt": agents_dir / "ASSEMBLER_SYSTEM_PROMPT.md",
                "readable_files": [
                    self.workflow_dir / "match_results.yaml",
                    self.workflow_dir / "business_mapping.json",
                    self.workflow_dir / "atomic_operations.yaml",
                    self.workflow_dir / "pipeline_graph.yaml",
                    workflow_dir_scaffold / "phase_6_assemble.md",
                    workflow_dir_scaffold / "phase_7_rehydrate.md",
                ],
                "writable_paths": [
                    self.pipeline_dir / "manifest.yaml",
                    self.pipeline_dir / "config.json",
                ],
            },
        }

        if agent_role not in contexts:
            raise ValueError(
                f"Unknown agent role: {agent_role}. "
                f"Must be one of: {list(contexts.keys())}"
            )

        return contexts[agent_role]

    def validate_pipeline_complete(self) -> tuple[bool, str]:
        """Final validation: run gate 6 and check etlai sync passes."""
        gate_result = self.run_gate(6)
        if not gate_result:
            return False, f"Gate 6 FAIL:\n{gate_result.error_summary()}"

        sync_result = subprocess.run(
            [sys.executable, "-m", "etlai.cli", "sync"],
            capture_output=True,
            text=True,
            cwd=str(self.project_root),
        )

        if sync_result.returncode != 0:
            return False, f"etlai sync FAIL:\n{sync_result.stdout}\n{sync_result.stderr}"

        return True, f"Pipeline '{self.pipeline_name}' created successfully."

    def _parse_gate_errors(self, output: str) -> list[str]:
        """Extract error messages from gate validator output."""
        errors = []
        for line in output.splitlines():
            stripped = line.strip()
            if stripped.startswith("- "):
                errors.append(stripped[2:])
            elif stripped.startswith("ERROR:"):
                errors.append(stripped[6:].strip())
        return errors

    def _find_agents_dir(self) -> Path:
        """Locate agent system prompts."""
        project_agents = self.project_root / "agents"
        if project_agents.is_dir():
            return project_agents

        from etlai import __file__ as pkg_init
        return Path(pkg_init).parent / "scaffold" / "agents"

    def _find_scaffold_workflow_dir(self) -> Path:
        """Locate workflow playbooks and templates."""
        project_workflow = self.project_root / "workflow"
        if project_workflow.is_dir():
            return project_workflow

        from etlai import __file__ as pkg_init
        return Path(pkg_init).parent / "scaffold" / "workflow"


def sanitize_pipeline_name(user_request: str) -> str:
    """Generate a valid pipeline name from user's request text."""
    import re
    words = re.findall(r"[a-z]+", user_request.lower())
    stop_words = {"a", "an", "the", "is", "are", "was", "were", "be", "been",
                  "being", "have", "has", "had", "do", "does", "did", "will",
                  "would", "could", "should", "may", "might", "shall", "can",
                  "me", "my", "i", "we", "our", "you", "your", "it", "its",
                  "that", "this", "these", "those", "with", "from", "for",
                  "and", "or", "but", "in", "on", "at", "to", "of", "by",
                  "want", "need", "build", "create", "make", "get", "let"}
    meaningful = [w for w in words if w not in stop_words and len(w) > 2]
    name = "_".join(meaningful[:5])
    return name or "new_pipeline"
