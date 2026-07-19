"""Config store — reads/writes per-pipeline JSON configuration."""

import json
import os

from helpers.folders import PipelineFolders


def load_config(folders: PipelineFolders) -> dict | None:
    """Load saved config for a pipeline. Returns None if no config exists."""
    if not os.path.isfile(folders.config_path):
        return None
    with open(folders.config_path, "r") as f:
        return json.load(f)


def save_config(folders: PipelineFolders, config: dict) -> None:
    """Save config for a pipeline."""
    os.makedirs(os.path.dirname(folders.config_path), exist_ok=True)
    with open(folders.config_path, "w") as f:
        json.dump(config, f, indent=2)


def config_exists(folders: PipelineFolders) -> bool:
    """Check if a config file exists for this pipeline."""
    return os.path.isfile(folders.config_path)
