"""Tests for ETLai registry."""

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
        assert manifest["form"] == "passthrough"
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


class TestFormResolution:
    """Tests for form resolution."""

    def test_resolve_shipped_form(self, tmp_path, monkeypatch):
        """Test resolving a shipped form from etlai.forms."""
        from etlai.registry import _resolve_form

        monkeypatch.chdir(tmp_path)

        # Should resolve to etlai.forms.passthrough
        form_module = _resolve_form("passthrough", tmp_path)

        assert hasattr(form_module, "configure")
        assert callable(form_module.configure)

    def test_resolve_user_form(self, tmp_path, monkeypatch):
        """Test resolving a user-defined form."""
        from etlai.registry import _resolve_form

        monkeypatch.chdir(tmp_path)

        # Create user form
        forms_dir = tmp_path / "forms"
        forms_dir.mkdir()

        custom_form = forms_dir / "custom.py"
        custom_form.write_text("""
def configure(file_paths, existing_config):
    return {"custom": "form"}
""")

        # Should resolve to user form
        form_module = _resolve_form("custom", tmp_path)

        assert hasattr(form_module, "configure")
        result = form_module.configure([], None)
        assert result == {"custom": "form"}


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

        # Mock atom that succeeds
        atom_mod = MagicMock()
        atom_mod.execute.return_value = '{"success": true, "message": "done"}'

        # Mock form that returns config
        form_mod = MagicMock()
        form_mod.configure.return_value = {"input_file": str(input_csv)}

        folders = PipelineFolders("test_pipe")

        # Should NOT raise AttributeError: 'NoneType' object has no attribute 'get'
        result = _execute_step(
            atom_module=atom_mod,
            form_module=form_mod,
            folders=folders,
            pipeline_name="test_pipe",
            step_index=0,
            file_paths=[str(input_csv)],
            is_first=True,
            is_last=True,
            context=None,
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

        atom_mod = MagicMock()
        atom_mod.execute.return_value = '{"success": true, "message": "done"}'

        form_mod = MagicMock()
        form_mod.configure.return_value = {"input_file": str(input_csv)}

        folders = PipelineFolders("test_pipe")

        # Context with op_config = None (the exact bug scenario)
        mock_context = MagicMock()
        mock_context.op_config = None

        result = _execute_step(
            atom_module=atom_mod,
            form_module=form_mod,
            folders=folders,
            pipeline_name="test_pipe",
            step_index=0,
            file_paths=[str(input_csv)],
            is_first=True,
            is_last=True,
            context=mock_context,
        )
        assert result is not None

    def test_execute_step_injects_reference_via_inject_as(self, tmp_path, monkeypatch):
        """inject_as in input_metadata resolves reference file path into config param."""
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

        # Atom captures the config it receives
        received_config = {}

        def mock_execute(params_json):
            import json
            received_config.update(json.loads(params_json))
            return '{"success": true, "message": "done"}'

        atom_mod = MagicMock()
        atom_mod.execute.side_effect = mock_execute

        form_mod = MagicMock()
        form_mod.configure.return_value = {"left_column": "sku", "right_column": "sku"}

        folders = PipelineFolders("test_pipe")

        input_metadata = [
            {"name": "sales", "role": "transient", "description": "Sales data"},
            {
                "name": "catalog",
                "role": "reference",
                "description": "Product catalog",
                "pattern": "catalog.csv",
                "inject_as": {"step": 0, "param": "right_file"},
            },
        ]

        _execute_step(
            atom_module=atom_mod,
            form_module=form_mod,
            folders=folders,
            pipeline_name="test_pipe",
            step_index=0,
            file_paths=[str(input_csv)],
            is_first=True,
            is_last=True,
            context=None,
            input_metadata=input_metadata,
        )

        # The reference file should be injected as "right_file"
        assert "right_file" in received_config
        assert received_config["right_file"].endswith("catalog.csv")

    def test_execute_step_single_transient_with_inject_as_sets_left_file(self, tmp_path, monkeypatch):
        """When inject_as sets right_file and there's 1 transient file, auto-inject sets left_file."""
        from unittest.mock import MagicMock
        from etlai.registry import _execute_step
        from etlai.helpers.folders import PipelineFolders

        monkeypatch.chdir(tmp_path)

        pipeline_dir = tmp_path / "pipelines" / "test_pipe"
        for d in ["inbox", "staging", "processed", "rejected", "output", "reference"]:
            (pipeline_dir / d).mkdir(parents=True)

        ref_file = pipeline_dir / "reference" / "catalog.csv"
        ref_file.write_text("sku,name\nA,Widget\n")

        input_csv = pipeline_dir / "inbox" / "sales.csv"
        input_csv.write_text("sku,qty\nA,5\n")

        received_config = {}

        def mock_execute(params_json):
            import json
            received_config.update(json.loads(params_json))
            return '{"success": true, "message": "done"}'

        atom_mod = MagicMock()
        atom_mod.execute.side_effect = mock_execute

        form_mod = MagicMock()
        form_mod.configure.return_value = {"left_column": "sku", "right_column": "sku"}

        folders = PipelineFolders("test_pipe")

        input_metadata = [
            {"name": "sales", "role": "transient", "description": "Sales data"},
            {
                "name": "catalog",
                "role": "reference",
                "description": "Product catalog",
                "pattern": "catalog.csv",
                "inject_as": {"step": 0, "param": "right_file"},
            },
        ]

        _execute_step(
            atom_module=atom_mod,
            form_module=form_mod,
            folders=folders,
            pipeline_name="test_pipe",
            step_index=0,
            file_paths=[str(input_csv)],
            is_first=True,
            is_last=True,
            context=None,
            input_metadata=input_metadata,
        )

        # right_file from inject_as, left_file from auto-injection (1 transient + right_file present)
        assert "right_file" in received_config
        assert "left_file" in received_config
        assert received_config["left_file"].endswith("sales.csv")
        assert received_config["right_file"].endswith("catalog.csv")

    def test_execute_step_inject_as_skips_wrong_step(self, tmp_path, monkeypatch):
        """inject_as targeting step 1 should not inject into step 0."""
        from unittest.mock import MagicMock
        from etlai.registry import _execute_step
        from etlai.helpers.folders import PipelineFolders

        monkeypatch.chdir(tmp_path)

        pipeline_dir = tmp_path / "pipelines" / "test_pipe"
        for d in ["inbox", "staging", "processed", "rejected", "output", "reference"]:
            (pipeline_dir / d).mkdir(parents=True)

        ref_file = pipeline_dir / "reference" / "supplier.csv"
        ref_file.write_text("sku,cost\nA,10\n")

        input_csv = pipeline_dir / "inbox" / "data.csv"
        input_csv.write_text("sku,qty\nA,5\n")

        received_config = {}

        def mock_execute(params_json):
            import json
            received_config.update(json.loads(params_json))
            return '{"success": true, "message": "done"}'

        atom_mod = MagicMock()
        atom_mod.execute.side_effect = mock_execute

        form_mod = MagicMock()
        form_mod.configure.return_value = {"left_column": "sku"}

        folders = PipelineFolders("test_pipe")

        input_metadata = [
            {
                "name": "supplier",
                "role": "reference",
                "description": "Supplier prices",
                "pattern": "supplier.csv",
                "inject_as": {"step": 1, "param": "right_file"},
            },
        ]

        _execute_step(
            atom_module=atom_mod,
            form_module=form_mod,
            folders=folders,
            pipeline_name="test_pipe",
            step_index=0,
            file_paths=[str(input_csv)],
            is_first=True,
            is_last=True,
            context=None,
            input_metadata=input_metadata,
        )

        # right_file should NOT be injected (targets step 1, we're in step 0)
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
                {"atom": "computed_column", "form": "passthrough"},
                {"atom": "rename_columns", "form": "passthrough", "name": "detail"},
                {"atom": "group_aggregate", "form": "passthrough", "input_from": 0},
                {"atom": "rename_columns", "form": "passthrough"},
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
