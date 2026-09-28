"""Check four host-visible skill paths against one installed release."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


SKILLS = ("legal-case", "legal-vocab", "legal-preprocess", "legal-initialize")
COMMANDS = ("legal-case", "legal-vocab", "legal-preprocess")
REFERENCES = ("case-cli.md", "vocab-cli.md", "preprocess-cli.md", "data-formats.md")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-root", type=Path, required=True)
    parser.add_argument("--skill", action="append", required=True, help="NAME=host-visible SKILL.md path; repeat for all four")
    args = parser.parse_args()
    try:
        root = args.install_root.expanduser().resolve(strict=True)
        runtime = json.loads((root / "runtime.json").read_text(encoding="utf-8"))
        if type(runtime) is not dict or set(runtime) != {"format_version", "release_version", "install_root", "environment_root", "python", "commands"}:
            raise ValueError("runtime.json fields are incomplete or unexpected")
        if type(runtime["format_version"]) is not int or runtime["format_version"] != 1:
            raise ValueError("runtime.json format_version must be integer 1")
        if type(runtime["release_version"]) is not str or not runtime["release_version"]:
            raise ValueError("runtime.json release_version is missing")
        if runtime["install_root"] != str(root):
            raise ValueError("runtime.json belongs to another installation root")
        environment = root / ".venv"
        if Path(runtime["environment_root"]).resolve() != environment.resolve():
            raise ValueError("runtime.json environment_root is not this installation's .venv")
        python = Path(runtime["python"])
        if not python.is_absolute() or not python.is_file() or not os.access(python, os.X_OK) or not python.absolute().is_relative_to(environment.absolute()):
            raise ValueError("runtime.json Python is not in this installation's .venv")
        if type(runtime["commands"]) is not dict or set(runtime["commands"]) != set(COMMANDS):
            raise ValueError("runtime.json must contain exactly three command paths")
        registered: dict[str, Path] = {}
        for entry in args.skill:
            name, separator, path = entry.partition("=")
            if not separator or name not in SKILLS or name in registered:
                raise ValueError(f"invalid or repeated --skill value: {entry}")
            registered[name] = Path(path).expanduser().resolve(strict=True)
        if set(registered) != set(SKILLS):
            raise ValueError("provide the host-visible paths of all four skills")
        for name, path in registered.items():
            expected = root / "skills" / name / "SKILL.md"
            if path != expected.resolve(strict=True) or not path.is_file():
                raise ValueError(f"{name} does not resolve to the installed skill")
            if not (path.parent / ".." / ".." / "README.md").is_file():
                raise ValueError(f"{name} cannot reach the installed README")
            if not (path.parent / ".." / ".." / "runtime.json").is_file():
                raise ValueError(f"{name} cannot reach runtime.json")
        for name in REFERENCES:
            if not (root / "references" / name).is_file():
                raise ValueError(f"shared reference missing: {name}")
        for name, command in runtime["commands"].items():
            path = Path(command)
            if not path.is_absolute() or not path.is_file() or not os.access(path, os.X_OK) or not path.resolve().is_relative_to(environment.resolve()):
                raise ValueError(f"installed command unavailable: {name}")
            process_environment = os.environ.copy()
            for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
                process_environment.pop(key, None)
            result = subprocess.run([str(path), "--help"], cwd=root, env=process_environment, capture_output=True, text=True, check=False)
            if result.returncode:
                raise ValueError(f"installed command failed: {name}: {result.stderr.strip()}")
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "host_registration": "verified", "install_root": str(root), "skills": list(SKILLS)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
