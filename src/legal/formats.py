"""Strict interchange parsing, canonical hashes, and shared validation."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path


class Invalid(Exception):
    def __init__(self, code: str, path: str = "", message: str = "", **details):
        self.code, self.path, self.message, self.details = code, path, message or code, details
        super().__init__(self.message)

    def item(self):
        return {"code": self.code, "path": self.path, "message": self.message, **self.details}


class InvalidBatch(Exception):
    def __init__(self, items):
        self.items = sorted(items, key=lambda e: (int(e.get("path", "").split("/")[2]) if e.get("path", "").startswith("/records/") and e.get("path", "").split("/")[2].isdigit() else -1,
                                                  e.get("path", ""), e.get("code", "")))
        super().__init__(f"{len(items)} validation errors")


def fail(code, path="", message="", **details):
    raise Invalid(code, path, message, **details)


def errors(exc: Invalid):
    return {"ok": False, "errors": [exc.item()], "errors_truncated": False}


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key: {key}")
        result[key] = value
    return result


def _bad_constant(value):
    raise ValueError(f"non-standard JSON constant: {value}")


def loads(data, path=""):
    try:
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="strict")
        if data.startswith("\ufeff"):
            raise ValueError("UTF-8 BOM is forbidden")
        obj = json.loads(data, object_pairs_hook=_unique_pairs, parse_constant=_bad_constant)
        canonical(obj)
        return obj
    except (UnicodeError, ValueError, TypeError, OverflowError) as exc:
        fail("INVALID_JSON", path, str(exc))


def read_json(path):
    try:
        return loads(Path(path).read_bytes(), str(path))
    except OSError as exc:
        fail("FILE_ERROR", str(path), str(exc))


def canonical(obj):
    try:
        return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        fail("INVALID_JSON", "", str(exc))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def hash_json(obj):
    return digest(canonical(obj))


def new_id():
    return str(uuid.uuid4())


def timestamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def require_object(value, path=""):
    if not isinstance(value, dict):
        fail("INVALID_ARGUMENT", path, "expected object")
    return value


def fields(value, required, optional=(), path=""):
    require_object(value, path)
    allowed = set(required) | set(optional)
    for key in value:
        if key not in allowed:
            fail("UNKNOWN_FIELD", f"{path}/{pointer_escape(key)}", "unknown field")
    for key in required:
        if key not in value:
            fail("INVALID_ARGUMENT", f"{path}/{pointer_escape(key)}", "required field is missing")
    return value


def pointer_escape(value):
    return str(value).replace("~", "~0").replace("/", "~1")


def pointer_get(value, pointer):
    if pointer == "":
        return value
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        fail("INVALID_ARGUMENT", pointer if isinstance(pointer, str) else "", "invalid JSON Pointer")
    node = value
    for token in pointer[1:].split("/"):
        if re.search(r"~(?![01])", token):
            fail("INVALID_ARGUMENT", pointer, "invalid pointer escape")
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict) and token in node:
            node = node[token]
        elif isinstance(node, list) and re.fullmatch(r"0|[1-9][0-9]*", token) and int(token) < len(node):
            node = node[int(token)]
        else:
            fail("INVALID_ARGUMENT", pointer, "pointer does not exist")
    return node


def integer(value, path, minimum=None):
    if type(value) is not int or (minimum is not None and value < minimum):
        fail("INVALID_ARGUMENT", path, "invalid integer")
    return value


def nonempty(value, path):
    if not isinstance(value, str) or not value.strip():
        fail("INVALID_ARGUMENT", path, "expected non-empty string")
    try:
        value.encode("utf-8")
    except UnicodeError:
        fail("INVALID_ARGUMENT", path, "invalid Unicode")
    return value


def uuid_value(value, path):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}", value):
        fail("INVALID_ARGUMENT", path, "expected canonical UUID")
    try:
        if str(uuid.UUID(value)) != value:
            raise ValueError()
    except ValueError:
        fail("INVALID_ARGUMENT", path, "expected canonical UUID")
    return value


def version(value, path="/format_version"):
    if type(value) is not int or value != 1:
        fail("UNSUPPORTED_VERSION", path, "only version 1 is supported")


def quote_positions(text, quote):
    """Exact Unicode substring starts, including overlapping occurrences."""
    if not quote:
        fail("INVALID_ARGUMENT", "/quote", "empty quote")
    found = []
    index = text.find(quote)
    while index >= 0:
        found.append(index)
        index = text.find(quote, index + 1)
    return found


def file_bytes(path):
    try:
        return Path(path).read_bytes()
    except OSError as exc:
        fail("FILE_ERROR", str(path), str(exc))


def file_text(path):
    try:
        data = file_bytes(path)
        if data.startswith(b"\xef\xbb\xbf"):
            fail("INVALID_ARGUMENT", str(path), "UTF-8 BOM is forbidden")
        return data.decode("utf-8")
    except UnicodeError as exc:
        fail("INVALID_ARGUMENT", str(path), str(exc))


def exclusive_write(path, data):
    created = False
    try:
        with open(path, "xb") as stream:
            created = True
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        fail("FILE_EXISTS", str(path), "file already exists")
    except OSError as exc:
        if created:
            try:
                Path(path).unlink()
            except OSError:
                pass
        fail("FILE_ERROR", str(path), str(exc))


def output(result, exit_code=0):
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False))
    return exit_code


def exception_result(exc):
    if isinstance(exc, InvalidBatch):
        return output({"ok": False, "errors": exc.items[:100], "errors_truncated": len(exc.items) > 100}, 2)
    if isinstance(exc, Invalid):
        code = 3 if exc.code in {"FILE_ERROR", "FILE_EXISTS", "DATABASE_ERROR", "CONVERTER_FAILED"} else 2
        return output(errors(exc), code)
    if isinstance(exc, OSError):
        return output(errors(Invalid("FILE_ERROR", "", str(exc))), 3)
    return output(errors(Invalid("DATABASE_ERROR", "", str(exc))), 3)
