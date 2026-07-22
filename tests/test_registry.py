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

        # Create a mock job (just a callable for this test)
        mock_job = lambda: None
        mock_job.__name__ = "test_job"

        rule = {"cron": "0 8 * * *"}

        schedule = _build_schedule_definition("test_pipeline", mock_job, rule)

        assert schedule is not None
        assert schedule.name == "test_pipeline_schedule"
        assert schedule.cron_schedule == "0 8 * * *"
