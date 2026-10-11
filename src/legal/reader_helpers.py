"""Optional task file operations. No database, CLI, or process access."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
from pathlib import Path
import sys

from .formats import (Invalid, InvalidBatch, canonical, exclusive_write, fail, fields, integer,
                      loads, nonempty, pointer_escape, quote_positions, uuid_value)
from .submission_structure import (validate_envelope, validate_record_envelope,
                                   validate_reference_shape, validate_source_structure)

CHECKED = ["json", "envelope", "record_envelopes", "batch_ids", "recognized_local_references"]
DEFERRED = ["record_content", "vocabulary_and_values", "database_state",
            "reference_targets", "evidence", "coverage", "legal_meaning"]

UNSET = object()


def _copy_json(value):
    try:
        return _copy_json_inner(value)
    except RecursionError:
        fail("INVALID_JSON", "", "JSON nesting exceeds interpreter limit")


def _copy_json_inner(value, path="", stack=None):
    """Copy only ordinary JSON data, without implicit conversions or aliases."""
    stack = set() if stack is None else stack
    if type(value) in (str, int, bool) or value is None:
        if isinstance(value, str):
            try:
                value.encode("utf-8")
            except UnicodeError as exc:
                fail("INVALID_JSON", path, str(exc))
        return value
    if type(value) is float:
        if not math.isfinite(value):
            fail("INVALID_JSON", path, "non-finite number")
        return value
    if type(value) not in (dict, list):
        fail("INVALID_JSON", path, "expected ordinary JSON data")
    if id(value) in stack:
        fail("INVALID_JSON", path, "cyclic data")
    stack.add(id(value))
    try:
        if type(value) is list:
            return [_copy_json_inner(item, f"{path}/{i}", stack) for i, item in enumerate(value)]
        result = {}
        for key, item in value.items():
            if type(key) is not str:
                fail("INVALID_JSON", path, "JSON keys must be strings")
            _copy_json_inner(key, path, stack)
            result[key] = _copy_json_inner(item, path + "/" + pointer_escape(key), stack)
        return result
    finally:
        stack.remove(id(value))


def read_json(path):
    return _read(_absolute(path, "/path"))


def read_text(path):
    path = _absolute(path, "/path")
    try:
        return path.read_bytes().decode("utf-8", errors="strict")
    except (OSError, UnicodeError) as exc:
        fail("FILE_ERROR", str(path), str(exc))


def write_json(path, value):
    path = _absolute(path, "/path")
    document = _copy_json(value)
    try:
        data = (json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        fail("INVALID_JSON", "", str(exc))
    exclusive_write(path, data)
    return str(path)


def quote_from_span(snapshot, *, local_id, clause_record_id, start, end):
    clauses = _snapshot(snapshot)
    nonempty(local_id, "/local_id")
    uuid_value(clause_record_id, "/clause_record_id")
    if clause_record_id not in clauses:
        fail("REFERENCE_NOT_FOUND", "/clause_record_id", "clause version absent from snapshot")
    text = clauses[clause_record_id]["data"]["text"]
    integer(start, "/start", 0)
    integer(end, "/end", 0)
    if not start < end <= len(text):
        fail("INVALID_ARGUMENT", "/end", "expected 0 <= start < end <= len(text)")
    quote = text[start:end]
    return {"local_id": local_id, "clause_record_id": clause_record_id, "quote": quote,
            "occurrence": quote_positions(text, quote).index(start) + 1}


def ref(*, object_id=UNSET, record_id=UNSET, local_id=UNSET, value_path=UNSET):
    result = {key: value for key, value in locals().items() if value is not UNSET}
    validate_reference_shape(result, "")
    return _copy_json(result)


def source(*, level, **fields):
    result = _copy_json({"level": level, **fields})
    validate_source_structure(result)
    return result


def evidence(*, path, source):
    if not isinstance(path, str) or (path != "" and not path.startswith("/")) or re.search(r"~(?![01])", path):
        fail("INVALID_ARGUMENT", "/path", "invalid JSON Pointer")
    validate_source_structure(source)
    return _copy_json({"path": path, "source": source})


def record(*, local_id, kind, data, evidence, object_id=UNSET, previous_record_id=UNSET,
           status=UNSET, withdrawal_reason=UNSET):
    result = _copy_json({key: value for key, value in locals().items() if value is not UNSET})
    validate_record_envelope(result, "")
    return result


def _typed_fields(fields, fixed):
    if not isinstance(fields, dict):
        fail("INVALID_ARGUMENT", "/fields", "expected object")
    for key in fixed:
        if key in fields:
            fail("INVALID_ARGUMENT", "/fields/" + key, "fixed field cannot be redefined")
    return {**fixed, **fields}


def node(*, local_id, node_kind, fields, evidence):
    return record(local_id=local_id, kind="node", data=_typed_fields(fields, {"node_kind": node_kind}), evidence=evidence)


def relation(*, local_id, relation_kind, fields, evidence):
    return record(local_id=local_id, kind="relation", data=_typed_fields(fields, {"relation_kind": relation_kind}), evidence=evidence)


def reference(*, local_id, reference_kind, from_ref, to_ref, fields, evidence):
    return record(local_id=local_id, kind="reference", data=_typed_fields(fields, {
        "reference_kind": reference_kind, "from": from_ref, "to": to_ref}), evidence=evidence)


def detail(*, local_id, owner, slot_id, value, evidence):
    return record(local_id=local_id, kind="detail", data={"owner": owner, "slot_id": slot_id, "value": value}, evidence=evidence)


def clause_revision(*, local_id, clause, tags, classification, evidence):
    if not isinstance(clause, dict) or clause.get("kind") != "clause" or clause.get("status") != "active":
        fail("INVALID_ARGUMENT", "/clause", "expected active complete clause query record")
    for key in ("object_id", "record_id"):
        uuid_value(clause.get(key), "/clause/" + key)
    data = fields(clause.get("data"), ["text_version", "sequence", "text", "start_offset", "end_offset", "tags", "classification"], ["original_number"], "/clause/data")
    _snapshot({"case_id": clause["object_id"], "checked_sequence": 0, "items": [clause]})
    integer(data["sequence"], "/clause/data/sequence", 1)
    if "original_number" in data and data["original_number"] is not None and not isinstance(data["original_number"], str):
        fail("INVALID_ARGUMENT", "/clause/data/original_number")
    if not isinstance(tags, list):
        fail("INVALID_ARGUMENT", "/tags", "expected array")
    for i, tag in enumerate(tags):
        uuid_value(tag, f"/tags/{i}")
    if len(set(tags)) != len(tags):
        fail("DUPLICATE_ID", "/tags", "duplicate tag")
    if not isinstance(classification, str) or classification not in {"ordinary", "no_content", "unmatched"} or (classification == "ordinary") != bool(tags):
        fail("INVALID_ARGUMENT", "/classification", "classification and tags differ")
    return record(local_id=local_id, kind="clause", data={**data, "tags": tags, "classification": classification},
                  evidence=evidence, object_id=clause["object_id"], previous_record_id=clause["record_id"])


def header(*, format_version, case_id, vocabulary_hash, submitted_by, phase, covered_clauses, issues, overview=UNSET):
    result = _copy_json({key: value for key, value in locals().items() if value is not UNSET})
    validate_envelope({**result, "records": []})
    return result


def assemble(*, header, record_groups):
    header = _copy_json(header)
    groups = _copy_json(record_groups)
    if not isinstance(groups, list) or not groups or any(not isinstance(group, list) for group in groups):
        fail("INVALID_ARGUMENT", "/record_groups", "expected one or more record arrays")
    return _assemble(header, groups)


class FileChecksFailed(InvalidBatch):
    def __init__(self, errors):
        self.errors = errors
        self.items = errors
        Exception.__init__(self, f"{len(errors)} validation errors")


class Diagnostics:
    def __init__(self):
        self.errors = []

    def check(self, fn, *args, file=None):
        try:
            return fn(*args)
        except Invalid as exc:
            item = exc.item()
            if file is not None:
                item["file"] = str(file)
            self.errors.append(item)

    def finish(self):
        if self.errors:
            raise FileChecksFailed(self.errors)


def _read(path):
    try:
        return loads(Path(path).read_bytes())
    except Invalid as exc:
        exc.details["file"] = str(path)
        raise
    except RecursionError:
        fail("INVALID_JSON", "", "JSON nesting exceeds interpreter limit", file=str(path))
    except OSError as exc:
        fail("FILE_ERROR", "", str(exc), file=str(path))


def _absolute(path, argument):
    try:
        result = Path(path)
    except (TypeError, ValueError) as exc:
        fail("INVALID_ARGUMENT", argument, str(exc))
    if not result.is_absolute():
        fail("INVALID_ARGUMENT", argument, "file path must be absolute")
    if "\x00" in str(result):
        fail("FILE_ERROR", argument, "file path contains a null character")
    return result


def _publish(output, document):
    # Serialize completely before creating a target; exclusive_write removes a
    # newly created file on write/flush/fsync failure and never replaces one.
    exclusive_write(output, canonical(document) + b"\n")


def _snapshot(snapshot):
    fields(snapshot, ["case_id", "checked_sequence", "items"])
    uuid_value(snapshot["case_id"], "/case_id")
    integer(snapshot["checked_sequence"], "/checked_sequence", 0)
    if not isinstance(snapshot["items"], list):
        fail("INVALID_ARGUMENT", "/items", "expected complete clause query records")
    indexed = {}
    for i, item in enumerate(snapshot["items"]):
        path = f"/items/{i}"
        if not isinstance(item, dict):
            fail("INVALID_ARGUMENT", path, "expected clause query record")
        record_id = uuid_value(item.get("record_id"), path + "/record_id")
        uuid_value(item.get("object_id"), path + "/object_id")
        if item.get("kind") != "clause" or not isinstance(item.get("data"), dict):
            fail("INVALID_ARGUMENT", path, "expected complete clause query record")
        data = item["data"]
        if not isinstance(data.get("text"), str):
            fail("INVALID_ARGUMENT", path + "/data/text", "full clause text is required")
        validate_reference_shape(data.get("text_version"), path + "/data/text_version")
        start = integer(data.get("start_offset"), path + "/data/start_offset", 0)
        end = integer(data.get("end_offset"), path + "/data/end_offset", 0)
        if end - start != len(data["text"]):
            fail("INVALID_ARGUMENT", path + "/data", "clause address differs from text length")
        if record_id in indexed and (indexed[record_id]["object_id"] != item["object_id"] or indexed[record_id]["data"] != data):
            fail("INVALID_ARGUMENT", path + "/record_id", "conflicting clause content for one record_id")
        indexed[record_id] = item
    return indexed


def _quote_request(request, path):
    fields(request, ["local_id", "clause_record_id", "quote"], ["occurrence"], path)
    nonempty(request["local_id"], path + "/local_id")
    uuid_value(request["clause_record_id"], path + "/clause_record_id")
    # A whitespace-only quote is a legitimate exact anchor under spec 3.4.
    if not isinstance(request["quote"], str) or not request["quote"]:
        fail("INVALID_ARGUMENT", path + "/quote", "quote must be a non-empty original string")
    if "occurrence" in request and (type(request["occurrence"]) is not int or request["occurrence"] < 1):
        fail("ANCHOR_OCCURRENCE", path + "/occurrence", "occurrence must be a positive integer")
    return request


def find_quote_files(clauses_file, input_file, output_file):
    clauses_file = _absolute(clauses_file, "--clauses")
    input_file = _absolute(input_file, "--input")
    output_file = _absolute(output_file, "--output")
    checks = Diagnostics()
    snapshot = checks.check(_read, clauses_file)
    requests = checks.check(_read, input_file)
    checks.finish()
    clauses = checks.check(_snapshot, snapshot, file=clauses_file)
    if not isinstance(requests, list) or not requests:
        checks.check(fail, "INVALID_ARGUMENT", "", "quote requests must be a non-empty array", file=input_file)
    checks.finish()
    records, matches, seen = [], [], set()
    for i, request in enumerate(requests):
        path = f"/{i}"
        if checks.check(_quote_request, request, path, file=input_file) is None:
            continue
        local_id = request["local_id"]
        if local_id in seen:
            checks.check(fail, "DUPLICATE_LOCAL_ID", path + "/local_id", "duplicate request local ID", file=input_file)
            continue
        seen.add(local_id)
        record_id = request["clause_record_id"]
        if record_id not in clauses:
            checks.check(fail, "REFERENCE_NOT_FOUND", path + "/clause_record_id",
                         "clause version was not found in this input snapshot", file=input_file)
            continue
        quote = request["quote"]
        found = quote_positions(clauses[record_id]["data"]["text"], quote)
        if not found:
            checks.check(fail, "ANCHOR_NOT_FOUND", path + "/quote", "exact quote absent from input clause", file=input_file)
            continue
        if len(found) > 1 and "occurrence" not in request:
            checks.errors.append({"code": "ANCHOR_AMBIGUOUS", "path": path + "/occurrence",
                                  "message": "multiple exact matches; specify occurrence", "file": str(input_file),
                                  "match_count": len(found), "candidates_truncated": len(found) > 100,
                                  "candidates": [{"occurrence": j + 1, "start_offset": start,
                                                  "end_offset": start + len(quote)} for j, start in enumerate(found[:100])]})
            continue
        occurrence = request.get("occurrence", 1)
        if occurrence > len(found):
            checks.check(fail, "ANCHOR_OCCURRENCE", path + "/occurrence", "occurrence outside matches", file=input_file)
            continue
        start = found[occurrence - 1]
        records.append({"local_id": local_id, "kind": "anchor", "data": {
            "clause": {"record_id": record_id}, "quote": quote, "occurrence": occurrence}, "evidence": []})
        matches.append({"local_id": local_id, "clause_record_id": record_id, "occurrence": occurrence,
                        "start_offset": start, "end_offset": start + len(quote)})
    checks.finish()
    _publish(output_file, records)
    return {"ok": True, "scope": "task_files", "output_file": str(output_file), "record_count": len(records),
            "case_id": snapshot["case_id"], "checked_sequence": snapshot["checked_sequence"], "matches": matches}


def _value_references(value, path):
    """Walk only spec 5 value positions, never arbitrary same-named keys."""
    if not isinstance(value, dict) or ("form" in value and "type" in value):
        return
    form = value.get("form")
    if form == "reference":
        if "target" in value:
            yield value["target"], path + "/target"
    elif form == "time":
        kind = value.get("kind")
        if kind == "relative" and "event" in value:
            yield value["event"], path + "/event"
        elif kind == "interval":
            for key in ("start", "end"):
                yield from _value_references(value.get(key), path + "/" + key)
    elif form == "condition":
        operator = value.get("operator")
        if not isinstance(operator, str):
            return
        if operator == "event" and "event" in value:
            yield value["event"], path + "/event"
        elif operator in {"all", "any"} and isinstance(value.get("operands"), list):
            for i, item in enumerate(value["operands"]):
                yield from _value_references(item, f"{path}/operands/{i}")
        elif operator == "not":
            yield from _value_references(value.get("operand"), path + "/operand")
        elif operator == "compare":
            for key in ("left", "right"):
                yield from _value_references(value.get(key), path + "/" + key)
        elif operator == "count":
            for key in ("condition", "period"):
                yield from _value_references(value.get(key), path + "/" + key)
    elif form == "formula" and isinstance(value.get("operands"), list):
        for i, item in enumerate(value["operands"]):
            yield from _value_references(item, f"{path}/operands/{i}")
    elif "form" not in value and value.get("type") == "object" and isinstance(value.get("fields"), dict):
        for key, item in value["fields"].items():
            yield from _value_references(item, path + "/fields/" + pointer_escape(key))
    elif "form" not in value and value.get("type") == "list" and isinstance(value.get("items"), list):
        for i, item in enumerate(value["items"]):
            yield from _value_references(item, f"{path}/items/{i}")


def _record_references(record, path):
    data, kind = record["data"], record["kind"]
    base = path + "/data"
    direct = {"clause": ("text_version",), "anchor": ("clause",), "detail": ("owner",),
              "gap": ("clause", "related_object"), "no_content": ("clause",)}.get(kind, ())
    for key in direct:
        if key in data:
            yield data[key], base + "/" + key
    if kind == "node":
        if data.get("node_kind") == "event":
            if isinstance(data.get("participants"), list):
                for i, item in enumerate(data["participants"]):
                    if isinstance(item, dict) and "subject" in item:
                        yield item["subject"], f"{base}/participants/{i}/subject"
            yield from _value_references(data.get("object"), base + "/object")
        elif data.get("node_kind") == "defined_value":
            yield from _value_references(data.get("value"), base + "/value")
            if isinstance(data.get("scope"), list):
                for i, ref in enumerate(data["scope"]):
                    yield ref, f"{base}/scope/{i}"
    elif kind == "relation":
        if data.get("relation_kind") == "party" and isinstance(data.get("parties"), list):
            for i, item in enumerate(data["parties"]):
                if isinstance(item, dict) and "subject" in item:
                    yield item["subject"], f"{base}/parties/{i}/subject"
        elif data.get("relation_kind") == "contract" and "subject" in data:
            yield data["subject"], base + "/subject"
    elif kind == "detail":
        yield from _value_references(data.get("value"), base + "/value")
    elif kind == "reference":
        reference_kind = data.get("reference_kind")
        if isinstance(reference_kind, str) and reference_kind in {"appellation", "role", "composition", "definition", "event_of",
                                                              "scope", "priority", "amendment", "redirect", "distinct"}:
            for key in ("from", "to", "scope", "exclude"):
                if key not in data or key == "scope" and reference_kind != "appellation" or key == "exclude" and reference_kind != "scope":
                    continue
                value = data[key]
                if reference_kind == "scope" and key in {"to", "exclude"}:
                    if isinstance(value, list):
                        for i, ref in enumerate(value):
                            yield ref, f"{base}/{key}/{i}"
                else:
                    yield value, base + "/" + key
    for i, entry in enumerate(record["evidence"]):
        if not isinstance(entry, dict) or not isinstance(entry.get("source"), dict):
            continue
        source = entry["source"]
        level = source.get("level")
        key = "anchors" if type(level) is int and level in (1, 2) else "premises" if type(level) is int and level == 3 else None
        if key and isinstance(source.get(key), list):
            for j, ref in enumerate(source[key]):
                yield ref, f"{path}/evidence/{i}/source/{key}/{j}"


def _check_local(ref, path, locals):
    validate_reference_shape(ref, path)
    if "local_id" in ref and ref["local_id"] not in locals:
        fail("REFERENCE_NOT_FOUND", path, "local target was not found in this merged batch")


def build_submission_files(header_file, records_files, output_file):
    header_file = _absolute(header_file, "--header")
    output_file = _absolute(output_file, "--output")
    paths = [_absolute(path, "--records") for path in records_files]
    if not paths:
        fail("INVALID_ARGUMENT", "--records", "at least one records file is required")
    normalized = [os.path.normcase(str(path.resolve())) for path in paths]
    if len(normalized) != len(set(normalized)):
        fail("INVALID_ARGUMENT", "--records", "duplicate normalized records file path")
    checks = Diagnostics()
    header = checks.check(_read, header_file)
    arrays = []
    for path in paths:
        before = len(checks.errors)
        array = checks.check(_read, path)
        if len(checks.errors) == before and not isinstance(array, list):
            checks.check(fail, "INVALID_ARGUMENT", "", "records file must contain an array", file=path)
        arrays.append(array)
    checks.finish()
    document = _assemble(header, arrays, header_file, paths)
    _publish(output_file, document)
    return {"ok": True, "scope": "task_files", "output_file": str(output_file), "record_count": len(document["records"]),
            "checked": CHECKED.copy(), "deferred_checks": DEFERRED.copy()}


def _assemble(header, arrays, header_file=None, paths=None):
    """One pure check implementation for memory and file interfaces."""
    checks = Diagnostics()
    memory = paths is None
    paths = [f"/record_groups/{i}" for i in range(len(arrays))] if memory else paths
    # The header cannot smuggle in or overwrite records, even an empty array.
    checks.check(fields, header, ["format_version", "case_id", "vocabulary_hash", "submitted_by", "phase", "covered_clauses", "issues"], ["overview"], "", file=header_file)
    checks.finish()
    records = [record for array in arrays for record in array]
    document = {**header, "records": records}
    checks.check(validate_envelope, document, file=header_file)
    valid, locations, locals, objects = [], [], set(), set()
    for file, array in zip(paths, arrays):
        for i, record in enumerate(array):
            path = f"/{i}"
            before = len(checks.errors)
            checks.check(validate_record_envelope, record, path, file=file)
            if len(checks.errors) != before:
                continue
            local_id = record["local_id"]
            if local_id in locals:
                checks.check(fail, "DUPLICATE_LOCAL_ID", path + "/local_id", "duplicate local ID in merged batch", file=file)
            locals.add(local_id)
            if "object_id" in record:
                if record["object_id"] in objects:
                    checks.check(fail, "DUPLICATE_ID", path + "/object_id", "object revised twice in merged batch", file=file)
                objects.add(record["object_id"])
            valid.append(record)
            locations.append((file, path))
    # All identifiers are collected before resolving forward references.
    if isinstance(header.get("overview"), dict) and isinstance(header["overview"].get("text_versions"), list):
        for i, ref in enumerate(header["overview"]["text_versions"]):
            checks.check(_check_local, ref, f"/overview/text_versions/{i}", locals, file=header_file)
    # Collect record errors first, then order by file and item below.
    for record, (file, path) in zip(valid, locations):
        for ref, at in _record_references(record, path):
            checks.check(_check_local, ref, at, locals, file=file)
    order = {str(file): i for i, file in enumerate([header_file, *paths])}
    checks.errors.sort(key=lambda item: (order.get(item.get("file"), -1),
                                       int(item["path"].split("/")[1]) if item["path"].startswith("/") and item["path"].split("/")[1].isdigit() else -1))
    if memory:
        for item in checks.errors:
            if "file" in item:
                item["path"] = item.pop("file") + item["path"]
    checks.finish()
    return document


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        fail("INVALID_ARGUMENT", "", message)


class _Single(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if getattr(namespace, self.dest, None) is not None:
            fail("INVALID_ARGUMENT", option_string, "single-value argument repeated")
        setattr(namespace, self.dest, values)


def main(tool, argv=None):
    parser = _Parser(description="Optional contract task file helper", allow_abbrev=False)
    if tool == "find_quote":
        parser.add_argument("--clauses", required=True, action=_Single)
        parser.add_argument("--input", required=True, action=_Single)
    elif tool == "build_submission":
        parser.add_argument("--header", required=True, action=_Single)
        parser.add_argument("--records", required=True, action="append")
    else:
        raise ValueError("unknown helper")
    parser.add_argument("--output", required=True, action=_Single)
    try:
        args = parser.parse_args(argv)
        if tool == "find_quote":
            response = find_quote_files(args.clauses, args.input, args.output)
        else:
            response = build_submission_files(args.header, args.records, args.output)
        code = 0
    except (Invalid, FileChecksFailed) as exc:
        items = [exc.item()] if isinstance(exc, Invalid) else exc.errors
        response = {"ok": False, "errors": items[:100], "errors_truncated": len(items) > 100}
        code = 3 if any(item["code"] in {"FILE_ERROR", "FILE_EXISTS"} for item in items) else 2
    except (OSError, ValueError, RecursionError) as exc:
        response = {"ok": False, "errors": [{"code": "FILE_ERROR" if isinstance(exc, OSError) else "INVALID_ARGUMENT",
                                            "path": "", "message": str(exc)}], "errors_truncated": False}
        code = 3 if isinstance(exc, OSError) else 2
    print(json.dumps(response, ensure_ascii=False, separators=(",", ":"), allow_nan=False), file=sys.stdout)
    return code
