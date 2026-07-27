"""Gate 1→2: Validates pipeline_graph.yaml is structurally complete and confirmed.

Usage: python gate_1_graph_complete.py <pipeline_dir>
Exit 0 = PASS, Exit 1 = FAIL
"""

import sys
from pathlib import Path

import yaml


def validate(pipeline_dir: Path) -> tuple[bool, list[str]]:
    errors = []
    graph_path = pipeline_dir / "workflow" / "pipeline_graph.yaml"

    if not graph_path.exists():
        return False, ["pipeline_graph.yaml does not exist"]

    with open(graph_path) as f:
        graph = yaml.safe_load(f)

    if not graph:
        return False, ["pipeline_graph.yaml is empty"]

    # Owner confirmation
    if not graph.get("owner_confirmed"):
        errors.append("owner_confirmed is not true")

    # Name and description
    if not graph.get("name"):
        errors.append("name is empty")
    if not graph.get("description"):
        errors.append("description is empty")

    # Data sources
    sources = graph.get("data_sources") or []
    if not sources:
        errors.append("data_sources is empty")

    FORBIDDEN = {"unknown", "tbd", "tbc", ""}
    for i, src in enumerate(sources):
        p = f"data_sources[{i}]"
        for field in ["name", "description", "retrieval", "frequency", "format", "role"]:
            val = str(src.get(field, "")).strip().lower()
            if val in FORBIDDEN:
                errors.append(f"{p}.{field} is empty or unknown")
        if not src.get("fields"):
            errors.append(f"{p}.fields is empty")
        for j, fld in enumerate(src.get("fields") or []):
            if not fld.get("name"):
                errors.append(f"{p}.fields[{j}].name is empty")
            if not fld.get("type"):
                errors.append(f"{p}.fields[{j}].type is empty")

    # Nodes
    nodes = graph.get("nodes") or []
    if not nodes:
        errors.append("nodes is empty")

    node_ids = set()
    for i, node in enumerate(nodes):
        p = f"nodes[{i}]"
        nid = node.get("id", "")
        if not nid:
            errors.append(f"{p}.id is empty")
        elif nid in node_ids:
            errors.append(f"{p}.id '{nid}' is duplicated")
        node_ids.add(nid)

        for field in ["operation", "description"]:
            val = str(node.get(field, "")).strip().lower()
            if val in FORBIDDEN:
                errors.append(f"{p}.{field} is empty or unknown")
        if not node.get("inputs"):
            errors.append(f"{p}.inputs is empty")
        if not node.get("outputs"):
            errors.append(f"{p}.outputs is empty")

    # Edges
    edges = graph.get("edges") or []
    if not edges:
        errors.append("edges is empty")

    source_names = {s.get("name") for s in sources}
    valid_from = node_ids | source_names
    for i, edge in enumerate(edges):
        frm = edge.get("from", "")
        to = edge.get("to", "")
        if frm not in valid_from:
            errors.append(f"edges[{i}].from '{frm}' is not a valid node or source")
        if to not in node_ids:
            errors.append(f"edges[{i}].to '{to}' is not a valid node")

    # Orphan check: every node must be reachable via edges
    connected = set()
    for edge in edges:
        connected.add(edge.get("from", ""))
        connected.add(edge.get("to", ""))
    orphans = node_ids - connected
    if orphans:
        errors.append(f"Orphan nodes (not connected by any edge): {sorted(orphans)}")

    # Triggers
    triggers = graph.get("triggers") or []
    if not triggers:
        errors.append("triggers is empty")

    # Output
    output = graph.get("output") or {}
    if not output.get("description"):
        errors.append("output.description is empty")
    if not output.get("fields"):
        errors.append("output.fields is empty")

    return len(errors) == 0, errors


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python gate_1_graph_complete.py <pipeline_dir>")
        sys.exit(1)

    passed, errors = validate(Path(sys.argv[1]))
    if passed:
        print("GATE 1: PASS — pipeline_graph.yaml is complete and confirmed")
    else:
        print("GATE 1: FAIL")
        for e in errors:
            print(f"  - {e}")
    sys.exit(0 if passed else 1)
