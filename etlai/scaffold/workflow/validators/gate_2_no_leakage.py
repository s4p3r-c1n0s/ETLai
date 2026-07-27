"""Gate 2→3: Validates logical_graph.yaml has ZERO domain term leakage.

Scans logical_graph against all real_name values in business_mapping.json.
If ANY business term appears in the logical graph, the separation failed.

Usage: python gate_2_no_leakage.py <pipeline_dir>
Exit 0 = PASS, Exit 1 = FAIL
"""

import json
import sys
from pathlib import Path

import yaml


OPERATION_VERBS = frozenset([
    "join", "compute", "group", "filter", "sort",
    "rename", "flag", "aggregate", "fetch",
])


def _collect_real_names(mapping: dict) -> set[str]:
    """Extract all real business terms from the mapping file."""
    names = set()

    for col_data in (mapping.get("columns") or {}).values():
        rn = col_data.get("real_name", "")
        if rn and len(rn) > 2:
            names.add(rn.lower())

    for src_data in (mapping.get("sources") or {}).values():
        rn = src_data.get("real_name", "")
        if rn and len(rn) > 2:
            names.add(rn.lower())
        fp = src_data.get("file_pattern", "")
        if fp and len(fp) > 2:
            names.add(fp.lower().replace("*", "").replace(".csv", "").replace(".json", "").strip())

    for out_data in (mapping.get("output_columns") or {}).values():
        bn = out_data.get("business_name", "")
        if bn and len(bn) > 2:
            names.add(bn.lower())

    for thresh_data in (mapping.get("thresholds") or {}).values():
        desc = thresh_data.get("description", "")
        # Don't add descriptions — too broad. Only add explicit names.

    for formula_data in (mapping.get("formulas") or {}).values():
        real_expr = formula_data.get("real_expression", "")
        # Extract column-like tokens from expressions
        for token in real_expr.replace("*", " ").replace("/", " ").replace("+", " ").replace("-", " ").split():
            token = token.strip().lower()
            if len(token) > 2 and not token.replace(".", "").isdigit():
                names.add(token)

    return names


def _scan_value(value, path: str, real_names: set[str], errors: list):
    """Recursively scan a YAML value for domain leakage."""
    if isinstance(value, dict):
        for k, v in value.items():
            _scan_value(v, f"{path}.{k}", real_names, errors)
    elif isinstance(value, list):
        for i, item in enumerate(value):
            _scan_value(item, f"{path}[{i}]", real_names, errors)
    elif isinstance(value, str):
        lower = value.lower()
        for name in real_names:
            if name in lower:
                errors.append(f"Domain leakage at {path}: contains '{name}' (value: '{value}')")


def validate(pipeline_dir: Path) -> tuple[bool, list[str]]:
    errors = []
    logical_path = pipeline_dir / "workflow" / "logical_graph.yaml"
    mapping_path = pipeline_dir / "workflow" / "business_mapping.json"

    if not logical_path.exists():
        return False, ["logical_graph.yaml does not exist"]
    if not mapping_path.exists():
        return False, ["business_mapping.json does not exist"]

    with open(logical_path) as f:
        logical = yaml.safe_load(f)
    with open(mapping_path) as f:
        mapping = json.load(f)

    if not logical:
        return False, ["logical_graph.yaml is empty"]

    real_names = _collect_real_names(mapping)
    if not real_names:
        errors.append("WARNING: business_mapping.json has no real names — leakage check cannot run")

    # Scan entire logical graph for real name presence
    _scan_value(logical, "root", real_names, errors)

    # Validate operation verbs
    for i, node in enumerate(logical.get("nodes") or []):
        op = node.get("operation", "")
        if op and op.lower() not in OPERATION_VERBS:
            errors.append(
                f"nodes[{i}].operation '{op}' is not a valid generic verb. "
                f"Allowed: {sorted(OPERATION_VERBS)}"
            )

    # Check that nodes exist
    if not logical.get("nodes"):
        errors.append("nodes list is empty")

    return len(errors) == 0, errors


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python gate_2_no_leakage.py <pipeline_dir>")
        sys.exit(1)

    passed, errors = validate(Path(sys.argv[1]))
    if passed:
        print("GATE 2: PASS — logical_graph.yaml has no domain leakage")
    else:
        print("GATE 2: FAIL")
        for e in errors:
            print(f"  - {e}")
    sys.exit(0 if passed else 1)
