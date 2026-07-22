# Contributing to ETLai

## Overview

ETLai is a local, folder-driven Dagster CSV transformation engine. Contributions are welcome for new atoms, forms, helpers, documentation, and tests.

---

## Getting Started

### 1. Clone and setup

```bash
git clone <repo-url>
cd etlai
pip install -e ".[dev]"
```

### 2. Install git hooks

```bash
./scripts/install-hooks.sh
```

This enables:
- Pre-commit tests (all 34 tests must pass)
- Documentation consistency checks
- Automatic git tagging for releases

---

## Development Workflow

### Branch naming

- `feat/<short-description>` — New features
- `fix/<bug-description>` — Bug fixes
- `refactor/<description>` — Code improvements
- `docs/<description>` — Documentation only

Example: `feat/add-sql-atom`, `fix/vlookup-dtype-error`

### Making changes

1. **Create branch:** `git checkout -b feat/your-feature`
2. **Make changes** — Edit code, add tests
3. **Run tests:** `pytest --cov=etlai`
4. **Commit:** Follow [COMMIT_GUIDELINES.md](COMMIT_GUIDELINES.md)
5. **Push:** `git push origin feat/your-feature`

### Commit messages

**Read [COMMIT_GUIDELINES.md](COMMIT_GUIDELINES.md) before committing.**

Quick summary:
- Short title (max 70 chars) with type prefix (feat, fix, refactor, test, docs, ci, chore)
- Bullet points explaining WHY, not what
- **NO AI attribution lines** (never "Co-Authored-By: Claude")

---

## Testing Requirements

### All changes must include tests

- **New atoms:** Add tests in `tests/test_atoms.py` (success + failure paths)
- **New forms:** Add tests in `tests/test_forms.py`
- **New helpers:** Add tests in `tests/test_helpers.py`
- **Bug fixes:** Add regression test demonstrating the bug

### Running tests

```bash
# All tests
pytest

# With coverage
pytest --cov=etlai --cov-report=html

# Single test file
pytest tests/test_atoms.py

# Single test
pytest tests/test_atoms.py::TestVlookup::test_basic_join

# Skip slow/integration tests
pytest -m "not slow and not integration"
```

### Coverage requirements

- **Overall:** 80%+
- **Atoms:** 90%+ (pure functions, easy to test)
- **Forms:** 70%+ (Tkinter UI harder to test)
- **Registry:** 85%+ (critical path)
- **Helpers:** 90%+ (utility functions)

Run `pytest --cov=etlai` to check current coverage.

---

## Code Guidelines

### Atoms

**Contract:** `execute(params_json: str) -> str` returning `{"success": bool, "message": str, ...}`

**Rules:**
- Domain-agnostic (no hardcoded business logic)
- All params come from `params_json` (config.json)
- Read input files, write output to `target_path`
- Return `{"success": False, "message": "..."}` on error
- No Dagster imports (pure Python)

### Forms

**Contract:** `configure(file_paths: list[str], existing_config: dict | None) -> dict`

**Rules:**
- Return `existing_config` immediately if valid (no UI)
- Show Tkinter UI on first run only
- Raise RuntimeError to reject files
- For no-UI pipelines: use `passthrough` form + pre-written config.json

### Documentation

- Update `README.md` if changing user-facing API
- Update `ARCHITECTURE.md` if changing internal design
- Update `TESTS.md` if adding new tests
- Add docstrings to new functions

---

## Pull Request Process

1. **Run tests locally:** `pytest --cov=etlai`
2. **Verify pre-commit hook passes** (will run automatically)
3. **Push branch:** `git push origin feat/your-feature`
4. **Create PR** with:
   - Clear title (same format as commit messages)
   - Summary of changes (bullet points)
   - Test plan (how to verify)
   - Screenshots (if UI changes)

### PR template

```markdown
## Summary
- <what changed and why>
- <what changed and why>

## Test plan
- [ ] Added tests in tests/test_*.py
- [ ] All 34 existing tests pass
- [ ] Manually tested: <describe steps>

## Checklist
- [ ] Followed COMMIT_GUIDELINES.md
- [ ] Added tests for new code
- [ ] Updated documentation
- [ ] No AI attribution in commits
```

---

## Release Process

See [CICD.md](CICD.md) for complete release workflow.

**Quick summary:**
1. Update version in 3 files: `pyproject.toml`, `etlai/__init__.py`, `RELEASE.md`
2. Commit: `release: vX.Y.Z - <summary>`
3. Post-commit hook auto-creates git tag
4. Build: `python -m build`
5. Publish: `python -m twine upload dist/*`

---

## Questions?

- **Tests:** See [TESTS.md](TESTS.md)
- **CI/CD:** See [CICD.md](CICD.md)
- **Commits:** See [COMMIT_GUIDELINES.md](COMMIT_GUIDELINES.md)
- **Architecture:** See [ARCHITECTURE.md](ARCHITECTURE.md)
- **Issues:** Open issue on GitHub

---

## License

MIT License. By contributing, you agree to license your contributions under the same terms.
