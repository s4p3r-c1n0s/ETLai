"""ETLai CLI — scaffold, validate, and run the pipeline engine."""

import argparse
import fnmatch
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml


def _package_root() -> Path:
    return Path(__file__).resolve().parent


def _scaffold_dir() -> Path:
    return _package_root() / "scaffold"


def cmd_init(args):
    target = Path(args.directory).resolve()
    target.mkdir(parents=True, exist_ok=True)

    scaffold = _scaffold_dir()

    for item in ["etlai.yaml", "dagster.yaml", "definitions.py", "CLAUDE.md", "ORCHESTRATION.md", "HOW_TO_USE_AGENTS.md"]:
        src = scaffold / item
        dst = target / item
        if dst.exists() and not args.force:
            print(f"  skip {item} (exists, use --force to overwrite)")
        else:
            shutil.copy2(src, dst)
            print(f"  wrote {item}")

    # Create directory structure
    for d in ["atoms", "forms"]:
        (target / d).mkdir(exist_ok=True)
        print(f"  created {d}/")

    # Copy workflow directory (validators, phase playbooks, templates)
    scaffold_workflow = scaffold / "workflow"
    if scaffold_workflow.is_dir():
        target_workflow = target / "workflow"
        if target_workflow.exists() and not args.force:
            print("  skip workflow/ (exists, use --force to overwrite)")
        else:
            shutil.copytree(scaffold_workflow, target_workflow, dirs_exist_ok=True)
            print("  wrote workflow/ (validators, phase playbooks, templates)")

    # Copy agents directory (system prompts)
    scaffold_agents = scaffold / "agents"
    if scaffold_agents.is_dir():
        target_agents = target / "agents"
        if target_agents.exists() and not args.force:
            print("  skip agents/ (exists, use --force to overwrite)")
        else:
            shutil.copytree(scaffold_agents, target_agents, dirs_exist_ok=True)
            print("  wrote agents/ (system prompts)")

    # Copy example pipelines
    scaffold_pipelines = scaffold / "pipelines"
    if scaffold_pipelines.is_dir():
        for pipeline_dir in sorted(scaffold_pipelines.iterdir()):
            if not pipeline_dir.is_dir():
                continue
            dest_pipeline = target / "pipelines" / pipeline_dir.name
            dest_pipeline.mkdir(parents=True, exist_ok=True)
            # Copy manifest and config.json if present
            for fname in ["manifest.yaml", "config.json"]:
                src = pipeline_dir / fname
                if src.is_file():
                    dst = dest_pipeline / fname
                    if dst.exists() and not args.force:
                        print(f"  skip pipelines/{pipeline_dir.name}/{fname}")
                    else:
                        shutil.copy2(src, dst)
                        print(f"  wrote pipelines/{pipeline_dir.name}/{fname}")
            # Create lifecycle folders
            for folder in ["inbox", "staging", "processed", "rejected", "output", "reference"]:
                (dest_pipeline / folder).mkdir(exist_ok=True)

    print(f"\nETLai project initialized in {target}")
    print("Next steps:")
    print("  1. Drop CSV files into pipelines/<name>/inbox/")
    print("  2. Run: etlai run")
    print("  3. To add pipelines, open this folder in Claude Code")


def cmd_sync(args):
    project_root = Path(os.getcwd())
    config_path = project_root / "etlai.yaml"
    if not config_path.is_file():
        print("ERROR: No etlai.yaml found. Run 'etlai init' first.")
        sys.exit(1)

    with open(config_path) as f:
        config = yaml.safe_load(f) or {}

    pipelines_root = Path(config.get("pipelines_root", "./pipelines"))
    if not pipelines_root.is_absolute():
        pipelines_root = project_root / pipelines_root

    if not pipelines_root.is_dir():
        print(f"No pipelines directory at {pipelines_root}")
        return

    errors = []
    for manifest_path in sorted(pipelines_root.glob("*/manifest.yaml")):
        with open(manifest_path) as f:
            manifest = yaml.safe_load(f)

        name = manifest.get("name", manifest_path.parent.name)

        # Handle path: ask — prompt user for folder location
        if manifest.get("path") == "ask":
            chosen_path = _ask_folder_path(name)
            if not chosen_path:
                errors.append(f"{name}: folder selection cancelled")
                continue
            manifest["path"] = chosen_path
            with open(manifest_path, "w") as f:
                yaml.safe_dump(manifest, f, default_flow_style=False, sort_keys=False)
            print(f"  SET {name} path → {chosen_path}")

        # Determine data root for this pipeline
        pipeline_data_root = Path(manifest["path"]) if manifest.get("path") else manifest_path.parent
        if not pipeline_data_root.is_absolute():
            pipeline_data_root = project_root / pipeline_data_root

        # Create lifecycle folders
        for folder in ["inbox", "staging", "processed", "rejected", "output", "reference"]:
            (pipeline_data_root / folder).mkdir(parents=True, exist_ok=True)

        # Validate atom reference
        atoms_to_check = []
        if "steps" in manifest:
            for step in manifest["steps"]:
                atoms_to_check.append(step["atom"])
                if step.get("form") and step["form"] != "passthrough":
                    _check_form(step["form"], project_root, name, errors)
        else:
            atoms_to_check.append(manifest["atom"])
            form = manifest.get("form", "passthrough")
            if form != "passthrough":
                _check_form(form, project_root, name, errors)

        for atom_name in atoms_to_check:
            _check_atom(atom_name, project_root, name, errors)

        # Validate env file if specified
        env_file = manifest.get("env_file")
        requires_env = manifest.get("requires_env", [])
        if env_file and requires_env:
            from etlai.helpers.env_loader import validate_env_vars
            missing = validate_env_vars(env_file, requires_env)
            if missing:
                errors.append(f"{name}: env file '{env_file}' missing vars: {', '.join(missing)}")
        elif env_file:
            env_path = Path(env_file).expanduser().resolve()
            if not env_path.is_file():
                errors.append(f"{name}: env file not found: {env_file}")

        # Handle inputs: field — validate and generate README
        inputs_def = manifest.get("inputs")
        if inputs_def:
            _validate_inputs(inputs_def, name, pipeline_data_root, errors)
            _generate_pipeline_readme(manifest, inputs_def, pipeline_data_root)

            # Auto-calculate min_files from transient inputs if not explicitly set
            if "min_files" not in manifest:
                transient_count = sum(1 for inp in inputs_def if inp.get("role") == "transient")
                manifest["_effective_min_files"] = transient_count

        print(f"  OK  {name} ({len(atoms_to_check)} atom(s))")

    if errors:
        print(f"\n{len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("\nAll pipelines valid.")


def _ask_folder_path(pipeline_name: str) -> str | None:
    """Open a Tkinter folder picker for the pipeline's data root."""
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    folder = filedialog.askdirectory(
        title=f"Select data folder for pipeline: {pipeline_name}",
        mustexist=False,
    )

    root.destroy()
    return folder if folder else None


def _check_atom(atom_name: str, project_root: Path, pipeline_name: str, errors: list):
    user_path = project_root / "atoms" / f"{atom_name}.py"
    if user_path.is_file():
        return
    try:
        import importlib
        importlib.import_module(f"etlai.atoms.{atom_name}")
    except ImportError:
        errors.append(f"{pipeline_name}: atom '{atom_name}' not found in atoms/ or etlai.atoms")


def _check_form(form_name: str, project_root: Path, pipeline_name: str, errors: list):
    user_path = project_root / "forms" / f"{form_name}.py"
    if user_path.is_file():
        return
    try:
        import importlib
        importlib.import_module(f"etlai.forms.{form_name}")
    except ImportError:
        errors.append(f"{pipeline_name}: form '{form_name}' not found in forms/ or etlai.forms")


def _validate_inputs(inputs_def: list[dict], pipeline_name: str, data_root: Path, errors: list):
    """Validate inputs declarations and check file placement."""
    for inp in inputs_def:
        name = inp.get("name")
        role = inp.get("role")
        description = inp.get("description")

        if not name:
            errors.append(f"{pipeline_name}: input missing required 'name' field")
            continue
        if role not in ("transient", "reference"):
            errors.append(f"{pipeline_name}: input '{name}' has invalid role '{role}' (must be transient or reference)")
            continue
        if not description:
            errors.append(f"{pipeline_name}: input '{name}' missing required 'description' field")
            continue

        # Check reference files exist
        if role == "reference":
            ref_dir = data_root / "reference"
            pattern = inp.get("pattern")
            if ref_dir.is_dir():
                ref_files = list(ref_dir.iterdir())
                if pattern:
                    matched = [f for f in ref_files if fnmatch.fnmatch(f.name, pattern)]
                    if not matched:
                        print(f"  WARN {pipeline_name}: reference input '{name}' — no files matching '{pattern}' in reference/")
                elif not ref_files:
                    print(f"  WARN {pipeline_name}: reference input '{name}' — reference/ folder is empty")
            else:
                print(f"  WARN {pipeline_name}: reference input '{name}' — reference/ folder does not exist")

        # Check transient file patterns in inbox
        if role == "transient" and inp.get("pattern"):
            inbox_dir = data_root / "inbox"
            if inbox_dir.is_dir():
                inbox_files = list(inbox_dir.iterdir())
                matched = [f for f in inbox_files if fnmatch.fnmatch(f.name, inp["pattern"])]
                if matched:
                    print(f"  INFO {pipeline_name}: transient input '{name}' — {len(matched)} file(s) in inbox matching '{inp['pattern']}'")


def _generate_pipeline_readme(manifest: dict, inputs_def: list[dict], data_root: Path):
    """Generate PIPELINE_README.md from manifest inputs metadata."""
    name = manifest.get("name", "unknown")

    # Build step description
    if "steps" in manifest:
        steps_desc = " -> ".join(s["atom"] for s in manifest["steps"])
    else:
        steps_desc = manifest.get("atom", "unknown")

    lines = [
        f"# {name}",
        "",
        f"**Processing:** {steps_desc}",
        "",
        "## Input Files",
        "",
        "| Name | Folder | Role | Pattern | Description |",
        "|------|--------|------|---------|-------------|",
    ]

    for inp in inputs_def:
        folder = "inbox/" if inp["role"] == "transient" else "reference/"
        pattern = inp.get("pattern", "—")
        lines.append(f"| {inp['name']} | `{folder}` | {inp['role']} | `{pattern}` | {inp['description']} |")

    lines.append("")
    lines.append("## Folder Layout")
    lines.append("")
    lines.append("```")
    lines.append(f"{name}/")
    lines.append("  inbox/       <- Drop transient input files here (processed once, then moved)")
    lines.append("  reference/   <- Place permanent lookup/reference files here (never moved)")
    lines.append("  staging/     <- In-flight (managed by framework)")
    lines.append("  processed/   <- Successfully consumed transient files")
    lines.append("  rejected/    <- Failed files + error logs")
    lines.append("  output/      <- Transformation results")
    lines.append("```")
    lines.append("")
    lines.append("## Workflow")
    lines.append("")

    ref_inputs = [inp for inp in inputs_def if inp["role"] == "reference"]
    transient_inputs = [inp for inp in inputs_def if inp["role"] == "transient"]

    step_num = 1
    if ref_inputs:
        ref_names = ", ".join(f"`{inp['name']}`" for inp in ref_inputs)
        lines.append(f"{step_num}. Place reference files ({ref_names}) in `reference/` (one-time setup)")
        step_num += 1
    if transient_inputs:
        trans_names = ", ".join(f"`{inp['name']}`" for inp in transient_inputs)
        lines.append(f"{step_num}. Drop transient files ({trans_names}) into `inbox/`")
        step_num += 1
    lines.append(f"{step_num}. Pipeline triggers automatically when files are detected")
    step_num += 1
    lines.append(f"{step_num}. Results appear in `output/`; input files move to `processed/`")
    lines.append("")

    readme_path = data_root / "PIPELINE_README.md"
    readme_path.write_text("\n".join(lines))
    print(f"  WROTE {readme_path.relative_to(data_root.parent) if data_root.parent != data_root else readme_path}")


def cmd_create(args):
    from etlai.orchestrator import Orchestrator, sanitize_pipeline_name

    project_root = Path(os.getcwd())
    config_path = project_root / "etlai.yaml"
    if not config_path.is_file():
        print("ERROR: No etlai.yaml found. Run 'etlai init' first.")
        sys.exit(1)

    user_request = args.request
    pipeline_name = args.name or sanitize_pipeline_name(user_request)

    orch = Orchestrator(project_root=project_root, pipeline_name=pipeline_name)
    workflow_dir = orch.initialize()

    print(f"Pipeline: {pipeline_name}")
    print(f"Workflow dir: {workflow_dir}")
    print(f"Request: {user_request}")
    print()

    # Phase 0-1: Business Analyst
    print("=" * 60)
    print("PHASE 0-1: Business Analyst")
    print("=" * 60)
    context = orch.build_agent_context("business_analyst")
    print(f"  System prompt: {context['system_prompt']}")
    print(f"  Output: {context['writable_paths'][0]}")
    print()
    print("  Waiting for Business Analyst to produce pipeline_graph.yaml...")
    print("  (In Claude Code: the BA agent loops with the user until confirmed)")
    print()

    # Gate 1
    gate1 = orch.run_gate(1)
    if not gate1:
        print(f"  GATE 1: FAIL")
        print(gate1.error_summary())
        print("  Fix errors in pipeline_graph.yaml and re-run 'etlai create'")
        sys.exit(1)
    print(f"  GATE 1: PASS")
    print()

    # Phase 2-3: Separator
    print("=" * 60)
    print("PHASE 2-3: Separator")
    print("=" * 60)
    context = orch.build_agent_context("separator")
    print(f"  System prompt: {context['system_prompt']}")
    print(f"  Input: pipeline_graph.yaml")
    print(f"  Output: logical_graph.yaml, business_mapping.json, atomic_operations.yaml")
    print()

    # Gates 2+3
    for gate_num in (2, 3):
        result = orch.run_gate(gate_num)
        if not result:
            print(f"  GATE {gate_num}: FAIL")
            print(result.error_summary())
            sys.exit(1)
        print(f"  GATE {gate_num}: PASS")
    print()

    # Phase 4-5: Atom Smith (FIREWALL)
    print("=" * 60)
    print("PHASE 4-5: Atom Smith (FIREWALL ACTIVE)")
    print("=" * 60)
    firewall_activated = orch.activate_firewall()
    if firewall_activated:
        print("  FIREWALL: business_mapping.json hidden from Atom Smith")
    context = orch.build_agent_context("atom_smith")
    print(f"  System prompt: {context['system_prompt']}")
    print(f"  Input: atomic_operations.yaml ONLY")
    print(f"  Output: match_results.yaml + any new atoms")
    print()

    # Gates 4+5
    for gate_num in (4, 5):
        result = orch.run_gate(gate_num)
        if not result:
            print(f"  GATE {gate_num}: FAIL")
            print(result.error_summary())
            orch.deactivate_firewall()
            sys.exit(1)
        print(f"  GATE {gate_num}: PASS")

    orch.deactivate_firewall()
    print("  FIREWALL: business_mapping.json restored")
    print()

    # Phase 6-7: Assembler
    print("=" * 60)
    print("PHASE 6-7: Assembler")
    print("=" * 60)
    context = orch.build_agent_context("assembler")
    print(f"  System prompt: {context['system_prompt']}")
    print(f"  Input: all four artifacts + business_mapping")
    print(f"  Output: manifest.yaml + config.json")
    print()

    # Gate 6
    gate6 = orch.run_gate(6)
    if not gate6:
        print(f"  GATE 6: FAIL")
        print(gate6.error_summary())
        sys.exit(1)
    print(f"  GATE 6: PASS")
    print()

    # Success
    print("=" * 60)
    print(f"SUCCESS: Pipeline '{pipeline_name}' created!")
    print("=" * 60)
    print()
    print("Next steps:")
    print(f"  1. Run: etlai sync")
    print(f"  2. Drop files into pipelines/{pipeline_name}/inbox/")
    print(f"  3. Run: etlai run")


def cmd_run(args):
    os.environ.setdefault("DAGSTER_HOME", os.getcwd())
    cmd = [sys.executable, "-m", "dagster", "dev", "-m", "definitions"]
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        pass


def cmd_list(args):
    project_root = Path(os.getcwd())
    config_path = project_root / "etlai.yaml"
    if not config_path.is_file():
        print("ERROR: No etlai.yaml found. Run 'etlai init' first.")
        sys.exit(1)

    with open(config_path) as f:
        config = yaml.safe_load(f) or {}

    pipelines_root = Path(config.get("pipelines_root", "./pipelines"))
    if not pipelines_root.is_absolute():
        pipelines_root = project_root / pipelines_root

    if not pipelines_root.is_dir():
        print("No pipelines found.")
        return

    print(f"{'Pipeline':<30} {'Atom(s)':<25} {'Form(s)':<25} {'Files'}")
    print("-" * 90)

    for manifest_path in sorted(pipelines_root.glob("*/manifest.yaml")):
        with open(manifest_path) as f:
            manifest = yaml.safe_load(f)

        name = manifest.get("name", "?")
        min_files = manifest.get("min_files", 1)

        if "steps" in manifest:
            atoms = ", ".join(s["atom"] for s in manifest["steps"])
            forms = ", ".join(s.get("form", "passthrough") for s in manifest["steps"])
        else:
            atoms = manifest.get("atom", "?")
            forms = manifest.get("form", "passthrough")

        print(f"{name:<30} {atoms:<25} {forms:<25} {min_files}")


def main():
    parser = argparse.ArgumentParser(prog="etlai", description="ETLai — local CSV transformation engine")
    sub = parser.add_subparsers(dest="command")

    init_p = sub.add_parser("init", help="Scaffold a new ETLai project")
    init_p.add_argument("directory", nargs="?", default=".", help="Target directory (default: current)")
    init_p.add_argument("--force", action="store_true", help="Overwrite existing files")

    create_p = sub.add_parser("create", help="Create a pipeline using the 5-agent system")
    create_p.add_argument("request", help="Business request describing the pipeline to build")
    create_p.add_argument("--name", help="Pipeline name (auto-generated if omitted)")

    sub.add_parser("sync", help="Validate manifests and create missing folders")
    sub.add_parser("run", help="Start Dagster dev server")
    sub.add_parser("list", help="List registered pipelines")

    args = parser.parse_args()
    if args.command == "init":
        cmd_init(args)
    elif args.command == "create":
        cmd_create(args)
    elif args.command == "sync":
        cmd_sync(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "list":
        cmd_list(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
