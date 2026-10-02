"""Tests for ETLai registry."""

import json

import pytest


class TestManifestLoading:
    """Tests for manifest loading."""

    def test_load_valid_manifest(self, sample_manifest):
        """Test loading a valid manifest."""
        from etlai.registry import _load_manifest

        manifest = _load_manifest(sample_manifest)

        assert manifest is not None
        assert manifest["name"] == "test_pipeline"
        assert manifest["atom"] == "vlookup"
        assert manifest["min_files"] == 2

    def test_load_missing_manifest(self, tmp_path):
        """Test loading non-existent manifest returns None."""
        from etlai.registry import _load_manifest

        manifest = _load_manifest(tmp_path / "nonexistent.yaml")

        assert manifest is None

    def test_load_composite_manifest(self, sample_composite_manifest):
        """Test loading a composite manifest."""
        from etlai.registry import _load_manifest

        manifest = _load_manifest(sample_composite_manifest)

        assert manifest is not None
        assert manifest["name"] == "test_composite"
        assert "steps" in manifest
        assert len(manifest["steps"]) == 2
        assert manifest["steps"][0]["atom"] == "vlookup"
        assert manifest["steps"][1]["atom"] == "groupby"


class TestAtomResolution:
    """Tests for atom resolution."""

    def test_resolve_shipped_atom(self, tmp_path, monkeypatch):
        """Test resolving a shipped atom from etlai.atoms."""
        from etlai.registry import _resolve_atom

        monkeypatch.chdir(tmp_path)

        # Should resolve to etlai.atoms.vlookup
        atom_module = _resolve_atom("vlookup", tmp_path)

        assert hasattr(atom_module, "execute")
        assert callable(atom_module.execute)

    def test_resolve_user_atom(self, tmp_path, monkeypatch):
        """Test resolving a user-defined atom."""
        from etlai.registry import _resolve_atom

        monkeypatch.chdir(tmp_path)

        # Create user atom
        atoms_dir = tmp_path / "atoms"
        atoms_dir.mkdir()

        custom_atom = atoms_dir / "custom.py"
        custom_atom.write_text("""
def execute(params_json: str) -> str:
    return '{"success": true, "message": "custom atom"}'
""")

        # Should resolve to user atom
        atom_module = _resolve_atom("custom", tmp_path)

        assert hasattr(atom_module, "execute")
        result = atom_module.execute("{}")
        assert "custom atom" in result


class TestStepConfigLoading:
    """Tests for _load_step_config."""

    def test_returns_existing_config(self):
        from etlai.registry import _load_step_config

        config = _load_step_config({"group_column": "religion"})

        assert config == {"group_column": "religion"}

    def test_missing_config_raises(self):
        from etlai.registry import _load_step_config

        with pytest.raises(RuntimeError, match="No config.json"):
            _load_step_config(None)


class TestExecuteStep:
    """Tests for _execute_step."""

    def test_execute_step_with_no_context(self, tmp_path, monkeypatch):
        """context=None should not raise AttributeError."""
        from unittest.mock import MagicMock
        from etlai.registry import _execute_step
        from etlai.helpers.folders import PipelineFolders

        monkeypatch.chdir(tmp_path)

        # Set up pipeline folders
        pipeline_dir = tmp_path / "pipelines" / "test_pipe"
        for d in ["inbox", "staging", "processed", "rejected", "output", "reference"]:
            (pipeline_dir / d).mkdir(parents=True)

        # Create input file
        input_csv = pipeline_dir / "inbox" / "data.csv"
        input_csv.write_text("id,name\n1,Alice\n")

        # Pre-written config.json
        (pipeline_dir / "config.json").write_text(json.dumps({"step_0": {}}))

        # Mock atom that succeeds
        atom_mod = MagicMock()
        atom_mod.execute.return_value = '{"success": true, "message": "done"}'

        folders = PipelineFolders("test_pipe")

        # Should NOT raise AttributeError: 'NoneType' object has no attribute 'get'
        result = _execute_step(
            atom_module=atom_mod,
            folders=folders,
            pipeline_name="test_pipe",
            step_index=0,
            file_paths=[str(input_csv)],
            is_last=True,
            context=None,
            inputs_map=[{"param": "input_file"}],
        )
        assert result is not None

    def test_execute_step_with_context_op_config_none(self, tmp_path, monkeypatch):
        """context.op_config=None should not raise AttributeError."""
        from unittest.mock import MagicMock
        from etlai.registry import _execute_step
        from etlai.helpers.folders import PipelineFolders

        monkeypatch.chdir(tmp_path)

        pipeline_dir = tmp_path / "pipelines" / "test_pipe"
        for d in ["inbox", "staging", "processed", "rejected", "output", "reference"]:
            (pipeline_dir / d).mkdir(parents=True)

        input_csv = pipeline_dir / "inbox" / "data.csv"
        input_csv.write_text("id,name\n1,Alice\n")

        (pipeline_dir / "config.json").write_text(json.dumps({"step_0": {}}))

        atom_mod = MagicMock()
        atom_mod.execute.return_value = '{"success": true, "message": "done"}'

        folders = PipelineFolders("test_pipe")

        # Context with op_config = None (the exact bug scenario)
        mock_context = MagicMock()
        mock_context.op_config = None

        result = _execute_step(
            atom_module=atom_mod,
            folders=folders,
            pipeline_name="test_pipe",
            step_index=0,
            file_paths=[str(input_csv)],
            is_last=True,
            context=mock_context,
            inputs_map=[{"param": "input_file"}],
        )
        assert result is not None

    def test_execute_step_missing_config_rejects(self, tmp_path, monkeypatch):
        """A step with no config.json rejects the files and raises."""
        from unittest.mock import MagicMock
        from etlai.registry import _execute_step
        from etlai.helpers.folders import PipelineFolders

        monkeypatch.chdir(tmp_path)

        pipeline_dir = tmp_path / "pipelines" / "test_pipe"
        for d in ["inbox", "staging", "processed", "rejected", "output", "reference"]:
            (pipeline_dir / d).mkdir(parents=True)

        input_csv = pipeline_dir / "inbox" / "data.csv"
        input_csv.write_text("id,name\n1,Alice\n")

        atom_mod = MagicMock()

        folders = PipelineFolders("test_pipe")

        with pytest.raises(RuntimeError, match="No config.json"):
            _execute_step(
                atom_module=atom_mod,
                folders=folders,
                pipeline_name="test_pipe",
                step_index=0,
                file_paths=[str(input_csv)],
                is_last=True,
                context=None,
                inputs_map=[{"param": "input_file"}],
            )

        # Atom never ran; files were moved to rejected
        atom_mod.execute.assert_not_called()
        assert (pipeline_dir / "rejected" / "data.csv").exists()

    def test_execute_step_injects_reference_via_source(self, tmp_path, monkeypatch):
        """source: reference in inputs_map binds a reference/ file to its param."""
        from unittest.mock import MagicMock
        from etlai.registry import _execute_step
        from etlai.helpers.folders import PipelineFolders

        monkeypatch.chdir(tmp_path)

        pipeline_dir = tmp_path / "pipelines" / "test_pipe"
        for d in ["inbox", "staging", "processed", "rejected", "output", "reference"]:
            (pipeline_dir / d).mkdir(parents=True)

        # Create reference file
        ref_file = pipeline_dir / "reference" / "catalog.csv"
        ref_file.write_text("sku,name\nA,Widget\n")

        # Create inbox file
        input_csv = pipeline_dir / "inbox" / "sales.csv"
        input_csv.write_text("sku,qty\nA,5\n")

        (pipeline_dir / "config.json").write_text(
            json.dumps({"step_0": {"left_column": "sku", "right_column": "sku"}})
        )

        # Atom captures the config it receives
        received_config = {}

        def mock_execute(params_json):
            received_config.update(json.loads(params_json))
            return '{"success": true, "message": "done"}'

        atom_mod = MagicMock()
        atom_mod.execute.side_effect = mock_execute

        folders = PipelineFolders("test_pipe")

        _execute_step(
            atom_module=atom_mod,
            folders=folders,
            pipeline_name="test_pipe",
            step_index=0,
            file_paths=[str(input_csv)],
            is_last=True,
            context=None,
            inputs_map=[
                {"param": "left_file"},
                {"param": "right_file", "source": "reference", "pattern": "catalog.csv"},
            ],
        )

        # left bound from inbox, right bound from reference/
        assert received_config["left_file"].endswith("sales.csv")
        assert received_config["right_file"].endswith("catalog.csv")

    def test_execute_step_reference_no_match_leaves_param_unset(self, tmp_path, monkeypatch):
        """A source: reference pattern that matches nothing leaves its param unset."""
        from unittest.mock import MagicMock
        from etlai.registry import _execute_step
        from etlai.helpers.folders import PipelineFolders

        monkeypatch.chdir(tmp_path)

        pipeline_dir = tmp_path / "pipelines" / "test_pipe"
        for d in ["inbox", "staging", "processed", "rejected", "output", "reference"]:
            (pipeline_dir / d).mkdir(parents=True)

        ref_file = pipeline_dir / "reference" / "other.csv"
        ref_file.write_text("sku,name\nA,Widget\n")

        input_csv = pipeline_dir / "inbox" / "data.csv"
        input_csv.write_text("sku,qty\nA,5\n")

        (pipeline_dir / "config.json").write_text(json.dumps({"step_0": {"left_column": "sku"}}))

        received_config = {}

        def mock_execute(params_json):
            received_config.update(json.loads(params_json))
            return '{"success": true, "message": "done"}'

        atom_mod = MagicMock()
        atom_mod.execute.side_effect = mock_execute

        folders = PipelineFolders("test_pipe")

        _execute_step(
            atom_module=atom_mod,
            folders=folders,
            pipeline_name="test_pipe",
            step_index=0,
            file_paths=[str(input_csv)],
            is_last=True,
            context=None,
            inputs_map=[
                {"param": "input_file"},
                {"param": "right_file", "source": "reference", "pattern": "catalog.csv"},
            ],
        )

        # catalog.csv does not exist in reference/, so right_file stays unset
        assert received_config["input_file"].endswith("data.csv")
        assert "right_file" not in received_config


class TestInputFrom:
    """Tests for input_from (non-linear step input routing)."""

    def test_build_composite_job_with_input_from(self, tmp_path, monkeypatch):
        """Composite job with input_from builds without error."""
        from etlai.registry import _build_composite_job

        monkeypatch.chdir(tmp_path)

        # Create pipeline folders
        pipeline_dir = tmp_path / "pipelines" / "branching_pipe"
        for d in ["inbox", "staging", "processed", "rejected", "output", "reference"]:
            (pipeline_dir / d).mkdir(parents=True)

        manifest = {
            "name": "branching_pipe",
            "min_files": 1,
            "steps": [
                {"atom": "computed_column"},
                {"atom": "rename_columns", "name": "detail"},
                {"atom": "group_aggregate", "input_from": 0},
                {"atom": "rename_columns"},
            ],
        }

        job = _build_composite_job(manifest, tmp_path)
        assert job is not None
        assert job.name == "branching_pipe"

    def test_input_from_map_extraction(self):
        """input_from declarations are correctly extracted from steps."""
        steps = [
            {"atom": "vlookup"},
            {"atom": "computed_column"},
            {"atom": "rename_columns", "name": "export"},
            {"atom": "group_aggregate", "input_from": 1},
            {"atom": "rename_columns"},
        ]

        input_from_map = {}
        for i, step in enumerate(steps):
            if "input_from" in step:
                input_from_map[i] = step["input_from"]

        assert input_from_map == {3: 1}

    def test_input_from_not_present_gives_empty_map(self):
        """Linear pipeline (no input_from) gives empty map."""
        steps = [
            {"atom": "vlookup"},
            {"atom": "computed_column"},
            {"atom": "rename_columns"},
        ]

        input_from_map = {}
        for i, step in enumerate(steps):
            if "input_from" in step:
                input_from_map[i] = step["input_from"]

        assert input_from_map == {}


class TestTriggerBuilding:
    """Tests for trigger building."""

    def test_build_inbox_files_sensor(self, tmp_path, monkeypatch):
        """Test building an inbox_files sensor."""
        from etlai.registry import _build_inbox_files_sensor

        monkeypatch.chdir(tmp_path)

        # Create pipeline directory
        pipeline_dir = tmp_path / "pipelines" / "test_pipeline"
        pipeline_dir.mkdir(parents=True)

        manifest = {
            "name": "test_pipeline",
            "min_files": 2
        }

        sensor = _build_inbox_files_sensor(manifest, "test_pipeline")

        assert sensor is not None
        # Sensor is a Dagster @sensor decorated function
        assert callable(sensor)

    def test_build_inbox_files_sensor_with_zero_min_files(self, tmp_path):
        """Test that sensor is None when min_files is 0."""
        from etlai.registry import _build_inbox_files_sensor

        manifest = {
            "name": "api_pipeline",
            "min_files": 0
        }

        sensor = _build_inbox_files_sensor(manifest, "api_pipeline")

        assert sensor is None

    def test_build_schedule_definition(self):
        """Test building a schedule definition."""
        from etlai.registry import _build_schedule_definition
        from dagster import job, op

        # Create a real Dagster job for this test
        @op
        def test_op():
            pass

        @job
        def test_job():
            test_op()

        rule = {"cron": "0 8 * * *"}

        schedule = _build_schedule_definition("test_pipeline", test_job, rule)

        assert schedule is not None
        assert schedule.name == "test_pipeline_schedule"
        assert schedule.cron_schedule == "0 8 * * *"


class TestStep0ConfigRegression:
    """Regression: every step — including step 0 — reads its step_N key."""

    def test_step_0_reads_step_0_key(self, tmp_path, monkeypatch):
        """Step 0 in a composite pipeline uses config.json['step_0'], not flat top-level."""
        from unittest.mock import MagicMock
        from etlai.registry import _execute_step
        from etlai.helpers.folders import PipelineFolders

        monkeypatch.chdir(tmp_path)

        pipeline_dir = tmp_path / "pipelines" / "test_pipe"
        for d in ["inbox", "staging", "processed", "rejected", "output", "reference"]:
            (pipeline_dir / d).mkdir(parents=True)

        config_path = pipeline_dir / "config.json"
        config_path.write_text(json.dumps({
            "step_0": {"left_column": "sku", "right_column": "sku"},
            "step_1": {"expression": "a * b", "output_column": "result"},
        }))

        input_csv = pipeline_dir / "inbox" / "data.csv"
        input_csv.write_text("sku,qty\nA,5\n")

        received_config = {}

        def mock_execute(params_json):
            received_config.update(json.loads(params_json))
            return '{"success": true, "message": "done"}'

        atom_mod = MagicMock()
        atom_mod.execute.side_effect = mock_execute

        folders = PipelineFolders("test_pipe")

        _execute_step(
            atom_module=atom_mod,
            folders=folders,
            pipeline_name="test_pipe",
            step_index=0,
            file_paths=[str(input_csv)],
            is_last=False,
            context=None,
            inputs_map=[{"param": "input_file"}],
        )

        assert received_config["left_column"] == "sku"
        assert received_config["right_column"] == "sku"
        # Must not leak sibling step configs into step 0 params
        assert "step_1" not in received_config


class TestMidPipelineJoinRegression:
    """Regression: mid-pipeline join (step ≥ 1) should set left_file when right_file is injected."""

    def test_step_1_with_reference_sets_left_file(self, tmp_path, monkeypatch):
        """Mid-pipeline join: prev_output → left_file, reference → right_file."""
        from unittest.mock import MagicMock
        from etlai.registry import _execute_step
        from etlai.helpers.folders import PipelineFolders

        monkeypatch.chdir(tmp_path)

        pipeline_dir = tmp_path / "pipelines" / "test_pipe"
        for d in ["inbox", "staging", "processed", "rejected", "output", "reference"]:
            (pipeline_dir / d).mkdir(parents=True)

        ref_file = pipeline_dir / "reference" / "prices.csv"
        ref_file.write_text("sku,price\nA,10\n")

        # Simulate prev_output from step 0
        prev_output_file = pipeline_dir / "output" / "_intermediate_0.csv"
        prev_output_file.write_text("sku,qty\nA,5\n")

        config_path = pipeline_dir / "config.json"
        config_path.write_text(json.dumps({
            "step_0": {"left_column": "sku", "right_column": "sku"},
            "step_1": {"left_column": "sku", "right_column": "sku"},
        }))

        received_config = {}

        def mock_execute(params_json):
            received_config.update(json.loads(params_json))
            return '{"success": true, "message": "done"}'

        atom_mod = MagicMock()
        atom_mod.execute.side_effect = mock_execute

        folders = PipelineFolders("test_pipe")

        _execute_step(
            atom_module=atom_mod,
            folders=folders,
            pipeline_name="test_pipe",
            step_index=1,
            file_paths=[str(prev_output_file)],
            is_last=True,
            prev_output=str(prev_output_file),
            context=None,
            inputs_map=[
                {"param": "left_file", "source": "prev_output"},
                {"param": "right_file", "source": "reference", "pattern": "prices.csv"},
            ],
        )

        # right_file set from reference/, left_file from prev_output
        assert "right_file" in received_config
        assert received_config["right_file"].endswith("prices.csv")
        assert "left_file" in received_config
        assert received_config["left_file"] == str(prev_output_file)
        # input_file should NOT be set when right_file is present
        assert "input_file" not in received_config

    def test_step_1_without_reference_sets_input_file(self, tmp_path, monkeypatch):
        """Normal step ≥ 1 (no reference) sets input_file = prev_output as before."""
        from unittest.mock import MagicMock
        from etlai.registry import _execute_step
        from etlai.helpers.folders import PipelineFolders

        monkeypatch.chdir(tmp_path)

        pipeline_dir = tmp_path / "pipelines" / "test_pipe"
        for d in ["inbox", "staging", "processed", "rejected", "output", "reference"]:
            (pipeline_dir / d).mkdir(parents=True)

        prev_output_file = pipeline_dir / "output" / "_intermediate_0.csv"
        prev_output_file.write_text("sku,qty\nA,5\n")

        config_path = pipeline_dir / "config.json"
        config_path.write_text(json.dumps({
            "step_0": {"left_column": "sku"},
            "step_1": {"expression": "a * b", "output_column": "result"},
        }))

        received_config = {}

        def mock_execute(params_json):
            received_config.update(json.loads(params_json))
            return '{"success": true, "message": "done"}'

        atom_mod = MagicMock()
        atom_mod.execute.side_effect = mock_execute

        folders = PipelineFolders("test_pipe")

        _execute_step(
            atom_module=atom_mod,
            folders=folders,
            pipeline_name="test_pipe",
            step_index=1,
            file_paths=[str(prev_output_file)],
            is_last=True,
            prev_output=str(prev_output_file),
            context=None,
            inputs_map=[{"param": "input_file", "source": "prev_output"}],
        )

        # No reference → input_file = prev_output (normal behavior)
        assert "input_file" in received_config
        assert received_config["input_file"] == str(prev_output_file)
        assert "left_file" not in received_config
        assert "right_file" not in received_config
