"""ETLai CLI — scaffold, validate, and run the pipeline engine."""

import argparse
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

    for item in ["etlai.yaml", "dagster.yaml", "definitions.py", "CLAUDE.md"]:
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

    sub.add_parser("sync", help="Validate manifests and create missing folders")
    sub.add_parser("run", help="Start Dagster dev server")
    sub.add_parser("list", help="List registered pipelines")

    args = parser.parse_args()
    if args.command == "init":
        cmd_init(args)
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
