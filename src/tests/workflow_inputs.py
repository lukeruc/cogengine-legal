"""Explicit synthetic handoff inputs for older regression fixtures."""
from pathlib import Path
from legal.initial_reading import export_initial_reading_tasks as export_reading, export_initial_synthesis_tasks
from legal.handoff import export_extraction_tasks as export_extraction
from legal.formats import read_json


def task_context(db):
    file = Path(db).parent / "tasks/fixture-context.md"
    file.parent.mkdir(parents=True, exist_ok=True)
    if not file.exists():
        file.write_text("仅为虚构工程夹具的入库测试；按完整条款责任表达合同规定。", encoding="utf-8")
    return file


def export_initial_reading_tasks(db, output, resources, preparation_file, **options):
    file = Path(preparation_file)
    return export_reading(db, output, resources, {"records": file, "overview": file.with_name(file.stem + "-overview.json")},
                          task_context_file=task_context(db), **options)


def reports(manifest):
    return [{"task_id": t["task_id"], "notes_file": t["output_file"],
             "read_ranges": [{"text_version_id": e["text_version_id"], "start_offset": e["start_offset"], "end_offset": e["end_offset"]}
                             for e in manifest["directory"] if e["object_id"] in {c["object_id"] for c in t["main_reading_clauses"]}],
             "unread_ranges": [], "issues": []} for t in manifest["tasks"]]


def export_initial_synthesis_task(db, manifest_file, unused_old_task_path):
    manifest = read_json(manifest_file)
    resources = Path(manifest["references"][0]).parents[3]
    result = export_initial_synthesis_tasks(db, manifest_file, Path(unused_old_task_path).with_suffix(""), reports(manifest), resources)
    return result["tasks"][0]


def export_extraction_tasks(db, plans, output, resources, **options):
    return export_extraction(db, plans, output, resources, task_context_file=task_context(db), **options)
