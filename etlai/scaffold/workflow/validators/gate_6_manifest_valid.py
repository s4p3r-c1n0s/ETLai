"""Gate 6→done: Validates manifest.yaml and config.json are structurally complete.

Checks:
- manifest.yaml has required fields (name, steps/atom, inputs, trigger)
- config.json has entries for each step
- Reference inputs have inject_as declarations
- Last step is rename_columns (rehydration)
- All referenced atoms exist on disk
- No generic placeholders leaked into config (col_a, threshold_1 should be real values)

Usage: python gate_6_manifest_valid.py <pipeline_dir> [project_root]
Exit 0 = PASS, Exit 1 = FAIL
"""

import json
import re
import sys
from pathlib import Path

import yaml


PLACEHOLDER_PATTERN = re.compile(r"^(col_[a-z]|source_\d+|threshold_\d+|computed_\d+|flag_\d+)$")


def validate(pipeline_dir: Path, project_root: Path) -> tuple[bool, list[str]]:
    errors = []
    manifest_path = pipeline_dir / "manifest.yaml"
    config_path = pipeline_dir / "config.json"

    if not manifest_path.exists():
        return False, ["manifest.yaml does not exist"]
    if not config_path.exists():
        return False, ["config.json does not exist"]

    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)
    with open(config_path) as f:
        config = json.load(f)

    if not manifest:
        return False, ["manifest.yaml is empty"]

    # Name required
    if not manifest.get("name"):
        errors.append("manifest.name is empty")

    # Steps or atom required
    steps = manifest.get("steps")
    atom = manifest.get("atom")

    if not steps and not atom:
        errors.append("manifest must have 'steps' (composite) or 'atom' (single)")
        return False, errors

    if steps:
        # Composite pipeline checks
        for i, step in enumerate(steps):
            step_atom = step.get("atom", "")
            if not step_atom:
                errors.append(f"steps[{i}].atom is empty")
                continue

            # Verify atom exists
            user_path = project_root / "atoms" / f"{step_atom}.py"
            shipped = False
            try:
                import importlib
                importlib.import_module(f"etlai.atoms.{step_atom}")
                shipped = True
            except ImportError:
                pass

            if not shipped and not user_path.exists():
                errors.append(f"steps[{i}].atom '{step_atom}' not found (not shipped, not in atoms/)")

        # Last step should be rename_columns
        if steps:
            last_atom = steps[-1].get("atom", "")
            if last_atom != "rename_columns":
                errors.append(
                    f"Last step atom is '{last_atom}', expected 'rename_columns' for rehydration"
                )

        # Config must have step_N entries (step_0 uses flat top-level config at runtime)
        if "step_0" not in config and len(steps) > 0:
            top_level_has_params = any(
                k for k in config if not k.startswith("step_")
            )
            if not top_level_has_params:
                errors.append(
                    "config.json missing params for step 0: "
                    "place step-0 params at the top level (runtime reads flat config for step 0)"
                )
        for i in range(1, len(steps)):
            key = f"step_{i}"
            if key not in config:
                errors.append(f"config.json missing '{key}' for step {i}")

    else:
        # Single atom pipeline
        user_path = project_root / "atoms" / f"{atom}.py"
        shipped = False
        try:
            import importlib
            importlib.import_module(f"etlai.atoms.{atom}")
            shipped = True
        except ImportError:
            pass
        if not shipped and not user_path.exists():
            errors.append(f"atom '{atom}' not found (not shipped, not in atoms/)")

    # Inputs validation
    inputs = manifest.get("inputs") or []
    for i, inp in enumerate(inputs):
        p = f"inputs[{i}]"
        if not inp.get("name"):
            errors.append(f"{p}.name is empty")
        role = inp.get("role", "")
        if role not in ("transient", "reference"):
            errors.append(f"{p}.role must be 'transient' or 'reference', got '{role}'")
        if role == "reference" and not inp.get("inject_as"):
            errors.append(f"{p}: reference input must have inject_as declaration")

    # Trigger check
    trigger = manifest.get("trigger") or {}
    rules = trigger.get("rules") or []
    min_files = manifest.get("min_files")
    if not rules and min_files is None:
        errors.append("No trigger.rules and no min_files — pipeline cannot trigger")

    # Check config for placeholder leakage (col_a, threshold_1 should not be in final config)
    config_text = json.dumps(config)
    placeholders_found = PLACEHOLDER_PATTERN.findall(config_text)
    # More thorough: scan all string values
    _scan_config_placeholders(config, "config", errors)

    return len(errors) == 0, errors


def _scan_config_placeholders(obj, path: str, errors: list):
    """Scan config values for un-translated generic placeholders."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            _scan_config_placeholders(v, f"{path}.{k}", errors)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _scan_config_placeholders(item, f"{path}[{i}]", errors)
    elif isinstance(obj, str):
        if PLACEHOLDER_PATTERN.match(obj):
            errors.append(
                f"Untranslated placeholder in {path}: '{obj}' — "
                f"should be a real value from business_mapping"
            )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python gate_6_manifest_valid.py <pipeline_dir> [project_root]")
        sys.exit(1)

    pipeline_dir = Path(sys.argv[1])
    project_root = Path(sys.argv[2]) if len(sys.argv) > 2 else Path.cwd()

    passed, errors = validate(pipeline_dir, project_root)
    if passed:
        print("GATE 6: PASS — manifest and config are structurally valid")
    else:
        print("GATE 6: FAIL")
        for e in errors:
            print(f"  - {e}")
    sys.exit(0 if passed else 1)
