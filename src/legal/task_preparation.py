"""Deterministic host preparation, without models or a second task state store."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import runpy
import sys

from .formats import (Invalid, digest, exclusive_write, fail, fields as checked_fields, file_bytes, file_text,
                      integer, loads, nonempty, read_json, uuid_value, version)
from .vocabulary import load as load_vocabulary


def fields(value, required, optional=(), path=""):
    try:
        return checked_fields(value, required, optional, path)
    except Invalid as exc:
        if exc.code == "UNKNOWN_FIELD":
            exc.code = "INVALID_ARGUMENT"
        raise


def absolute(value, path):
    if not isinstance(value, (str, Path)) or not Path(value).is_absolute() or "\x00" in str(value):
        fail("INVALID_ARGUMENT", path, "absolute path required")
    return Path(value).resolve()


def context_text(path, contract):
    file = absolute(path, "/task_context_file")
    if not file.is_relative_to(contract / "tasks"):
        fail("INVALID_ARGUMENT", "/task_context_file", "context must be under contract/tasks")
    text = file_text(file)
    nonempty(text, "/task_context_file")
    return text


def output_directory(path, contract):
    result = absolute(path, "/output_dir")
    if result == contract / "tasks" or not result.is_relative_to(contract / "tasks"):
        fail("INVALID_ARGUMENT", "/output_dir", "new tasks subdirectory required")
    if result.exists() and (not result.is_dir() or any(result.iterdir())):
        fail("FILE_EXISTS", "/output_dir", "output directory must be empty")
    return result


def binding(mode, task, vocab_hash, submitted_by, text_ids=()):
    result = {"format_version": 1, "mode": mode, "case_id": task["case_id"],
              "vocabulary_hash": vocab_hash, "submitted_by": submitted_by, "output_file": task["output_file"]}
    if mode == "preparation_overview":
        result.update(overview_text_versions=[{"object_id": i} for i in text_ids], overview_authored_by=submitted_by)
    return result


def overview_context(snapshot):
    result = "\n\n正式案件概要（背景，不代替原文来源）：\n"
    for item in snapshot["items"]:
        result += "overview_id=" + item["overview_id"] + "；text_versions=" + json.dumps(item["text_versions"]) + "\n\n" + item["body"] + "\n"
    return result


def instructions(resources, template, context, task, details, on_demand=(), binding_data=None):
    fixed = file_text(resources / "skills/legal-case/templates" / (template + ".md"))
    fixed = fixed.split("## 二、共享任务总体上下文", 1)[0].rstrip()
    body = fixed + "\n\n## 二、共享任务总体上下文\n\n" + context + "\n\n## 三、个别任务要求\n\n"
    body += f"task_id：{task['task_id']}；职责：{task.get('purpose', 'reading')}。\n\n{details}\n\n"
    body += "### 可读文件白名单\n\n"
    for path in task["input_files"]:
        if path == task.get("binding_file"):
            usage = "仅供 complete_task 程序读取固定参数；模型无需探测结构，不修改"
        elif path in on_demand:
            usage = "按需：具体歧义/依据不足时定向回读原文；构造时查适用格式/样例，程序可读完整快照"
        else:
            usage = "开始阅读：完整内容；用于本任务判断与理解"
        body += f"- `{path}`：{usage}。\n"
    body += f"\n唯一输出：`{task['output_file']}`。工作文件仅限 `{Path(task['instructions_file']).parent / (task['task_id'] + '-work')}`，可创建并读取自己的工作文件。\n"
    if binding_data:
        tool = resources / "skills/legal-case/scripts/complete_task.py"
        body += f"\n专用解释器：`{sys.executable}`；允许执行 `{tool}`（执行不授予源码读取权限）。\n"
        argv = [sys.executable, str(tool), "--binding", task["binding_file"], "--issues", "<本任务 issues 数组文件>"]
        if binding_data["mode"] == "preparation_overview":
            argv += ["--body", "<六栏目 UTF-8 正文文件>"]
            body += "只填写六栏目正文及显式 issues 字符串数组；不构造节点、锚或信封。\n"
        else:
            argv += ["--records", "<本任务记录数组文件；可重复 --records>"]
            body += "业务文件是严格 JSON 记录数组；issues 为显式字符串数组（可为 []）。固定信封取绑定，不重新拼写。\n"
            if binding_data["mode"] == "extraction":
                argv += ["--covered-clauses", "<本人明确认定的覆盖数组文件>"]
            if any(Path(p).name == "clauses.json" for p in task["input_files"]):
                quote_tool = resources / "skills/legal-case/scripts/find_quote.py"
                clauses = next(p for p in task["input_files"] if Path(p).name == "clauses.json")
                body += "精确锚命令参数数组：" + json.dumps([sys.executable, str(quote_tool), "--clauses", clauses,
                           "--input", "<引句请求数组>", "--output", "<锚数组>"], ensure_ascii=False) + "。\n"
                body += '引句请求项：{"local_id":"a1","clause_record_id":"已交付的实际条款版本 UUID","quote":"逐字原句"}；重复匹配明确 occurrence。\n'
            body += "记录项包含 local_id、kind、data、evidence；同批引用 {local_id}，既有对象 {object_id}，固定版本 {record_id}。公开 legal.reader_helpers 函数可用；固定条款修订用 clause_revision。\n"
        body += "固定构造命令参数数组：" + json.dumps(argv, ensure_ascii=False) + "。替换业务文件参数为分配工作目录下绝对路径；完整保存 stdout、stderr 和退出码。\n"
    body += "\n返回实例名、task_id、产物路径、实际范围/记录数量、未完成内容及 issues；不将文件构造成功称为正式写入或语义通过。\n"
    return body


def workspace_selection(root, workspace_root, selected=None, contract_root=None):
    workspace = absolute(workspace_root, "/workspace_root")
    file = root / "workspaces.json"
    try:
        config = read_json(file)
        fields(config, ["format_version", "workspaces"])
        version(config["format_version"])
        if not isinstance(config["workspaces"], list):
            fail("INVALID_ARGUMENT", "/workspaces", "array required")
        found, seen = None, set()
        for index, item in enumerate(config["workspaces"]):
            at = f"/workspaces/{index}"
            fields(item, ["workspace_root", "contract_root", "vocabulary_list"], [], at)
            wr = absolute(item["workspace_root"], at + "/workspace_root")
            cr = absolute(item["contract_root"], at + "/contract_root")
            vl = absolute(item["vocabulary_list"], at + "/vocabulary_list")
            if not wr.is_dir() or wr in seen or not vl.is_relative_to(root / "vocabularies") or vl == root / "vocabularies":
                fail("INVALID_ARGUMENT", at, "workspace missing/duplicate or list outside installation/vocabularies")
            seen.add(wr)
            if wr == workspace:
                found = (cr, vl)
    except Invalid as exc:
        if exc.code != "FILE_ERROR":
            exc.code = "WORKSPACE_CONFIG_INVALID"
        exc.details["file"] = str(file)
        raise
    if found is None:
        fail("WORKSPACE_NOT_REGISTERED", "/workspace_root", "session workspace not registered", file=str(file))
    contract, listing = found
    paths, normalized = [], set()
    # Only LF and CRLF terminate a registry line; other Unicode characters
    # remain path characters instead of becoming implicit line delimiters.
    for number, raw in enumerate(file_text(listing).split("\n"), 1):
        line = raw[:-1] if raw.endswith("\r") else raw
        if not line.strip():
            continue
        at = f"/lines/{number}"
        try:
            path = absolute(line, at)
            if path in normalized:
                fail("INVALID_ARGUMENT", at, "duplicate normalized path")
        except Invalid as exc:
            exc.code = "VOCABULARY_LIST_INVALID"
            exc.details["file"] = str(listing)
            raise
        normalized.add(path)
        paths.append(path)
    if not paths:
        fail("VOCABULARY_NOT_CONFIGURED", "/vocabulary_list", "vocabulary list empty", file=str(listing))
    choice = absolute(selected, "/vocabulary") if selected is not None else paths[0]
    if choice not in paths:
        fail("VOCABULARY_NOT_REGISTERED", "/vocabulary", "selected file not registered", file=str(listing))
    if not choice.is_file():
        fail("FILE_ERROR", "/vocabulary", "selected vocabulary must be an existing file", file=str(choice))
    try:
        load_vocabulary(choice)
    except Invalid as exc:
        exc.details["file"] = str(choice)
        raise
    return choice, absolute(contract_root, "/contract_root") if contract_root is not None else contract


def _copy_plan(source, relative, plan):
    source = absolute(source, "/materials/path")
    if not source.is_file():
        fail("FILE_ERROR", "/materials/path", "input must be a file", file=str(source))
    content = file_bytes(source)
    for previous_source, previous_relative, previous_content in plan:
        if previous_relative == relative:
            if previous_source == source and previous_content == content:
                return
            fail("INVALID_ARGUMENT", str(relative), "conflicting copy targets")
    plan.append((source, relative, content))


def prepare_case(data, root):
    runtime_file = absolute(data["runtime_file"], "/runtime_file")
    if runtime_file != root / "runtime.json":
        fail("INVALID_ARGUMENT", "/runtime_file", "use this installation's runtime.json")
    bootstrap = runpy.run_path(str(root / "scripts/prepare_task.py"))
    checked = bootstrap["runtime"]({"format_version": 1, "skill_file": str(root / "skills/legal-case/SKILL.md"),
                                    "workspace_root": data["workspace_root"]})["result"]
    if Path(sys.prefix).resolve() != (root / ".venv").resolve():
        fail("INVALID_ARGUMENT", "/python", "case preparation requires the dedicated interpreter")
    vocabulary, parent = workspace_selection(root, checked["workspace_root"], data.get("vocabulary"), data.get("contract_root"))
    if not isinstance(data["materials"], list) or not data["materials"]:
        fail("INVALID_ARGUMENT", "/materials", "nonempty material array required")
    plan, config_source_hashes = [], {}
    _copy_plan(vocabulary, Path("inputs/vocabulary") / vocabulary.name, plan)
    for index, item in enumerate(data["materials"], 1):
        at = f"/materials/{index - 1}"
        fields(item, ["path"], ["converter_config"], at)
        source = absolute(item["path"], at + "/path")
        _copy_plan(source, Path("inputs/materials") / f"{index:03d}-{source.name}", plan)
        if "converter_config" in item:
            config_file = absolute(item["converter_config"], at + "/converter_config")
            raw_config = file_bytes(config_file)
            config_source_hashes[str(config_file)] = digest(raw_config)
            config = loads(raw_config, at + "/converter_config")
            fields(config, ["format_version", "argv"])
            version(config["format_version"])
            argv = config["argv"]
            if not isinstance(argv, list) or len(argv) < 3 or any(not isinstance(p, str) or not p for p in argv):
                fail("INVALID_ARGUMENT", at + "/converter_config/argv", "argument string array required")
            if argv.count("{input}") != 1 or argv.count("{output_dir}") != 1:
                fail("INVALID_ARGUMENT", at + "/converter_config/argv", "exact placeholders required")
            executable = absolute(argv[0], at + "/converter_config/argv/0")
            if not executable.is_file():
                fail("FILE_ERROR", at + "/converter_config/argv/0", "converter executable missing")
            # Resolve installed code; copy explicit non-code file operands with
            # their relative layout. No filesystem search or code discovery.
            prefix = Path(f"inputs/converters/{index:03d}/0001")
            copied_config = {"format_version": 1, "argv": list(argv)}
            for n, arg in enumerate(argv[1:], 1):
                if arg in {"{input}", "{output_dir}"} or arg.startswith("-"):
                    continue
                candidate = Path(arg) if Path(arg).is_absolute() else config_file.parent / arg
                if candidate.is_file():
                    if candidate.suffix.lower() in {".py", ".sh", ".exe", ".bat", ".ps1"} or os.access(candidate, os.X_OK):
                        copied_config["argv"][n] = str(candidate.resolve())
                    else:
                        relative = Path(arg) if not Path(arg).is_absolute() and ".." not in Path(arg).parts else Path("assets") / f"{n:03d}-{candidate.name}"
                        _copy_plan(candidate, prefix / relative, plan)
                        copied_config["argv"][n] = "./" + relative.as_posix()
            plan.append((config_file, prefix / "config.json", json_bytes(copied_config)))
    name = "contract-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    parent.mkdir(parents=True, exist_ok=True)
    index = 1
    while True:
        directory = parent / (name if index == 1 else f"{name}-{index:02d}")
        try:
            directory.mkdir()
            break
        except FileExistsError:
            index += 1
    source_hashes = {str(source): config_source_hashes[str(source)] if str(source) in config_source_hashes else digest(content)
                     for source, _, content in plan}
    for source, _, _ in plan:
        if digest(file_bytes(source)) != source_hashes[str(source)]:
            fail("ORIGINAL_CHANGED", str(source), "source changed during preparation")
    copied = []
    owned_paths = [directory]
    try:
        for source, relative, content in plan:
            target = directory / relative
            missing, parent_dir = [], target.parent
            while not parent_dir.exists():
                missing.append(parent_dir)
                parent_dir = parent_dir.parent
            for parent_dir in reversed(missing):
                parent_dir.mkdir()
                owned_paths.append(parent_dir)
            exclusive_write(target, content)
            owned_paths.append(target)
            if file_bytes(target) != content:
                fail("FILE_ERROR", str(target), "copy verification failed")
            if digest(file_bytes(source)) != source_hashes[str(source)]:
                fail("ORIGINAL_CHANGED", str(source), "source changed during copy")
            copied.append({"source": str(source), "target": str(target), "sha256": digest(content)})
        for name in ("tasks", "submissions", "receipts", "groups", "reports", "converted"):
            (directory / name).mkdir()
            owned_paths.append(directory / name)
    except Exception as exc:
        # The directory is ours exclusively; preserve all pre-existing paths.
        from .task_files import cleanup_owned
        cleanup_owned(owned_paths, exc)
        raise
    return {"ok": True, "operation": "case", "files": [c["target"] for c in copied],
            "result": {"contract_dir": str(directory), "db_path": str(directory / "contract.sqlite"), "copied": copied}}


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def validate_reader_reports(manifest, reports):
    if not isinstance(reports, list):
        fail("INVALID_ARGUMENT", "/reader_reports", "array required")
    expected = {t["task_id"]: t for t in manifest["tasks"]}
    seen, notes = set(), []
    for index, report in enumerate(reports):
        at = f"/reader_reports/{index}"
        fields(report, ["task_id", "notes_file", "read_ranges", "unread_ranges", "issues"], [], at)
        task = expected.get(report["task_id"])
        if task is None or report["task_id"] in seen:
            fail("INVALID_ARGUMENT", at + "/task_id", "unknown or duplicate reader task")
        seen.add(report["task_id"])
        file = absolute(report["notes_file"], at + "/notes_file")
        if str(file) != task["output_file"]:
            fail("INVALID_ARGUMENT", at + "/notes_file", "use assigned notes file")
        if not file_text(file).strip():
            fail("INVALID_ARGUMENT", at + "/notes_file", "notes blank", file=str(file))
        for key in ("read_ranges", "unread_ranges"):
            if not isinstance(report[key], list):
                fail("INVALID_ARGUMENT", at + "/" + key, "range array required")
            for j, r in enumerate(report[key]):
                pos = f"{at}/{key}/{j}"
                fields(r, ["text_version_id", "start_offset", "end_offset"], [], pos)
                uuid_value(r["text_version_id"], pos + "/text_version_id")
                integer(r["start_offset"], pos + "/start_offset", 0)
                integer(r["end_offset"], pos + "/end_offset", 1)
                if r["start_offset"] >= r["end_offset"]:
                    fail("INVALID_ARGUMENT", pos, "nonempty half-open range required")
        if report["unread_ranges"]:
            fail("INVALID_ARGUMENT", at + "/unread_ranges", "unread ranges remain; return to reader")
        required = [e for e in manifest["directory"] if e["object_id"] in {c["object_id"] for c in task["main_reading_clauses"]}]
        intervals = {}
        for r in report["read_ranges"]:
            intervals.setdefault(r["text_version_id"], []).append((r["start_offset"], r["end_offset"]))
        expected_ranges = {}
        for e in required:
            expected_ranges.setdefault(e["text_version_id"], []).append((e["start_offset"], e["end_offset"]))
        def union(ranges):
            merged = []
            for start, end in sorted(ranges):
                if merged and start <= merged[-1][1]:
                    merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
                else:
                    merged.append((start, end))
            return merged
        if {k: union(v) for k, v in intervals.items()} != {k: union(v) for k, v in expected_ranges.items()}:
            fail("INVALID_ARGUMENT", at + "/read_ranges", "reported main coverage differs from assigned range")
        if not isinstance(report["issues"], list) or any(not isinstance(v, str) for v in report["issues"]):
            fail("INVALID_ARGUMENT", at + "/issues", "string array required")
        notes.append(str(file))
    if seen != set(expected):
        fail("INVALID_ARGUMENT", "/reader_reports", "missing reader reports")
    return notes


def _result(operation, exported, manifest=None):
    tasks = []
    for task in exported["tasks"]:
        task_file = str(Path(task["instructions_file"]).parent / (task["task_id"] + ".json"))
        role = task.get("role", "extractor")
        tasks.append({"task_id": task["task_id"], "role": role,
                      "purpose": task.get("purpose", "extraction" if role == "extractor" else "reading"),
                      "task_file": task_file, "instructions_file": task["instructions_file"],
                      "binding_file": task.get("binding_file"), "output_file": task["output_file"]})
    return {"ok": True, "operation": operation, "files": exported["files"],
            "result": {"manifest_file": manifest, "tasks": tasks}}


def prepare(operation, data, resource_root):
    contracts = {
        "case": (["runtime_file", "workspace_root", "materials"], ["vocabulary", "contract_root"]),
        "reading": (["db_path", "output_dir", "task_context_file", "preparation_files"], ["text_version_ids", "target_chars", "window_chars"]),
        "synthesis": (["db_path", "manifest_file", "output_dir", "reader_reports"], []),
        "tagging": (["db_path", "output_dir", "task_context_file", "plans"], []),
        "extraction": (["db_path", "output_dir", "task_context_file", "plans"], ["clause_ids"])}
    required, optional = contracts[operation]
    fields(data, ["format_version", *required], optional)
    version(data["format_version"])
    root = absolute(resource_root, "/install_root")
    # Public entry is installed and must use the bound interpreter. Library
    # callers (unit fixtures) can separately exercise pure operations.
    if (root / "runtime.json").is_file() and Path(sys.prefix).resolve() != (root / ".venv").resolve():
        fail("INVALID_ARGUMENT", "/python", "use bound interpreter")
    if operation == "case":
        return prepare_case(data, root)
    db = absolute(data["db_path"], "/db_path")
    output_directory(data["output_dir"], db.parent)
    if operation == "reading":
        from .initial_reading import export_initial_reading_tasks
        fields(data["preparation_files"], ["records", "overview"], [], "/preparation_files")
        for k, v in data["preparation_files"].items():
            absolute(v, "/preparation_files/" + k)
        exported = export_initial_reading_tasks(db, data["output_dir"], root, data["preparation_files"],
            data.get("text_version_ids"), data.get("target_chars", 20000), data.get("window_chars", 6000), data["task_context_file"])
        return _result(operation, exported, exported["manifest_file"])
    if operation == "synthesis":
        from .initial_reading import export_initial_synthesis_tasks
        absolute(data["manifest_file"], "/manifest_file")
        exported = export_initial_synthesis_tasks(db, data["manifest_file"], data["output_dir"], data["reader_reports"], root)
        return _result(operation, exported, data["manifest_file"])
    context_text(data["task_context_file"], db.parent)
    if not isinstance(data["plans"], list) or not data["plans"]:
        fail("INVALID_ARGUMENT", "/plans", "nonempty task plans required")
    for index, plan in enumerate(data["plans"]):
        at = f"/plans/{index}"
        if not isinstance(plan, dict) or "output_file" not in plan:
            fail("INVALID_ARGUMENT", at + "/output_file", "task output required")
        absolute(plan["output_file"], at + "/output_file")
        if operation == "extraction":
            if "group_file" not in plan:
                fail("INVALID_ARGUMENT", at + "/group_file", "group file required")
            absolute(plan["group_file"], at + "/group_file")
    if operation == "tagging":
        return _result(operation, export_tagging_tasks(db, data["plans"], data["output_dir"], root, data["task_context_file"]))
    from .handoff import export_extraction_tasks
    exported = export_extraction_tasks(db, data["plans"], data["output_dir"], root, data.get("clause_ids"),
                                       task_context_file=data["task_context_file"])
    # Extraction machine task stays v1; file handles are returned separately.
    for t in exported["tasks"]:
        t["instructions_file"] = str(Path(data["output_dir"]) / (t["task_id"] + "-instructions.md"))
        t["binding_file"] = str(Path(data["output_dir"]) / (t["task_id"] + "-binding.json"))
    return _result(operation, exported)


def export_tagging_tasks(db, plans, output_dir, root, task_context_file):
    from .initial_reading import _snapshot, _json_bytes, _publish
    destination = output_directory(output_dir, Path(db).parent)
    basis, _, exports = _snapshot(db)
    current = {c["object_id"]: c for c in exports["clauses"]["items"]}
    vocabulary = exports["vocabulary"]["items"][0]
    if not exports["overview"]["items"]:
        fail("INVALID_ARGUMENT", "/overview", "successful preparation overview required")
    context = context_text(task_context_file, Path(db).parent)
    context += overview_context(exports["overview"])
    if not isinstance(plans, list) or not plans:
        fail("INVALID_ARGUMENT", "/plans", "nonempty plans required")
    files = {"units.json": _json_bytes(vocabulary["units"]), "overview.json": _json_bytes(exports["overview"])}
    assigned, names, outputs, tasks = set(), set(), set(), []
    for index, plan in enumerate(plans):
        at = f"/plans/{index}"
        fields(plan, ["task_id", "responsible_clauses", "context_clauses", "output_file"], [], at)
        task_id = plan["task_id"]
        nonempty(task_id, at + "/task_id")
        if Path(task_id).name != task_id or task_id in {".", "..", "units", "overview"} or task_id in names:
            fail("INVALID_ARGUMENT", at + "/task_id", "unique simple file name required")
        names.add(task_id)
        generated_names = [task_id + ".json", task_id + "-binding.json", task_id + "-instructions.md", task_id + "-clauses.md",
                           task_id + "-work/clauses.json"]
        if any(name in files for name in generated_names):
            fail("INVALID_ARGUMENT", at + "/task_id", "generated file name conflicts with another task")
        chosen = []
        for key in ("responsible_clauses", "context_clauses"):
            refs = plan[key]
            if not isinstance(refs, list) or key == "responsible_clauses" and not refs:
                fail("INVALID_ARGUMENT", at + "/" + key, "clause array required")
            local = set()
            for j, ref in enumerate(refs):
                pos = f"{at}/{key}/{j}"
                fields(ref, ["object_id", "record_id"], [], pos)
                uuid_value(ref["object_id"], pos + "/object_id")
                uuid_value(ref["record_id"], pos + "/record_id")
                c = current.get(ref["object_id"])
                if not c or c["record_id"] != ref["record_id"]:
                    fail("STALE_REVISION", pos, "current clause object/record pair required")
                if ref["object_id"] in local or key == "responsible_clauses" and ref["object_id"] in assigned:
                    fail("INVALID_ARGUMENT", pos, "duplicate/overlapping responsibility")
                local.add(ref["object_id"])
                chosen.append(c)
            if key == "responsible_clauses":
                assigned.update(local)
        output = absolute(plan["output_file"], at + "/output_file")
        if not output.is_relative_to(Path(db).parent / "submissions") or output.exists() or output in outputs:
            fail("FILE_EXISTS", at + "/output_file", "unique unused submission path required")
        outputs.add(output)
        clauses = {"case_id": basis["case_id"], "checked_sequence": basis["quality"]["current_sequence"],
                   "items": list({c["object_id"]: c for c in chosen}.values())}
        # Each tagger receives only its clause versions; a full root snapshot
        # would grant unrelated access. Helpers retain full fixed clause fields.
        prefix = task_id + "-work"
        files[prefix + "/clauses.json"] = _json_bytes(clauses)
        files[task_id + "-clauses.md"] = ("\n\n".join(f"## {c['object_id']} / {c['record_id']}\n\n{c['data']['text']}" for c in clauses["items"])).encode("utf-8")
        task = {"format_version": 2, "task_id": task_id, "role": "tagger", "purpose": "tagging",
                "case_id": basis["case_id"], "checked_sequence": basis["quality"]["current_sequence"],
                "responsible_clauses": plan["responsible_clauses"], "context_clauses": plan["context_clauses"],
                "input_files": [str(destination / (task_id + "-clauses.md")), str(destination / "units.json"),
                                str(destination / (prefix + "/clauses.json")), str(root / "references/data-formats.md"),
                                str(root / "skills/legal-case/references/helper-tools.md"), str(root / "skills/legal-case/examples/tagging.py")],
                "instructions_file": str(destination / (task_id + "-instructions.md")),
                "binding_file": str(destination / (task_id + "-binding.json")), "output_file": str(output)}
        task["input_files"].append(task["binding_file"])
        fixed = binding("tagging", task, vocabulary["hash"], f"tagger-{index + 1}")
        files[task_id + "-binding.json"] = _json_bytes(fixed)
        files[task_id + "-instructions.md"] = instructions(root, "tagger", context, task,
            "负责条款：" + json.dumps(plan["responsible_clauses"]) + "\n仅供理解上下文：" + json.dumps(plan["context_clauses"]),
            on_demand=task["input_files"][2:], binding_data=fixed).encode("utf-8")
        files[task_id + ".json"] = _json_bytes(task)
        tasks.append(task)
    from .handoff import _all
    fresh, _ = _all(db, view="progress")
    if fresh["quality"]["current_sequence"] != basis["quality"]["current_sequence"]:
        fail("STALE_REVISION", "/plans", "case changed during export")
    return {"tasks": tasks, "files": _publish(destination, files)}
