"""Global vocabulary file validation and atomic mutations."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .formats import (Invalid, fields, fail, hash_json, nonempty, read_json,
                      uuid_value, version, file_bytes, digest, new_id)


EMPTY = {"format_version": 1, "units": [], "slots": [], "assignments": []}
FORMS = {"quantity", "time", "condition", "formula", "text", "reference"}
TARGET_KINDS = {"material", "text_version", "clause", "anchor", "node:subject",
                "node:event", "node:defined_value", "node:external_benchmark",
                "node:contract", "relation", "detail", "reference"}


def _string_array(items, path, uuid_items=False):
    if not isinstance(items, list):
        fail("INVALID_ARGUMENT", path, "expected array")
    seen = set()
    for i, item in enumerate(items):
        (uuid_value if uuid_items else nonempty)(item, f"{path}/{i}")
        if item in seen:
            fail("DUPLICATE_ID", f"{path}/{i}", "duplicate item")
        seen.add(item)


def validate_schema(schema, path="/value_schema"):
    if not isinstance(schema, dict):
        fail("INVALID_VALUE", path, "expected value schema")
    if "form" in schema:
        form = schema["form"]
        if not isinstance(form, str) or form not in FORMS:
            fail("INVALID_VALUE", path + "/form", "unknown form")
        extra = {"quantity": "allowed_units", "text": "enum", "reference": "target_kinds"}.get(form)
        fields(schema, ["form"], [extra] if extra else [], path)
        if extra in schema:
            _string_array(schema[extra], path + "/" + extra)
            if not schema[extra]:
                fail("INVALID_VALUE", path + "/" + extra, "empty constraint")
            if extra == "target_kinds" and set(schema[extra]) - TARGET_KINDS:
                fail("INVALID_VALUE", path + "/target_kinds", "unknown target kind")
    elif schema.get("type") == "object":
        fields(schema, ["type", "fields"], ["required_fields"], path)
        if not isinstance(schema["fields"], dict) or not schema["fields"]:
            fail("INVALID_VALUE", path + "/fields", "expected non-empty mapping")
        for name, sub in schema["fields"].items():
            nonempty(name, path + "/fields")
            validate_schema(sub, path + "/fields/" + name)
        required = schema.get("required_fields", [])
        _string_array(required, path + "/required_fields")
        if set(required) - set(schema["fields"]):
            fail("INVALID_VALUE", path + "/required_fields", "unknown required field")
    elif schema.get("type") == "list":
        fields(schema, ["type", "items"], [], path)
        validate_schema(schema["items"], path + "/items")
    elif "one_of" in schema:
        fields(schema, ["one_of"], [], path)
        if not isinstance(schema["one_of"], list) or len(schema["one_of"]) < 2:
            fail("INVALID_VALUE", path + "/one_of", "at least two branches required")
        for i, sub in enumerate(schema["one_of"]):
            validate_schema(sub, f"{path}/one_of/{i}")
    else:
        fail("INVALID_VALUE", path, "invalid value schema")


def normalize(doc):
    fields(doc, ["format_version", "units", "slots", "assignments"])
    version(doc["format_version"])
    for kind in ("units", "slots", "assignments"):
        if not isinstance(doc[kind], list):
            fail("INVALID_ARGUMENT", "/" + kind, "expected array")
    normalized = {"format_version": 1, "units": [], "slots": [], "assignments": []}
    ids = {"units": set(), "slots": set()}
    for kind in ("units", "slots"):
        for index, original in enumerate(doc[kind]):
            path = f"/{kind}/{index}"
            optional = ["examples", "replaces"] + (["aliases", "origin_unit_id"] if kind == "units" else [])
            required = ["id", "name", "description"] + (["value_schema"] if kind == "slots" else [])
            fields(original, required, optional, path)
            entry = dict(original)
            uuid_value(entry["id"], path + "/id")
            if entry["id"] in ids[kind]:
                fail("DUPLICATE_ID", path + "/id", "duplicate entry")
            ids[kind].add(entry["id"])
            nonempty(entry["name"], path + "/name")
            nonempty(entry["description"], path + "/description")
            for name in ("examples", "replaces") + (("aliases",) if kind == "units" else ()):
                entry.setdefault(name, [])
                _string_array(entry[name], path + "/" + name, name == "replaces")
            if kind == "units" and "origin_unit_id" in entry:
                uuid_value(entry["origin_unit_id"], path + "/origin_unit_id")
            if kind == "slots":
                validate_schema(entry["value_schema"], path + "/value_schema")
            normalized[kind].append(entry)
    seen_assignments = set()
    for index, assignment in enumerate(doc["assignments"]):
        path = f"/assignments/{index}"
        fields(assignment, ["unit_id", "slot_id"], [], path)
        unit, slot = assignment["unit_id"], assignment["slot_id"]
        uuid_value(unit, path + "/unit_id")
        uuid_value(slot, path + "/slot_id")
        if unit not in ids["units"] or slot not in ids["slots"]:
            fail("REFERENCE_NOT_FOUND", path, "assignment target missing")
        if (unit, slot) in seen_assignments:
            fail("DUPLICATE_ASSIGNMENT", path, "duplicate assignment")
        seen_assignments.add((unit, slot))
        normalized["assignments"].append({"unit_id": unit, "slot_id": slot})
    normalized["units"].sort(key=lambda e: e["id"])
    normalized["slots"].sort(key=lambda e: e["id"])
    normalized["assignments"].sort(key=lambda a: (a["unit_id"], a["slot_id"]))
    return normalized


def load(path):
    target = Path(path)
    if target.is_dir():
        merged = {"format_version": 1, "units": [], "slots": [], "assignments": []}
        files = sorted((p for p in target.rglob("*") if p.is_file() and p.suffix in {".json", ".yaml"}), key=lambda p: str(p.relative_to(target)))
        sources = []
        for item in files:
            raw = read_json(item)
            fields(raw, ["format_version", "units", "slots", "assignments"])
            version(raw["format_version"])
            # Directory fragments may declare assignments to entries in another file.
            part = normalize({**raw, "assignments": []})
            if not isinstance(raw["assignments"], list):
                fail("INVALID_ARGUMENT", str(item), "assignments must be an array")
            sources.append({"path": str(item.relative_to(target)), "content_hash": digest(file_bytes(item))})
            for kind in ("units", "slots"):
                by_id = {e["id"]: e for e in merged[kind]}
                for entry in part[kind]:
                    if entry["id"] in by_id and by_id[entry["id"]] != entry:
                        fail("DUPLICATE_ID", str(item), "same ID has different content")
                    if entry["id"] not in by_id:
                        merged[kind].append(entry)
            merged["assignments"].extend(raw["assignments"])
        return normalize(merged), sources
    document = normalize(read_json(target))
    return document, [{"path": target.name, "content_hash": digest(file_bytes(target))}]


def vocabulary_hash(doc):
    return hash_json(normalize(doc))


def save(path, doc, exclusive=False):
    target = Path(path)
    if target.is_dir():
        fail("READ_ONLY_LAYOUT", str(target), "directory vocabulary is read only")
    data = (json.dumps(normalize(doc), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if exclusive:
        try:
            with target.open("xb") as out:
                out.write(data)
                out.flush()
                os.fsync(out.fileno())
        except FileExistsError:
            fail("FILE_EXISTS", str(target), "vocabulary already exists")
        except OSError as exc:
            fail("FILE_ERROR", str(target), str(exc))
        return
    try:
        handle, temporary = tempfile.mkstemp(prefix=".vocabulary-", dir=target.parent)
        try:
            with os.fdopen(handle, "wb") as out:
                out.write(data)
                out.flush()
                os.fsync(out.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    except OSError as exc:
        fail("FILE_ERROR", str(target), str(exc))


def diff(left, right):
    left, right = normalize(left), normalize(right)
    result = {"added": [], "removed": [], "assignment_added": [], "assignment_removed": [], "illegal_content_changes": []}
    for kind in ("units", "slots"):
        old = {e["id"]: e for e in left[kind]}
        new = {e["id"]: e for e in right[kind]}
        label = kind[:-1]
        result["added"].extend({"kind": label, "entry": new[key]} for key in sorted(new.keys() - old.keys()))
        result["removed"].extend({"kind": label, "entry": old[key]} for key in sorted(old.keys() - new.keys()))
        result["illegal_content_changes"].extend({"kind": label, "id": key, "before": old[key], "after": new[key]} for key in sorted(old.keys() & new.keys()) if old[key] != new[key])
    old_pairs = {(e["unit_id"], e["slot_id"]) for e in left["assignments"]}
    new_pairs = {(e["unit_id"], e["slot_id"]) for e in right["assignments"]}
    result["assignment_added"] = [{"unit_id": u, "slot_id": s} for u, s in sorted(new_pairs - old_pairs)]
    result["assignment_removed"] = [{"unit_id": u, "slot_id": s} for u, s in sorted(old_pairs - new_pairs)]
    return result


def apply_change(current, change):
    fields(change, ["format_version", "expected_hash", "operations"], ["orphan_slots"])
    version(change["format_version"])
    before = vocabulary_hash(current)
    if change["expected_hash"] != before:
        fail("HASH_CONFLICT", "/expected_hash", "vocabulary changed")
    operations = change["operations"]
    if not isinstance(operations, list):
        fail("INVALID_ARGUMENT", "/operations", "expected array")
    final = {"format_version": 1, "units": [dict(e) for e in current["units"]],
             "slots": [dict(e) for e in current["slots"]], "assignments": [dict(e) for e in current["assignments"]]}
    id_map, removed = {}, set()
    for i, operation in enumerate(operations):
        path = f"/operations/{i}"
        if not isinstance(operation, dict) or not isinstance(operation.get("action"), str) or operation.get("action") not in {"add", "remove"} or not isinstance(operation.get("kind"), str) or operation.get("kind") not in {"unit", "slot"}:
            fail("INVALID_ARGUMENT", path, "invalid operation")
        if operation["action"] == "add":
            fields(operation, ["action", "kind", "local_id", "entry"], ["unit_ids"], path)
            local = nonempty(operation["local_id"], path + "/local_id")
            if local in id_map:
                fail("DUPLICATE_LOCAL_ID", path + "/local_id", "duplicate local ID")
            id_map[local] = new_id()
        else:
            fields(operation, ["action", "kind", "id"], [], path)
    def resolve(value, path):
        if isinstance(value, dict):
            fields(value, ["local_id"], [], path)
            if value["local_id"] not in id_map:
                fail("REFERENCE_NOT_FOUND", path, "unknown local unit")
            return id_map[value["local_id"]]
        return uuid_value(value, path)
    for i, operation in enumerate(operations):
        path = f"/operations/{i}"
        kind = operation["kind"] + "s"
        if operation["action"] == "add":
            entry = dict(operation["entry"])
            if "id" in entry:
                fail("UNKNOWN_FIELD", path + "/entry/id", "ID is generated by tool")
            entry["id"] = id_map[operation["local_id"]]
            final[kind].append(entry)
            if "unit_ids" in operation:
                if kind != "slots" or not isinstance(operation["unit_ids"], list):
                    fail("INVALID_ARGUMENT", path + "/unit_ids", "unit_ids only applies to slots")
                for index, unit in enumerate(operation["unit_ids"]):
                    final["assignments"].append({"unit_id": resolve(unit, f"{path}/unit_ids/{index}"), "slot_id": entry["id"]})
        else:
            key = (kind, uuid_value(operation["id"], path + "/id"))
            if key in removed:
                fail("DUPLICATE_OPERATION", path, "duplicate removal")
            removed.add(key)
            if not any(e["id"] == key[1] for e in final[kind]):
                fail("NOT_FOUND", path + "/id", "entry not found")
            final[kind] = [e for e in final[kind] if e["id"] != key[1]]
            final["assignments"] = [a for a in final["assignments"] if a["unit_id"] != key[1]] if kind == "units" else [a for a in final["assignments"] if a["slot_id"] != key[1]]
    original_assignments = {e["slot_id"] for e in current["assignments"]}
    remaining_assignments = {e["slot_id"] for e in final["assignments"]}
    remaining_slots = {e["id"] for e in final["slots"]}
    orphans = (original_assignments & remaining_slots) - remaining_assignments
    dispositions = change.get("orphan_slots", [])
    if not isinstance(dispositions, list):
        fail("INVALID_ARGUMENT", "/orphan_slots", "expected array")
    seen = set()
    for i, item in enumerate(dispositions):
        path = f"/orphan_slots/{i}"
        fields(item, ["slot_id", "disposition"], ["unit_ids"], path)
        slot = uuid_value(item["slot_id"], path + "/slot_id")
        if slot not in orphans or slot in seen:
            fail("ORPHAN_DISPOSITION_INVALID", path, "disposition not applicable")
        seen.add(slot)
        action = item["disposition"]
        if action == "remove":
            if "unit_ids" in item:
                fail("ORPHAN_DISPOSITION_INVALID", path, "remove does not take unit_ids")
            final["slots"] = [e for e in final["slots"] if e["id"] != slot]
        elif action == "reassign":
            units = item.get("unit_ids")
            if not isinstance(units, list) or not units:
                fail("ORPHAN_DISPOSITION_INVALID", path, "reassign requires unit_ids")
            for index, unit in enumerate(units):
                final["assignments"].append({"unit_id": resolve(unit, f"{path}/unit_ids/{index}"), "slot_id": slot})
        elif action != "general" or "unit_ids" in item:
            fail("ORPHAN_DISPOSITION_INVALID", path, "invalid disposition")
    if seen != orphans:
        fail("ORPHAN_DISPOSITION_REQUIRED", "/orphan_slots", "all orphan slots need disposition")
    final = normalize(final)
    return final, {"ok": True, "before_hash": before, "after_hash": vocabulary_hash(final),
                   "id_map": id_map, "changes": {key: value for key, value in diff(current, final).items() if key != "illegal_content_changes"}}
