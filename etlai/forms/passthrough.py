"""Form: no UI — reads config.json and passes it to the atom."""


def configure(file_paths: list[str], existing_config: dict | None) -> dict:
    """Return existing config directly. No UI shown.

    For no-UI pipelines, config.json must be pre-written (by Claude Code or manually).
    Raises if no config exists.
    """
    if existing_config is not None:
        return existing_config

    raise RuntimeError(
        "No config.json found for this pipeline. "
        "For no-UI pipelines, create config.json with the required parameters before running."
    )
