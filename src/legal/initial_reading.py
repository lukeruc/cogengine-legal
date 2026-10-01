"""Prepare fixed, continuous reading inputs for the existing preparation step.

Library helpers only: no new CLI, database state or semantic completion check.
Reader notes remain Markdown work files; the host submits preparation with write.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .formats import digest, exclusive_write, fail, fields, integer, read_json, uuid_value
from .handoff import _all


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _bytes(path):
    try:
        return Path(path).read_bytes()
    except OSError as exc:
        fail("FILE_ERROR", str(path), str(exc))


def _manifest(path, contract):
    path = Path(path).resolve()
    if not path.is_relative_to(contract / "tasks"):
        fail("INVALID_ARGUMENT", "/reading/manifest", "manifest must stay under contract/tasks")
    manifest = read_json(path)
    fields(manifest, ["format_version", "case_id", "checked_sequence", "target_chars", "window_chars",
                      "selected_text_versions", "materials", "directory", "tasks", "preparation_file",
                      "references", "input_hashes"], [], "/reading/manifest")
    if type(manifest["format_version"]) is not int or manifest["format_version"] != 1:
        fail("UNSUPPORTED_VERSION", "/reading/format_version", "unsupported reading work file version")
    for name in ("materials", "directory", "tasks", "references", "selected_text_versions"):
        if not isinstance(manifest[name], list) or not manifest[name]:
            fail("INVALID_ARGUMENT", "/reading/" + name, "nonempty list required")
    if not isinstance(manifest["input_hashes"], dict):
        fail("INVALID_ARGUMENT", "/reading/input_hashes", "expected input file hashes")
    for filename, expected in manifest["input_hashes"].items():
        source = (path.parent / filename).resolve()
        if not source.is_relative_to(path.parent):
            fail("INVALID_ARGUMENT", "/reading/input_hashes", "input path leaves reading directory")
        if digest(_bytes(source)) != expected:
            fail("STALE_REVISION", str(source), "fixed reading input changed")
    for reference in manifest["references"]:
        if not Path(reference).is_file():
            fail("FILE_ERROR", reference, "installed reading reference missing")
    return manifest


def _snapshot(db_path):
    basis, progress = _all(db_path, view="progress")
    sequence = basis["quality"]["current_sequence"]
    exports = {}
    for name, options in (
        ("materials", {"view": "materials"}),
        ("texts", {"view": "records", "kinds": ["text_version"]}),
        ("clauses", {"view": "clauses"}),
        ("vocabulary", {"view": "vocabulary"}),
        ("overview", {"view": "overview"}),
        ("events", {"view": "events"}),
        ("shared-objects", {"view": "records", "kinds": ["node"]}),
    ):
        header, items = _all(db_path, **options)
        if header["case_id"] != basis["case_id"] or header["quality"]["current_sequence"] != sequence:
            fail("STALE_REVISION", "/reading/inputs", "case changed during reading export")
        exports[name] = {"case_id": basis["case_id"], "checked_sequence": sequence, "items": items}
    current = {m["text_version_id"]: m for m in progress[0]["materials"]}
    exports["texts"]["items"] = [t for t in exports["texts"]["items"] if t["object_id"] in current]
    exports["clauses"]["items"] = [c for c in exports["clauses"]["items"]
                                    if c["data"]["text_version"]["object_id"] in current]
    return basis, current, exports


def _publish(destination, files):
    destination.mkdir(parents=True, exist_ok=True)
    created = []
    try:
        for name, data in files.items():
            path = destination / name
            path.parent.mkdir(parents=True, exist_ok=True)
            exclusive_write(path, data)
            created.append(path)
    except Exception:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise
    return [str(path) for path in created]


def _contexts(clauses):
    """Retain preceding structural headings as context, never as new ranges."""
    prior, result = {}, {}
    for clause in clauses:
        first = clause["data"]["text"].split("\n", 1)[0]
        heading = re.match(r"^ {0,3}(#{1,6})[ \t]+", first)
        if heading:
            level = len(heading.group(1))
            result[clause["object_id"]] = [prior[k] for k in sorted(prior) if k < level]
            prior = {k: v for k, v in prior.items() if k < level}
            if ".unnumbered" not in first:
                prior[level] = clause["object_id"]
        elif re.match(r"^\s*(?:第[一二三四五六七八九十百千\d]+章|CHAPTER\s+(?:[IVXLCDM]+|\d+)\b)", first, re.I):
            prior = {0: clause["object_id"]}
            result[clause["object_id"]] = []
        else:
            result[clause["object_id"]] = list(prior.values()) if clause["data"]["original_number"] else []
    return result


def export_initial_reading_tasks(db_path, output_dir, resource_root, preparation_file,
                                text_version_ids=None, target_chars=20_000, window_chars=6_000):
    """Export all inputs before dispatch, partitioning whole current clauses.

    output_dir is a new/empty numbered directory under contract/tasks.
    preparation_file is a caller-assigned unused path under submissions.
    text_version_ids selects complete current materials for an incremental pass;
    all current materials remain available for directed contextual rereading.
    window_chars is independently chosen for the host's tool output capacity.
    """
    integer(target_chars, "/reading/target_chars", 1)
    integer(window_chars, "/reading/window_chars", 1)
    contract = Path(db_path).resolve().parent
    destination = Path(output_dir).resolve()
    output = Path(preparation_file).resolve()
    if not destination.is_relative_to(contract / "tasks") or destination == contract / "tasks":
        fail("INVALID_ARGUMENT", "/reading/output_dir", "use a new contract/tasks subdirectory")
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        fail("FILE_EXISTS", "/reading/output_dir", "reading directory is not empty")
    if not output.is_relative_to(contract / "submissions") or output == contract / "submissions" or output.exists():
        fail("FILE_EXISTS", "/reading/preparation_file", "use an unused contract submission path")
    resources = Path(resource_root).resolve()
    references = [resources / "skills/legal-case/references/preparation.md",
                  resources / "references/data-formats.md"]
    dependencies = [resources / "skills/legal-case/references/reading-inputs.md",
                    resources / "skills/legal-case/references/handoff.md",
                    resources / "references/case-cli.md"]
    for path in references + dependencies:
        if not path.is_file():
            fail("FILE_ERROR", str(path), "installed reading reference missing")
    basis, current, exports = _snapshot(db_path)
    if text_version_ids is None:
        selected = set(current)
    else:
        if not isinstance(text_version_ids, (list, tuple, set, frozenset)):
            fail("INVALID_ARGUMENT", "/reading/text_version_ids", "expected text version collection")
        for index, identifier in enumerate(text_version_ids):
            uuid_value(identifier, f"/reading/text_version_ids/{index}")
        selected = set(text_version_ids)
    if not selected or not selected <= current.keys():
        fail("COVERAGE_INVALID", "/reading/text_version_ids", "select nonempty current text versions")
    texts = {t["object_id"]: t for t in exports["texts"]["items"]}
    materials = {m["object_id"]: m for m in exports["materials"]["items"]}
    clauses_by_text = {identifier: [] for identifier in current}
    for clause in exports["clauses"]["items"]:
        clauses_by_text[clause["data"]["text_version"]["object_id"]].append(clause)
    files = {f"{name}.json": _json_bytes(value) for name, value in exports.items()}
    directory, material_list, segments = [], [], []
    # UUID sorting only makes presentation stable; it implies no legal priority.
    for text_index, text_id in enumerate(sorted(current), 1):
        text_record = texts[text_id]
        text = text_record["data"]["text"]
        material_id = current[text_id]["material_id"]
        material = materials[material_id]
        full_name = f"texts/{text_index:04d}-text.txt"
        files[full_name] = text.encode("utf-8")
        material_list.append({"object_id": material_id, "record_id": material["record_id"],
                              "name": material["data"]["name"], "text_version_id": text_id,
                              "text_record_id": text_record["record_id"], "char_length": len(text),
                              "text_file": str(destination / full_name),
                              "main_reading": text_id in selected,
                              "anomalies": text_record["data"]["anomalies"]})
        clauses = sorted(clauses_by_text[text_id], key=lambda c: c["data"]["sequence"])
        if text_id in selected and not current[text_id]["split_completed"]:
            fail("COVERAGE_INVALID", "/reading/clauses", "split selected material before preparing reading")
        contexts = _contexts(clauses)
        position, sequences, pending, pending_size = 0, set(), [], 0
        for clause in clauses:
            data = clause["data"]
            start, end = data["start_offset"], data["end_offset"]
            if (data["sequence"] in sequences or start != position or end <= start or
                    text[start:end] != data["text"] or end > len(text)):
                fail("COVERAGE_INVALID", "/reading/clauses", "clause ranges must reconstruct text in sequence order")
            sequences.add(data["sequence"])
            position = end
            name = f"clauses/{text_index:04d}-{data['sequence']:04d}.txt"
            files[name] = data["text"].encode("utf-8")
            entry = {"object_id": clause["object_id"], "record_id": clause["record_id"],
                     "material_id": material_id, "material_record_id": material["record_id"],
                     "text_version_id": text_id, "text_record_id": text_record["record_id"],
                     "sequence": data["sequence"], "original_number": data["original_number"],
                     "label": data["original_number"] or f"区域 {data['sequence']} [{start},{end})",
                     "char_length": len(data["text"]), "start_offset": start, "end_offset": end,
                     "text_file": str(destination / name), "text_sha256": digest(data["text"].encode("utf-8")),
                     "context_clauses": contexts[clause["object_id"]], "reading_status": "unread"}
            directory.append(entry)
            if text_id not in selected:
                continue
            size = entry["char_length"]
            if pending and pending_size + size > target_chars:
                segments.append(pending)
                pending, pending_size = [], 0
            pending.append(entry)
            pending_size += size
            if size > target_chars:
                segments.append(pending)
                pending, pending_size = [], 0
        if text_id in selected and position != len(text):
            fail("COVERAGE_INVALID", "/reading/clauses", "selected material is not fully covered")
        if pending:
            segments.append(pending)
    if not segments:
        fail("COVERAGE_INVALID", "/reading/clauses", "selected materials have no reading ranges")
    entries = {c["object_id"]: c for c in directory}
    common = [str(path) for path in references] + [str(destination / name) for name in
              ("manifest.json", "directory.md", "materials.json", "vocabulary.json", "overview.json", "events.json", "shared-objects.json")]
    tasks = []
    for index, segment in enumerate(segments, 1):
        task_id = f"{index:04d}-reading"
        windows = []
        for clause_index, entry in enumerate(segment, 1):
            original = files[str(Path(entry["text_file"]).relative_to(destination))].decode("utf-8")
            for window_index, start in enumerate(range(0, len(original), window_chars), 1):
                end = min(start + window_chars, len(original))
                name = f"windows/{task_id}-{clause_index:04d}-{window_index:04d}.txt"
                files[name] = original[start:end].encode("utf-8")
                windows.append({"clause_id": entry["object_id"], "clause_record_id": entry["record_id"],
                                "clause_start": start, "clause_end": end,
                                "text_start": entry["start_offset"] + start,
                                "text_end": entry["start_offset"] + end,
                                "file": str(destination / name), "reading_status": "unread"})
        context_ids = list(dict.fromkeys(c for entry in segment for c in entry["context_clauses"]))
        context = [entries[c] for c in context_ids]
        # Management headings live in a companion document, never inside raw files.
        guide_name = f"{task_id}.md"
        guide = [f"# {task_id}\n\n主读顺序如下；逐个读取全部窗口，截断须补读。\n"]
        for entry in segment:
            guide.append(f"\n## {entry['label']}\n\n条款 {entry['object_id']} / {entry['record_id']}；"
                         f"文本版本 {entry['text_version_id']}；[{entry['start_offset']},{entry['end_offset']})。\n")
            for identifier in entry["context_clauses"]:
                guide.append(f"\n上级原文上下文：{entries[identifier]['text_file']}\n")
            for window in windows:
                if window["clause_id"] == entry["object_id"]:
                    guide.append(f"\n- [{window['clause_start']},{window['clause_end']})：{window['file']}\n")
        files[guide_name] = "".join(guide).encode("utf-8")
        task = {"format_version": 1, "task_id": task_id,
                "role": "reading_and_synthesis" if len(segments) == 1 else "segment_reading",
                "main_reading_clauses": [{"object_id": e["object_id"], "record_id": e["record_id"]} for e in segment],
                "context_clauses": context, "windows": windows,
                "input_files": common + [str(destination / guide_name)] + [e["text_file"] for e in context],
                "output_file": str(destination / f"{index:04d}-notes.md"),
                "preparation_file": str(output) if len(segments) == 1 else None}
        files[f"{task_id}.json"] = _json_bytes(task)
        tasks.append(task)
    manifest = {"format_version": 1, "case_id": basis["case_id"],
                "checked_sequence": basis["quality"]["current_sequence"],
                "target_chars": target_chars, "window_chars": window_chars,
                "selected_text_versions": sorted(selected), "materials": material_list,
                "directory": directory, "tasks": tasks, "preparation_file": str(output),
                "references": [str(path) for path in references]}
    directory_text = ["# 全文阅读目录\n\n字符位置为 Unicode 半开区间。素材展示顺序不表示法律优先顺位。"
                      "本清单仅列已提供材料；引用但未提供的材料由实际阅读笔记记录。\n"]
    for material in material_list:
        directory_text.append(f"\n## {material['name']}\n\n素材 {material['object_id']} / {material['record_id']}；"
                              f"文本 {material['text_version_id']} / {material['text_record_id']}；"
                              f"{material['char_length']} 字符；全文入口 {material['text_file']}。\n")
        for entry in directory:
            if entry["material_id"] == material["object_id"]:
                directory_text.append(f"\n- {entry['label']}：{entry['object_id']} / {entry['record_id']}；"
                                      f"sequence={entry['sequence']}；{entry['char_length']} 字符；"
                                      f"[{entry['start_offset']},{entry['end_offset']})；{entry['text_file']}\n")
    files["directory.md"] = "".join(directory_text).encode("utf-8")
    manifest["input_hashes"] = {name: digest(data) for name, data in files.items()}
    files["manifest.json"] = _json_bytes(manifest)
    header, _ = _all(db_path, view="progress")
    if header["case_id"] != basis["case_id"] or header["quality"]["current_sequence"] != basis["quality"]["current_sequence"]:
        fail("STALE_REVISION", "/reading/inputs", "case changed before publishing reading tasks")
    created = _publish(destination, files)
    return {"case_id": basis["case_id"], "checked_sequence": manifest["checked_sequence"],
            "manifest_file": str(destination / "manifest.json"), "tasks": tasks, "files": created}


def check_reading_versions(db_path, manifest_file):
    """Check note reuse against current identities, not an 'already read' flag.

    This allows unrelated submissions while rejecting replaced text/clause input.
    It does not check whether the reader read, or whether its notes are accurate.
    """
    manifest_path = Path(manifest_file).resolve()
    manifest = _manifest(manifest_path, Path(db_path).resolve().parent)
    basis, current, exports = _snapshot(db_path)
    if manifest["case_id"] != basis["case_id"]:
        fail("STALE_REVISION", "/reading/case_id", "reading inputs belong to another contract")
    current_texts = {t["object_id"]: t for t in exports["texts"]["items"]}
    current_materials = {m["object_id"]: m for m in exports["materials"]["items"]}
    current_clauses = {c["object_id"]: c for c in exports["clauses"]["items"]}
    old_text_ids = {m["text_version_id"] for m in manifest["materials"]}
    old_clause_ids = {entry["object_id"] for entry in manifest["directory"]}
    expected_clause_ids = {c["object_id"] for c in exports["clauses"]["items"]
                           if c["data"]["text_version"]["object_id"] in old_text_ids}
    if old_clause_ids != expected_clause_ids:
        fail("STALE_REVISION", "/reading/directory", "clause range changed; reassess affected reading")
    for material in manifest["materials"]:
        text = current_texts.get(material["text_version_id"])
        original = current_materials.get(material["object_id"])
        if not text or not original or text["record_id"] != material["text_record_id"] or original["record_id"] != material["record_id"]:
            fail("STALE_REVISION", "/reading/materials", "material/text version changed; reassess affected reading")
        if _bytes(material["text_file"]) != text["data"]["text"].encode("utf-8"):
            fail("STALE_REVISION", "/reading/materials", "exported full text differs from fixed version")
    for entry in manifest["directory"]:
        clause = current_clauses.get(entry["object_id"])
        if not clause or clause["record_id"] != entry["record_id"]:
            fail("STALE_REVISION", "/reading/directory", "clause version changed; reassess affected reading")
        raw = _bytes(entry["text_file"])
        if digest(raw) != entry["text_sha256"] or raw != clause["data"]["text"].encode("utf-8"):
            fail("STALE_REVISION", "/reading/directory", "exported original differs from fixed clause")
    return {"case_id": basis["case_id"], "current_sequence": basis["quality"]["current_sequence"],
            "versions_match": True, "additional_text_versions": sorted(set(current) - old_text_ids)}


def export_initial_synthesis_task(db_path, manifest_file, output_file):
    """Collect existing notes into one synthesis assignment after host inspection.

    File existence is checked here; actual reading and question handling must be
    inspected by the host/reader. A single reading task continues on its same
    reader; this helper never spawns agents or writes preparation to SQLite.
    """
    manifest_path = Path(manifest_file).resolve()
    contract = Path(db_path).resolve().parent
    destination = Path(output_file).resolve()
    if not manifest_path.is_relative_to(contract / "tasks") or destination.parent != manifest_path.parent:
        fail("INVALID_ARGUMENT", "/reading/synthesis", "use the original contract task directory")
    manifest = _manifest(manifest_path, contract)
    check_reading_versions(db_path, manifest_path)
    # Shared identities may have changed while readers worked. Re-export them
    # into this synthesis input so the reader reuses the latest formal objects.
    basis, _, exports = _snapshot(db_path)
    notes = []
    for task in manifest["tasks"]:
        path = Path(task["output_file"]).resolve()
        if not path.is_relative_to(manifest_path.parent) or not path.is_file():
            fail("FILE_ERROR", "/reading/notes", "all assigned note files must be present; return missing ranges to readers")
        try:
            contents = _bytes(path).decode("utf-8", errors="strict")
        except UnicodeError as exc:
            fail("FILE_ERROR", str(path), str(exc))
        if not contents.strip():
            fail("FILE_ERROR", "/reading/notes", "empty note file; return unread ranges to reader")
        notes.append(str(path))
    preparation = Path(manifest["preparation_file"]).resolve()
    if not preparation.is_relative_to(contract / "submissions") or preparation.exists():
        fail("FILE_EXISTS", "/reading/preparation_file", "query/replay an existing preparation instead of creating duplicate identities")
    if destination.exists() or destination.suffix != ".json":
        fail("FILE_EXISTS", "/reading/synthesis", "use an unused JSON task file")
    context_name = destination.stem + "-shared.json"
    context = {key: exports[key] for key in ("overview", "events", "shared-objects", "vocabulary")}
    task = {"format_version": 1, "task_id": destination.stem, "role": "synthesis",
            "continue_reader_task_id": manifest["tasks"][0]["task_id"] if len(manifest["tasks"]) == 1 else None,
            "case_id": manifest["case_id"], "checked_sequence": basis["quality"]["current_sequence"],
            "input_files": manifest["references"] + [str(manifest_path), str(manifest_path.parent / "directory.md"),
                           str(manifest_path.parent / context_name)] + notes,
            "output_file": str(preparation), "covered_clauses": []}
    header, _ = _all(db_path, view="progress")
    if header["case_id"] != basis["case_id"] or header["quality"]["current_sequence"] != task["checked_sequence"]:
        fail("STALE_REVISION", "/reading/synthesis", "case changed before publishing synthesis task")
    # Repeat the input-version check against the synthesis snapshot, since a
    # change could have happened between the initial check and shared export.
    freshness = check_reading_versions(db_path, manifest_path)
    if freshness["current_sequence"] != task["checked_sequence"]:
        fail("STALE_REVISION", "/reading/synthesis", "case changed during synthesis preparation")
    _publish(manifest_path.parent, {context_name: _json_bytes(context), destination.name: _json_bytes(task)})
    return task
