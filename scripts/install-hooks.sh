#!/bin/bash

# Install ETLai git hooks

set -e

echo "📦 Installing git hooks..."

# Configure git to use .githooks directory
git config core.hooksPath .githooks

# Make hooks executable
chmod +x .githooks/pre-commit
chmod +x .githooks/prepare-commit-msg
chmod +x .githooks/post-commit

echo "✅ Git hooks installed successfully"
echo "   - pre-commit: runs tests and checks docs"
echo "   - prepare-commit-msg: validates release commits"
echo "   - post-commit: auto-creates git tags"
echo ""
echo "ℹ️  Hooks are now active. Tests will run before each commit."
