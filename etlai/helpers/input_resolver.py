"""InputResolver — binds inbound files to atom config params (explicit only).

Atom file inputs are declared per-step in the manifest via ``inputs_map``, an
ordered list of ``{param, source}`` entries:

    inputs_map:
      - param: left_file                 # next inbox file (source: inbox)
      - param: right_file                # second inbox file
      - param: input_file
        source: prev_output              # previous step's output path
      - param: input_files
        source: inbox_all                # all inbox files as a list

Sources:
  * ``inbox`` (default) — the next unclaimed inbox file, in pipeline order
  * ``prev_output``     — the previous step's output path
  * ``inbox_all``       — the full list of inbox files

Reference files are NOT resolved here: the registry injects them via the
``inject_as`` declaration before this resolver runs. A param that is already
populated (by ``inject_as`` or an explicit value in config.json) is left alone.

There is no heuristic fallback: a step with inbound files MUST declare
``inputs_map``, otherwise resolution fails loudly.
"""

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
    """Maps inbound files and previous outputs to atom config params.

    Explicit only: every step's manifest declares ``inputs_map`` naming the
    param(s) it binds and the source of each path.
    """

    def resolve(
        self,
        *,
        file_paths: list[str],
        prev_output: str | None,
        config: dict,
        inputs_map: list[dict] | None,
    ) -> dict:
        """Inject file paths into config and return it.

        Args:
            file_paths: inbox files available to the pipeline (empty for API pipelines)
            prev_output: output path from the previous step (None for the first step)
            config: current step config (mutated in place)
            inputs_map: explicit mapping from the manifest step declaration,
                        e.g. [{"param": "left_file"}, {"param": "right_file"}]

        Returns:
            The mutated config dict with file paths injected.
        """
        if not inputs_map:
            if file_paths:
                raise ValueError(
                    "Step has inbound files but no `inputs_map` declared. "
                    "Add an explicit `inputs_map` to the manifest step, e.g.:\n"
                    "  inputs_map:\n"
                    "    - param: input_file"
                )
            # No inbound files and no declared mapping (e.g. an API fetch
            # pipeline) — nothing to bind.
            return config

        cursor = 0
        for mapping in inputs_map:
            param = mapping["param"]

            # Already populated (reference injection via inject_as, or an
            # explicit path in config.json) — leave it untouched.
            if param in config:
                continue

            source = mapping.get("source", "inbox")

            if source == "prev_output":
                if prev_output is not None:
                    config[param] = prev_output
            elif source == "inbox_all":
                config[param] = list(file_paths)
            elif source == "inbox":
                if cursor < len(file_paths):
                    config[param] = file_paths[cursor]
                    cursor += 1
            else:
                raise ValueError(
                    f"Unknown source {source!r} in inputs_map for param {param!r}. "
                    "Expected one of: inbox, prev_output, inbox_all."
                )

        return config