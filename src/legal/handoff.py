"""Build existing reader task files from complete, current query results.

This is a library helper for the host's existing assignment step, not a CLI
command or a second task-state database. The caller chooses responsibilities.
"""

from __future__ import annotations

import json
from pathlib import Path

from .formats import exclusive_write, fail, fields, loads, nonempty, uuid_value
from .query import query


def _all(db_path, **options):
    items, offset, first = [], 0, None
    while True:
        page = query(db_path, {**options, "limit": 100, "offset": offset})
        first = first or page
        if page["case_id"] != first["case_id"] or page["quality"]["current_sequence"] != first["quality"]["current_sequence"]:
            fail("STALE_REVISION", "/tasks/input_files", "case changed during input export")
        items.extend(page["items"])
        if page["next_offset"] is None:
            return first, items
        offset = page["next_offset"]


def export_extraction_tasks(db_path, plans, output_dir, resource_root, clause_ids=None):
    """Export spec §10.1 tasks; reject missing, duplicate or stale assignments.

    Each plan has task_id, unit_id, responsible_clauses, context_clauses,
    group_file and output_file. The group must be an existing group export.
    output_dir is a new tasks subdirectory in the contract's directory.
    """
    contract = Path(db_path).resolve().parent
    destination = Path(output_dir).resolve()
    resources = Path(resource_root).resolve()
    if not destination.is_relative_to(contract / "tasks"):
        fail("INVALID_ARGUMENT", "/tasks/output_dir", "task inputs must stay under contract/tasks")
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        fail("FILE_EXISTS", "/tasks/output_dir", "task directory is not empty")
    if not isinstance(plans, list) or not plans:
        fail("INVALID_ARGUMENT", "/tasks", "nonempty task plans required")
    basis, progress = _all(db_path, view="progress")
    material_by_text = {m["text_version_id"]: m["material_id"] for m in progress[0]["materials"]}
    text_ids = set(material_by_text)
    exports = {}
    for name, options in (
        ("frozen-vocabulary.json", {"view": "vocabulary"}),
        ("overview.json", {"view": "overview"}),
        ("events.json", {"view": "events"}),
        ("shared-objects.json", {"view": "records", "kinds": ["node"]}),
        ("clauses.json", {"view": "clauses"}),
    ):
        header, items = _all(db_path, **options)
        if header["case_id"] != basis["case_id"] or header["quality"]["current_sequence"] != basis["quality"]["current_sequence"]:
            fail("STALE_REVISION", "/tasks/input_files", "case changed during input export")
        if name == "clauses.json":
            items = [item for item in items if item["data"]["text_version"]["object_id"] in text_ids]
        exports[name] = {"case_id": basis["case_id"], "checked_sequence": basis["quality"]["current_sequence"], "items": items}
    if not exports["overview.json"]["items"]:
        fail("INVALID_ARGUMENT", "/tasks/input_files/overview", "preparation overview must be available")
    current = {item["object_id"]: item for item in exports["clauses.json"]["items"]}
    if clause_ids is not None:
        if not isinstance(clause_ids, (list, tuple, set, frozenset)):
            fail("INVALID_ARGUMENT", "/tasks/clause_ids", "expected clause ID collection")
        for index, identifier in enumerate(clause_ids):
            uuid_value(identifier, f"/tasks/clause_ids/{index}")
    expected = set(current) if clause_ids is None else set(clause_ids)
    if not expected or not expected <= current.keys():
        fail("COVERAGE_INVALID", "/tasks/responsible_clauses", "unknown or empty requested clause range")
    units = {u["id"] for u in exports["frozen-vocabulary.json"]["items"][0]["units"]}
    assigned, task_names, outputs, tasks = set(), set(), set(), []
    files = {name: (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
             for name, value in exports.items()}
    for source, name in ((resources / "skills/legal-case/references/extraction.md", "extraction.md"),
                         (resources / "references/data-formats.md", "data-formats.md")):
        if not source.is_file():
            fail("FILE_ERROR", str(source), "installed task reference missing")
        files[name] = source.read_bytes()
    for index, plan in enumerate(plans):
        path = f"/tasks/{index}"
        fields(plan, ["task_id", "unit_id", "responsible_clauses", "context_clauses", "group_file", "output_file"], [], path)
        nonempty(plan["task_id"], path + "/task_id")
        task_id = plan["task_id"]
        if task_id in task_names or Path(task_id).name != task_id or task_id in {".", ".."}:
            fail("INVALID_ARGUMENT", path + "/task_id", "task ID must be unique and a file name")
        task_names.add(task_id)
        unit = plan["unit_id"]
        if unit is not None:
            uuid_value(unit, path + "/unit_id")
            if unit not in units:
                fail("REFERENCE_NOT_FOUND", path + "/unit_id", "unit is absent from frozen vocabulary")
        for key in ("responsible_clauses", "context_clauses"):
            if not isinstance(plan[key], list) or key == "responsible_clauses" and not plan[key]:
                fail("INVALID_ARGUMENT", path + "/" + key, "expected clause reference list")
            seen = set()
            for j, ref in enumerate(plan[key]):
                at = f"{path}/{key}/{j}"
                fields(ref, ["object_id", "record_id"], [], at)
                for field in ("object_id", "record_id"):
                    uuid_value(ref[field], at + "/" + field)
                item = current.get(ref["object_id"])
                if item is None or item["record_id"] != ref["record_id"]:
                    fail("STALE_REVISION", at, "clause must be a current version in the selected text range")
                if ref["object_id"] in seen:
                    fail("COVERAGE_INVALID", at, "duplicate clause in task list")
                seen.add(ref["object_id"])
            if key == "responsible_clauses":
                if assigned & seen or not seen <= expected:
                    fail("COVERAGE_INVALID", path + "/" + key, "responsibilities overlap or exceed selected range")
                assigned.update(seen)
        group = Path(plan["group_file"]).resolve()
        if not group.is_relative_to(contract / "groups") or not group.is_file():
            fail("FILE_ERROR", path + "/group_file", "group must be in contract/groups")
        group_bytes = group.read_bytes()
        content = loads(group_bytes, path + "/group_file")
        fields(content, ["format_version", "case_id", "vocabulary_hash", "unit_id", "classification", "clauses"], [], path + "/group_file")
        if content["format_version"] != 1 or not isinstance(content["clauses"], list):
            fail("INVALID_ARGUMENT", path + "/group_file", "unsupported or malformed group export")
        if content["classification"] not in {"ordinary", "unmatched", "no_content"}:
            fail("INVALID_ARGUMENT", path + "/group_file/classification", "unsupported group classification")
        vocab_hash = exports["frozen-vocabulary.json"]["items"][0]["hash"]
        if content.get("case_id") != basis["case_id"] or content.get("vocabulary_hash") != vocab_hash or content.get("unit_id") != unit:
            fail("INVALID_ARGUMENT", path + "/group_file", "group case, vocabulary or unit differs")
        for clause in content["clauses"]:
            fields(clause, ["object_id", "record_id", "material_id", "text_version_id", "sequence", "original_number", "text", "tags", "context_clauses"], [], path + "/group_file/clauses")
            item = current.get(clause["object_id"])
            if item is None or any(clause[field] != (item["data"][field] if field in {"text", "tags", "sequence", "original_number"} else item[field])
                                   for field in ("record_id", "text", "tags", "sequence", "original_number")):
                fail("STALE_REVISION", path + "/group_file", "group clause differs from current database")
            text_id = item["data"]["text_version"]["object_id"]
            if clause["text_version_id"] != text_id or clause["material_id"] != material_by_text[text_id]:
                fail("STALE_REVISION", path + "/group_file", "group text or material identity differs from current database")
            if content["classification"] != item["data"]["classification"] or (unit is not None) != (content["classification"] == "ordinary") or unit is not None and unit not in clause["tags"]:
                fail("INVALID_ARGUMENT", path + "/group_file", "group classification or unit membership differs")
            if not isinstance(clause["context_clauses"], list):
                fail("INVALID_ARGUMENT", path + "/group_file/context_clauses", "expected context clause list")
            for context in clause.get("context_clauses", []):
                fields(context, ["object_id", "sequence", "text"], [], path + "/group_file/context_clauses")
                item = current.get(context["object_id"])
                if item is None or context["text"] != item["data"]["text"] or context["sequence"] != item["data"]["sequence"]:
                    fail("STALE_REVISION", path + "/group_file", "group context differs from current database")
        group_name = f"{task_id}-group.json"
        if group_name in files:
            fail("INVALID_ARGUMENT", path + "/task_id", "group filename conflicts with another task input")
        files[group_name] = group_bytes
        output = Path(plan["output_file"]).resolve()
        if not output.is_relative_to(contract / "submissions") or output in outputs or output.exists():
            fail("FILE_EXISTS", path + "/output_file", "output must be a new unique contract submission path")
        outputs.add(output)
        task = {"format_version": 1, "task_id": task_id, "unit_id": unit,
                "responsible_clauses": plan["responsible_clauses"], "context_clauses": plan["context_clauses"],
                "input_files": [str(destination / name) for name in (*exports, "extraction.md", "data-formats.md", group_name)],
                "output_file": str(output)}
        task_name = f"{task_id}.json"
        if task_name in files:
            fail("INVALID_ARGUMENT", path + "/task_id", "task filename conflicts with input snapshot")
        files[task_name] = (json.dumps(task, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        tasks.append(task)
    if assigned != expected:
        fail("COVERAGE_INVALID", "/tasks/responsible_clauses", "task union does not cover selected clause range")
    header, _ = _all(db_path, view="progress")
    if header["case_id"] != basis["case_id"] or header["quality"]["current_sequence"] != basis["quality"]["current_sequence"]:
        fail("STALE_REVISION", "/tasks/input_files", "case changed before publishing tasks")
    destination.mkdir(parents=True, exist_ok=True)
    created = []
    try:
        for name, data in files.items():
            target = destination / name
            exclusive_write(target, data)
            created.append(target)
    except Exception:
        for target in created:
            target.unlink(missing_ok=True)
        raise
    return {"case_id": basis["case_id"], "checked_sequence": basis["quality"]["current_sequence"],
            "tasks": tasks, "files": [str(path) for path in created]}
