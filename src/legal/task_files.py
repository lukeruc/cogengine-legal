"""Track only files owned by this publication, reporting cleanup failures."""
from pathlib import Path
from .formats import Invalid, fail, exclusive_write


def cleanup_owned(paths, exc):
    remaining = list(getattr(exc, "remaining_paths", [])) + list(getattr(exc, "details", {}).get("remaining_paths", []))
    for path in reversed(paths):
        try:
            if path.is_dir():
                path.rmdir()  # Never recursively delete another writer's files.
            else:
                path.unlink(missing_ok=True)
        except OSError:
            if path.exists():
                remaining.append(str(path.absolute()))
    if remaining:
        exc.remaining_paths = sorted(set(remaining))


def publish(destination, files):
    destination = Path(destination)
    created, dirs = [], []
    try:
        for name, content in files.items():
            path = destination / name
            missing, parent = [], path.parent
            while not parent.exists():
                missing.append(parent)
                parent = parent.parent
            for parent in reversed(missing):
                parent.mkdir()
                dirs.append(parent)
            exclusive_write(path, content)
            created.append(path)
            if name.endswith("-binding.json"):
                path.chmod(0o444)
    except Exception as exc:
        remaining = list(getattr(exc, "details", {}).get("remaining_paths", []))
        for path in reversed(created):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                remaining.append(str(path))
        for path in reversed(dirs):
            try:
                path.rmdir()
            except OSError:
                if path.exists():
                    remaining.append(str(path))
        if remaining:
            exc.remaining_paths = sorted(set(remaining))
        raise
    return [str(p) for p in created]
