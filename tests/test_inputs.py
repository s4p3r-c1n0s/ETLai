"""Tests for the inputs: manifest field — validation, README generation, and min_files auto-calc."""

import fnmatch
from pathlib import Path

from etlai.cli import _validate_inputs, _validate_references, _generate_pipeline_readme


class TestValidateInputs:
    """Tests for _validate_inputs()."""

    def test_valid_inputs_no_errors(self, tmp_path):
        inputs_def = [
            {"name": "sales", "role": "transient", "description": "Weekly sales"},
        ]
        errors = []
        _validate_inputs(inputs_def, "test_pipe", tmp_path, errors)
        assert errors == []

    def test_missing_name_field(self, tmp_path):
        inputs_def = [{"role": "transient", "description": "No name"}]
        errors = []
        _validate_inputs(inputs_def, "test_pipe", tmp_path, errors)
        assert len(errors) == 1
        assert "missing required 'name'" in errors[0]

    def test_invalid_role(self, tmp_path):
        inputs_def = [{"name": "sales", "role": "permanent", "description": "Bad role"}]
        errors = []
        _validate_inputs(inputs_def, "test_pipe", tmp_path, errors)
        assert len(errors) == 1
        assert "invalid role" in errors[0]

    def test_missing_description(self, tmp_path):
        inputs_def = [{"name": "sales", "role": "transient"}]
        errors = []
        _validate_inputs(inputs_def, "test_pipe", tmp_path, errors)
        assert len(errors) == 1
        assert "missing required 'description'" in errors[0]

    def test_reference_warns_when_no_matching_file(self, tmp_path, capsys):
        ref_dir = tmp_path / "reference"
        ref_dir.mkdir()
        (ref_dir / "other.csv").write_text("x\n1")

        manifest = {
            "steps": [{"atom": "vlookup", "inputs_map": [
                {"param": "left_file"},
                {"param": "right_file", "source": "reference", "pattern": "catalog_*.csv"},
            ]}],
        }
        _validate_references(manifest, "test_pipe", tmp_path)
        assert "no files matching" in capsys.readouterr().out

    def test_reference_warns_when_folder_missing(self, tmp_path, capsys):
        manifest = {
            "steps": [{"atom": "vlookup", "inputs_map": [
                {"param": "right_file", "source": "reference", "pattern": "catalog.csv"},
            ]}],
        }
        _validate_references(manifest, "test_pipe", tmp_path)
        assert "does not exist" in capsys.readouterr().out

    def test_transient_pattern_reports_matches(self, tmp_path, capsys):
        inbox = tmp_path / "inbox"
        inbox.mkdir()
        (inbox / "sales_2026.csv").write_text("x\n1")

        inputs_def = [{"name": "sales", "role": "transient", "description": "Sales", "pattern": "sales_*.csv"}]
        errors = []
        _validate_inputs(inputs_def, "test_pipe", tmp_path, errors)
        assert errors == []
        assert "1 file(s) in inbox" in capsys.readouterr().out


class TestGeneratePipelineReadme:
    """Tests for _generate_pipeline_readme()."""

    def test_generates_readme_file(self, tmp_path):
        manifest = {
            "name": "weekly_report",
            "steps": [
                {"atom": "vlookup", "inputs_map": [
                    {"param": "left_file"},
                    {"param": "right_file", "source": "reference", "pattern": "catalog.csv", "description": "Product catalog"},
                ]},
                {"atom": "groupby", "inputs_map": [{"param": "input_file", "source": "prev_output"}]},
            ],
        }
        inputs_def = [
            {"name": "sales", "role": "transient", "description": "Weekly sales CSV", "pattern": "sales_*.csv"},
        ]
        _generate_pipeline_readme(manifest, inputs_def, tmp_path)

        readme = tmp_path / "PIPELINE_README.md"
        assert readme.exists()
        content = readme.read_text()

        assert "# weekly_report" in content
        assert "vlookup -> groupby" in content
        assert "| sales |" in content
        assert "`inbox/`" in content
        assert "| right_file |" in content
        assert "`reference/`" in content

    def test_readme_contains_workflow_steps(self, tmp_path):
        manifest = {
            "name": "pipe",
            "steps": [{"atom": "vlookup", "inputs_map": [
                {"param": "left_file"},
                {"param": "right_file", "source": "reference", "pattern": "lookup.csv"},
            ]}],
        }
        inputs_def = [
            {"name": "data", "role": "transient", "description": "Input data"},
        ]
        _generate_pipeline_readme(manifest, inputs_def, tmp_path)
        content = (tmp_path / "PIPELINE_README.md").read_text()

        assert "Place reference files" in content
        assert "Drop transient files" in content
        assert "Pipeline triggers automatically" in content
        assert "Results appear in `output/`" in content

    def test_readme_single_atom_pipeline(self, tmp_path):
        manifest = {"name": "simple", "atom": "vlookup"}
        inputs_def = [{"name": "data", "role": "transient", "description": "CSV file"}]
        _generate_pipeline_readme(manifest, inputs_def, tmp_path)
        content = (tmp_path / "PIPELINE_README.md").read_text()

        assert "**Processing:** vlookup" in content

    def test_readme_overwrites_existing(self, tmp_path):
        readme = tmp_path / "PIPELINE_README.md"
        readme.write_text("old content")

        manifest = {"name": "pipe", "atom": "vlookup"}
        inputs_def = [{"name": "x", "role": "transient", "description": "desc"}]
        _generate_pipeline_readme(manifest, inputs_def, tmp_path)

        assert "old content" not in readme.read_text()
        assert "# pipe" in readme.read_text()


class TestMinFilesAutoCalc:
    """Tests for auto-calculating min_files from transient inputs."""

    def test_transient_count_determines_min_files(self):
        inputs_def = [
            {"name": "a", "role": "transient", "description": "x"},
            {"name": "b", "role": "transient", "description": "y"},
            {"name": "c", "role": "reference", "description": "z"},
        ]
        transient_count = sum(1 for inp in inputs_def if inp.get("role") == "transient")
        assert transient_count == 2

    def test_all_reference_means_zero_transient(self):
        inputs_def = [
            {"name": "a", "role": "reference", "description": "x"},
            {"name": "b", "role": "reference", "description": "y"},
        ]
        transient_count = sum(1 for inp in inputs_def if inp.get("role") == "transient")
        assert transient_count == 0
