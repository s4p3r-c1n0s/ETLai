# Commit Message Guidelines

## Quick Reference

```
<type>: <short summary (max 70 chars)>

- <bullet point explaining WHY, not what>
- <another bullet point>
- <another bullet point>
```

**Critical:** NO AI attribution. Never include "Co-Authored-By:", "Authored by Claude", or similar.

---

## Rules

1. **Title: max 70 characters** — Keep it scannable
2. **Imperative mood** — "add feature" not "added feature"
3. **Type prefix required** — feat, fix, refactor, test, docs, ci, chore
4. **Body: bullet points** — Explain WHY, not WHAT (code shows what)
5. **NO AI attribution** — This is human work using AI tools

---

## Types

- `feat:` — New feature (new atom, command, helper)
- `fix:` — Bug fix
- `refactor:` — Code reorganization (no behavior change)
- `test:` — Test additions or fixes
- `docs:` — Documentation only
- `ci:` — CI/CD configuration (hooks, workflows)
- `chore:` — Tooling, dependencies, maintenance

---

## Examples

### ✅ Good

```
feat: add api_fetch atom for REST API ingestion

- Generic HTTP client with configurable auth
- Supports JSON/XML/CSV response parsing
- Inline ${ENV_VAR} resolution in headers
- Field mapping with dot-notation for nested data
```

```
fix: resolve prepare-commit-msg v prefix bug

- RELEASE.md uses ## v0.3.2 format (with v)
- Hook was grepping for ## 0.3.2 (without v)
- Now correctly greps for ## v$NEW_VERSION
```

```
refactor: extract shared _execute_step function

- Eliminates 150+ lines duplication between jobs
- Both single/composite paths use unified executor
- Easier to extend with new step injection
```

### ❌ Bad

```
feat: added a bunch of stuff

This is a new feature that does some things.
Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```
**Problems:** Vague title, prose body, AI attribution

```
update code

Fixed some bugs and added features.
```
**Problems:** No type prefix, past tense, no details

```
WIP: temporary commit

- Still testing
```
**Problems:** WIP commits shouldn't reach main

---

## Why Not What

**Bad (describes WHAT):**
```
fix: add validation to env loader

- Added check for missing variables
- Validates file exists
```

**Good (explains WHY):**
```
fix: prevent runtime errors from missing env vars

- Validate required vars exist before atom execution
- Early failure at sync time vs runtime
- Clear error message shows which vars missing
```

---

## Release Commits

Special format for version releases:

```
release: vX.Y.Z - <one-line summary>

- <feature or improvement>
- <bug fix>
- <other change>
```

Example:
```
release: v0.3.2 - testing and registry improvements

- Tests covering atoms, helpers, registry
- Extracted shared _execute_step function
- Fixed prepare-commit-msg v prefix bug
- Added git hooks for automated test validation
```

The post-commit hook automatically creates git tags for releases.

---

## Enforcement

**Pre-commit hook checks:**
- ✅ Tests pass
- ✅ Documentation staged when source changes
- ✅ Version numbers match across files
- ⬜ Commit message format (not yet implemented)

**If you added AI attribution by mistake:**
```bash
# Install git-filter-repo if not already installed
pip install git-filter-repo

# Remove Co-Authored-By lines from all commits
git filter-repo --message-callback 'return re.sub(rb"^Co-Authored-By:.*\n?", b"", message, flags=re.MULTILINE)'
```

**Note:** Use `git filter-repo` (not deprecated `git filter-branch`)

---

## For AI Agents (Claude Code, etc.)

When writing commits:
1. Follow this format strictly
2. Never add "Co-Authored-By:" or "Authored by Claude" lines
3. Assume the committer is human using AI as a tool
4. Focus on WHY changes were made, not WHAT changed
5. Keep titles short and scannable

The human developer is the author. AI is a tool, not a co-author.
