"""Tests for the orchestrator module — gate running, firewall, context building."""

import json
from pathlib import Path

import pytest
import yaml

from etlai.orchestrator import GateResult, Orchestrator, sanitize_pipeline_name


@pytest.fixture
def orch(tmp_path):
    """Create an orchestrator with a temp project root."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "etlai.yaml").write_text("pipelines_root: ./pipelines\n")
    (project / "atoms").mkdir()
    (project / "tests").mkdir()
    o = Orchestrator(project_root=project, pipeline_name="test_pipeline")
    return o


class TestInitialize:
    def test_creates_workflow_dir(self, orch):
        result = orch.initialize()
        assert result.is_dir()
        assert result == orch.workflow_dir
        assert orch.pipeline_dir.is_dir()

    def test_idempotent(self, orch):
        orch.initialize()
        orch.initialize()
        assert orch.workflow_dir.is_dir()


class TestFirewall:
    def test_activate_hides_mapping(self, orch):
        orch.initialize()
        mapping_path = orch.workflow_dir / "business_mapping.json"
        mapping_path.write_text('{"columns": []}')

        assert orch.activate_firewall() is True
        assert not mapping_path.exists()
        assert (orch.workflow_dir / ".business_mapping.json.firewalled").exists()
        assert orch.firewall_active is True

    def test_deactivate_restores_mapping(self, orch):
        orch.initialize()
        mapping_path = orch.workflow_dir / "business_mapping.json"
        mapping_path.write_text('{"columns": []}')

        orch.activate_firewall()
        assert orch.deactivate_firewall() is True
        assert mapping_path.exists()
        assert not (orch.workflow_dir / ".business_mapping.json.firewalled").exists()
        assert orch.firewall_active is False

    def test_activate_no_file_returns_false(self, orch):
        orch.initialize()
        assert orch.activate_firewall() is False
        assert orch.firewall_active is False

    def test_deactivate_no_file_returns_false(self, orch):
        orch.initialize()
        assert orch.deactivate_firewall() is False

    def test_content_preserved_through_firewall(self, orch):
        orch.initialize()
        mapping_path = orch.workflow_dir / "business_mapping.json"
        original = {"columns": [{"placeholder": "col_a", "real_name": "revenue"}]}
        mapping_path.write_text(json.dumps(original))

        orch.activate_firewall()
        orch.deactivate_firewall()

        restored = json.loads(mapping_path.read_text())
        assert restored == original


class TestGateResult:
    def test_pass_is_truthy(self):
        r = GateResult(gate_num=1, passed=True, errors=[], raw_output="GATE 1: PASS")
        assert bool(r) is True

    def test_fail_is_falsy(self):
        r = GateResult(gate_num=1, passed=False, errors=["missing field"], raw_output="")
        assert bool(r) is False

    def test_error_summary(self):
        r = GateResult(gate_num=2, passed=False, errors=["err1", "err2"], raw_output="")
        summary = r.error_summary()
        assert "err1" in summary
        assert "err2" in summary


class TestRunGate:
    def test_gate_1_pass_with_valid_graph(self, orch):
        orch.initialize()
        graph = {
            "owner_confirmed": True,
            "name": "test",
            "description": "A test pipeline",
            "data_sources": [{
                "name": "src1",
                "description": "Source one",
                "retrieval": "upload",
                "frequency": "daily",
                "format": "csv",
                "role": "transient",
                "fields": [{"name": "col_a", "type": "string"}],
            }],
            "nodes": [{
                "id": "op_1",
                "operation": "compute a value",
                "description": "Compute something",
                "inputs": ["src1"],
                "outputs": ["result"],
            }],
            "edges": [{"from": "src1", "to": "op_1"}],
            "triggers": [{"type": "inbox_files", "min_files": 1}],
            "outputs": [{
                "name": "result",
                "description": "The output",
                "fields": [{"name": "value", "type": "number"}],
            }],
        }
        graph_path = orch.workflow_dir / "pipeline_graph.yaml"
        with open(graph_path, "w") as f:
            yaml.safe_dump(graph, f)

        result = orch.run_gate(1)
        assert result.passed is True
        assert result.gate_num == 1

    def test_gate_1_fail_missing_file(self, orch):
        orch.initialize()
        result = orch.run_gate(1)
        assert result.passed is False
        assert result.gate_num == 1

    def test_invalid_gate_number_raises(self, orch):
        orch.initialize()
        with pytest.raises(ValueError, match="Invalid gate number"):
            orch.run_gate(7)


class TestPhaseStatus:
    def test_empty_workflow(self, orch):
        orch.initialize()
        status = orch.get_phase_status()
        assert status["current_phase"] == 0
        assert status["pipeline_graph"] is False

    def test_after_phase_1(self, orch):
        orch.initialize()
        (orch.workflow_dir / "pipeline_graph.yaml").write_text("name: test\n")
        status = orch.get_phase_status()
        assert status["pipeline_graph"] is True
        assert status["current_phase"] == 2

    def test_fully_complete(self, orch):
        orch.initialize()
        (orch.workflow_dir / "pipeline_graph.yaml").write_text("name: test\n")
        (orch.workflow_dir / "logical_graph.yaml").write_text("nodes: []\n")
        (orch.workflow_dir / "business_mapping.json").write_text("{}")
        (orch.workflow_dir / "atomic_operations.yaml").write_text("operations: []\n")
        (orch.workflow_dir / "match_results.yaml").write_text("matches: []\n")
        (orch.pipeline_dir / "manifest.yaml").write_text("name: test\n")
        (orch.pipeline_dir / "config.json").write_text("{}")
        status = orch.get_phase_status()
        assert status["current_phase"] == 7


class TestAgentContext:
    def test_business_analyst_context(self, orch):
        orch.initialize()
        ctx = orch.build_agent_context("business_analyst")
        assert "BUSINESS_ANALYST" in ctx["system_prompt"].name
        assert len(ctx["writable_paths"]) == 1

    def test_atom_smith_context_excludes_mapping(self, orch):
        orch.initialize()
        ctx = orch.build_agent_context("atom_smith")
        readable_names = [p.name for p in ctx["readable_files"]]
        assert "business_mapping.json" not in readable_names
        assert "pipeline_graph.yaml" not in readable_names

    def test_assembler_context_includes_mapping(self, orch):
        orch.initialize()
        ctx = orch.build_agent_context("assembler")
        readable_names = [p.name for p in ctx["readable_files"]]
        assert "business_mapping.json" in readable_names
        assert "pipeline_graph.yaml" in readable_names

    def test_invalid_role_raises(self, orch):
        with pytest.raises(ValueError, match="Unknown agent role"):
            orch.build_agent_context("unknown_agent")


class TestSanitizePipelineName:
    def test_basic_request(self):
        name = sanitize_pipeline_name("Build me a sales reconciliation pipeline")
        assert "sales" in name
        assert "reconciliation" in name
        assert "pipeline" in name

    def test_strips_stop_words(self):
        name = sanitize_pipeline_name("I want to create a weekly sales thing")
        assert "want" not in name
        assert "create" not in name
        assert "weekly" in name

    def test_empty_yields_default(self):
        name = sanitize_pipeline_name("a")
        assert name == "new_pipeline"

    def test_limits_length(self):
        name = sanitize_pipeline_name(
            "very long request with many words about building something complex and interesting"
        )
        parts = name.split("_")
        assert len(parts) <= 5


class TestReadArtifact:
    def test_read_yaml(self, orch):
        orch.initialize()
        data = {"name": "test", "steps": []}
        (orch.workflow_dir / "pipeline_graph.yaml").write_text(yaml.safe_dump(data))
        result = orch.read_artifact("pipeline_graph")
        assert result == data

    def test_read_json(self, orch):
        orch.initialize()
        data = {"columns": [{"placeholder": "col_a", "real_name": "sku"}]}
        (orch.workflow_dir / "business_mapping.json").write_text(json.dumps(data))
        result = orch.read_artifact("business_mapping")
        assert result == data

    def test_missing_returns_none(self, orch):
        orch.initialize()
        assert orch.read_artifact("pipeline_graph") is None

    def test_unknown_name_returns_none(self, orch):
        orch.initialize()
        assert orch.read_artifact("nonexistent") is None
