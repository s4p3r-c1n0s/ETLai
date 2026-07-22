"""Tests for ETLai atoms."""

import json
import pandas as pd
import pytest
from pathlib import Path


class TestVlookup:
    """Tests for vlookup atom."""

    def test_basic_join(self, tmp_path):
        """Test basic left join between two CSVs."""
        from etlai.atoms.vlookup import execute

        # Create test data
        left_csv = tmp_path / "users.csv"
        right_csv = tmp_path / "roles.csv"
        output_csv = tmp_path / "output.csv"

        left_csv.write_text("id,name\n1,Alice\n2,Bob\n3,Charlie\n")
        right_csv.write_text("id,role\n1,Admin\n2,User\n")

        params = {
            "left_file": str(left_csv),
            "right_file": str(right_csv),
            "left_column": "id",
            "right_column": "id",
            "left_output_columns": ["name"],
            "right_output_columns": ["role"],
            "target_path": str(output_csv)
        }

        result_json = execute(json.dumps(params))
        result = json.loads(result_json)

        assert result["success"] is True
        assert "joined" in result["message"].lower()
        assert output_csv.exists()

        # Verify output
        df = pd.read_csv(output_csv)
        assert list(df.columns) == ["name", "role"]
        assert len(df) == 3
        assert df.iloc[0]["name"] == "Alice"
        assert df.iloc[0]["role"] == "Admin"
        assert pd.isna(df.iloc[2]["role"])  # Charlie has no role

    def test_missing_file(self, tmp_path):
        """Test error handling when input file is missing."""
        from etlai.atoms.vlookup import execute

        output_csv = tmp_path / "output.csv"
        params = {
            "left_file": "/nonexistent/left.csv",
            "right_file": "/nonexistent/right.csv",
            "left_column": "id",
            "right_column": "id",
            "left_output_columns": [],
            "right_output_columns": [],
            "target_path": str(output_csv)
        }

        result_json = execute(json.dumps(params))
        result = json.loads(result_json)

        assert result["success"] is False
        assert "message" in result

    def test_missing_column(self, tmp_path):
        """Test error when join column doesn't exist."""
        from etlai.atoms.vlookup import execute

        left_csv = tmp_path / "left.csv"
        right_csv = tmp_path / "right.csv"
        output_csv = tmp_path / "output.csv"

        left_csv.write_text("id,name\n1,Alice\n")
        right_csv.write_text("user_id,role\n1,Admin\n")

        params = {
            "left_file": str(left_csv),
            "right_file": str(right_csv),
            "left_column": "id",
            "right_column": "id",  # doesn't exist in right
            "left_output_columns": ["name"],
            "right_output_columns": ["role"],
            "target_path": str(output_csv)
        }

        result_json = execute(json.dumps(params))
        result = json.loads(result_json)

        assert result["success"] is False
        assert "column" in result["message"].lower()


class TestGroupby:
    """Tests for groupby atom."""

    def test_basic_groupby(self, tmp_path):
        """Test basic group by operation."""
        from etlai.atoms.groupby import execute

        input_csv = tmp_path / "input.csv"
        output_csv = tmp_path / "output.csv"

        input_csv.write_text("name,religion\nAlice,Christian\nBob,Muslim\nCharlie,Christian\n")

        params = {
            "input_file": str(input_csv),
            "group_column": "religion",
            "target_path": str(output_csv)
        }

        result_json = execute(json.dumps(params))
        result = json.loads(result_json)

        assert result["success"] is True
        assert output_csv.exists()

        # Verify output
        df = pd.read_csv(output_csv)
        assert list(df.columns) == ["religion", "count"]
        assert len(df) == 2
        assert df[df["religion"] == "Christian"]["count"].iloc[0] == 2
        assert df[df["religion"] == "Muslim"]["count"].iloc[0] == 1

    def test_invalid_column(self, tmp_path):
        """Test error when grouping column doesn't exist."""
        from etlai.atoms.groupby import execute

        input_csv = tmp_path / "input.csv"
        output_csv = tmp_path / "output.csv"

        input_csv.write_text("name,age\nAlice,30\n")

        params = {
            "input_file": str(input_csv),
            "group_column": "religion",  # doesn't exist
            "target_path": str(output_csv)
        }

        result_json = execute(json.dumps(params))
        result = json.loads(result_json)

        assert result["success"] is False


class TestMockGenerate:
    """Tests for mock_generate atom."""

    def test_basic_generation(self, tmp_path):
        """Test basic synthetic data generation."""
        from etlai.atoms.mock_generate import execute

        input_csv = tmp_path / "template.csv"
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        input_csv.write_text("name,email,age\n")

        params = {
            "input_files": [str(input_csv)],
            "target_path": str(output_dir) + "/",
            "rows": 10
        }

        result_json = execute(json.dumps(params))
        result = json.loads(result_json)

        assert result["success"] is True

        # Verify output file exists and has correct number of rows
        output_files = list(output_dir.glob("*.csv"))
        assert len(output_files) == 1

        df = pd.read_csv(output_files[0])
        assert len(df) == 10
        assert list(df.columns) == ["name", "email", "age"]

    def test_empty_input(self, tmp_path):
        """Test with empty input file."""
        from etlai.atoms.mock_generate import execute

        input_csv = tmp_path / "template.csv"
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        input_csv.write_text("")

        params = {
            "input_files": [str(input_csv)],
            "target_path": str(output_dir) + "/",
            "rows": 5
        }

        result_json = execute(json.dumps(params))
        result = json.loads(result_json)

        # Should fail or handle gracefully
        assert "success" in result


class TestApiFetch:
    """Tests for api_fetch atom."""

    def test_missing_env_var(self, tmp_path):
        """Test error handling when env var is missing."""
        from etlai.atoms.api_fetch import execute
        import os

        # Make sure the var doesn't exist
        os.environ.pop("NONEXISTENT_VAR", None)

        output_csv = tmp_path / "output.csv"
        params = {
            "endpoint": "https://api.example.com/data",
            "headers": {"Authorization": "Bearer ${NONEXISTENT_VAR}"},
            "response_format": "json",
            "target_path": str(output_csv)
        }

        result_json = execute(json.dumps(params))
        result = json.loads(result_json)

        assert result["success"] is False
        assert "env" in result["message"].lower() or "unresolved" in result["message"].lower()

    def test_env_var_resolution(self, tmp_path):
        """Test that env vars are resolved in headers."""
        from etlai.atoms.api_fetch import _resolve_env_vars
        import os

        os.environ["TEST_TOKEN"] = "secret123"

        headers = {"Authorization": "Bearer ${TEST_TOKEN}"}
        resolved = _resolve_env_vars(headers)

        assert resolved["Authorization"] == "Bearer secret123"

        # Cleanup
        del os.environ["TEST_TOKEN"]
