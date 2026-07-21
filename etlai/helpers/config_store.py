"""Config store — reads/writes per-pipeline JSON configuration."""

import json
import os

from etlai.helpers.folders import PipelineFolders


def load_config(folders: PipelineFolders) -> dict | None:
    if not os.path.isfile(folders.config_path):
        return None
    with open(folders.config_path, "r") as f:
        return json.load(f)


def save_config(folders: PipelineFolders, config: dict) -> None:
    os.makedirs(os.path.dirname(folders.config_path), exist_ok=True)
    with open(folders.config_path, "w") as f:
        json.dump(config, f, indent=2)


def config_exists(folders: PipelineFolders) -> bool:
    return os.path.isfile(folders.config_path)
