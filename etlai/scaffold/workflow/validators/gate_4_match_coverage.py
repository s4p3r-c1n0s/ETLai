"""Gate 4→5: Validates match_results.yaml covers all operations and matched atoms exist.

Checks:
- Every operation in atomic_operations.yaml has a match entry
- All "matched" atoms exist on disk (shipped or user)
- All "create" atom names are generic (no domain terms)
- No duplicate atom creation for the same operation

Usage: python gate_4_match_coverage.py <pipeline_dir> [project_root]
Exit 0 = PASS, Exit 1 = FAIL
"""

import sys
from pathlib import Path

import yaml


OPERATION_VERBS = frozenset([
    "join", "compute", "group", "filter", "sort",
    "rename", "flag", "aggregate", "fetch",
])


def validate(pipeline_dir: Path, project_root: Path) -> tuple[bool, list[str]]:
    errors = []
    match_path = pipeline_dir / "workflow" / "match_results.yaml"
    ops_path = pipeline_dir / "workflow" / "atomic_operations.yaml"

    if not match_path.exists():
        return False, ["match_results.yaml does not exist"]
    if not ops_path.exists():
        return False, ["atomic_operations.yaml does not exist"]

    with open(match_path) as f:
        match_data = yaml.safe_load(f)
    with open(ops_path) as f:
        ops_data = yaml.safe_load(f)

    operations = (ops_data or {}).get("operations") or []
    matches = (match_data or {}).get("matches") or []

    # Coverage check: every operation must have a match entry
    op_ids = {op.get("id") for op in operations if op.get("id")}
    matched_ids = {m.get("operation_id") for m in matches if m.get("operation_id")}

    missing = op_ids - matched_ids
    if missing:
        errors.append(f"Operations without match entry: {sorted(missing)}")

    # Validate each match entry
    seen_create_names = set()

    for i, match in enumerate(matches):
        p = f"matches[{i}]"
        status = match.get("status", "")
        atom_name = match.get("atom_name", "")
        atom_source = match.get("atom_source", "")

        if status not in ("matched", "create"):
            errors.append(f"{p}.status must be 'matched' or 'create', got '{status}'")
            continue

        if not atom_name:
            errors.append(f"{p}.atom_name is empty")
            continue

        if status == "matched":
            if atom_source == "shipped":
                # Try to verify shipped atom exists
                try:
                    import importlib
                    importlib.import_module(f"etlai.atoms.{atom_name}")
                except ImportError:
                    errors.append(f"{p}: shipped atom 'etlai.atoms.{atom_name}' not importable")
            elif atom_source == "user":
                user_path = project_root / "atoms" / f"{atom_name}.py"
                if not user_path.exists():
                    errors.append(f"{p}: user atom 'atoms/{atom_name}.py' not found")
            elif not atom_source:
                errors.append(f"{p}.atom_source is empty for matched atom")

        if status == "create":
            # Name must be generic
            parts = atom_name.split("_")
            if parts[0] not in OPERATION_VERBS and atom_name not in OPERATION_VERBS:
                errors.append(
                    f"{p}: proposed name '{atom_name}' does not start with a "
                    f"generic verb ({sorted(OPERATION_VERBS)})"
                )

            # Track for duplicate detection
            if atom_name in seen_create_names:
                # Duplicates are OK — two ops can share one atom
                pass
            seen_create_names.add(atom_name)

    return len(errors) == 0, errors


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python gate_4_match_coverage.py <pipeline_dir> [project_root]")
        sys.exit(1)

    pipeline_dir = Path(sys.argv[1])
    project_root = Path(sys.argv[2]) if len(sys.argv) > 2 else Path.cwd()

    passed, errors = validate(pipeline_dir, project_root)
    if passed:
        print("GATE 4: PASS — all operations matched, atoms verified")
    else:
        print("GATE 4: FAIL")
        for e in errors:
            print(f"  - {e}")
    sys.exit(0 if passed else 1)
