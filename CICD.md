# CI/CD Guide

## Quick Setup (Do This First)

```bash
# Install git hooks (one-time setup)
./scripts/install-hooks.sh

# Verify installation
git config core.hooksPath  # Should output: .githooks
```

After setup, **pytest runs automatically before each commit**. All releases are automatically tagged.

## Overview

ETLai uses **git hooks** for local quality gates before commits. This ensures all commits pass tests, documentation is current, and releases are properly tagged and published.

## Hooks Overview

| Hook | Purpose | When it runs |
|------|---------|--------------|
| `pre-commit` | Run tests, check docs | Before every commit |
| `prepare-commit-msg` | Detect release commits | Before commit message is finalized |
| `post-commit` | Verify release tagging | After commit is created |

## Pre-commit Hook

Runs before every commit. Enforces:

1. **All tests pass** — Runs `pytest` on staged changes
2. **Documentation is current** — Checks if README.md, ARCHITECTURE.md need updates
3. **Test documentation updated** — Verifies TESTS.md reflects new test files

### What it checks

```bash
# 1. Run tests
pytest --maxfail=1 --tb=short

# 2. Check for documentation staleness
# - If etlai/ code changed, flag README.md for review
# - If registry.py changed, flag ARCHITECTURE.md
# - If tests/ changed, flag TESTS.md

# 3. Verify staged files are consistent
# - Version in pyproject.toml matches etlai/__init__.py
# - TODO/FIXME in production code (warnings only)
```

### Bypassing the hook

Only when absolutely necessary (e.g., WIP commits on a feature branch):

```bash
git commit --no-verify -m "WIP: work in progress"
```

**Do not** use `--no-verify` for commits to `main` or release branches.

## Release Commit Detection

The `prepare-commit-msg` hook detects release commits by analyzing:

1. **Version bump in pyproject.toml** — Staged changes increment version
2. **RELEASE.md update** — New version entry exists
3. **Commit message pattern** — Matches `release: v*` or `chore: bump version to *`

### Release commit requirements

When the hook detects a release commit, it verifies:

- ✅ Version in `pyproject.toml` matches new RELEASE.md entry
- ✅ Version in `etlai/__init__.py` matches pyproject.toml
- ✅ RELEASE.md has a new section for this version
- ✅ README.md mentions the new version (if user-facing)

If any check fails, the commit is **blocked** with an actionable error message.

### Release commit format

```bash
# Good release commit messages:
git commit -m "release: v0.4.0 - add workflow orchestration"
git commit -m "chore: bump version to 0.4.0"

# Bad (won't be detected as release):
git commit -m "updated version"
git commit -m "release stuff"
```

## Post-commit Hook (Release Tagging)

After a release commit succeeds, the `post-commit` hook:

1. Detects if the commit is a release (checks RELEASE.md changes)
2. Extracts version from `pyproject.toml`
3. Creates an **annotated git tag**: `git tag -a v0.4.0 -m "Release v0.4.0"`
4. Reminds you to push tags: `git push origin --tags`

### Manual tagging (if hook is bypassed)

```bash
# After a release commit:
VERSION=$(grep '^version = ' pyproject.toml | cut -d'"' -f2)
git tag -a "v${VERSION}" -m "Release v${VERSION}"
git push origin --tags
```

## Documentation Consistency Checks

### README.md

**Trigger:** Any change to `etlai/` source files (atoms, forms, helpers, CLI)

**Checks:**
- Version number in README matches `pyproject.toml`
- Installation examples are current
- Feature list reflects shipped atoms/forms/helpers

**Action:** Hook warns and prompts:
```
⚠️  Source code changed but README.md not staged.
   Review README.md for outdated content:
   - Installation instructions
   - Available atoms/forms
   - Usage examples
   
   Stage README.md if updated, or commit with --no-verify if no docs changes needed.
```

### ARCHITECTURE.md

**Trigger:** Changes to `etlai/registry.py`, `etlai/cli.py`, or package structure

**Checks:**
- Registry design documented
- CLI commands documented
- Folder structure diagram current

**Action:** Hook warns similarly to README check.

### TESTS.md

**Trigger:** New test files added in `tests/`

**Checks:**
- Status table in TESTS.md updated
- Coverage column reflects new test count
- New test files listed in "Current test status"

**Action:** Hook **blocks commit** if new test file added but TESTS.md not updated:
```
❌ New test file detected: tests/test_cli.py
   TESTS.md must be updated to reflect new tests.
   
   Update the "Current test status" table and re-stage TESTS.md.
```

## Release Workflow

### Complete release process (step-by-step)

#### 1. Pre-release checks

```bash
# Ensure you're on main and up to date
git checkout main
git pull origin main

# Run full test suite with coverage
pytest --cov=etlai --cov-report=term

# Verify all tests pass
# Verify coverage is acceptable (>80%)
```

#### 2. Update version numbers

Edit **3 files** to match the new version:

**pyproject.toml:**
```toml
version = "0.4.0"
```

**etlai/__init__.py:**
```python
__version__ = "0.4.0"
```

**RELEASE.md** (add new section at the top):
```markdown
## v0.4.0 (2026-07-22)

### Added
- Workflow orchestration with multi-agent support
- New `etlai workflow` command

### Fixed
- Registry trigger building performance
- Composite pipeline config handling

### Changed
- Refactored registry for better modularity
```

#### 3. Update documentation (if needed)

**README.md:**
- Update installation examples with new version
- Add new features to feature list
- Update usage examples if API changed

**ARCHITECTURE.md:**
- Document new architectural components
- Update diagrams if structure changed

**TESTS.md:**
- Update status table if new test coverage added

#### 4. Commit release

```bash
# Stage version files
git add pyproject.toml etlai/__init__.py RELEASE.md

# Stage documentation if updated
git add README.md ARCHITECTURE.md TESTS.md

# Commit with release message format
git commit -m "release: v0.4.0 - add workflow orchestration"
```

The `pre-commit` hook will:
- Run all tests
- Verify version consistency across files
- Check documentation is staged

The `post-commit` hook will:
- Create annotated git tag `v0.4.0`
- Remind you to push tags

#### 5. Push to repository

```bash
# Push commits
git push origin main

# Push tags
git push origin --tags
```

#### 6. Build distribution packages

```bash
# Clean old builds
rm -rf dist/ build/ *.egg-info

# Build source distribution and wheel
python -m build

# Verify build artifacts
ls -lh dist/
# Should see:
# ETLai-0.4.0-py3-none-any.whl
# ETLai-0.4.0.tar.gz
```

#### 7. Verify package integrity

```bash
# Check package contents
tar -tzf dist/ETLai-0.4.0.tar.gz | head -20

# Install locally to test
pip install dist/ETLai-0.4.0-py3-none-any.whl

# Run quick smoke test
etlai --version
# Should output: 0.4.0
```

#### 8. Publish to PyPI

**Option A: Using Twine (recommended)**

```bash
# Check package first (validates metadata)
python -m twine check dist/*

# Upload to PyPI (will prompt for credentials)
python -m twine upload dist/*

# Or use token authentication
python -m twine upload dist/* --username __token__ --password YOUR_PYPI_TOKEN
```

**Option B: Using PyPI API token (preferred for automation)**

Create `~/.pypirc`:
```ini
[pypi]
username = __token__
password = pypi-AgEIcHlwaS5vcmc...YOUR_TOKEN_HERE
```

Then:
```bash
python -m twine upload dist/*
```

#### 9. Verify PyPI publication

```bash
# Wait 1-2 minutes for PyPI to process

# Check on PyPI web interface
open https://pypi.org/project/ETLai/

# Test installation from PyPI
pip install --upgrade ETLai==0.4.0

# Verify it works
etlai --version
python -c "import etlai; print(etlai.__version__)"
```

#### 10. Create GitHub Release (optional)

```bash
# Using GitHub CLI
gh release create v0.4.0 \
  --title "v0.4.0 - Workflow orchestration" \
  --notes-file RELEASE.md \
  dist/*

# Or manually via GitHub web interface:
# 1. Go to https://github.com/umang/ETLai/releases/new
# 2. Select tag: v0.4.0
# 3. Title: v0.4.0 - Workflow orchestration
# 4. Copy changelog from RELEASE.md
# 5. Attach dist/ files
# 6. Publish release
```

#### 11. Post-release verification

```bash
# Test in a clean environment
python -m venv /tmp/test-etlai
source /tmp/test-etlai/bin/activate
pip install ETLai==0.4.0
etlai init /tmp/test-project
cd /tmp/test-project
etlai list
deactivate
```

### Emergency rollback

If a critical bug is discovered immediately after release:

```bash
# 1. Delete the PyPI release (cannot be undone)
# Contact PyPI support or use web interface

# 2. Delete the git tag
git tag -d v0.4.0
git push origin :refs/tags/v0.4.0

# 3. Revert the release commit
git revert HEAD
git push origin main

# 4. Publish a hotfix release (0.4.1)
```

**Note:** PyPI does not allow re-uploading the same version. If v0.4.0 has a critical bug, you must release v0.4.1.

## Hook Scripts

All hooks live in `.githooks/` and are version-controlled.

### Installation

```bash
# One-time setup per clone
git config core.hooksPath .githooks

# Make hooks executable
chmod +x .githooks/*
```

### Disable hooks temporarily

```bash
# For a single commit
git commit --no-verify

# Disable for the session
git config core.hooksPath ""

# Re-enable
git config core.hooksPath .githooks
```

## CI/CD Pipeline (GitHub Actions - Future)

Once the project is public or has collaborators, add GitHub Actions workflows:

### `.github/workflows/test.yml`

Runs on every push and PR:

```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.10', '3.11', '3.12']
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"
      
      - name: Run tests with coverage
        run: pytest --cov=etlai --cov-report=xml --cov-report=term
      
      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
          fail_ci_if_error: false
```

### `.github/workflows/release.yml`

Runs when a tag is pushed:

```yaml
name: Release
on:
  push:
    tags:
      - 'v*'

jobs:
  build-and-publish:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install build tools
        run: pip install build twine
      
      - name: Build package
        run: python -m build
      
      - name: Verify version matches tag
        run: |
          TAG_VERSION=${GITHUB_REF#refs/tags/v}
          PKG_VERSION=$(grep '^version = ' pyproject.toml | cut -d'"' -f2)
          if [ "$TAG_VERSION" != "$PKG_VERSION" ]; then
            echo "Tag version ($TAG_VERSION) does not match package version ($PKG_VERSION)"
            exit 1
          fi
      
      - name: Publish to PyPI
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_TOKEN }}
        run: twine upload dist/*
      
      - name: Create GitHub Release
        uses: softprops/action-gh-release@v1
        with:
          files: dist/*
          body_path: RELEASE.md
          draft: false
          prerelease: false
```

## PyPI Credentials Setup

### Creating a PyPI API token

1. Go to https://pypi.org/manage/account/token/
2. Click "Add API token"
3. Name: "ETLai Releases"
4. Scope: "Project: ETLai" (after first upload) or "Entire account" (for first upload)
5. Copy the token (starts with `pypi-`)

### Storing token securely

**For local releases:**

Create `~/.pypirc`:
```ini
[pypi]
username = __token__
password = pypi-YOUR_TOKEN_HERE
```

Set permissions:
```bash
chmod 600 ~/.pypirc
```

**For GitHub Actions:**

1. Go to repository settings → Secrets → Actions
2. Add secret: `PYPI_TOKEN` = your token
3. GitHub Actions will use it automatically

**For team releases:**

Use a password manager (1Password, LastPass) to share the token securely. Never commit tokens to git.

## Checklist: Preparing for a Release

- [ ] All tests pass (`pytest --cov=etlai`)
- [ ] Version bumped in 3 places (pyproject.toml, __init__.py, RELEASE.md)
- [ ] RELEASE.md has new section with changelog
- [ ] README.md reflects new features (if user-facing changes)
- [ ] ARCHITECTURE.md updated (if internal design changed)
- [ ] TESTS.md updated (if new tests added)
- [ ] All documentation reviewed for accuracy
- [ ] Clean build environment (`rm -rf dist/ build/ *.egg-info`)
- [ ] Commit with message: `release: vX.Y.Z - <summary>`
- [ ] Hook creates tag automatically (verify with `git tag`)
- [ ] Push: `git push origin main --tags`
- [ ] Build: `python -m build`
- [ ] Verify package: `python -m twine check dist/*`
- [ ] Test install locally: `pip install dist/ETLai-X.Y.Z*.whl`
- [ ] Publish: `python -m twine upload dist/*`
- [ ] Verify on PyPI: `pip install --upgrade ETLai==X.Y.Z`
- [ ] Create GitHub Release (optional)
- [ ] Test in clean environment

## Troubleshooting

### Build fails

```bash
# Check for syntax errors
python -m py_compile etlai/**/*.py

# Check manifest includes all files
python -m build --sdist
tar -tzf dist/ETLai-*.tar.gz | grep etlai/
```

### Twine upload fails

```bash
# "Invalid distribution file" error
python -m twine check dist/*

# Authentication error
# Check ~/.pypirc has correct token

# "File already exists" error
# You cannot re-upload the same version to PyPI
# Bump version and try again
```

### Version mismatch errors

```bash
# Find all version references
grep -r "0.3.1" pyproject.toml etlai/__init__.py RELEASE.md README.md

# Update all to match
```

### Git tag conflicts

```bash
# Tag already exists locally
git tag -d v0.4.0

# Tag exists on remote
git push origin :refs/tags/v0.4.0

# Then recreate and push
git tag -a v0.4.0 -m "Release v0.4.0"
git push origin v0.4.0
```

## Best Practices

1. **Never skip tests before releasing** — Even if "it's just a docs change"
2. **Always test local install before publishing** — Install from dist/ wheel and verify
3. **Keep release notes clear and actionable** — Focus on what changed for users
4. **Tag releases immediately after commit** — Don't separate commit and tag by days
5. **Verify PyPI publication** — Always test `pip install` after publishing
6. **Increment versions semantically** — Major.Minor.Patch (0.4.0 → 0.5.0 for features, 0.4.1 for bugfixes)
7. **Never force-push after tagging** — Tags should be immutable
8. **Clean build artifacts before building** — Prevents stale files in distribution

## Questions?

**Can I publish from a feature branch?**  
No. Always release from `main` to keep tags and releases predictable.

**What if I forget to update RELEASE.md?**  
The pre-commit hook will catch it and block the commit.

**Can I delete a release from PyPI?**  
You can remove files, but the version number is permanently reserved. Publish a new version instead.

**Should I publish to TestPyPI first?**  
For major releases, yes:
```bash
python -m twine upload --repository testpypi dist/*
pip install --index-url https://test.pypi.org/simple/ ETLai==0.4.0
```
