#!/usr/bin/env bash
set -euo pipefail

export PATH="${HOME}/.local/bin:${PATH:-/usr/local/bin:/usr/bin:/bin}"

# Tkinter is required for etlai sync when manifests use path: ask.
if ! python3 -c "import tkinter" 2>/dev/null; then
  sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-tk
fi

cd /workspace
pip install --user -e ".[dev]"
