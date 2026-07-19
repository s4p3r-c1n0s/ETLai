"""Centralized folder management for business pipeline file lifecycles."""

import os
import shutil
from datetime import datetime

_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
PIPELINES_ROOT = os.path.join(_PROJECT_ROOT, "pipelines")


class PipelineFolders:
    """Folder paths and lifecycle operations for a specific business pipeline."""

    def __init__(self, pipeline_name: str):
        self.root = os.path.join(PIPELINES_ROOT, pipeline_name)
        self.inbox = os.path.join(self.root, "inbox")
        self.staging = os.path.join(self.root, "staging")
        self.processed = os.path.join(self.root, "processed")
        self.rejected = os.path.join(self.root, "rejected")
        self.output = os.path.join(self.root, "output")
        self.config_path = os.path.join(self.root, "config.json")

    def ensure(self):
        """Create all lifecycle folders."""
        for folder in [self.inbox, self.staging, self.processed, self.rejected, self.output]:
            os.makedirs(folder, exist_ok=True)

    def move_to_staging(self, file_paths: list[str]) -> list[str]:
        """Move files to staging. Returns new paths."""
        os.makedirs(self.staging, exist_ok=True)
        moved = []
        for fpath in file_paths:
            if os.path.isfile(fpath):
                dest = os.path.join(self.staging, os.path.basename(fpath))
                shutil.move(fpath, dest)
                moved.append(dest)
        return moved

    def move_to_processed(self, file_paths: list[str]) -> list[str]:
        """Move files to processed. Returns new paths."""
        os.makedirs(self.processed, exist_ok=True)
        moved = []
        for fpath in file_paths:
            if os.path.isfile(fpath):
                dest = os.path.join(self.processed, os.path.basename(fpath))
                shutil.move(fpath, dest)
                moved.append(dest)
        return moved

    def move_to_rejected(self, file_paths: list[str], reason: str) -> list[str]:
        """Move files to rejected with error description. Returns new paths."""
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
        """Return an absolute path in the output folder."""
        os.makedirs(self.output, exist_ok=True)
        return os.path.join(self.output, filename)

    def list_inbox_files(self, pattern) -> list[str]:
        """List files in inbox matching a compiled regex."""
        if not os.path.isdir(self.inbox):
            return []
        return sorted(
            os.path.join(self.inbox, f)
            for f in os.listdir(self.inbox)
            if pattern.match(f) and os.path.isfile(os.path.join(self.inbox, f))
        )
