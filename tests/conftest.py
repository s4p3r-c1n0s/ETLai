"""Shared pytest fixtures for ETLai tests."""

import pytest
from pathlib import Path


@pytest.fixture
def tmp_project(tmp_path):
    """Create a minimal ETLai project structure."""
    pipelines = tmp_path / "pipelines"
    pipelines.mkdir()

    etlai_yaml = tmp_path / "etlai.yaml"
    etlai_yaml.write_text("pipelines_root: ./pipelines\n")

    return tmp_path


@pytest.fixture
def sample_csv(tmp_path):
    """Create a sample CSV file with user data."""
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("id,name,age\n1,Alice,30\n2,Bob,25\n3,Charlie,35\n")
    return csv_path


@pytest.fixture
def sample_users_csv(tmp_path):
    """Create a sample users CSV for join tests."""
    csv_path = tmp_path / "users.csv"
    csv_path.write_text("id,name,email\n1,Alice,alice@example.com\n2,Bob,bob@example.com\n3,Charlie,charlie@example.com\n")
    return csv_path


@pytest.fixture
def sample_roles_csv(tmp_path):
    """Create a sample roles CSV for join tests."""
    csv_path = tmp_path / "roles.csv"
    csv_path.write_text("user_id,role\n1,Admin\n2,User\n1,Editor\n")
    return csv_path


@pytest.fixture
def mock_env_file(tmp_path):
    """Create a mock .env file."""
    env_path = tmp_path / "test.env"
    env_path.write_text("API_KEY=test_key_123\nAPI_URL=https://api.test.com\n")
    return env_path


@pytest.fixture
def sample_manifest(tmp_path):
    """Create a sample single-atom manifest."""
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text("""name: test_pipeline
atom: vlookup
min_files: 2
""")
    return manifest_path


@pytest.fixture
def sample_composite_manifest(tmp_path):
    """Create a sample composite manifest."""
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text("""name: test_composite
min_files: 2
steps:
  - atom: vlookup
  - atom: groupby
""")
    return manifest_path
