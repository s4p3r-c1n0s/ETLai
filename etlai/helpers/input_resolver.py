"""InputResolver — maps inbox files and previous outputs to atom config params."""

from __future__ import annotations

import fnmatch
import os


def order_files_by_pattern(file_paths: list[str], inputs: list[dict]) -> list[str]:
    """Reorder inbox files to match declared input patterns.

    Args:
        file_paths: unordered list of file paths from inbox
        inputs: manifest inputs[] declarations (must have 'pattern' and role=='transient')

    Returns:
        Reordered file list matching input declaration order.
        Files not matching any pattern are appended at the end.
    """
    transient_inputs = [inp for inp in inputs if inp.get("role") == "transient"]
    if not transient_inputs:
        return file_paths

    ordered = []
    remaining = list(file_paths)

    for inp in transient_inputs:
        pattern = inp.get("pattern")
        if not pattern:
            if remaining:
                ordered.append(remaining.pop(0))
            continue

        matched = None
        for fp in remaining:
            if fnmatch.fnmatch(os.path.basename(fp), pattern):
                matched = fp
                break

        if matched:
            remaining.remove(matched)
            ordered.append(matched)

    ordered.extend(remaining)
    return ordered


class InputResolver:
    """Resolves file paths into atom config params.

    Supports two modes:
    1. Explicit: manifest step declares `inputs_map` — N files, any param names
    2. Fallback: legacy heuristic for manifests without inputs_map
    """

    def resolve(
        self,
        *,
        is_first: bool,
        file_paths: list[str],
        prev_output: str | None,
        config: dict,
        inputs_map: list[dict] | None = None,
    ) -> dict:
        """Inject file paths into config and return it.

        Args:
            is_first: True if this is step 0
            file_paths: inbox files available to the pipeline
            prev_output: output path from the previous step (None if is_first)
            config: current step config (mutated in place)
            inputs_map: optional explicit mapping from manifest step declaration
                        e.g. [{"param": "left_file"}, {"param": "right_file"}]

        Returns:
            The mutated config dict with file paths injected.
        """
        if inputs_map:
            return self._resolve_explicit(is_first, file_paths, prev_output, config, inputs_map)
        return self._resolve_fallback(is_first, file_paths, prev_output, config)

    def _resolve_explicit(
        self,
        is_first: bool,
        file_paths: list[str],
        prev_output: str | None,
        config: dict,
        inputs_map: list[dict],
    ) -> dict:
        """Explicit mode: assign files to params in declared order."""
        if is_first:
            for i, mapping in enumerate(inputs_map):
                param = mapping["param"]
                if param in config:
                    continue
                source = mapping.get("source", "inbox")
                if source == "inbox" and i < len(file_paths):
                    config[param] = file_paths[i]
        else:
            first_param = inputs_map[0]["param"]
            if first_param not in config:
                config[first_param] = prev_output
            for i, mapping in enumerate(inputs_map[1:], start=1):
                param = mapping["param"]
                if param in config:
                    continue
                source = mapping.get("source", "inbox")
                if source == "inbox" and i < len(file_paths):
                    config[param] = file_paths[i]

        return config

    def _resolve_fallback(
        self,
        is_first: bool,
        file_paths: list[str],
        prev_output: str | None,
        config: dict,
    ) -> dict:
        """Legacy heuristic for manifests without inputs_map."""
        if is_first:
            if file_paths and "left_file" not in config and "input_file" not in config and "input_files" not in config:
                if len(file_paths) >= 2:
                    config["left_file"] = file_paths[0]
                    config["right_file"] = file_paths[1]
                elif "right_file" in config:
                    config["left_file"] = file_paths[0]
                else:
                    config["input_file"] = file_paths[0]
        else:
            if "left_file" not in config and "input_file" not in config:
                if "right_file" in config:
                    config["left_file"] = prev_output
                else:
                    config["input_file"] = prev_output

        return config
