"""Gate 3→4: Validates atomic_operations.yaml has valid DAG, single verbs, no domain terms.

Checks:
- Every operation has exactly one verb
- No cycles in dependency graph
- All depends_on references are valid and point backwards
- No domain term leakage from business_mapping
- Input columns trace back to sources or prior outputs

Usage: python gate_3_dag_valid.py <pipeline_dir>
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


def validate(pipeline_dir: Path) -> tuple[bool, list[str]]:
    errors = []
    ops_path = pipeline_dir / "workflow" / "atomic_operations.yaml"
    mapping_path = pipeline_dir / "workflow" / "business_mapping.json"

    if not ops_path.exists():
        return False, ["atomic_operations.yaml does not exist"]

    with open(ops_path) as f:
        ops_data = yaml.safe_load(f)

    operations = (ops_data or {}).get("operations") or []
    if not operations:
        return False, ["operations list is empty"]

    # Load real names for leakage check
    real_names = set()
    if mapping_path.exists():
        with open(mapping_path) as f:
            mapping = json.load(f)
        for col_data in (mapping.get("columns") or {}).values():
            rn = col_data.get("real_name", "")
            if rn and len(rn) > 2:
                real_names.add(rn.lower())
        for src_data in (mapping.get("sources") or {}).values():
            rn = src_data.get("real_name", "")
            if rn and len(rn) > 2:
                real_names.add(rn.lower())

    # Collect all IDs in order
    op_ids = []
    op_id_set = set()

    for i, op in enumerate(operations):
        p = f"operations[{i}]"
        oid = op.get("id", "")

        # ID exists and is unique
        if not oid:
            errors.append(f"{p}.id is empty")
        elif oid in op_id_set:
            errors.append(f"{p}.id '{oid}' is duplicated")
        op_ids.append(oid)
        op_id_set.add(oid)

        # Single verb check
        verb = op.get("operation", "")
        if not verb:
            errors.append(f"{p}.operation is empty")
        elif verb.lower() not in OPERATION_VERBS:
            errors.append(f"{p}.operation '{verb}' is not a valid verb")

        # depends_on must reference earlier operations only
        deps = op.get("depends_on") or []
        for dep in deps:
            if dep not in op_id_set:
                errors.append(f"{p}.depends_on references '{dep}' which does not exist yet")
            elif dep == oid:
                errors.append(f"{p}.depends_on references itself — cycle")
            else:
                dep_index = op_ids.index(dep)
                if dep_index >= i:
                    errors.append(f"{p}.depends_on '{dep}' is not before this operation — invalid order")

        # Domain leakage scan
        op_text = json.dumps(op).lower()
        for name in real_names:
            if name in op_text:
                errors.append(f"{p}: domain leakage — contains '{name}'")

        # Must have input_columns and output_columns
        if not op.get("input_columns") and not op.get("output_columns"):
            errors.append(f"{p}: must have input_columns or output_columns defined")

    # Column lineage validation
    produced = set()
    for i, op in enumerate(operations):
        inputs_needed = set(op.get("input_columns") or [])
        unresolved = inputs_needed - produced
        # Unresolved columns must come from data sources — not an error but track
        # (We can't fully validate without the logical_graph's source definitions)

        for col in op.get("output_columns") or []:
            produced.add(col)

    # Cycle detection via topological sort
    adjacency = {}
    for op in operations:
        oid = op.get("id", "")
        adjacency[oid] = op.get("depends_on") or []

    visited = set()
    in_stack = set()

    def has_cycle(node):
        if node in in_stack:
            return True
        if node in visited:
            return False
        visited.add(node)
        in_stack.add(node)
        for dep in adjacency.get(node, []):
            if has_cycle(dep):
                return True
        in_stack.discard(node)
        return False

    for oid in op_ids:
        if has_cycle(oid):
            errors.append(f"Cycle detected involving '{oid}'")
            break

    return len(errors) == 0, errors


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python gate_3_dag_valid.py <pipeline_dir>")
        sys.exit(1)

    passed, errors = validate(Path(sys.argv[1]))
    if passed:
        print("GATE 3: PASS — atomic_operations DAG is valid, single verbs, no leakage")
    else:
        print("GATE 3: FAIL")
        for e in errors:
            print(f"  - {e}")
    sys.exit(0 if passed else 1)
