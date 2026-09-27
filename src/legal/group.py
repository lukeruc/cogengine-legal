"""Lossless tagged clause exports for reading assignments."""

import json
from pathlib import Path

from .formats import exclusive_write, fail
from .query import default_text_versions
from .storage import CaseStore


def group(db_path, output_dir, text_version_id=None):
    store = CaseStore(db_path)
    try:
        selected = [text_version_id] if text_version_id else default_text_versions(store)
        if text_version_id:
            row = store.current(text_version_id)
            if not row or row["kind"] != "text_version":
                fail("REFERENCE_NOT_FOUND", "/arguments/text-version", "text version missing")
        destination = Path(output_dir).absolute()
        if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
            fail("FILE_EXISTS", "/arguments/output-dir", "output directory is not empty")
        buckets = {}
        ordered = []
        for text_id in selected:
            text_row = store.current(text_id)
            material_id = json.loads(text_row["data_json"])["material"]["object_id"]
            material = store.db.execute("SELECT registered_order FROM materials WHERE record_id=?", (store.current(material_id)["record_id"],)).fetchone()
            for row in store.db.execute("SELECT r.*,o.kind FROM active_records r JOIN objects o USING(object_id) WHERE o.kind='clause'"):
                data = json.loads(row["data_json"])
                if data["text_version"]["object_id"] != text_id:
                    continue
                if data["classification"] == "unclassified":
                    fail("UNCLASSIFIED_CLAUSE", "/arguments/db", "unclassified clause in selected range")
                item = {"object_id": row["object_id"], "record_id": row["record_id"],
                        "material_id": material_id, "text_version_id": text_id, "sequence": data["sequence"],
                        "original_number": data["original_number"], "text": data["text"], "tags": data["tags"]}
                ordered.append((material[0], data["sequence"], item))
        for _, _, item in sorted(ordered, key=lambda x: (x[0], x[1], x[2]["object_id"])):
            if item["tags"]:
                for unit in item["tags"]:
                    buckets.setdefault(("ordinary", unit), []).append(item)
            else:
                row = store.current(item["object_id"])
                kind = json.loads(row["data_json"])["classification"]
                buckets.setdefault((kind, None), []).append(item)
        destination.mkdir(parents=True, exist_ok=True)
        created, files = [], []
        try:
            for (classification, unit_id), clauses in sorted(buckets.items(), key=lambda x: (x[0][0], x[0][1] or "")):
                filename = f"unit-{unit_id}.json" if unit_id else f"{classification}.json"
                path = destination / filename
                content = {"format_version": 1, "case_id": store.case_id(),
                           "vocabulary_hash": store.info["vocabulary_hash"], "unit_id": unit_id,
                           "classification": classification, "clauses": clauses}
                exclusive_write(path, (json.dumps(content, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
                created.append(path)
                files.append({"path": str(path), "unit_id": unit_id, "classification": classification,
                              "clause_ids": [c["object_id"] for c in clauses]})
        except Exception:
            for item in created:
                try:
                    item.unlink()
                except OSError:
                    pass
            raise
        return {"ok": True, "files": files, "clause_count": len(ordered)}
    finally:
        store.close()
