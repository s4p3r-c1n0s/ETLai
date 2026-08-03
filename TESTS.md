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

# Run all tests in a single test class
pytest tests/test_atoms.py::TestVlookup

# Run one test method from a class
pytest tests/test_atoms.py::TestVlookup::test_basic_join
```

## Test structure

```
tests/
├── conftest.py              # Shared fixtures
├── test_atoms.py            # ✅ Atom contract tests (created)
├── test_forms.py            # ✅ Form contract tests (created)
├── test_registry.py         # ✅ Manifest loading, job building, inject_as, input_from
├── test_helpers.py          # ✅ Folder, config, env helpers (created)
├── test_input_resolver.py   # ✅ InputResolver: fallback heuristic + explicit inputs_map
├── test_orchestrator.py     # ✅ Gate runner, firewall, context building, phase status
├── test_sensors.py          # TODO (partially covered in registry tests)
├── test_cli.py              # TODO (future phase)
├── test_integration.py      # TODO (future phase)
└── fixtures/                # TODO (created dynamically via conftest fixtures)
```

Note: Fixtures are created programmatically via pytest fixtures in conftest.py (tmp_path, sample_csv, etc).
No static fixture files needed.

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

See `tests/conftest.py` for all available fixtures:

- `tmp_project` — Minimal ETLai project with pipelines/ and etlai.yaml
- `sample_csv` — Sample data.csv with id, name, age columns
- `sample_users_csv` — Users CSV for join tests
- `sample_roles_csv` — Roles CSV for join tests
- `mock_env_file` — Mock .env with API_KEY and API_URL
- `sample_manifest` — Single-atom manifest YAML
- `sample_composite_manifest` — Multi-step composite manifest

All use `tmp_path` for isolated, auto-cleaned temporary directories.

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

Tests run automatically via git hooks before every commit. See:
- **[CICD.md](CICD.md)** — Pre-commit hooks, release workflow, git tagging
- **[PUBLISH.md](PUBLISH.md)** — Building and publishing to PyPI

**Quick setup:**
```bash
# Install git hooks
git config core.hooksPath .githooks
chmod +x .githooks/*

# Now pytest runs automatically before each commit
```

## Current test status

| Component | Tests | Goal | Status |
|-----------|-------|------|--------|
| Atoms | ✅ | 90%+ | ✅ Done (vlookup, groupby, mock_generate, api_fetch, computed_column, group_aggregate, filter_rows, flag_rows, rename_columns, sort_rows) |
| Forms | ✅ | 70%+ | ✅ Done (passthrough) |
| Registry | ✅ | 85%+ | ✅ Done (manifest loading, resolution, triggers, execute_step, inject_as, input_from, mid-pipeline joins) |
| Helpers | ✅ | 90%+ | ✅ Done (config_store, env_loader, folders) |
| Inputs | ✅ | 90%+ | ✅ Done (validation, README gen, min_files calc) |
| InputResolver | ✅ | 95%+ | ✅ Done (fallback heuristic, explicit N-file mapping, continuation, pattern ordering) |
| Orchestrator | ✅ | 85%+ | ✅ Done (gate runner, firewall, agent context, phase status, pipeline naming) |
| Sensors | ⬜ | 80%+ | TODO (covered partially in registry tests) |
| CLI | ⬜ | 60%+ | TODO |
| **Overall** | **126 tests** | **80%+** | **✅ Comprehensive coverage** |

Check actual coverage: `pip install -e ".[dev]"` then `pytest --cov=etlai --cov-report=html`

All tests passing. Pre-commit hook validates tests before each commit.

---

## Future work (roadmap, not stale TODOs)

**Phase 2: CLI tests** (when CLI becomes stable)
- `tests/test_cli.py`: etlai init, sync, list, run commands
- Use tmp_project fixture for project creation

**Phase 3: Integration tests** (after Phase 2)
- `tests/test_integration.py`: end-to-end pipelines
- Mark with `@pytest.mark.integration` for optional execution
- Requires Dagster runtime (may be slow)

**Phase 4: Coverage gaps** (ongoing)
- Edge cases: empty files, large files, unicode
- Error paths: missing files, invalid config, bad manifest
- Performance: mark slow tests with `@pytest.mark.slow`

Start Phase 2 when needed. Don't rush — current tests provide solid foundation.
