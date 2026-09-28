"""Install one release into a dedicated environment and publish runtime.json."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1]
SKILLS = ("legal-case", "legal-vocab", "legal-preprocess", "legal-initialize")
COMMANDS = ("legal-case", "legal-vocab", "legal-preprocess")
REFERENCES = ("case-cli.md", "vocab-cli.md", "preprocess-cli.md", "data-formats.md")
MARKER = ".cogengine-legal-environment"
ROOT_MARKER = ".cogengine-legal-install"


def owned(path: Path) -> bool:
    return path.is_file() and not path.is_symlink() and path.read_text(encoding="utf-8") == "cogengine-legal\n"


def run(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    for name in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        environment.pop(name, None)
    result = subprocess.run(args, cwd=cwd, env=environment, text=True, capture_output=True, check=False)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"command failed ({result.returncode}): {args[0]}: {detail}")
    return result


def project_version() -> tuple[str, str]:
    project = tomllib.loads((SOURCE / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    version = project["version"]
    required = project["requires-python"]
    init = (SOURCE / "legal" / "__init__.py").read_text(encoding="utf-8")
    if f'__version__ = "{version}"' not in init:
        raise RuntimeError("pyproject version and legal.__version__ differ")
    return version, required


def check_interpreter(python: Path, required: str) -> None:
    if not python.is_file() or not os.access(python, os.X_OK):
        raise RuntimeError(f"Python interpreter unavailable: {python}")
    probe = run([str(python), "-c", "import json,sqlite3,sys,venv; print(json.dumps(list(sys.version_info[:3])))"])
    major, minor, _ = json.loads(probe.stdout)
    # The project currently declares >=3.11,<3.14. Fail closed if that changes.
    if required != ">=3.11,<3.14" or major != 3 or not 11 <= minor < 14:
        raise RuntimeError(f"unsupported Python {major}.{minor}; project requires {required}")
    run([str(python), "-m", "pip", "--version"])


def wheel_version(path: Path, release: str) -> None:
    expected = f"cogengine_legal-{release}-"
    if not path.is_file() or not path.name.startswith(expected) or path.suffix != ".whl":
        raise RuntimeError(f"expected a cogengine-legal {release} wheel: {path}")


def environment_python(root: Path) -> Path:
    candidates = (root / "bin" / "python", root / "Scripts" / "python.exe")
    for path in candidates:
        if path.is_file():
            return path.absolute()
    raise RuntimeError(f"environment Python missing under {root}")


def check_environment(python: Path, environment: Path) -> None:
    result = run([str(python), "-c", "import json,sys; print(json.dumps([sys.prefix,sys.base_prefix]))"])
    prefix, base = json.loads(result.stdout)
    if Path(prefix).resolve() != environment.resolve() or Path(prefix).resolve() == Path(base).resolve():
        raise RuntimeError("Python is not bound to the dedicated .venv")


def command_paths(environment: Path) -> dict[str, str]:
    directory = environment / ("Scripts" if os.name == "nt" else "bin")
    result: dict[str, str] = {}
    for name in COMMANDS:
        candidates = (directory / name, directory / f"{name}.exe")
        command = next((path for path in candidates if path.is_file() and os.access(path, os.X_OK)), None)
        if command is None:
            raise RuntimeError(f"installed command missing: {name}")
        result[name] = str(command.absolute())
    return result


def inspect_package(python: Path, environment: Path, version: str, cwd: Path) -> None:
    script = (
        "import importlib.metadata as m, json, legal, pathlib; "
        "p=pathlib.Path(legal.__file__); "
        "print(json.dumps([m.version('cogengine-legal'),legal.__version__,str(p),"
        "(p.parent/'schema.sql').is_file(),(p.parent/'config'/'units.v1.json').is_file()]))"
    )
    result = run([str(python), "-c", script], cwd=cwd)
    installed, imported, location, schema, units = json.loads(result.stdout)
    if installed != version or imported != version or not schema or not units:
        raise RuntimeError("installed package version or resources do not match delivery")
    if not Path(location).resolve().is_relative_to(environment.resolve()):
        raise RuntimeError(f"package imported from unexpected location: {location}")


def smoke_check(commands: dict[str, str], python: Path, root: Path, cwd: Path) -> None:
    for command in commands.values():
        run([command, "--help"], cwd=cwd)
    vocabulary = cwd / "vocabulary.json"
    database = cwd / "contract.sqlite"
    run([commands["legal-vocab"], "init", "--vocabulary", str(vocabulary)], cwd=cwd)
    run([commands["legal-case"], "init", "--db", str(database), "--vocabulary", str(vocabulary)], cwd=cwd)
    run([commands["legal-case"], "query", "--db", str(database), "--view", "progress"], cwd=cwd)
    if not database.is_file() or not vocabulary.is_file():
        raise RuntimeError("temporary package initialization did not create expected files")
    check_environment(python, root / ".venv")


def temporary_parent(root: Path) -> Path:
    for candidate in (Path(tempfile.gettempdir()), Path("/var/tmp"), Path.home()):
        if candidate.is_dir() and not candidate.resolve().is_relative_to(root) and not candidate.resolve().is_relative_to(SOURCE):
            return candidate
    raise RuntimeError("no temporary location outside installation and source roots")


def copy_delivery(root: Path) -> None:
    if (root / "skills").is_symlink() or (root / "references").is_symlink() or (root / "README.md").is_symlink():
        raise RuntimeError("refusing to replace linked installation resources")
    for name in REFERENCES:
        if (root / "references" / name).is_symlink():
            raise RuntimeError(f"refusing to replace linked reference: {name}")
    for name in SKILLS:
        if (root / "skills" / name).is_symlink():
            raise RuntimeError(f"refusing to replace linked skill: {name}")
    for name in SKILLS:
        source = SOURCE / "skills" / name
        target = root / "skills" / name
        if target.is_symlink():
            raise RuntimeError(f"refusing to replace skill symlink: {target}")
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
    refs = root / "references"
    if refs.is_symlink():
        raise RuntimeError(f"refusing to replace references symlink: {refs}")
    refs.mkdir(exist_ok=True)
    for name in REFERENCES:
        shutil.copy2(SOURCE / "references" / name, refs / name)
    if (root / "README.md").is_symlink():
        raise RuntimeError("refusing to replace README symlink")
    shutil.copy2(SOURCE / "README.md", root / "README.md")


def publish_runtime(root: Path, environment: Path, python: Path, commands: dict[str, str], version: str) -> None:
    payload = {
        "format_version": 1,
        "release_version": version,
        "install_root": str(root.resolve()),
        "environment_root": str(environment.resolve()),
        "python": str(python.absolute()),
        "commands": commands,
    }
    file_descriptor, temporary = tempfile.mkstemp(prefix=".runtime-", suffix=".json", dir=root)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, root / "runtime.json")
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-root", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True, help="Absolute path of the selected base interpreter")
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--upgrade", action="store_true", help="Explicitly replace an older package and matching skill files")
    parser.add_argument("--repair", action="store_true", help="Explicitly rebuild this project's damaged .venv")
    args = parser.parse_args()
    root = args.install_root.expanduser().resolve()
    python = args.python.expanduser().absolute()
    wheel = args.wheel.expanduser().resolve()
    try:
        if not args.python.expanduser().is_absolute():
            raise RuntimeError("--python must be an absolute interpreter path")
        if root == Path("/") or root == SOURCE or root.is_relative_to(SOURCE):
            raise RuntimeError("installation root must be outside the delivery source")
        version, required = project_version()
        wheel_version(wheel, version)
        check_interpreter(python, required)
        if root.exists() and not root.is_dir():
            raise RuntimeError(f"installation root is not a directory: {root}")
        root.mkdir(parents=True, exist_ok=True)
        root_marker = root / ROOT_MARKER
        if root_marker.is_symlink():
            raise RuntimeError("refusing linked installation marker")
        environment = root / ".venv"
        if environment.is_symlink():
            raise RuntimeError("refusing linked .venv")
        if environment.exists() and not owned(environment / MARKER) and not (args.repair and owned(root_marker)):
            raise RuntimeError(f"refusing to take over an unrecognized environment: {environment}")
        if args.repair and environment.exists():
            if not owned(root_marker) and not owned(environment / MARKER):
                raise RuntimeError("refusing to repair an unrecognized environment")
            runtime = root / "runtime.json"
            if runtime.is_symlink():
                raise RuntimeError("refusing to replace runtime.json symlink")
            if runtime.is_file():
                prior = json.loads(runtime.read_text(encoding="utf-8"))
                if prior.get("install_root") != str(root):
                    raise RuntimeError("runtime.json belongs to another installation root")
                if prior.get("release_version") != version and not args.upgrade:
                    raise RuntimeError("repair of another release requires --upgrade")
                runtime.unlink()
            shutil.rmtree(environment)
        if not owned(root_marker):
            if root_marker.exists():
                raise RuntimeError("unrecognized installation marker")
            root_marker.write_text("cogengine-legal\n", encoding="utf-8")
        if not environment.exists():
            run([str(python), "-m", "venv", str(environment)])
            (environment / MARKER).write_text("cogengine-legal\n", encoding="utf-8")
        bound_python = environment_python(environment)
        check_environment(bound_python, environment)
        existing = root / "runtime.json"
        if existing.is_symlink():
            raise RuntimeError("refusing to replace runtime.json symlink")
        if existing.is_file():
            prior = json.loads(existing.read_text(encoding="utf-8"))
            if prior.get("install_root") != str(root):
                raise RuntimeError("runtime.json belongs to another installation root")
            if prior.get("release_version") != version and not args.upgrade:
                raise RuntimeError("another release is installed; use --upgrade explicitly")
        if args.upgrade and existing.is_file():
            existing.unlink()
        if not existing.is_file() or args.upgrade:
            install_args = [str(bound_python), "-m", "pip", "install", "--no-deps", "--no-index"]
            if args.upgrade:
                install_args.append("--force-reinstall")
            run([*install_args, str(wheel)])
        commands = command_paths(environment)
        with tempfile.TemporaryDirectory(prefix="legal-install-check-", dir=temporary_parent(root)) as temp:
            cwd = Path(temp)
            inspect_package(bound_python, environment, version, cwd)
            smoke_check(commands, bound_python, root, cwd)
        if existing.is_file():
            existing.unlink()
        copy_delivery(root)
        publish_runtime(root, environment, bound_python, commands, version)
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "program_installed": True, "host_registration": "pending", "install_root": str(root), "release_version": version}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
