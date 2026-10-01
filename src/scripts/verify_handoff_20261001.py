"""Export full handoff inputs from an isolated copy of the acceptance baseline.

Run with the candidate installation's Python. This regression does not endorse
the submitted baseline's semantics or change its source database.
"""

from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

from legal.group import group
from legal.handoff import export_extraction_tasks
from legal.query import query


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, document):
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submitted-db", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--resource-root", type=Path, required=True)
    args = parser.parse_args()
    original = args.submitted_db.resolve()
    root = args.output_dir.resolve()
    before = digest(original)
    root.mkdir(parents=True, exist_ok=False)
    database = root / "contract.sqlite"
    with closing(sqlite3.connect(original.as_uri() + "?mode=ro", uri=True)) as source:
        with closing(sqlite3.connect(database)) as target:
            source.backup(target)
    for directory in ("tasks", "submissions", "groups", "reports"):
        (root / directory).mkdir()
    grouped = group(database, root / "groups/0001")
    save(root / "reports/group-receipt.json", grouped)
    # Existing group membership is used only to exercise the transfer contract.
    # The first group containing a clause owns it in this mechanical fixture.
    assigned, plans = set(), []
    for info in grouped["files"]:
        document = json.loads(Path(info["path"]).read_text(encoding="utf-8"))
        responsible = [{"object_id": item["object_id"], "record_id": item["record_id"]}
                       for item in document["clauses"] if item["object_id"] not in assigned]
        if not responsible:
            continue
        assigned.update(item["object_id"] for item in responsible)
        identifier = f"{len(plans) + 1:04d}-extraction"
        plans.append({"task_id": identifier, "unit_id": document["unit_id"], "responsible_clauses": responsible,
                      "context_clauses": [], "group_file": info["path"],
                      "output_file": str(root / "submissions" / (identifier + ".json"))})
    save(root / "reports/plans.json", plans)
    receipt = export_extraction_tasks(database, plans, root / "tasks/0001", args.resource_root)
    save(root / "reports/handoff-receipt.json", receipt)
    save(root / "reports/progress.json", query(database, {"view": "progress"}))
    counts = {name: len(json.loads((root / "tasks/0001" / name).read_text(encoding="utf-8"))["items"])
              for name in ("frozen-vocabulary.json", "overview.json", "events.json", "shared-objects.json", "clauses.json")}
    after = digest(original)
    if before != after:
        raise RuntimeError("acceptance source database changed during regression")
    result = {"ok": True, "source_database": str(original), "source_sha256_before": before,
              "source_sha256_after": after, "case_id": receipt["case_id"], "checked_sequence": receipt["checked_sequence"],
              "task_count": len(plans), "responsible_clause_count": len(assigned), "input_counts": counts,
              "scope": "handoff transfer only; original semantic errors are retained"}
    save(root / "reports/result.json", result)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
