# Publishing Guide

Complete guide for building and publishing ETLai to PyPI.

## Prerequisites

```bash
# Install build tools (one-time setup)
pip install build twine

# Verify PyPI credentials are configured
cat ~/.pypirc  # Should contain [pypi] username and password/token
```

## Quick Publish (for maintainers)

After the release commit is merged and tagged:

```bash
# 1. Clean old builds
rm -rf dist/ build/ *.egg-info

# 2. Build distribution packages
python -m build

# 3. Verify package integrity
python -m twine check dist/*

# 4. Publish to PyPI
python -m twine upload dist/*

# 5. Verify publication
pip install --upgrade ETLai==$(grep '^version = ' pyproject.toml | cut -d'"' -f2)
etlai --version
```

For first-time setup or troubleshooting, see sections below.

---

## Step-by-Step Publishing

### 1. Clean build environment

```bash
# Remove old build artifacts
rm -rf dist/ build/ *.egg-info

# Verify clean slate
ls dist/  # Should not exist or be empty
```

**Why:** Prevents stale files from previous builds being included in the distribution.

### 2. Build distribution packages

```bash
# Build source distribution (.tar.gz) and wheel (.whl)
python -m build
```

**Output:**
```
Successfully built etlai-0.3.5.tar.gz and etlai-0.3.5-py3-none-any.whl
```

**Verify build artifacts:**
```bash
ls -lh dist/
# Should see both:
# ETLai-0.3.5-py3-none-any.whl
# ETLai-0.3.5.tar.gz
```

### 3. Verify package integrity

```bash
# Check package metadata and structure
python -m twine check dist/*

# Inspect package contents (optional)
tar -tzf dist/ETLai-*.tar.gz | head -20
```

**Expected output:**
```
Checking dist/ETLai-0.3.5-py3-none-any.whl: PASSED
Checking dist/ETLai-0.3.5.tar.gz: PASSED
```

### 4. Test local installation

```bash
# Install from local wheel (in a venv if desired)
pip install dist/ETLai-*-py3-none-any.whl

# Verify version
etlai --version
python -c "import etlai; print(etlai.__version__)"

# Quick smoke test
etlai --help
```

### 5. Publish to PyPI

**Option A: Interactive (will prompt for credentials)**
```bash
python -m twine upload dist/*
```

**Option B: Using configured token (recommended)**
```bash
# Reads credentials from ~/.pypirc
python -m twine upload dist/*
```

**Option C: Explicit token**
```bash
python -m twine upload dist/* \
  --username __token__ \
  --password YOUR_PYPI_TOKEN
```

**Expected output:**
```
Uploading distributions to https://upload.pypi.org/legacy/
Uploading etlai-0.3.5-py3-none-any.whl
100% ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 43.5/43.5 kB
Uploading etlai-0.3.5.tar.gz
100% ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 42.4/42.4 kB

View at:
https://pypi.org/project/ETLai/0.3.5/
```

### 6. Verify PyPI publication

```bash
# Wait 1-2 minutes for PyPI to process the upload

# Check web interface
open https://pypi.org/project/ETLai/

# Test installation from PyPI in a clean environment
python -m venv /tmp/test-etlai
source /tmp/test-etlai/bin/activate
pip install ETLai==0.3.5
etlai --version  # Should output: 0.3.5
etlai init /tmp/test-project
cd /tmp/test-project
etlai list
deactivate
rm -rf /tmp/test-etlai /tmp/test-project
```

---

## PyPI Credentials Setup

### Creating a PyPI API token

1. Go to https://pypi.org/manage/account/token/
2. Click "Add API token"
3. **Name:** "ETLai Releases"
4. **Scope:** 
   - For first upload: "Entire account"
   - After first upload: "Project: ETLai" (more secure)
5. Copy the token (starts with `pypi-`)
6. **Important:** Save it immediately — you cannot view it again

### Storing token securely

**For local releases:**

Create `~/.pypirc`:
```ini
[pypi]
username = __token__
password = pypi-AgEIcHlwaS5vcmcCJGFiY2QxMjM0...YOUR_TOKEN_HERE
```

Set correct permissions:
```bash
chmod 600 ~/.pypirc
```

**For GitHub Actions (future):**
1. Go to repository settings → Secrets → Actions
2. Add secret: `PYPI_TOKEN` = your token
3. Reference in workflow: `${{ secrets.PYPI_TOKEN }}`

**For team releases:**
- Use a password manager (1Password, Bitwarden, LastPass) to share tokens
- Never commit tokens to git
- Never paste tokens in Slack/email

---

## Publishing to TestPyPI (recommended for major releases)

TestPyPI is a separate instance for testing package uploads without affecting the production index.

### Setup TestPyPI credentials

Add to `~/.pypirc`:
```ini
[testpypi]
username = __token__
password = pypi-AgENdGVzdC5weXBpLm9yZwIk...TEST_TOKEN_HERE
```

Get a TestPyPI token at: https://test.pypi.org/manage/account/token/

### Publish to TestPyPI

```bash
# Upload to test instance
python -m twine upload --repository testpypi dist/*

# Test installation from TestPyPI
pip install --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  ETLai==0.3.5
```

**Note:** `--extra-index-url https://pypi.org/simple/` is needed because TestPyPI doesn't have all dependencies (dagster, pandas, etc). This tells pip to fall back to production PyPI for dependencies.

### When to use TestPyPI

- ✅ Major version releases (0.x.0 → 1.0.0)
- ✅ First time publishing a new package
- ✅ Significant changes to package structure
- ✅ Testing new PyPI token/credentials
- ⬜ Minor/patch releases (can publish directly to PyPI)

---

## Troubleshooting

### Build fails with "invalid command 'bdist_wheel'"

```bash
# Install wheel package
pip install wheel

# Try building again
python -m build
```

### Twine check fails: "Invalid distribution file"

```bash
# Check pyproject.toml for syntax errors
python -m toml pyproject.toml  # If toml module installed

# Rebuild from scratch
rm -rf dist/ build/ *.egg-info
python -m build
python -m twine check dist/*
```

### Twine upload fails: "403 Forbidden"

**Cause:** Invalid or expired PyPI token.

**Fix:**
```bash
# 1. Check ~/.pypirc has correct token
cat ~/.pypirc

# 2. Generate new token at https://pypi.org/manage/account/token/

# 3. Update ~/.pypirc with new token

# 4. Try upload again
python -m twine upload dist/*
```

### "File already exists" error on upload

**Cause:** PyPI does not allow re-uploading the same version.

**Fix:**
```bash
# You MUST bump the version number
# Edit: pyproject.toml, etlai/__init__.py, CHANGELOG.md
# Then rebuild and upload

# Example: 0.3.5 → 0.3.6
sed -i '' 's/0.3.5/0.3.6/' pyproject.toml etlai/__init__.py
# Update CHANGELOG.md manually
git commit -am "chore: bump to v0.3.6"
rm -rf dist/ build/
python -m build
python -m twine upload dist/*
```

### Version mismatch between files

```bash
# Find all version references
grep -r "0.3.5" pyproject.toml etlai/__init__.py CHANGELOG.md

# Ensure all match before building
```

### Package missing files after installation

**Cause:** Files not included in `pyproject.toml` package data.

**Fix:** Check `[tool.setuptools.package-data]` section:
```toml
[tool.setuptools.package-data]
"etlai" = ["scaffold/**/*", "scaffold/*"]
```

Rebuild and verify contents:
```bash
python -m build
tar -tzf dist/ETLai-*.tar.gz | grep scaffold
```

### Import error after installation

```bash
# Verify package installed correctly
pip show ETLai

# Check installed files
pip show -f ETLai | grep -E '\.py$'

# Try reinstalling
pip uninstall ETLai
pip install ETLai --no-cache-dir
```

---

## Best Practices

1. **Always clean build directory before building** — `rm -rf dist/ build/ *.egg-info`
2. **Run twine check before uploading** — Catches metadata issues early
3. **Test local install before publishing** — Install from dist/ wheel and verify
4. **Use TestPyPI for major releases** — Safer to test the full upload/install flow
5. **Never re-use version numbers** — If upload fails, bump version and retry
6. **Keep .pypirc secure** — `chmod 600 ~/.pypirc`, never commit to git
7. **Verify on PyPI after upload** — Check https://pypi.org/project/ETLai/
8. **Test pip install in clean environment** — Use venv to verify installation
9. **Use API tokens, not passwords** — Tokens are scoped and revokable
10. **Keep build tools updated** — `pip install --upgrade build twine`

---

## Checklist: Before Publishing

Run through this checklist before every `twine upload`:

- [ ] **CHANGELOG.md has entry for this version** (MANDATORY — never publish without changelog)
- [ ] Version bumped in 2 files: `pyproject.toml`, `etlai/__init__.py`
- [ ] CHANGELOG.md `[Unreleased]` section moved to `[X.Y.Z] — YYYY-MM-DD`
- [ ] Release commit created and tagged (see [CICD.md](CICD.md))
- [ ] All tests pass: `pytest --cov=etlai`
- [ ] Build directory cleaned: `rm -rf dist/ build/ *.egg-info`
- [ ] Package built: `python -m build`
- [ ] Package verified: `python -m twine check dist/*`
- [ ] Package contents inspected: `tar -tzf dist/ETLai-*.tar.gz | head -20`
- [ ] Local install tested: `pip install dist/ETLai-*.whl && etlai --version`
- [ ] PyPI credentials configured: `cat ~/.pypirc`
- [ ] (Optional) Uploaded to TestPyPI first for major releases
- [ ] Ready to publish: `python -m twine upload dist/*`

---

## Related Documentation

- **[CICD.md](CICD.md)** — Complete release workflow including version bumping, git hooks, tagging
- **[CHANGELOG.md](CHANGELOG.md)** — Changelog and version history
- **[CONTRIBUTING.md](CONTRIBUTING.md)** — Development workflow and guidelines

---

## Quick Reference

```bash
# Complete publish workflow (copy-paste)
rm -rf dist/ build/ *.egg-info && \
python -m build && \
python -m twine check dist/* && \
python -m twine upload dist/*
```

```bash
# Publish to TestPyPI first (for major releases)
rm -rf dist/ build/ *.egg-info && \
python -m build && \
python -m twine check dist/* && \
python -m twine upload --repository testpypi dist/* && \
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ ETLai==$(grep '^version = ' pyproject.toml | cut -d'"' -f2)
```
