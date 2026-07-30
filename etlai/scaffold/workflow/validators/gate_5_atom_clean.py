"""Gate 5→6: Validates newly created atoms have no domain leakage and conform to contract.

Checks:
- Every "create" atom in match_results now exists as a file
- Atom source code contains no real business terms from business_mapping.json
- Atom has an execute(params_json) function
- Atom does not import or read business_mapping.json

Usage: python gate_5_atom_clean.py <pipeline_dir> [project_root]
Exit 0 = PASS, Exit 1 = FAIL
"""

import json
import sys
from pathlib import Path

import yaml


def _collect_real_names(mapping: dict) -> set[str]:
    """Extract real business terms from mapping."""
    names = set()

    for col_data in (mapping.get("columns") or {}).values():
        rn = col_data.get("real_name", "")
        if rn and len(rn) > 2:
            names.add(rn.lower())

    for src_data in (mapping.get("sources") or {}).values():
        rn = src_data.get("real_name", "")
        if rn and len(rn) > 2:
            names.add(rn.lower())

    for out_data in (mapping.get("output_columns") or {}).values():
        bn = out_data.get("business_name", "")
        if bn and len(bn) > 2:
            names.add(bn.lower())

    for formula_data in (mapping.get("formulas") or {}).values():
        real_expr = formula_data.get("real_expression", "")
        for token in real_expr.replace("*", " ").replace("/", " ").replace("+", " ").replace("-", " ").split():
            token = token.strip().lower()
            if len(token) > 2 and not token.replace(".", "").isdigit():
                names.add(token)

    return names


def validate(pipeline_dir: Path, project_root: Path) -> tuple[bool, list[str]]:
    errors = []
    match_path = pipeline_dir / "workflow" / "match_results.yaml"
    mapping_path = pipeline_dir / "workflow" / "business_mapping.json"

    if not match_path.exists():
        return False, ["match_results.yaml does not exist"]

    with open(match_path) as f:
        match_data = yaml.safe_load(f)

    # Load business terms for leakage detection
    real_names = set()
    if mapping_path.exists():
        with open(mapping_path) as f:
            mapping = json.load(f)
        real_names = _collect_real_names(mapping)

    matches = (match_data or {}).get("matches") or []
    created = [m for m in matches if m.get("status") == "create"]

    if not created:
        # Nothing to create — pass
        return True, []

    seen_atoms = set()

    for match in created:
        atom_name = match.get("atom_name", "")
        if atom_name in seen_atoms:
            continue
        seen_atoms.add(atom_name)

        atom_path = project_root / "atoms" / f"{atom_name}.py"

        # Check file exists
        if not atom_path.exists():
            errors.append(f"Atom '{atom_name}' marked for creation but atoms/{atom_name}.py not found")
            continue

        source = atom_path.read_text()
        source_lower = source.lower()

        # Check execute function exists
        if "def execute(" not in source:
            errors.append(f"atoms/{atom_name}.py: missing def execute() function")

        # Check params_json parameter
        if "params_json" not in source:
            errors.append(f"atoms/{atom_name}.py: execute() does not accept params_json parameter")

        # Check for business_mapping import/read
        if "business_mapping" in source_lower:
            errors.append(f"atoms/{atom_name}.py: references 'business_mapping' — atoms must not read mapping")

        # Check for domain leakage
        for name in real_names:
            # Skip very short names that could be false positives (matches gate 2 threshold)
            if len(name) <= 2:
                continue
            if name in source_lower:
                # Check if it's in a comment vs actual code
                # Simple heuristic: if the name appears in a non-comment line, flag it
                for line_num, line in enumerate(source.split("\n"), 1):
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    if name in line.lower():
                        errors.append(
                            f"atoms/{atom_name}.py line {line_num}: "
                            f"domain leakage — contains '{name}'"
                        )
                        break

        # Check atom doesn't hardcode file paths
        if "reference/" in source or "inbox/" in source or "pipelines/" in source:
            errors.append(f"atoms/{atom_name}.py: hardcodes folder path — must use params only")

    return len(errors) == 0, errors


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python gate_5_atom_clean.py <pipeline_dir> [project_root]")
        sys.exit(1)

    pipeline_dir = Path(sys.argv[1])
    project_root = Path(sys.argv[2]) if len(sys.argv) > 2 else Path.cwd()

    passed, errors = validate(pipeline_dir, project_root)
    if passed:
        print("GATE 5: PASS — new atoms are clean, domain-agnostic, and conform to contract")
    else:
        print("GATE 5: FAIL")
        for e in errors:
            print(f"  - {e}")
    sys.exit(0 if passed else 1)
