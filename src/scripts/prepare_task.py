"""Host-only preparation; runtime bootstrap uses only the standard library."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


class BootstrapError(Exception):
    def __init__(self, code, path, message, file=None):
        self.item = dict(code=code, path=path, message=message)
        if file is not None:
            self.item["file"] = str(file)


def reject(code, path, message, file=None):
    raise BootstrapError(code, path, message, file)


def pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


def strict_json(data):
    def bad(value):
        raise ValueError("non-standard JSON number: " + value)
    value = json.loads(data, object_pairs_hook=pairs, parse_constant=bad)
    json.dumps(value, allow_nan=False)
    return value


def absolute(value, path):
    if not isinstance(value, str) or not Path(value).is_absolute() or "\x00" in value:
        reject("INVALID_ARGUMENT", path, "absolute path required")
    return Path(value)


def runtime(data):
    if type(data) is not dict or set(data) != {"format_version", "skill_file", "workspace_root"}:
        reject("INVALID_ARGUMENT", "", "runtime requires format_version, skill_file and workspace_root")
    if type(data["format_version"]) is not int or data["format_version"] != 1:
        reject("UNSUPPORTED_VERSION", "/format_version", "only version 1 supported")
    skill = absolute(data["skill_file"], "/skill_file").resolve(strict=True)
    root = skill.parent.parent.parent
    if skill.name != "SKILL.md" or skill.parent.name not in {"legal-case", "legal-vocab", "legal-preprocess", "legal-initialize"}:
        reject("INVALID_ARGUMENT", "/skill_file", "installed skill entry required")
    workspace = absolute(data["workspace_root"], "/workspace_root").resolve(strict=True)
    if not workspace.is_dir():
        reject("INVALID_ARGUMENT", "/workspace_root", "workspace must be a directory")
    file = root / "runtime.json"
    try:
        info = strict_json(file.read_bytes().decode("utf-8"))
    except ValueError as exc:
        reject("INVALID_ARGUMENT", "", str(exc), file)
    keys = {"format_version", "release_version", "install_root", "environment_root", "python", "commands"}
    if type(info) is not dict or set(info) != keys:
        reject("INVALID_ARGUMENT", "", "runtime fields incomplete or unexpected", file)
    if type(info["format_version"]) is not int or info["format_version"] != 1:
        reject("UNSUPPORTED_VERSION", "/format_version", "unsupported runtime", file)
    if not isinstance(info["release_version"], str) or not info["release_version"].strip():
        reject("INVALID_ARGUMENT", "/release_version", "version required", file)
    environment = root / ".venv"
    if info["install_root"] != str(root) or info["environment_root"] != str(environment):
        reject("INVALID_ARGUMENT", "/install_root", "runtime belongs to another installation", file)
    commands = info["commands"]
    if type(commands) is not dict or set(commands) != {"legal-case", "legal-vocab", "legal-preprocess"}:
        reject("INVALID_ARGUMENT", "/commands", "exactly three commands required", file)
    for at, value in [("/python", info["python"]), *[("/commands/" + k, v) for k, v in commands.items()]]:
        tool = absolute(value, at)
        # Preserve the venv launcher path, which may link to a base Python.
        if not tool.absolute().is_relative_to(environment) or not tool.is_file() or not os.access(tool, os.X_OK):
            reject("FILE_ERROR", at, "executable must be inside the bound environment", file)
        if at != "/python" and not tool.resolve().is_relative_to(environment.resolve()):
            reject("INVALID_ARGUMENT", at, "command points outside environment", file)
    env = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        env.pop(key, None)
    probe = subprocess.run([info["python"], "-c", "import json,sys,legal; print(json.dumps([sys.prefix,legal.__version__,legal.__file__,list(sys.version_info[:2])]))"],
                           cwd=root, env=env, capture_output=True, text=True, check=False)
    if probe.returncode:
        reject("FILE_ERROR", "/python", f"bound interpreter probe failed ({probe.returncode}): {probe.stdout}\n{probe.stderr}", file)
    prefix, release, module, python_version = strict_json(probe.stdout)
    if Path(prefix).resolve() != environment.resolve() or release != info["release_version"] or not Path(module).resolve().is_relative_to(environment.resolve()) or python_version[0] != 3 or not 11 <= python_version[1] < 14:
        reject("INVALID_ARGUMENT", "/release_version", "installed package or interpreter differs from runtime", file)
    return {"ok": True, "operation": "runtime", "files": [], "result": {
        "install_root": str(root), "release_version": release, "python": info["python"], "commands": commands,
        "workspace_root": str(workspace), "workspaces_file": str(root / "workspaces.json")}}


class Parser(argparse.ArgumentParser):
    def error(self, message):
        reject("INVALID_ARGUMENT", "/arguments", message)


class Single(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if getattr(namespace, self.dest, None) is not None:
            reject("INVALID_ARGUMENT", option_string, "single input repeated")
        setattr(namespace, self.dest, values)


def main():
    try:
        parser = Parser(description=__doc__, allow_abbrev=False)
        parser.add_argument("operation", choices=("runtime", "case", "reading", "synthesis", "tagging", "extraction"))
        parser.add_argument("--input", required=True, action=Single)
        args = parser.parse_args()
        raw = sys.stdin.buffer.read() if args.input == "-" else absolute(args.input, "--input").read_bytes()
        data = strict_json(raw.decode("utf-8"))
        if args.operation == "runtime":
            result = runtime(data)
        else:
            from legal.task_preparation import prepare
            result = prepare(args.operation, data, Path(__file__).resolve().parent.parent)
        code = 0
    except BootstrapError as exc:
        result, code = {"ok": False, "scope": "task_files", "errors": [exc.item]}, 2
    except Exception as exc:
        # Imported validation exceptions provide the same diagnostics as bootstrap.
        item = getattr(exc, "item", None)
        items = [item() if callable(item) else item] if item is not None else getattr(exc, "items", [
            {"code": "FILE_ERROR" if isinstance(exc, (OSError, ImportError)) else "INVALID_ARGUMENT", "path": "", "message": str(exc)}])
        result, code = {"ok": False, "scope": "task_files", "errors": items}, 2
        remaining = getattr(exc, "remaining_paths", None)
        if remaining:
            result["remaining_paths"] = remaining
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
