"""Tests for ETLai helper modules."""

import os
import pytest
from pathlib import Path


class TestConfigStore:
    """Tests for config_store helper."""

    def test_save_and_load(self, tmp_path, monkeypatch):
        """Test saving and loading config."""
        from etlai.helpers.config_store import save_config, load_config, config_exists
        from etlai.helpers.folders import PipelineFolders

        # Mock working directory
        monkeypatch.chdir(tmp_path)

        # Create pipeline structure
        pipeline_dir = tmp_path / "pipelines" / "test_pipeline"
        pipeline_dir.mkdir(parents=True)

        folders = PipelineFolders("test_pipeline")
        config = {"group_column": "religion", "target_path": "/tmp/out.csv"}

        # Save
        save_config(folders, config)
        assert config_exists(folders)

        # Load
        loaded = load_config(folders)
        assert loaded == config

    def test_load_missing_config(self, tmp_path, monkeypatch):
        """Test loading non-existent config returns None."""
        from etlai.helpers.config_store import load_config, config_exists
        from etlai.helpers.folders import PipelineFolders

        monkeypatch.chdir(tmp_path)

        pipeline_dir = tmp_path / "pipelines" / "test_pipeline"
        pipeline_dir.mkdir(parents=True)

        folders = PipelineFolders("test_pipeline")

        assert not config_exists(folders)
        assert load_config(folders) is None


class TestEnvLoader:
    """Tests for env_loader helper."""

    def test_load_env_file(self, mock_env_file):
        """Test loading environment variables from file."""
        from etlai.helpers.env_loader import load_env_file

        load_env_file(str(mock_env_file))

        assert os.environ["API_KEY"] == "test_key_123"
        assert os.environ["API_URL"] == "https://api.test.com"

        # Cleanup
        del os.environ["API_KEY"]
        del os.environ["API_URL"]

    def test_load_missing_file(self):
        """Test error when env file doesn't exist."""
        from etlai.helpers.env_loader import load_env_file

        with pytest.raises(FileNotFoundError):
            load_env_file("/nonexistent/path.env")

    def test_validate_env_vars_success(self, mock_env_file):
        """Test validation succeeds when all vars present."""
        from etlai.helpers.env_loader import load_env_file, validate_env_vars

        load_env_file(str(mock_env_file))

        # Should return empty list (no missing vars)
        missing = validate_env_vars(str(mock_env_file), ["API_KEY", "API_URL"])
        assert missing == []

        # Cleanup
        del os.environ["API_KEY"]
        del os.environ["API_URL"]

    def test_validate_env_vars_missing(self, tmp_path):
        """Test validation fails when vars are missing."""
        from etlai.helpers.env_loader import validate_env_vars

        env_file = tmp_path / "empty.env"
        env_file.write_text("")

        missing = validate_env_vars(str(env_file), ["MISSING_VAR"])
        assert "MISSING_VAR" in missing


class TestPipelineFolders:
    """Tests for PipelineFolders helper."""

    def test_folder_structure(self, tmp_path, monkeypatch):
        """Test that folder structure is created correctly."""
        from etlai.helpers.folders import PipelineFolders

        monkeypatch.chdir(tmp_path)

        pipeline_dir = tmp_path / "pipelines" / "test_pipeline"
        pipeline_dir.mkdir(parents=True)

        folders = PipelineFolders("test_pipeline")
        folders.ensure()

        assert Path(folders.inbox).exists()
        assert Path(folders.staging).exists()
        assert Path(folders.processed).exists()
        assert Path(folders.rejected).exists()
        assert Path(folders.output).exists()
        assert Path(folders.reference).exists()

    def test_list_inbox_files(self, tmp_path, monkeypatch):
        """Test listing files in inbox."""
        from etlai.helpers.folders import PipelineFolders
        import re

        monkeypatch.chdir(tmp_path)

        pipeline_dir = tmp_path / "pipelines" / "test_pipeline"
        pipeline_dir.mkdir(parents=True)

        folders = PipelineFolders("test_pipeline")
        folders.ensure()

        # Create test files
        (Path(folders.inbox) / "data1.csv").write_text("test")
        (Path(folders.inbox) / "data2.xlsx").write_text("test")
        (Path(folders.inbox) / "ignored.txt").write_text("test")

        pattern = re.compile(r"^(.+)\.(csv|xlsx)$", re.IGNORECASE)
        files = folders.list_inbox_files(pattern)

        assert len(files) == 2
        assert any("data1.csv" in f for f in files)
        assert any("data2.xlsx" in f for f in files)
        assert not any("ignored.txt" in f for f in files)

    def test_move_to_staging(self, tmp_path, monkeypatch):
        """Test moving files from inbox to staging."""
        from etlai.helpers.folders import PipelineFolders

        monkeypatch.chdir(tmp_path)

        pipeline_dir = tmp_path / "pipelines" / "test_pipeline"
        pipeline_dir.mkdir(parents=True)

        folders = PipelineFolders("test_pipeline")
        folders.ensure()

        # Create test file
        inbox_file = Path(folders.inbox) / "data.csv"
        inbox_file.write_text("test")

        # Move to staging
        staged = folders.move_to_staging([str(inbox_file)])

        assert len(staged) == 1
        assert not inbox_file.exists()
        assert Path(staged[0]).exists()
        assert str(Path(staged[0]).parent) == folders.staging

    def test_move_to_processed(self, tmp_path, monkeypatch):
        """Test moving files to processed folder."""
        from etlai.helpers.folders import PipelineFolders

        monkeypatch.chdir(tmp_path)

        pipeline_dir = tmp_path / "pipelines" / "test_pipeline"
        pipeline_dir.mkdir(parents=True)

        folders = PipelineFolders("test_pipeline")
        folders.ensure()

        # Create test file in staging
        staging_file = Path(folders.staging) / "data.csv"
        staging_file.write_text("test")

        # Move to processed
        folders.move_to_processed([str(staging_file)])

        assert not staging_file.exists()
        assert (Path(folders.processed) / "data.csv").exists()

    def test_move_to_rejected(self, tmp_path, monkeypatch):
        """Test moving files to rejected with error message."""
        from etlai.helpers.folders import PipelineFolders

        monkeypatch.chdir(tmp_path)

        pipeline_dir = tmp_path / "pipelines" / "test_pipeline"
        pipeline_dir.mkdir(parents=True)

        folders = PipelineFolders("test_pipeline")
        folders.ensure()

        # Create test file
        staging_file = Path(folders.staging) / "data.csv"
        staging_file.write_text("test")

        # Move to rejected
        error_msg = "Test error message"
        folders.move_to_rejected([str(staging_file)], error_msg)

        assert not staging_file.exists()
        assert (Path(folders.rejected) / "data.csv").exists()
        assert (Path(folders.rejected) / "data.csv.error.txt").exists()

        error_content = (Path(folders.rejected) / "data.csv.error.txt").read_text()
        assert error_msg in error_content
