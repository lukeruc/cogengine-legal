"""Current and historical case queries with anchored provenance."""

from __future__ import annotations

import json
from pathlib import Path

from .formats import digest, exclusive_write, fail, uuid_value
from .storage import CaseStore, _json


def default_text_versions(store):
    rows = store.db.execute("""SELECT t.material_id,t.version_number,r.object_id
        FROM text_versions t JOIN record_versions r ON r.record_id=t.record_id
        ORDER BY t.material_id,t.version_number DESC""").fetchall()
    result = {}
    for row in rows:
        result.setdefault(row["material_id"], row["object_id"])
    return sorted(result.values())


def quality(store):
    current_sequence = store.sequence()
    expected_scope = sorted(default_text_versions(store))
    rows = store.db.execute("SELECT * FROM reconciliation_reports ORDER BY created_at DESC,report_id DESC").fetchall()
    selected = None
    state = "not_checked"
    for row in rows:
        scope = json.loads(row["scope_json"])
        if sorted(scope["text_version_ids"]) == expected_scope and not scope["history"] and row["checked_sequence"] == current_sequence:
            selected = row
            state = "passed" if not json.loads(row["result_json"])["errors"] else "failed"
            break
    if selected is None and rows:
        selected = rows[0]
        state = "stale"
    if selected is None:
        return {"state": state, "report_id": None, "checked_sequence": None,
                "current_sequence": current_sequence, "scope": None,
                "errors_count": None, "notices_count": None}
    result = json.loads(selected["result_json"])
    return {"state": state, "report_id": selected["report_id"],
            "checked_sequence": selected["checked_sequence"], "current_sequence": current_sequence,
            "scope": json.loads(selected["scope_json"]), "errors_count": len(result["errors"]),
            "notices_count": len(result["notices"])}


def progress(store):
    materials = []
    unclassified, uncompleted = [], []
    supported = supported_clause_ids(store)
    for text_id in default_text_versions(store):
        text_row = store.current(text_id)
        material_id = json.loads(text_row["data_json"])["material"]["object_id"]
        clauses = [row for row in store.db.execute("SELECT c.object_id,c.data_json FROM active_records c JOIN objects o USING(object_id) WHERE o.kind='clause'")
                   if json.loads(row["data_json"])["text_version"]["object_id"] == text_id]
        clauses.sort(key=lambda row: json.loads(row["data_json"])["sequence"])
        split_done = any(json.loads(row["input_json"]).get("text_version_id") == text_id
                         for row in store.db.execute("SELECT input_json FROM submissions WHERE phase='split'"))
        materials.append({"material_id": material_id, "text_version_id": text_id,
                          "split_completed": bool(clauses) or split_done,
                          "clause_count": len(clauses)})
        for clause in clauses:
            data = json.loads(clause["data_json"])
            if data["classification"] == "unclassified":
                unclassified.append(clause["object_id"])
            if not clause_completed(store, clause["object_id"], data, supported):
                uncompleted.append(clause["object_id"])
    event_ids = []
    for row in store.db.execute("SELECT object_id,data_json FROM active_records r JOIN objects o USING(object_id) WHERE o.kind='node'"):
        if json.loads(row["data_json"])["node_kind"] == "event":
            event_ids.append(row["object_id"])
    overview = store.db.execute("SELECT overview_id FROM case_overviews ORDER BY rowid DESC LIMIT 1").fetchone()
    return {"materials": materials, "unclassified_clauses": unclassified,
            "uncompleted_clauses": uncompleted, "latest_overview_id": overview[0] if overview else None,
            "event_ids": sorted(event_ids), "quality": quality(store)}


def _provenance(store, record_id, seen=None):
    seen = seen or set()
    if record_id in seen:
        return []
    seen.add(record_id)
    result = []
    record = store.record(record_id)
    if record and record["kind"] == "anchor":
        anchor_data = json.loads(record["data_json"])
        clause_record = anchor_data["clause"]["record_id"]
        clause = store.record(clause_record)
        positions = store.db.execute("SELECT start_offset,end_offset FROM anchors WHERE record_id=?", (record_id,)).fetchone()
        if clause and positions:
            clause_data = json.loads(clause["data_json"])
            text_id = clause_data["text_version"]["object_id"]
            text = store.current(text_id)
            material_id = json.loads(text["data_json"])["material"]["object_id"] if text else None
            return [{"path": "", "level": 1, "premises": [], "anchors": [{
                "anchor_record_id": record_id, "clause_id": clause["object_id"],
                "clause_record_id": clause_record, "text_version_id": text_id,
                "material_id": material_id, "sequence": clause_data["sequence"],
                "quote": anchor_data["quote"],
                "start_offset": clause_data["start_offset"] + positions["start_offset"],
                "end_offset": clause_data["start_offset"] + positions["end_offset"]}]}]
        return []
    for evidence in store.db.execute("SELECT path,level,source_json FROM assertion_sources WHERE record_id=? ORDER BY path", (record_id,)):
        source = json.loads(evidence["source_json"])
        anchors, premises = [], []
        for ref in source.get("anchors", []):
            anchor_id = ref["record_id"]
            anchor = store.record(anchor_id)
            if not anchor:
                continue
            anchor_data = json.loads(anchor["data_json"])
            clause_record = anchor_data["clause"]["record_id"]
            clause = store.record(clause_record)
            if not clause:
                continue
            clause_data = json.loads(clause["data_json"])
            text_id = clause_data["text_version"]["object_id"]
            text = store.current(text_id)
            material_id = json.loads(text["data_json"])["material"]["object_id"] if text else None
            positions = store.db.execute("SELECT start_offset,end_offset FROM anchors WHERE record_id=?", (anchor_id,)).fetchone()
            anchors.append({"anchor_record_id": anchor_id, "clause_id": clause["object_id"],
                            "clause_record_id": clause_record, "text_version_id": text_id,
                            "material_id": material_id, "sequence": clause_data["sequence"],
                            "quote": anchor_data["quote"], "start_offset": clause_data["start_offset"] + positions[0],
                            "end_offset": clause_data["start_offset"] + positions[1]})
        for ref in source.get("premises", []):
            premise_id = ref["record_id"]
            premise = store.record(premise_id)
            current = store.current(premise["object_id"]) if premise else None
            premises.append({"record_id": premise_id, "current_record_id": current["record_id"] if current else None,
                             "changed": bool(current and current["record_id"] != premise_id),
                             "withdrawn": bool(current and current["status"] == "withdrawn")})
            for root in _provenance(store, premise_id, seen | {record_id}):
                anchors.extend(root["anchors"])
        unique = {a["anchor_record_id"]: a for a in anchors}
        result.append({"path": evidence["path"], "level": evidence["level"],
                       "anchors": list(unique.values()), "premises": premises})
    return result


def _identity(store, object_id, sequence=None):
    edges, distinct = {}, set()
    for object_row in store.db.execute("SELECT object_id FROM objects WHERE kind='reference'"):
        row = store.current(object_row["object_id"], sequence)
        if row is None or row["status"] != "active":
            continue
        data = json.loads(row["data_json"])
        if data.get("reference_kind") == "redirect":
            edges.setdefault(data["from"]["object_id"], []).append((data["to"]["object_id"], row["record_id"]))
        elif data.get("reference_kind") == "distinct":
            distinct.add(frozenset((data["from"]["object_id"], data["to"]["object_id"])))
    candidates = set()
    involved = set()
    def walk(node, visited):
        if node in visited or node not in edges:
            candidates.add(node)
            return
        for target, record in edges[node]:
            involved.add(record)
            walk(target, visited | {node})
    walk(object_id, set())
    conflicts = []
    if len(candidates) > 1:
        conflicts.append({"record_ids": sorted(involved), "code": "multiple_targets"})
    if any(frozenset((object_id, target)) in distinct for target in candidates):
        conflicts.append({"record_ids": sorted(involved), "code": "distinct_conflict"})
    return {"original_id": object_id, "canonical_id": next(iter(candidates)) if len(candidates) == 1 and not conflicts else None,
            "candidates": sorted(candidates), "conflicts": conflicts}


def clause_has_support(store, clause_id):
    for row in store.db.execute("SELECT r.*,o.kind FROM active_records r JOIN objects o USING(object_id) WHERE o.kind IN ('node','relation','detail','reference','gap','no_content')"):
        submission = store.db.execute("SELECT phase FROM submissions WHERE submission_id=?", (row["submission_id"],)).fetchone()
        if submission and submission[0] == "preparation":
            continue
        if any(anchor["clause_id"] == clause_id for root in _provenance(store, row["record_id"]) for anchor in root["anchors"]):
            return True
    return False


def supported_clause_ids(store):
    result = set()
    for row in store.db.execute("""SELECT r.record_id,s.phase FROM active_records r
        JOIN objects o USING(object_id) JOIN submissions s USING(submission_id)
        WHERE o.kind IN ('node','relation','detail','reference','gap','no_content')"""):
        if row["phase"] == "preparation":
            continue
        for root in _provenance(store, row["record_id"]):
            result.update(anchor["clause_id"] for anchor in root["anchors"])
    return result


def clause_completed(store, clause_id, current_data=None, supported=None):
    current = store.current(clause_id)
    if current is None or current["status"] != "active":
        return False
    current_data = current_data or json.loads(current["data_json"])
    if current_data["classification"] == "unclassified" or current_data["classification"] == "ordinary" and not current_data["tags"]:
        return False
    keys = ("text_version", "sequence", "text", "start_offset", "end_offset", "original_number")
    for completion in store.db.execute("SELECT clause_record_id FROM extraction_completions WHERE clause_id=?", (clause_id,)):
        old = store.record(completion["clause_record_id"])
        if old:
            old_data = json.loads(old["data_json"])
            has_support = clause_has_support(store, clause_id) if supported is None else clause_id in supported
            if all(old_data.get(key) == current_data.get(key) for key in keys) and has_support:
                return True
    return False


def _gaps(store, row):
    data = json.loads(row["data_json"])
    targets = {row["object_id"]}
    if row["kind"] == "clause":
        targets.add(row["record_id"])
    result = []
    for gap in store.db.execute("SELECT * FROM active_records r JOIN objects o USING(object_id) WHERE o.kind='gap'"):
        item = json.loads(gap["data_json"])
        clause = store.record(item["clause"]["record_id"])
        related = item.get("related_object", {}).get("record_id")
        related_row = store.record(related) if related else None
        if clause and (clause["object_id"] in targets or related_row and related_row["object_id"] == row["object_id"]):
            target_row = related_row or clause
            current = store.current(target_row["object_id"]) if target_row else None
            result.append({"object_id": gap["object_id"], "record_id": gap["record_id"],
                           "gap_kind": item["gap_kind"], "description": item["description"],
                           "target_changed": bool(current and current["record_id"] != target_row["record_id"]),
                           "target_withdrawn": bool(current and current["status"] == "withdrawn")})
    return result


def record_item(store, row, sequence=None, nest=False):
    data = json.loads(row["data_json"])
    evidence = [{"path": e["path"], "source": json.loads(e["source_json"])}
                for e in store.db.execute("SELECT * FROM assertion_sources WHERE record_id=? ORDER BY path", (row["record_id"],))]
    details, missing = [], []
    if row["kind"] == "relation" and not nest:
        sequence = sequence or store.sequence()
        for detail in store.db.execute("""SELECT r.*,o.kind FROM record_versions r JOIN objects o USING(object_id)
            JOIN submissions s ON s.submission_id=r.submission_id
            WHERE o.kind='detail' AND s.sequence<=? ORDER BY s.sequence,o.object_id,r.revision""", (sequence,)):
            if json.loads(detail["data_json"])["owner"]["object_id"] != row["object_id"]:
                continue
            if store.current(detail["object_id"], sequence)["record_id"] == detail["record_id"] and detail["status"] == "active":
                details.append(record_item(store, detail, sequence, nest=True))
        assigned = {a["slot_id"] for a in store.db.execute("SELECT slot_id FROM vocabulary_assignments WHERE unit_id=?", (data["unit_id"],))}
        all_assigned = {a["slot_id"] for a in store.db.execute("SELECT slot_id FROM vocabulary_assignments")}
        general = {s["slot_id"] for s in store.db.execute("SELECT slot_id FROM vocabulary_slots")} - all_assigned
        filled = {d["data"]["slot_id"] for d in details}
        missing = sorted((assigned | general) - filled)
    identity = {"resolution": None, "endpoints": []}
    if row["kind"] == "node":
        identity["resolution"] = _identity(store, row["object_id"], sequence)
    elif row["kind"] == "relation" and data["relation_kind"] == "party":
        identity["endpoints"] = [_identity(store, p["subject"]["object_id"], sequence) for p in data["parties"]]
        left, right = identity["endpoints"]
        if left["canonical_id"] and left["canonical_id"] == right["canonical_id"]:
            conflict = {"record_ids": [row["record_id"]], "code": "collapsed_parties"}
            for endpoint in identity["endpoints"]:
                endpoint["canonical_id"] = None
                endpoint["conflicts"].append(conflict)
    if sequence is None:
        submission = store.db.execute("SELECT sequence FROM submissions WHERE submission_id=?", (row["submission_id"],)).fetchone()
        sequence = submission[0]
    return {"object_id": row["object_id"], "record_id": row["record_id"], "revision": row["revision"],
            "previous_record_id": row["previous_record_id"], "submission_id": row["submission_id"],
            "kind": row["kind"], "status": row["status"], "withdrawal_reason": row["withdrawal_reason"],
            "data": data, "evidence": evidence, "provenance": _provenance(store, row["record_id"]),
            "details": details, "missing_slots": missing, "gaps": [] if nest else _gaps(store, row),
            "identity": identity, "expansion_sequence": sequence, "matched_paths": []}


def _filter_item(store, item, options):
    kind = item["kind"]
    data = item["data"]
    if options.get("kinds") and kind not in options["kinds"]:
        return False
    if options.get("units"):
        unit = data.get("unit_id") if kind == "relation" else None
        if kind == "detail":
            owner = store.current(data["owner"]["object_id"])
            unit = json.loads(owner["data_json"])["unit_id"] if owner else None
        if unit not in options["units"]:
            return False
    if options.get("slots"):
        if kind == "detail":
            found = data["slot_id"] in options["slots"]
        elif kind == "relation":
            found = any(d["data"]["slot_id"] in options["slots"] for d in item["details"])
        else:
            found = False
        if not found:
            return False
    if options.get("parties"):
        allowed = set(options["parties"])
        if kind == "relation" and data["relation_kind"] == "party":
            party_ids = {p["subject"]["object_id"] for p in data["parties"]}
            party_ids.update(e["canonical_id"] for e in item["identity"]["endpoints"] if e["canonical_id"])
            found = bool(party_ids & allowed)
        elif kind == "detail":
            owner = store.current(data["owner"]["object_id"], item["expansion_sequence"])
            party_ids = {p["subject"]["object_id"] for p in json.loads(owner["data_json"]).get("parties", [])} if owner else set()
            party_ids.update(identity["canonical_id"] for subject_id in list(party_ids)
                             if (identity := _identity(store, subject_id, item["expansion_sequence"]))["canonical_id"])
            found = bool(party_ids & allowed)
        else:
            found = False
        if not found:
            return False
    if options.get("clauses"):
        found = kind == "clause" and item["object_id"] in options["clauses"]
        found |= any(anchor["clause_id"] in options["clauses"] for provenance in item["provenance"] for anchor in provenance["anchors"])
        if not found:
            return False
    if options.get("source_levels"):
        paths = [p["path"] for p in item["provenance"] if p["level"] in options["source_levels"]]
        if kind == "relation":
            paths.extend(f"/details/{d['object_id']}{p['path']}" for d in item["details"] for p in d["provenance"] if p["level"] in options["source_levels"])
        if not paths:
            return False
        item["matched_paths"] = sorted(set(paths))
    return True


def query(db_path, options):
    store = CaseStore(db_path)
    try:
        view = options.get("view", "records")
        fmt = options.get("format", "json")
        if fmt not in {"json", "markdown", "original"}:
            fail("INVALID_ARGUMENT", "/arguments/format", "unknown output format")
        if options.get("kinds") and set(options["kinds"]) - {"material", "text_version", "clause", "anchor", "node", "relation", "detail", "reference", "gap", "no_content"}:
            fail("INVALID_ARGUMENT", "/arguments/kind", "unknown record kind")
        limit, offset = options.get("limit", 100), options.get("offset", 0)
        if type(limit) is not int or limit <= 0 or type(offset) is not int or offset < 0:
            fail("INVALID_ARGUMENT", "/arguments", "invalid pagination")
        if options.get("object") and options.get("record"):
            fail("INVALID_ARGUMENT", "/arguments", "object and record are exclusive")
        if options.get("record") and options.get("history"):
            fail("INVALID_ARGUMENT", "/arguments", "record and history are exclusive")
        if fmt == "original":
            if view != "materials" or not options.get("object") or not options.get("output"):
                fail("INVALID_ARGUMENT", "/arguments/format", "original export requires material object and output")
            if any(options.get(key) for key in ("record", "history", "kinds", "parties", "units", "slots", "source_levels", "clauses")):
                fail("INVALID_ARGUMENT", "/arguments/format", "original export does not accept record filters")
            row = store.current(options["object"])
            if not row or row["kind"] != "material":
                fail("NOT_FOUND", "/arguments/object", "material missing")
            material = store.db.execute("SELECT original_bytes,content_hash FROM materials WHERE record_id=?", (row["record_id"],)).fetchone()
            if digest(material[0]) != material[1]:
                fail("DATABASE_ERROR", "", "original hash differs")
            exclusive_write(options["output"], material[0])
            return {"ok": True, "material_id": row["object_id"], "output": str(Path(options["output"]).absolute()),
                    "content_hash": material[1], "size": len(material[0])}
        if view not in {"overview", "report"} and options.get("history") and view in {"vocabulary", "progress"}:
            fail("INVALID_ARGUMENT", "/arguments/history", "history does not apply to this view")
        if view in {"vocabulary", "overview", "progress", "report"}:
            if any(options.get(key) for key in ("kinds", "object", "record", "parties", "units", "slots", "source_levels", "clauses")):
                fail("INVALID_ARGUMENT", "/arguments/view", "filters do not apply to management view")
            if view == "vocabulary":
                items = [{**store.vocabulary(), "hash": store.info["vocabulary_hash"]}]
            elif view == "progress":
                items = [progress(store)]
            elif view == "overview":
                rows = store.db.execute("SELECT * FROM case_overviews ORDER BY rowid DESC" if not options.get("history") else "SELECT * FROM case_overviews ORDER BY rowid").fetchall()
                if not options.get("history"):
                    rows = rows[:1]
                items = [{"overview_id": r["overview_id"], "submission_id": r["submission_id"],
                          "text_versions": json.loads(r["text_versions_json"]), "body": r["body"],
                          "authored_by": r["authored_by"]} for r in rows]
            else:
                rows = store.db.execute("SELECT * FROM reconciliation_reports ORDER BY created_at DESC" if not options.get("history") else "SELECT * FROM reconciliation_reports ORDER BY created_at").fetchall()
                if not options.get("history"):
                    rows = rows[:1]
                items = [json.loads(r["result_json"]) for r in rows]
        else:
            if options.get("record"):
                row = store.record(options["record"])
                if not row:
                    fail("NOT_FOUND", "/arguments/record", "record missing")
                rows = [row]
            elif options.get("object"):
                row = store.current(options["object"])
                if not row:
                    fail("NOT_FOUND", "/arguments/object", "object missing")
                rows = store.db.execute("SELECT r.*,o.kind FROM record_versions r JOIN objects o USING(object_id) WHERE object_id=? ORDER BY revision", (options["object"],)).fetchall() if options.get("history") else [row]
            else:
                rows = store.db.execute("""SELECT r.*,o.kind FROM record_versions r JOIN objects o USING(object_id)
                    JOIN submissions s ON s.submission_id=r.submission_id ORDER BY s.sequence,o.object_id,r.revision""").fetchall() if options.get("history") else store.db.execute("""SELECT r.*,o.kind FROM current_records r JOIN objects o USING(object_id)
                    JOIN submissions s ON s.submission_id=r.submission_id ORDER BY s.sequence,o.object_id,r.revision""").fetchall()
            expected = {"materials": {"material"}, "clauses": {"clause"}, "events": {"node"}, "gaps": {"gap"}}.get(view)
            if view not in {"records", "materials", "clauses", "events", "gaps"}:
                fail("INVALID_ARGUMENT", "/arguments/view", "unknown view")
            if expected and options.get("kinds") and set(options["kinds"]) - expected:
                fail("INVALID_ARGUMENT", "/arguments/kind", "kind conflicts with selected view")
            eligible = []
            owner_units = {}
            requested_clauses = set(options.get("clauses") or ())
            requested_slots = set(options.get("slots") or ())
            requested_parties = set(options.get("parties") or ())
            requested_levels = set(options.get("source_levels") or ())
            party_identities = {}
            owner_parties = {}
            level_records = set()
            level_detail_owners = set()
            if requested_levels and not options.get("history") and not options.get("record"):
                for source_row in store.db.execute("""SELECT s.record_id,s.level,o.kind,r.data_json
                    FROM assertion_sources s JOIN active_records r ON r.record_id=s.record_id
                    JOIN objects o USING(object_id)"""):
                    if source_row["level"] in requested_levels:
                        level_records.add(source_row["record_id"])
                        if source_row["kind"] == "detail":
                            level_detail_owners.add(json.loads(source_row["data_json"])["owner"]["object_id"])
            slot_owners = set()
            if requested_slots and not options.get("history") and not options.get("record"):
                for detail_row in store.db.execute("""SELECT r.data_json FROM active_records r
                    JOIN objects o USING(object_id) WHERE o.kind='detail'"""):
                    detail_data = json.loads(detail_row["data_json"])
                    if detail_data["slot_id"] in requested_slots:
                        slot_owners.add(detail_data["owner"]["object_id"])
            for row in rows:
                if row["status"] == "withdrawn" and not (options.get("history") or options.get("record") or options.get("include_withdrawn")):
                    continue
                if expected and row["kind"] not in expected:
                    continue
                if options.get("kinds") and row["kind"] not in options["kinds"]:
                    continue
                if view == "events" and json.loads(row["data_json"])["node_kind"] != "event":
                    continue
                if view == "records" and not any(options.get(k) for k in ("kinds", "object", "record")) and row["kind"] not in {"node", "relation", "detail", "reference", "gap", "no_content"}:
                    continue
                if options.get("units"):
                    data = json.loads(row["data_json"])
                    if row["kind"] == "relation":
                        unit = data["unit_id"]
                    elif row["kind"] == "detail":
                        owner_id = data["owner"]["object_id"]
                        if owner_id not in owner_units:
                            owner = store.current(owner_id)
                            owner_units[owner_id] = json.loads(owner["data_json"])["unit_id"] if owner else None
                        unit = owner_units[owner_id]
                    else:
                        unit = None
                    if unit not in options["units"]:
                        continue
                if requested_clauses:
                    if not (row["kind"] == "clause" and row["object_id"] in requested_clauses):
                        if not any(anchor["clause_id"] in requested_clauses
                                   for root in _provenance(store, row["record_id"])
                                   for anchor in root["anchors"]):
                            continue
                if requested_slots and not options.get("history") and not options.get("record"):
                    if row["kind"] == "detail":
                        if json.loads(row["data_json"])["slot_id"] not in requested_slots:
                            continue
                    elif row["kind"] == "relation":
                        if row["object_id"] not in slot_owners:
                            continue
                    else:
                        continue
                if requested_parties and not options.get("history") and not options.get("record"):
                    if row["kind"] == "relation":
                        relation_data = json.loads(row["data_json"])
                        if relation_data["relation_kind"] != "party":
                            continue
                        direct = {party["subject"]["object_id"] for party in relation_data["parties"]}
                        if not direct & requested_parties:
                            for subject_id in direct:
                                if subject_id not in party_identities:
                                    party_identities[subject_id] = _identity(store, subject_id)["canonical_id"]
                            if not {party_identities[x] for x in direct} & requested_parties:
                                continue
                    elif row["kind"] == "detail":
                        owner_id = json.loads(row["data_json"])["owner"]["object_id"]
                        if owner_id not in owner_parties:
                            owner = store.current(owner_id)
                            party_ids = (
                                {party["subject"]["object_id"] for party in json.loads(owner["data_json"]).get("parties", [])}
                                if owner else set()
                            )
                            for subject_id in list(party_ids):
                                if subject_id not in party_identities:
                                    party_identities[subject_id] = _identity(store, subject_id)["canonical_id"]
                                if party_identities[subject_id]:
                                    party_ids.add(party_identities[subject_id])
                            owner_parties[owner_id] = party_ids
                        if not owner_parties[owner_id] & requested_parties:
                            continue
                    else:
                        continue
                if requested_levels and not options.get("history") and not options.get("record"):
                    if row["record_id"] not in level_records and not (
                        row["kind"] == "relation" and row["object_id"] in level_detail_owners
                    ):
                        continue
                eligible.append(row)
            deep_filters = bool(
                (options.get("history") or options.get("record"))
                and (requested_slots or requested_parties or requested_levels)
            )
            if deep_filters:
                items = []
                for row in eligible:
                    item = record_item(store, row, store.db.execute("SELECT sequence FROM submissions WHERE submission_id=?", (row["submission_id"],)).fetchone()[0] if options.get("history") or options.get("record") else store.sequence())
                    if _filter_item(store, item, options):
                        items.append(item)
                total = len(items)
                page = items[offset:offset + limit]
            else:
                total = len(eligible)
                page = [
                    record_item(store, row, store.db.execute("SELECT sequence FROM submissions WHERE submission_id=?", (row["submission_id"],)).fetchone()[0] if options.get("history") or options.get("record") else store.sequence())
                    for row in eligible[offset:offset + limit]
                ]
                if requested_levels:
                    for item in page:
                        _filter_item(store, item, options)
        if view in {"vocabulary", "overview", "progress", "report"}:
            total = len(items)
            page = items[offset:offset + limit]
        result = {"ok": True, "case_id": store.case_id(), "view": view,
                  "result_status": "found" if total else "no_record", "total": total,
                  "offset": offset, "limit": limit,
                  "next_offset": offset + len(page) if offset + len(page) < total else None,
                  "items": page, "quality": quality(store)}
        if fmt == "markdown":
            rendered = "# Case query\n\n```json\n" + json.dumps(result, ensure_ascii=False, indent=2) + "\n```\n"
            if options.get("output"):
                exclusive_write(options["output"], rendered.encode("utf-8"))
                return {"ok": True, "output": str(Path(options["output"]).absolute()), "format": "markdown"}
            return rendered
        if options.get("output"):
            exclusive_write(options["output"], (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
            return {"ok": True, "output": str(Path(options["output"]).absolute()), "format": "json"}
        return result
    finally:
        store.close()
