"""Centralized folder management for business pipeline file lifecycles."""

import os
import shutil
from datetime import datetime


def _get_pipelines_root() -> str:
    """Resolve pipelines root from etlai.yaml in cwd, or default to ./pipelines/."""
    import yaml
    config_path = os.path.join(os.getcwd(), "etlai.yaml")
    if os.path.isfile(config_path):
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
        root = config.get("pipelines_root", "./pipelines")
        if not os.path.isabs(root):
            root = os.path.join(os.getcwd(), root)
        return root
    return os.path.join(os.getcwd(), "pipelines")


def _get_pipeline_path(pipeline_name: str) -> str | None:
    """Check if a pipeline has a custom path set in its manifest."""
    import yaml
    pipelines_root = _get_pipelines_root()
    manifest_path = os.path.join(pipelines_root, pipeline_name, "manifest.yaml")
    if os.path.isfile(manifest_path):
        with open(manifest_path) as f:
            manifest = yaml.safe_load(f) or {}
        path = manifest.get("path")
        if path and path != "ask":
            if not os.path.isabs(path):
                path = os.path.join(os.getcwd(), path)
            return path
    return None


class PipelineFolders:
    """Folder paths and lifecycle operations for a specific business pipeline."""

    def __init__(self, pipeline_name: str):
        pipelines_root = _get_pipelines_root()
        self._project_dir = os.path.join(pipelines_root, pipeline_name)

        custom_path = _get_pipeline_path(pipeline_name)
        if custom_path:
            self.root = custom_path
        else:
            self.root = self._project_dir

        self.inbox = os.path.join(self.root, "inbox")
        self.staging = os.path.join(self.root, "staging")
        self.processed = os.path.join(self.root, "processed")
        self.rejected = os.path.join(self.root, "rejected")
        self.output = os.path.join(self.root, "output")
        self.reference = os.path.join(self.root, "reference")
        # config.json always lives in the project directory, not the data directory
        self.config_path = os.path.join(self._project_dir, "config.json")

    def ensure(self):
        for folder in [self.inbox, self.staging, self.processed, self.rejected, self.output, self.reference]:
            os.makedirs(folder, exist_ok=True)

    def list_reference_files(self) -> list[str]:
        """List all files in the reference folder."""
        if not os.path.isdir(self.reference):
            return []
        return sorted(
            os.path.join(self.reference, f)
            for f in os.listdir(self.reference)
            if os.path.isfile(os.path.join(self.reference, f))
        )

    def move_to_staging(self, file_paths: list[str]) -> list[str]:
        os.makedirs(self.staging, exist_ok=True)
        moved = []
        for fpath in file_paths:
            if os.path.isfile(fpath):
                dest = os.path.join(self.staging, os.path.basename(fpath))
                shutil.move(fpath, dest)
                moved.append(dest)
        return moved

    def move_to_processed(self, file_paths: list[str]) -> list[str]:
        os.makedirs(self.processed, exist_ok=True)
        moved = []
        for fpath in file_paths:
            if os.path.isfile(fpath):
                dest = os.path.join(self.processed, os.path.basename(fpath))
                shutil.move(fpath, dest)
                moved.append(dest)
        return moved

    def move_to_rejected(self, file_paths: list[str], reason: str) -> list[str]:
        os.makedirs(self.rejected, exist_ok=True)
        moved = []
        for fpath in file_paths:
            if os.path.isfile(fpath):
                dest = os.path.join(self.rejected, os.path.basename(fpath))
                shutil.move(fpath, dest)
                moved.append(dest)
                error_path = os.path.join(self.rejected, f"{os.path.basename(fpath)}.error.txt")
                with open(error_path, "w") as f:
                    f.write(f"REJECTED: {os.path.basename(fpath)}\n")
                    f.write(f"Time: {datetime.now().isoformat()}\n")
                    f.write(f"Reason: {reason}\n")
        return moved

    def output_path(self, filename: str) -> str:
        os.makedirs(self.output, exist_ok=True)
        return os.path.join(self.output, filename)

    def list_inbox_files(self, pattern) -> list[str]:
        if not os.path.isdir(self.inbox):
            return []
        return sorted(
            os.path.join(self.inbox, f)
            for f in os.listdir(self.inbox)
            if pattern.match(f) and os.path.isfile(os.path.join(self.inbox, f))
        )
