"""Append-only SQLite case storage and management submissions."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from . import __version__
from .formats import (Invalid, canonical, digest, fail, file_bytes, file_text, hash_json,
                      new_id, read_json, timestamp, uuid_value, version, fields,
                      integer, nonempty)
from .values import validate_units
from .vocabulary import load, vocabulary_hash


SCHEMA = Path(__file__).with_name("schema.sql")
UNITS = Path(__file__).with_name("config") / "units.v1.json"


def _json(obj):
    return canonical(obj).decode("utf-8")


class CaseStore:
    def __init__(self, path, must_exist=True):
        self.path = Path(path)
        if must_exist and not self.path.is_file():
            fail("FILE_ERROR", str(path), "case database does not exist")
        try:
            self.db = sqlite3.connect(self.path)
            self.db.row_factory = sqlite3.Row
            self.db.execute("PRAGMA foreign_keys=ON")
            if must_exist:
                self.info = self.db.execute("SELECT * FROM case_info").fetchone()
                if self.info is None:
                    fail("DATABASE_ERROR", str(path), "case_info missing")
                for field in ("schema_version", "value_format_version", "code_version", "vocabulary_format_version"):
                    if self.info[field] != 1:
                        fail("UNSUPPORTED_VERSION", f"/case_info/{field}", "unsupported case format version")
            else:
                self.info = None
        except (sqlite3.Error, Invalid) as exc:
            self.db.close()
            if isinstance(exc, Invalid):
                raise
            fail("DATABASE_ERROR", str(path), str(exc))

    def close(self):
        self.db.close()

    def begin(self):
        self.db.execute("BEGIN IMMEDIATE")

    def sequence(self):
        return self.db.execute("SELECT COALESCE(MAX(sequence),0) FROM submissions").fetchone()[0]

    def replay(self, content_hash):
        row = self.db.execute("SELECT receipt_json FROM submissions WHERE content_hash=?", (content_hash,)).fetchone()
        if row:
            receipt = json.loads(row[0])
            receipt["replayed"] = True
            return receipt
        return None

    def current(self, object_id, sequence=None):
        if sequence is None:
            return self.db.execute("SELECT r.*,o.kind FROM current_records r JOIN objects o USING(object_id) WHERE object_id=?", (object_id,)).fetchone()
        return self.db.execute("""SELECT r.*,o.kind FROM record_versions r JOIN objects o USING(object_id)
            JOIN submissions s ON s.submission_id=r.submission_id WHERE r.object_id=? AND s.sequence<=?
            ORDER BY r.revision DESC LIMIT 1""", (object_id, sequence)).fetchone()

    def record(self, record_id):
        return self.db.execute("SELECT r.*,o.kind FROM record_versions r JOIN objects o USING(object_id) WHERE record_id=?", (record_id,)).fetchone()

    def kind(self, row):
        if row is None:
            return None
        if row["kind"] == "node":
            return "node:" + json.loads(row["data_json"])["node_kind"]
        return row["kind"]

    def case_id(self):
        return self.info["case_id"]

    def vocabulary(self):
        return {"format_version": 1,
                "units": [json.loads(row[0]) for row in self.db.execute("SELECT entry_json FROM vocabulary_units ORDER BY unit_id")],
                "slots": [json.loads(row[0]) for row in self.db.execute("SELECT entry_json FROM vocabulary_slots ORDER BY slot_id")],
                "assignments": [dict(row) for row in self.db.execute("SELECT unit_id,slot_id FROM vocabulary_assignments ORDER BY unit_id,slot_id")]}

    def unit_config(self):
        return json.loads(self.info["unit_config_json"])

    def add_submission(self, phase, content_hash, input_obj, receipt, submitted_by):
        self.db.execute("INSERT INTO submissions VALUES(?,?,?,?,?,?,?,?)",
                        (receipt["submission_id"], self.sequence() + 1, content_hash,
                         submitted_by, phase, _json(input_obj), _json(receipt), timestamp()))

    def add_record(self, object_id, record_id, revision, previous, submission_id,
                   kind, data, evidence, status="active", reason=None, typed=None):
        if revision == 1:
            self.db.execute("INSERT INTO objects VALUES(?,?,?)", (object_id, kind, submission_id))
        self.db.execute("INSERT INTO record_versions VALUES(?,?,?,?,?,?,?,?)",
                        (record_id, object_id, revision, previous, submission_id,
                         status, reason, _json(data)))
        for item in evidence:
            self.db.execute("INSERT INTO assertion_sources VALUES(?,?,?,?)",
                            (record_id, item["path"], item["source"]["level"], _json(item["source"])))
        if typed:
            table, values = typed
            columns = ",".join(values)
            marks = ",".join("?" for _ in values)
            self.db.execute(f"INSERT INTO {table} ({columns}) VALUES ({marks})", tuple(values.values()))


def initialize(db_path, vocabulary_path):
    target = Path(db_path)
    if target.exists():
        fail("FILE_EXISTS", str(target), "case target exists")
    vocabulary, source_files = load(vocabulary_path)
    units = read_json(UNITS)
    available_units = validate_units(units)
    def check_slot_units(schema):
        for code in schema.get("allowed_units", []):
            if code not in available_units:
                fail("UNKNOWN_UNIT", "/vocabulary/slots/value_schema/allowed_units", "slot names unknown unit")
        if schema.get("type") == "object":
            for sub in schema["fields"].values():
                check_slot_units(sub)
        elif schema.get("type") == "list":
            check_slot_units(schema["items"])
        elif "one_of" in schema:
            for sub in schema["one_of"]:
                check_slot_units(sub)
    for slot in vocabulary["slots"]:
        check_slot_units(slot["value_schema"])
    case_id, contract_id, record_id, submission_id = (new_id() for _ in range(4))
    vocab_hash = vocabulary_hash(vocabulary)
    unit_hash = hash_json({**units, "units": sorted(units["units"], key=lambda e: e["code"])})
    response = {"ok": True, "case_id": case_id, "contract_object_id": contract_id,
                "vocabulary_hash": vocab_hash, "unit_config_hash": unit_hash,
                "schema_version": 1, "submission_id": submission_id}
    try:
        with target.open("xb"):
            pass
        store = CaseStore(target, False)
        try:
            store.db.executescript(SCHEMA.read_text(encoding="utf-8"))
            store.begin()
            input_obj = {"operation": "init", "case_id": case_id,
                         "vocabulary_hash": vocab_hash, "unit_config_hash": unit_hash}
            store.db.execute("INSERT INTO submissions VALUES(?,?,?,?,?,?,?,?)",
                             (submission_id, 1, hash_json(input_obj), "case_cli", "init", _json(input_obj), _json(response), timestamp()))
            store.add_record(contract_id, record_id, 1, None, submission_id, "node",
                             {"node_kind": "contract"}, [], typed=("nodes", {"record_id": record_id, "node_kind": "contract", "name": None}))
            for unit in vocabulary["units"]:
                store.db.execute("INSERT INTO vocabulary_units VALUES(?,?)", (unit["id"], _json(unit)))
            for slot in vocabulary["slots"]:
                store.db.execute("INSERT INTO vocabulary_slots VALUES(?,?)", (slot["id"], _json(slot)))
            for relation in vocabulary["assignments"]:
                store.db.execute("INSERT INTO vocabulary_assignments VALUES(?,?)", (relation["unit_id"], relation["slot_id"]))
            store.db.execute("INSERT INTO case_info VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                             (1, case_id, contract_id, timestamp(), __version__, 1, 1, 1, 1,
                              vocab_hash, _json(source_files), _json(units), unit_hash))
            store.db.commit()
        finally:
            store.close()
    except (OSError, sqlite3.Error) as exc:
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass
        fail("DATABASE_ERROR", str(target), str(exc))
    return response


def register(db_path, original_path, text_path, metadata_path):
    original = file_bytes(original_path)
    text = file_text(text_path)
    metadata = read_json(metadata_path)
    fields(metadata, ["name", "media_type", "conversion_method", "converter_version", "anomalies"], ["material_id"])
    for name in ("name", "media_type", "conversion_method", "converter_version"):
        nonempty(metadata[name], "/metadata/" + name)
    if not isinstance(metadata["anomalies"], list):
        fail("INVALID_ARGUMENT", "/metadata/anomalies", "expected array")
    for i, anomaly in enumerate(metadata["anomalies"]):
        path = f"/metadata/anomalies/{i}"
        fields(anomaly, ["code", "message"], ["start_offset", "end_offset"], path)
        nonempty(anomaly["code"], path + "/code")
        nonempty(anomaly["message"], path + "/message")
        if ("start_offset" in anomaly) != ("end_offset" in anomaly):
            fail("INVALID_ARGUMENT", path, "both offsets required")
        if "start_offset" in anomaly:
            integer(anomaly["start_offset"], path + "/start_offset", 0)
            integer(anomaly["end_offset"], path + "/end_offset", 0)
            if not anomaly["start_offset"] < anomaly["end_offset"] <= len(text):
                fail("INVALID_ARGUMENT", path, "anomaly interval outside text")
    original_hash, text_hash = digest(original), digest(text.encode("utf-8"))
    input_obj = {"operation": "register", "original_hash": original_hash,
                 "text_hash": text_hash, "metadata": metadata}
    content_hash = hash_json(input_obj)
    store = CaseStore(db_path)
    try:
        store.begin()
        if receipt := store.replay(content_hash):
            store.db.rollback()
            return receipt
        if "material_id" in metadata:
            material_id = uuid_value(metadata["material_id"], "/metadata/material_id")
            existing = store.current(material_id)
            if existing is None or existing["kind"] != "material":
                fail("REFERENCE_NOT_FOUND", "/metadata/material_id", "material missing")
            old = store.db.execute("SELECT content_hash FROM materials WHERE record_id=?", (existing["record_id"],)).fetchone()
            if old[0] != original_hash:
                fail("ORIGINAL_MISMATCH", "/original", "original bytes changed")
            material_record_id = existing["record_id"]
            version_number = store.db.execute("SELECT COALESCE(MAX(version_number),0)+1 FROM text_versions WHERE material_id=?", (material_id,)).fetchone()[0]
        else:
            material_id, material_record_id = new_id(), new_id()
            version_number = 1
        text_id, text_record, submission_id = new_id(), new_id(), new_id()
        response = {"ok": True, "submission_id": submission_id, "content_hash": content_hash,
                    "replayed": False, "material": {"object_id": material_id, "record_id": material_record_id},
                    "text_version": {"object_id": text_id, "record_id": text_record, "version_number": version_number},
                    "original_hash": original_hash, "text_hash": text_hash,
                    "anomalies": metadata["anomalies"]}
        store.add_submission("register", content_hash, input_obj, response, "case_cli")
        if "material_id" not in metadata:
            material_data = {"name": metadata["name"], "media_type": metadata["media_type"],
                             "content_hash": original_hash, "original_path": str(Path(original_path).absolute())}
            order = store.db.execute("SELECT COALESCE(MAX(registered_order),0)+1 FROM materials").fetchone()[0]
            store.add_record(material_id, material_record_id, 1, None, submission_id, "material", material_data, [],
                             typed=("materials", {"record_id": material_record_id, "name": metadata["name"],
                                                  "media_type": metadata["media_type"], "content_hash": original_hash,
                                                  "registered_order": order, "original_bytes": original,
                                                  "original_path": str(Path(original_path).absolute())}))
        text_data = {"material": {"object_id": material_id}, "version_number": version_number,
                     "conversion_method": metadata["conversion_method"], "converter_version": metadata["converter_version"],
                     "text": text, "text_hash": text_hash, "anomalies": metadata["anomalies"]}
        store.add_record(text_id, text_record, 1, None, submission_id, "text_version", text_data, [],
                         typed=("text_versions", {"record_id": text_record, "material_id": material_id,
                                                  "version_number": version_number, "conversion_method": metadata["conversion_method"],
                                                  "converter_version": metadata["converter_version"], "text": text,
                                                  "text_hash": text_hash, "anomalies_json": _json(metadata["anomalies"])}))
        store.db.execute("INSERT INTO record_links VALUES(?,?,?,NULL)", (text_record, "/data/material", material_id))
        store.db.commit()
        return response
    except Exception:
        store.db.rollback()
        raise
    finally:
        store.close()


def split(db_path, text_version_id):
    from .splitter import ALGORITHM_VERSION, split_text
    uuid_value(text_version_id, "/arguments/text-version")
    store = CaseStore(db_path)
    try:
        store.begin()
        row = store.current(text_version_id)
        if row is None or row["kind"] != "text_version":
            fail("REFERENCE_NOT_FOUND", "/arguments/text-version", "text version missing")
        source = store.db.execute("SELECT text FROM text_versions WHERE record_id=?", (row["record_id"],)).fetchone()
        text = source[0]
        input_obj = {"operation": "split", "text_version_id": text_version_id,
                     "algorithm_version": ALGORITHM_VERSION}
        content_hash = hash_json(input_obj)
        if receipt := store.replay(content_hash):
            store.db.rollback()
            return receipt
        if store.db.execute("SELECT 1 FROM clauses WHERE text_version_id=? LIMIT 1", (text_version_id,)).fetchone():
            fail("SPLIT_ALREADY_EXISTS", "/arguments/text-version", "clauses already exist")
        clauses = split_text(text)
        submission_id = new_id()
        clause_results, gap_results, planned = [], [], []
        for item in clauses:
            clause_id, clause_record = new_id(), new_id()
            clause_results.append({"object_id": clause_id, "record_id": clause_record,
                                   "sequence": item["sequence"], "start_offset": item["start_offset"],
                                   "end_offset": item["end_offset"], "original_number": item["original_number"]})
            planned.append(("clause", clause_id, clause_record, item))
            if item["anomalies"]:
                anchor_id, anchor_record = new_id(), new_id()
                planned.append(("anchor", anchor_id, anchor_record, {"clause_id": clause_id,
                                                                       "clause_record": clause_record,
                                                                       "quote": item["text"]}))
                for anomaly in item["anomalies"]:
                    gap_id, gap_record = new_id(), new_id()
                    gap_results.append({"object_id": gap_id, "record_id": gap_record})
                    planned.append(("gap", gap_id, gap_record, {"clause_id": clause_id,
                                                                   "clause_record": clause_record,
                                                                   "anchor_record": anchor_record,
                                                                   "anomaly": anomaly}))
        response = {"ok": True, "submission_id": submission_id, "content_hash": content_hash,
                    "replayed": False, "text_version_id": text_version_id,
                    "algorithm_version": ALGORITHM_VERSION, "clauses": clause_results,
                    "gaps": gap_results,
                    "character_coverage": {"passed": True, "source_length": len(text),
                                           "clauses_length": sum(len(c["text"]) for c in clauses)}}
        store.add_submission("split", content_hash, input_obj, response, "splitter:" + ALGORITHM_VERSION)
        # Create all objects before inserting rows with same-batch foreign keys.
        for kind, object_id, record_id, item in planned:
            store.db.execute("INSERT INTO objects VALUES(?,?,?)", (object_id, kind, submission_id))
        for kind, object_id, record_id, item in planned:
            if kind == "clause":
                data = {"text_version": {"object_id": text_version_id}, "sequence": item["sequence"],
                        "original_number": item["original_number"], "text": item["text"],
                        "start_offset": item["start_offset"], "end_offset": item["end_offset"],
                        "tags": [], "classification": "unclassified"}
                typed = ("clauses", {"record_id": record_id, "text_version_id": text_version_id,
                                     "sequence": item["sequence"], "original_number": item["original_number"],
                                     "text": item["text"], "start_offset": item["start_offset"],
                                     "end_offset": item["end_offset"], "tags_json": "[]",
                                     "classification": "unclassified"})
                links = []
            elif kind == "anchor":
                data = {"clause": {"record_id": item["clause_record"]}, "quote": item["quote"], "occurrence": 1}
                typed = ("anchors", {"record_id": record_id, "clause_record_id": item["clause_record"],
                                     "quote": item["quote"], "occurrence": 1,
                                     "start_offset": 0, "end_offset": len(item["quote"])})
                links = []
            else:
                anomaly = item["anomaly"]
                description = f"{anomaly['type']}: {anomaly['detail']}（行 {anomaly['line']}）"
                data = {"clause": {"record_id": item["clause_record"]},
                        "gap_kind": "structure_anomaly", "description": description,
                        "reported_by": "splitter:" + ALGORITHM_VERSION}
                typed = ("gaps", {"record_id": record_id, "clause_record_id": item["clause_record"],
                                  "gap_kind": "structure_anomaly", "description": description,
                                  "reported_by": "splitter:" + ALGORITHM_VERSION})
                links = [{"path": "", "source": {"level": 1, "anchors": [{"record_id": item["anchor_record"]}]}}]
            store.db.execute("INSERT INTO record_versions VALUES(?,?,?,?,?,?,?,?)",
                             (record_id, object_id, 1, None, submission_id, "active", None, _json(data)))
            for evidence in links:
                store.db.execute("INSERT INTO assertion_sources VALUES(?,?,?,?)",
                                 (record_id, evidence["path"], 1, _json(evidence["source"])))
            table, values = typed
            store.db.execute(f"INSERT INTO {table} ({','.join(values)}) VALUES ({','.join('?' for _ in values)})", tuple(values.values()))
            if kind == "clause":
                store.db.execute("INSERT INTO record_links VALUES(?,?,?,NULL)", (record_id, "/data/text_version", text_version_id))
            elif kind == "anchor":
                store.db.execute("INSERT INTO record_links VALUES(?,?,NULL,?)", (record_id, "/data/clause", item["clause_record"]))
            else:
                store.db.execute("INSERT INTO record_links VALUES(?,?,NULL,?)", (record_id, "/data/clause", item["clause_record"]))
                store.db.execute("INSERT INTO record_links VALUES(?,?,NULL,?)", (record_id, "/evidence/0/source/anchors/0", item["anchor_record"]))
        store.db.commit()
        return response
    except Exception:
        store.db.rollback()
        raise
    finally:
        store.close()
