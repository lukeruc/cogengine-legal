"""Six mechanical checks and persisted case quality reports."""

from __future__ import annotations

import json
import re

from .formats import fail, new_id, timestamp
from .query import default_text_versions, _identity, supported_clause_ids
from .storage import CaseStore, _json
from .values import check_contract

CHECKS = ["character_coverage", "anchors", "value_candidates", "value_roundtrip", "classification_coverage", "appellations"]
DATE = r"[0-9]{4}(?:年[0-9]{1,2}(?:月[0-9]{1,2}日?)?|-[0-9]{2}(?:-[0-9]{2})?)"
PERCENT = r"-?(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?[%％]"
NUMBER = r"-?(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?"
CANDIDATES = re.compile(f"{DATE}|{PERCENT}|{NUMBER}")


def _diagnostic(code, message, record_id=None, path=None, text_version_id=None, clause_id=None, **extra):
    return {"code": code, "message": message, "record_id": record_id,
            "path": path, "text_version_id": text_version_id, "clause_id": clause_id, **extra}


def reconcile(db_path, text_version_id=None, history=False):
    store = CaseStore(db_path)
    try:
        store.begin()
        scope_ids = [text_version_id] if text_version_id else default_text_versions(store)
        if text_version_id:
            row = store.current(text_version_id)
            if not row or row["kind"] != "text_version":
                fail("REFERENCE_NOT_FOUND", "/arguments/text-version", "text version missing")
        scope = {"text_version_ids": scope_ids, "history": bool(history)}
        errors, notices = [], []
        checked = store.sequence()
        clause_rows = []
        for text_id in scope_ids:
            text_row = store.current(text_id)
            text = json.loads(text_row["data_json"])["text"]
            clauses = []
            for row in store.db.execute("SELECT r.*,o.kind FROM active_records r JOIN objects o USING(object_id) WHERE o.kind='clause'"):
                data = json.loads(row["data_json"])
                if data["text_version"]["object_id"] == text_id:
                    clauses.append((row, data))
                    clause_rows.append((row, data, text_id))
            clauses.sort(key=lambda pair: pair[1]["sequence"])
            if not clauses and text:
                errors.append((0, _diagnostic("CHARACTER_COVERAGE", "registered text has no clauses", text_version_id=text_id)))
            cursor = 0
            for index, (row, data) in enumerate(clauses, start=1):
                if data["sequence"] != index or data["start_offset"] != cursor or data["text"] != text[data["start_offset"]:data["end_offset"]]:
                    errors.append((0, _diagnostic("CHARACTER_COVERAGE", "clause text or address differs", row["record_id"], "/data", text_id, row["object_id"])))
                cursor = data["end_offset"]
            if clauses and cursor != len(text):
                errors.append((0, _diagnostic("CHARACTER_COVERAGE", "final clause does not reach text end", clauses[-1][0]["record_id"], "/data/end_offset", text_id, clauses[-1][0]["object_id"])))
            if history:
                historical_clauses = [(row["object_id"], row["submission_id"])
                                      for row in store.db.execute("SELECT r.object_id,r.submission_id,r.data_json FROM record_versions r JOIN objects o USING(object_id) WHERE o.kind='clause'")
                                      if json.loads(row["data_json"])["text_version"]["object_id"] == text_id]
                clause_objects = sorted({object_id for object_id, _ in historical_clauses})
                change_sequences = sorted({store.db.execute("SELECT sequence FROM submissions WHERE submission_id=?", (submission_id,)).fetchone()[0]
                                           for _, submission_id in historical_clauses})
                for at_sequence in change_sequences:
                    historical = []
                    for clause_object in clause_objects:
                        old = store.current(clause_object, at_sequence)
                        if old and old["status"] == "active":
                            historical.append((old, json.loads(old["data_json"])))
                    historical.sort(key=lambda pair: pair[1]["sequence"])
                    at_offset = 0
                    for index, (old, old_data) in enumerate(historical, start=1):
                        if old_data["sequence"] != index or old_data["start_offset"] != at_offset or old_data["text"] != text[old_data["start_offset"]:old_data["end_offset"]]:
                            errors.append((0, _diagnostic("CHARACTER_COVERAGE", f"historical clause coverage fails at submission {at_sequence}", old["record_id"], "/data", text_id, old["object_id"])))
                        at_offset = old_data["end_offset"]
                    if historical and at_offset != len(text):
                        errors.append((0, _diagnostic("CHARACTER_COVERAGE", f"historical text end differs at submission {at_sequence}", historical[-1][0]["record_id"], "/data/end_offset", text_id, historical[-1][0]["object_id"])))
        if not clause_rows:
            errors.append((4, _diagnostic("EMPTY_SCOPE", "no clauses in selected scope")))
        rows = store.db.execute("SELECT r.*,o.kind FROM record_versions r JOIN objects o USING(object_id)").fetchall() if history else store.db.execute("SELECT r.*,o.kind FROM active_records r JOIN objects o USING(object_id)").fetchall()
        for row in rows:
            data = json.loads(row["data_json"])
            if row["kind"] == "anchor":
                clause = store.record(data["clause"]["record_id"])
                if not clause:
                    errors.append((1, _diagnostic("ANCHOR_NOT_FOUND", "clause version missing", row["record_id"], "/data/clause")))
                    continue
                clause_data = json.loads(clause["data_json"])
                starts = [i for i in range(len(clause_data["text"])) if clause_data["text"].startswith(data["quote"], i)]
                if not starts or data["occurrence"] > len(starts):
                    errors.append((1, _diagnostic("ANCHOR_NOT_FOUND", "quote missing or occurrence invalid", row["record_id"], "/data/quote", clause_data["text_version"]["object_id"], clause["object_id"])))
            for evidence in store.db.execute("SELECT path,source_json FROM assertion_sources WHERE record_id=?", (row["record_id"],)):
                source = json.loads(evidence["source_json"])
                if source["level"] == 2:
                    try:
                        from .formats import pointer_get
                        target = pointer_get(data, evidence["path"])
                        quotes = [json.loads(store.record(a["record_id"])["data_json"])["quote"] for a in source["anchors"]]
                        quote = next((q for q in quotes if source["surface"] in q), "")
                        check_contract(target, source, quote, evidence["path"])
                    except Exception as exc:
                        errors.append((3, _diagnostic("ROUNDTRIP_FAILED", str(exc), row["record_id"], evidence["path"])))
            if row["kind"] in {"node", "relation", "detail", "reference", "gap", "no_content"}:
                source_count = store.db.execute("SELECT COUNT(*) FROM assertion_sources WHERE record_id=?", (row["record_id"],)).fetchone()[0]
                if source_count == 0 and not (row["kind"] == "node" and data == {"node_kind": "contract"}):
                    errors.append((4, _diagnostic("MISSING_SOURCE", "business record lacks source", row["record_id"], "/evidence")))
            elif row["kind"] == "clause" and data["classification"] != "unclassified":
                source_count = store.db.execute("SELECT COUNT(*) FROM assertion_sources WHERE record_id=?", (row["record_id"],)).fetchone()[0]
                if source_count == 0:
                    errors.append((4, _diagnostic("MISSING_SOURCE", "classified clause lacks source", row["record_id"], "/evidence", data["text_version"]["object_id"], row["object_id"])))
            if row["kind"] == "reference" and data.get("reference_kind") == "appellation":
                clause = store.record(data["from"]["record_id"])
                if not clause or data["label"] not in json.loads(clause["data_json"])["text"]:
                    errors.append((5, _diagnostic("APPELLATION_INVALID", "label absent from source clause", row["record_id"], "/data/label")))
        # Candidate checks only need values whose source anchors point into the
        # clause being checked. Build that index once instead of scanning every
        # detail and node again for each number in the contract.
        candidate_support = {}
        anchor_positions = {}
        for evidence in store.db.execute("""SELECT s.source_json,r.data_json FROM assertion_sources s
            JOIN active_records r ON r.record_id=s.record_id JOIN objects o USING(object_id)
            WHERE o.kind IN ('detail','node')"""):
            source = json.loads(evidence["source_json"])
            if source["level"] not in {1, 2}:
                continue
            value = json.loads(evidence["data_json"]).get("value")
            for ref in source["anchors"]:
                anchor_id = ref["record_id"]
                if anchor_id not in anchor_positions:
                    anchor = store.record(anchor_id)
                    if not anchor:
                        anchor_positions[anchor_id] = None
                    else:
                        anchor_data = json.loads(anchor["data_json"])
                        fixed_clause = store.record(anchor_data["clause"]["record_id"])
                        span = store.db.execute(
                            "SELECT start_offset,end_offset FROM anchors WHERE record_id=?",
                            (anchor_id,),
                        ).fetchone()
                        if not fixed_clause or not span:
                            anchor_positions[anchor_id] = None
                        else:
                            fixed_data = json.loads(fixed_clause["data_json"])
                            anchor_positions[anchor_id] = (
                                fixed_clause["object_id"],
                                fixed_data["start_offset"] + span[0],
                                fixed_data["start_offset"] + span[1],
                            )
                position = anchor_positions[anchor_id]
                if position:
                    clause_id, start, end = position
                    candidate_support.setdefault(clause_id, []).append(
                        (start, end, source["level"], source.get("surface", ""), value)
                    )
        supported_clauses = supported_clause_ids(store)
        unmatched_clauses = set()
        for gap in store.db.execute("""SELECT r.data_json FROM active_records r
            JOIN objects o USING(object_id) WHERE o.kind='gap'"""):
            gap_data = json.loads(gap["data_json"])
            if gap_data["gap_kind"] == "unmatched_unit":
                fixed_clause = store.record(gap_data["clause"]["record_id"])
                if fixed_clause:
                    unmatched_clauses.add(fixed_clause["object_id"])
        no_content_clauses = {
            json.loads(item["data_json"])["clause"]["object_id"]
            for item in store.db.execute("""SELECT r.data_json FROM active_records r
                JOIN objects o USING(object_id) WHERE o.kind='no_content'""")
        }
        for row, data, text_id in clause_rows:
            clause_id = row["object_id"]
            if data["classification"] == "unclassified" or data["classification"] == "ordinary" and not data["tags"]:
                errors.append((4, _diagnostic("CLASSIFICATION_MISSING", "clause has no valid classification", row["record_id"], "/data/classification", text_id, clause_id)))
            if data["classification"] == "unmatched":
                if clause_id not in unmatched_clauses:
                    errors.append((4, _diagnostic("CONTENT_UNSUPPORTED", "unmatched clause lacks gap", row["record_id"], None, text_id, clause_id)))
            if data["classification"] == "no_content":
                if clause_id not in no_content_clauses:
                    errors.append((4, _diagnostic("CONTENT_UNSUPPORTED", "no-content clause lacks record", row["record_id"], None, text_id, clause_id)))
            completion = store.db.execute(
                "SELECT clause_record_id FROM extraction_completions WHERE clause_id=?",
                (clause_id,),
            ).fetchall()
            keys = ("text_version", "sequence", "text", "start_offset", "end_offset", "original_number")
            completed = clause_id in supported_clauses and any(
                (old := store.record(item["clause_record_id"])) is not None
                and all(json.loads(old["data_json"]).get(key) == data.get(key) for key in keys)
                for item in completion
            )
            if not completed:
                errors.append((4, _diagnostic("EXTRACTION_INCOMPLETE", "clause not declared complete", row["record_id"], None, text_id, clause_id)))
            if completion and clause_id not in supported_clauses:
                errors.append((4, _diagnostic("CONTENT_UNSUPPORTED", "completed clause has no current modeled content", row["record_id"], None, text_id, clause_id)))
            text = data["text"]
            for candidate in CANDIDATES.finditer(text):
                surface = candidate.group()
                # A nearby quote alone is insufficient; check a matching value or format surface.
                corresponding = False
                candidate_start = data["start_offset"] + candidate.start()
                candidate_end = data["start_offset"] + candidate.end()
                for actual_start, actual_end, level, source_surface, value in candidate_support.get(clause_id, ()):
                    if not actual_start <= candidate_start < candidate_end <= actual_end:
                        continue
                    if level == 2 and surface in source_surface or isinstance(value, dict) and (
                        value.get("amount") == surface.replace(",", "").rstrip("%％")
                        or value.get("value") == surface
                    ):
                        corresponding = True
                        break
                if not corresponding:
                    notices.append((2, _diagnostic("VALUE_CANDIDATE_DIFFERENCE", "text value has no exact modeled counterpart", row["record_id"], "/data/text", text_id, clause_id,
                                                   start_offset=data["start_offset"] + candidate.start(), end_offset=data["start_offset"] + candidate.end(),
                                                   surface=surface, related_gaps=[])))
        for row in store.db.execute("SELECT r.object_id,r.record_id,r.data_json FROM active_records r JOIN objects o USING(object_id) WHERE o.kind='node'"):
            identity = _identity(store, row["object_id"])
            if identity["conflicts"]:
                notices.append((5, _diagnostic("IDENTITY_CONFLICT", "node identity has unresolved targets", row["record_id"], "/identity")))
        errors.sort(key=lambda e: (e[0], e[1]["text_version_id"] or "", e[1]["clause_id"] or "", e[1]["record_id"] or "", e[1]["path"] or "", e[1]["code"]))
        notices.sort(key=lambda e: (e[0], e[1]["text_version_id"] or "", e[1]["clause_id"] or "", e[1].get("start_offset", -1)))
        errors_only, notices_only = [e for _, e in errors], [n for _, n in notices]
        checks = []
        for i, name in enumerate(CHECKS):
            count = sum(1 for index, _ in errors if index == i)
            checks.append({"name": name, "passed": count == 0, "error_count": count,
                           "notice_count": sum(1 for index, _ in notices if index == i)})
        result = {"ok": True, "report_id": new_id(), "checked_sequence": checked, "scope": scope,
                  "rule_version": "1", "passed": not errors_only, "checks": checks,
                  "errors": errors_only, "notices": notices_only}
        store.db.execute("INSERT INTO reconciliation_reports VALUES(?,?,?,?,?,?)",
                         (result["report_id"], checked, _json(scope), "1", _json(result), timestamp()))
        store.db.commit()
        return result
    except Exception:
        store.db.rollback()
        raise
    finally:
        store.close()
