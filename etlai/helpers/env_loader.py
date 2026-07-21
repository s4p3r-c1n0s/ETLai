"""Load environment variables from an env file into os.environ for pipeline execution."""

import os
from pathlib import Path


def load_env_file(env_file_path: str) -> dict[str, str]:
    """Parse a .env file and load variables into os.environ. Returns loaded vars."""
    path = Path(env_file_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Env file not found: {path}")

    loaded = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'\"")
            os.environ[key] = value
            loaded[key] = value

    return loaded


def validate_env_vars(env_file_path: str, required_vars: list[str]) -> list[str]:
    """Check that required vars exist in the env file. Returns list of missing vars."""
    path = Path(env_file_path).expanduser().resolve()
    if not path.is_file():
        return required_vars

    present = set()
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, _ = line.partition("=")
            present.add(key.strip())

    return [v for v in required_vars if v not in present]
