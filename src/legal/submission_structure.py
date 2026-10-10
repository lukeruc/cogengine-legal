"""Database independent checks shared by write and task file helpers."""

from __future__ import annotations

import re

from .formats import fields, fail, nonempty, require_object, uuid_value, version

KINDS = {"clause", "anchor", "node", "relation", "detail", "reference", "gap", "no_content"}


def validate_reference_shape(ref, path):
    fields(ref, [], ["object_id", "record_id", "local_id", "value_path"], path)
    keys = {"object_id", "record_id", "local_id"} & ref.keys()
    if len(keys) != 1:
        fail("INVALID_ARGUMENT", path, "reference needs exactly one target")
    key = next(iter(keys))
    (nonempty if key == "local_id" else uuid_value)(ref[key], path + "/" + key)
    if "value_path" in ref:
        pointer = ref["value_path"]
        if key == "object_id" or not isinstance(pointer, str) or not (pointer == "/value" or pointer.startswith("/value/")) or re.search(r"~(?![01])", pointer):
            fail("INVALID_ARGUMENT", path + "/value_path", "invalid fixed value pointer")


def validate_envelope(doc):
    fields(doc, ["format_version", "case_id", "vocabulary_hash", "submitted_by", "phase",
                 "covered_clauses", "records", "issues"], ["overview"])
    version(doc["format_version"])
    uuid_value(doc["case_id"], "/case_id")
    if not isinstance(doc["vocabulary_hash"], str) or not re.fullmatch(r"[0-9a-f]{64}", doc["vocabulary_hash"]):
        fail("INVALID_ARGUMENT", "/vocabulary_hash", "expected SHA-256")
    nonempty(doc["submitted_by"], "/submitted_by")
    if not isinstance(doc["phase"], str) or doc["phase"] not in {"preparation", "tagging", "extraction", "correction"}:
        fail("INVALID_ARGUMENT", "/phase")
    for key in ("records", "covered_clauses", "issues"):
        if not isinstance(doc[key], list):
            fail("INVALID_ARGUMENT", "/" + key, "expected array")
    for i, issue in enumerate(doc["issues"]):
        nonempty(issue, f"/issues/{i}")
    if (doc["phase"] == "extraction") != bool(doc["covered_clauses"]):
        fail("COVERAGE_INVALID", "/covered_clauses", "only extraction declares completed clauses")
    covered = set()
    for i, item in enumerate(doc["covered_clauses"]):
        path = f"/covered_clauses/{i}"
        fields(item, ["object_id", "record_id"], [], path)
        object_id = uuid_value(item["object_id"], path + "/object_id")
        uuid_value(item["record_id"], path + "/record_id")
        if object_id in covered:
            fail("COVERAGE_INVALID", path, "duplicate covered clause")
        covered.add(object_id)
    if "overview" in doc:
        if doc["phase"] != "preparation":
            fail("INVALID_ARGUMENT", "/overview", "overview only belongs to preparation")
        overview = fields(doc["overview"], ["text_versions", "body", "authored_by"], [], "/overview")
        if not isinstance(overview["text_versions"], list) or not overview["text_versions"]:
            fail("INVALID_ARGUMENT", "/overview/text_versions", "expected non-empty array")
        seen = []
        for i, ref in enumerate(overview["text_versions"]):
            path = f"/overview/text_versions/{i}"
            fields(ref, [], ["object_id", "local_id"], path)
            validate_reference_shape(ref, path)
            if ref in seen:
                fail("DUPLICATE_ID", path, "duplicate text version")
            seen.append(ref)
        nonempty(overview["body"], "/overview/body")
        nonempty(overview["authored_by"], "/overview/authored_by")


def validate_record_envelope(raw, path):
    fields(raw, ["local_id", "kind", "data", "evidence"],
           ["object_id", "previous_record_id", "status", "withdrawal_reason"], path)
    nonempty(raw["local_id"], path + "/local_id")
    if not isinstance(raw["kind"], str) or raw["kind"] not in KINDS:
        fail("INVALID_ARGUMENT", path + "/kind", "unsupported record kind")
    require_object(raw["data"], path + "/data")
    if not isinstance(raw["evidence"], list):
        fail("INVALID_ARGUMENT", path + "/evidence", "expected array")
    if ("object_id" in raw) != ("previous_record_id" in raw):
        fail("INVALID_ARGUMENT", path, "object_id and previous_record_id must appear together")
    if "object_id" in raw:
        uuid_value(raw["object_id"], path + "/object_id")
        uuid_value(raw["previous_record_id"], path + "/previous_record_id")
    status = raw.get("status", "active")
    if not isinstance(status, str) or status not in {"active", "withdrawn"}:
        fail("INVALID_ARGUMENT", path + "/status")
    if status == "withdrawn":
        if "object_id" not in raw:
            fail("INVALID_ARGUMENT", path + "/status", "new object cannot be withdrawn")
        nonempty(raw.get("withdrawal_reason"), path + "/withdrawal_reason")
    elif "withdrawal_reason" in raw:
        fail("UNKNOWN_FIELD", path + "/withdrawal_reason")
