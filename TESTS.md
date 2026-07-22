# Testing Guide

## Overview

ETLai uses **pytest** for testing. Tests are organized by component and use temporary directories for file I/O isolation.

## Running tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage report
pytest --cov=etlai --cov-report=html --cov-report=term

# Run specific test file
pytest tests/test_atoms.py

# Run specific test
pytest tests/test_atoms.py::test_vlookup_basic

# Run with verbose output
pytest -v

# Run and stop on first failure
pytest -x

# Run tests matching a keyword
pytest -k "vlookup"
```

## Test structure

```
tests/
├── conftest.py              # Shared fixtures
├── test_atoms.py            # Atom contract tests
├── test_forms.py            # Form contract tests
├── test_registry.py         # Manifest loading and job building
├── test_helpers.py          # Folder, config, env helpers
├── test_sensors.py          # Trigger building
├── test_cli.py              # CLI command tests
└── fixtures/                # Sample manifests, CSVs, configs
    ├── sample_users.csv
    ├── sample_roles.csv
    └── manifests/
        ├── single_atom.yaml
        └── composite.yaml
```

## Test conventions

### 1. Atom tests

**Contract:** `execute(params_json: str) -> str` returning `{"success": bool, "message": str, ...}`

**Rules:**
- Use temporary directories for all file I/O
- Test both success and failure paths
- Verify output file contents, not just success flag
- Test with missing params, invalid file paths, malformed data
- No Dagster dependencies — atoms are pure Python

**Example:**
```python
def test_vlookup_basic(tmp_path):
    left_csv = tmp_path / "users.csv"
    right_csv = tmp_path / "roles.csv"
    output_csv = tmp_path / "output.csv"
    
    # Create test data
    left_csv.write_text("id,name\n1,Alice\n2,Bob")
    right_csv.write_text("id,role\n1,Admin\n2,User")
    
    # Execute atom
    from etlai.atoms.vlookup import execute
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
    
    # Assertions
    assert result["success"] is True
    assert output_csv.exists()
    
    # Verify output contents
    df = pd.read_csv(output_csv)
    assert list(df.columns) == ["name", "role"]
    assert len(df) == 2
```

### 2. Form tests

**Contract:** `configure(file_paths: list[str], existing_config: dict | None) -> dict`

**Rules:**
- Test with existing_config=None (first run)
- Test with existing_config present (subsequent run)
- Test with empty dict as existing_config (not None)
- Mock Tkinter UI interactions where needed
- Verify returned dict matches atom param expectations

**Example:**
```python
def test_passthrough_with_existing_config():
    from etlai.forms.passthrough import configure
    
    existing = {"group_column": "religion"}
    result = configure([], existing)
    
    assert result == existing

def test_passthrough_without_config_raises():
    from etlai.forms.passthrough import configure
    
    with pytest.raises(RuntimeError, match="No config.json found"):
        configure([], None)
```

### 3. Registry tests

**Rules:**
- Test manifest loading (valid, invalid, missing)
- Test single vs composite job building
- Test trigger building (sensors, schedules)
- Mock Dagster primitives to avoid runtime dependencies
- Use fixture manifests from `tests/fixtures/`

**Example:**
```python
def test_load_manifest(tmp_path):
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text("""
name: test_pipeline
atom: vlookup
form: passthrough
min_files: 2
""")
    
    from etlai.registry import _load_manifest
    manifest = _load_manifest(manifest_path)
    
    assert manifest["name"] == "test_pipeline"
    assert manifest["atom"] == "vlookup"
    assert manifest["min_files"] == 2
```

### 4. Helper tests

**Rules:**
- Test PipelineFolders: creation, listing, moving files
- Test config_store: load, save, exists
- Test env_loader: loading env files, validation, variable resolution
- Use tmp_path fixture for all file operations

### 5. Integration tests

**Rules:**
- Test end-to-end: manifest → job build → trigger build
- Test full pipeline execution (optional, requires Dagster runtime)
- Test CLI commands with temporary project directories
- Mark with `@pytest.mark.integration` for optional execution

## Fixtures (tests/conftest.py)

```python
import pytest
import tempfile
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
    """Create a sample CSV file."""
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("id,name,age\n1,Alice,30\n2,Bob,25\n3,Charlie,35\n")
    return csv_path

@pytest.fixture
def mock_env_file(tmp_path):
    """Create a mock .env file."""
    env_path = tmp_path / "test.env"
    env_path.write_text("API_KEY=test_key_123\nAPI_URL=https://api.test.com\n")
    return env_path
```

## Coverage goals

- **Atoms**: 90%+ coverage (pure functions, easy to test)
- **Forms**: 70%+ (Tkinter UI harder to test, focus on passthrough and logic)
- **Registry**: 85%+ (critical path, no UI)
- **Helpers**: 90%+ (pure utility functions)
- **CLI**: 60%+ (integration-style, harder to isolate)
- **Overall**: 80%+ coverage

## Testing checklist for new features

When adding a new atom, form, or helper:

- [ ] Unit tests for success path
- [ ] Unit tests for failure paths (missing params, invalid data)
- [ ] Test with edge cases (empty files, large files, unicode)
- [ ] Test error messages are clear and actionable
- [ ] Update TESTS.md if introducing new test patterns
- [ ] Run `pytest --cov` and verify coverage doesn't drop

## Continuous Integration

Once tests are in place:

```yaml
# .github/workflows/test.yml (future)
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install -e ".[dev]"
      - run: pytest --cov=etlai --cov-report=xml
      - uses: codecov/codecov-action@v3
```

## Current test status

| Component | Tests | Coverage | Status |
|-----------|-------|----------|--------|
| Atoms | ⬜ | 0% | TODO |
| Forms | ⬜ | 0% | TODO |
| Registry | ⬜ | 0% | TODO |
| Helpers | ⬜ | 0% | TODO |
| Sensors | ⬜ | 0% | TODO |
| CLI | ⬜ | 0% | TODO |

---

## Phase 1: Basic atom tests (start here)

Create `tests/test_atoms.py` with tests for:
1. vlookup - basic join, missing columns, file not found
2. groupby - basic group, invalid column
3. mock_generate - basic generation, empty input
4. api_fetch - basic fetch (mock HTTP), missing env var

Then expand to other components.
