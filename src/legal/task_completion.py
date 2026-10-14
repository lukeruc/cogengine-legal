"""Construct a task's submission from host bindings and explicit business data."""
from __future__ import annotations

import json
import sys

from . import reader_helpers as h
from .formats import Invalid, InvalidBatch, fail, fields, version


def complete(binding_file, issues_file, records_files=(), body_file=None, covered_file=None):
    # Validate file operands before reading the binding; a JSON literal passed
    # as --issues is an operand error, not a corrupt host binding.
    binding_file = h._absolute(binding_file, "--binding")
    issues_file = h._absolute(issues_file, "--issues")
    records_files = [h._absolute(p, "--records") for p in records_files]
    if body_file is not None:
        body_file = h._absolute(body_file, "--body")
    if covered_file is not None:
        covered_file = h._absolute(covered_file, "--covered-clauses")
    binding = h.read_json(binding_file)
    try:
        version(binding.get("format_version") if isinstance(binding, dict) else None)
        mode = binding.get("mode")
        if mode not in {"preparation_records", "preparation_overview", "tagging", "extraction"}:
            fail("INVALID_ARGUMENT", "/mode", "unknown task binding mode")
        overview = mode == "preparation_overview"
        fields(binding, ["format_version", "mode", "case_id", "vocabulary_hash", "submitted_by", "output_file"] +
               (["overview_text_versions", "overview_authored_by"] if overview else []))
        h._absolute(binding["output_file"], "/output_file")
        if overview:
            if records_files or body_file is None or covered_file is not None:
                fail("INVALID_ARGUMENT", "/arguments", "overview requires body; records and covered clauses forbidden")
        elif body_file is not None or not records_files or (mode == "extraction") != (covered_file is not None):
            fail("INVALID_ARGUMENT", "/arguments", "records required; covered clauses only and always for extraction")
        issues = h.read_json(issues_file)
        if not isinstance(issues, list) or any(not isinstance(i, str) for i in issues):
            fail("INVALID_ARGUMENT", "/issues", "explicit string array required", file=str(issues_file))
        covered = h.read_json(covered_file) if covered_file is not None else []
        args = dict(format_version=1, case_id=binding["case_id"], vocabulary_hash=binding["vocabulary_hash"],
                    submitted_by=binding["submitted_by"],
                    phase="preparation" if mode.startswith("preparation_") else mode,
                    covered_clauses=covered, issues=issues)
        if overview:
            body = h.read_text(body_file)
            if not body.strip():
                fail("INVALID_ARGUMENT", "/overview/body", "nonblank body required", file=str(body_file))
            args["overview"] = {"text_versions": binding["overview_text_versions"], "body": body,
                                "authored_by": binding["overview_authored_by"]}
        header = h.header(**args)
    except Invalid as exc:
        if exc.code == "UNKNOWN_FIELD":
            exc.code = "INVALID_ARGUMENT"
        actual_file = covered_file if exc.path.startswith("/covered_clauses") and covered_file is not None else binding_file
        exc.details.setdefault("file", str(actual_file))
        raise
    groups = [h.read_json(p) for p in records_files] if records_files else [[]]
    for path, group in zip(records_files, groups):
        if not isinstance(group, list):
            fail("INVALID_ARGUMENT", "", "records must be an array", file=str(path))
    normalized = [str(h._absolute(p, "--records").resolve()) for p in records_files]
    if len(normalized) != len(set(normalized)):
        fail("INVALID_ARGUMENT", "--records", "duplicate records file")
    document = h._assemble(header, groups, binding_file, list(records_files) if records_files else [body_file])
    h.write_json(binding["output_file"], document)
    return {"ok": True, "scope": "task_files", "output_file": binding["output_file"],
            "record_count": len(document["records"])}


def main(argv=None):
    parser = h._Parser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--binding", required=True, action=h._Single)
    parser.add_argument("--issues", required=True, action=h._Single)
    parser.add_argument("--records", action="append", default=[])
    parser.add_argument("--body", action=h._Single)
    parser.add_argument("--covered-clauses", action=h._Single)
    try:
        args = parser.parse_args(argv)
        result = complete(args.binding, args.issues, args.records, args.body, args.covered_clauses)
        code = 0
    except (Invalid, InvalidBatch, OSError, ValueError, RecursionError) as exc:
        items = [exc.item()] if isinstance(exc, Invalid) else exc.items if isinstance(exc, InvalidBatch) else [
            {"code": "FILE_ERROR" if isinstance(exc, OSError) else "INVALID_ARGUMENT", "path": "", "message": str(exc)}]
        result, code = {"ok": False, "scope": "task_files", "errors": items}, 2
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return code
