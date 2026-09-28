"""Validated, atomic append-only modeling submissions."""

from __future__ import annotations

import json
import re
from collections import Counter

from .formats import (Invalid, InvalidBatch, fields, fail, hash_json, integer, new_id,
                      nonempty, pointer_get, require_object, uuid_value, version)
from .storage import CaseStore, _json
from .values import matches_schema, validate_value, validate_units, check_contract

KINDS = {"clause", "anchor", "node", "relation", "detail", "reference", "gap", "no_content"}
NATURES = {"obligor", "recipient", "power_holder", "power_subject", "permission_holder",
           "permission_counterparty", "protected_party", "restricted_party"}
MODALITIES = {"obligation", "power", "permission", "immunity"}
REFERENCES = {"appellation", "role", "composition", "definition", "event_of", "scope",
              "priority", "amendment", "redirect", "distinct"}


class DependentInvalid(Exception):
    """A record whose prerequisite already failed in this submission."""


class ModelWriter:
    def __init__(self, store, document):
        self.store, self.document = store, document
        self.plans = []
        self.local = {}
        self.by_object = {}
        self.units = {e["id"]: e for e in store.vocabulary()["units"]}
        self.slots = {e["id"]: e for e in store.vocabulary()["slots"]}
        self.assignments = {(a["unit_id"], a["slot_id"]) for a in store.vocabulary()["assignments"]}
        self.unit_config = validate_units(store.unit_config())

    def prepare(self):
        doc = self.document
        fields(doc, ["format_version", "case_id", "vocabulary_hash", "submitted_by", "phase",
                     "covered_clauses", "records", "issues"], ["overview"])
        version(doc["format_version"])
        if doc["case_id"] != self.store.case_id():
            fail("CASE_MISMATCH", "/case_id", "case ID differs")
        if doc["vocabulary_hash"] != self.store.info["vocabulary_hash"]:
            fail("VOCABULARY_MISMATCH", "/vocabulary_hash", "frozen vocabulary differs")
        nonempty(doc["submitted_by"], "/submitted_by")
        if not isinstance(doc["phase"], str) or doc["phase"] not in {"preparation", "tagging", "extraction", "correction"}:
            fail("INVALID_ARGUMENT", "/phase")
        if not isinstance(doc["records"], list) or not isinstance(doc["covered_clauses"], list) or not isinstance(doc["issues"], list):
            fail("INVALID_ARGUMENT", "", "records, covered_clauses and issues must be arrays")
        for i, issue in enumerate(doc["issues"]):
            nonempty(issue, f"/issues/{i}")
        if doc["phase"] != "extraction" and doc["covered_clauses"] or doc["phase"] == "extraction" and not doc["covered_clauses"]:
            fail("COVERAGE_INVALID", "/covered_clauses", "only extraction declares completed clauses")
        if "overview" in doc:
            if doc["phase"] != "preparation":
                fail("INVALID_ARGUMENT", "/overview", "overview only belongs to preparation")
            fields(doc["overview"], ["text_versions", "body", "authored_by"], [], "/overview")
            if not isinstance(doc["overview"]["text_versions"], list) or not doc["overview"]["text_versions"]:
                fail("INVALID_ARGUMENT", "/overview/text_versions")
            nonempty(doc["overview"]["body"], "/overview/body")
            nonempty(doc["overview"]["authored_by"], "/overview/authored_by")
        for i, raw in enumerate(doc["records"]):
            path = f"/records/{i}"
            fields(raw, ["local_id", "kind", "data", "evidence"],
                   ["object_id", "previous_record_id", "status", "withdrawal_reason"], path)
            local = nonempty(raw["local_id"], path + "/local_id")
            if local in self.local:
                fail("DUPLICATE_LOCAL_ID", path + "/local_id", "duplicate local ID")
            kind = raw["kind"]
            require_object(raw["data"], path + "/data")
            if not isinstance(raw["evidence"], list):
                fail("INVALID_ARGUMENT", path + "/evidence", "expected array")
            if not isinstance(kind, str) or kind not in KINDS:
                fail("INVALID_ARGUMENT", path + "/kind", "unsupported record kind")
            revision = 1
            previous = None
            if ("object_id" in raw) != ("previous_record_id" in raw):
                fail("INVALID_ARGUMENT", path, "object_id and previous_record_id must appear together")
            if "object_id" in raw:
                object_id = uuid_value(raw["object_id"], path + "/object_id")
                previous = uuid_value(raw["previous_record_id"], path + "/previous_record_id")
                old = self.store.current(object_id)
                if old is None:
                    fail("REFERENCE_NOT_FOUND", path + "/object_id", "object missing")
                if old["record_id"] != previous:
                    fail("STALE_REVISION", path + "/previous_record_id", "previous version is stale", current_record_id=old["record_id"])
                if old["kind"] != kind:
                    fail("KIND_CHANGE", path + "/kind", "object kind is immutable")
                if kind in {"material", "text_version", "gap"}:
                    fail("IMMUTABLE_RECORD", path + "/kind")
                if kind == "node" and json.loads(old["data_json"])["node_kind"] != raw["data"].get("node_kind"):
                    fail("KIND_CHANGE", path + "/data/node_kind")
                if kind == "relation" and json.loads(old["data_json"])["relation_kind"] != raw["data"].get("relation_kind"):
                    fail("KIND_CHANGE", path + "/data/relation_kind")
                revision = old["revision"] + 1
            else:
                object_id = new_id()
                if kind == "node" and raw["data"].get("node_kind") == "contract":
                    fail("INVALID_ARGUMENT", path + "/data/node_kind", "contract node is created by init")
            if object_id in self.by_object:
                fail("DUPLICATE_ID", path + "/object_id", "object appears twice in one submission")
            status = raw.get("status", "active")
            if not isinstance(status, str) or status not in {"active", "withdrawn"}:
                fail("INVALID_ARGUMENT", path + "/status")
            if status == "withdrawn":
                if previous is None:
                    fail("INVALID_ARGUMENT", path + "/status", "new object cannot be withdrawn")
                nonempty(raw.get("withdrawal_reason"), path + "/withdrawal_reason")
                if object_id == self.store.info["contract_object_id"]:
                    fail("IMMUTABLE_RECORD", path, "contract container cannot be withdrawn")
                old = self.store.record(previous)
                if raw["data"] != json.loads(old["data_json"]):
                    fail("WITHDRAWAL_DATA_CHANGED", path + "/data", "withdrawal must copy prior data")
                old_evidence = [{"path": e["path"], "source": json.loads(e["source_json"])} for e in self.store.db.execute("SELECT * FROM assertion_sources WHERE record_id=? ORDER BY path", (previous,))]
                if sorted(raw["evidence"], key=lambda e: e["path"]) != old_evidence:
                    fail("WITHDRAWAL_DATA_CHANGED", path + "/evidence", "withdrawal must copy prior evidence")
            elif "withdrawal_reason" in raw:
                fail("UNKNOWN_FIELD", path + "/withdrawal_reason")
            record_id = new_id()
            plan = {"path": path, "local_id": local, "kind": kind, "object_id": object_id,
                    "record_id": record_id, "revision": revision, "previous": previous,
                    "raw": raw, "status": status, "reason": raw.get("withdrawal_reason"),
                    "data": None, "evidence": None}
            self.plans.append(plan)
            self.local[local] = plan
            self.by_object[object_id] = plan

    def _target(self, ref, path, fixed=False, allowed=None, allow_withdrawn=False):
        fields(ref, [], ["object_id", "record_id", "local_id", "value_path"], path)
        keys = {"object_id", "record_id", "local_id"} & set(ref)
        if len(keys) != 1:
            fail("INVALID_ARGUMENT", path, "reference needs exactly one target")
        key = next(iter(keys))
        if key == "local_id":
            plan = self.local.get(nonempty(ref[key], path + "/local_id"))
            if not plan:
                fail("REFERENCE_NOT_FOUND", path, "local target missing")
            if plan["object_id"] in getattr(self, "failed_objects", set()):
                raise DependentInvalid()
            row = None
            object_id, record_id, kind, status = plan["object_id"], plan["record_id"], plan["kind"], plan["status"]
            data = plan["data"] if plan["data"] is not None else plan["raw"]["data"]
        elif key == "object_id":
            object_id = uuid_value(ref[key], path + "/object_id")
            plan = self.by_object.get(object_id)
            if plan and plan["object_id"] in getattr(self, "failed_objects", set()):
                raise DependentInvalid()
            row = None if plan else self.store.current(object_id)
            if not plan and row is None:
                fail("REFERENCE_NOT_FOUND", path, "object missing")
            record_id = plan["record_id"] if plan else row["record_id"]
            kind = plan["kind"] if plan else row["kind"]
            status = plan["status"] if plan else row["status"]
            data = (plan["data"] or plan["raw"]["data"]) if plan else json.loads(row["data_json"])
        else:
            record_id = uuid_value(ref[key], path + "/record_id")
            plan = next((p for p in self.plans if p["record_id"] == record_id), None)
            if plan and plan["object_id"] in getattr(self, "failed_objects", set()):
                raise DependentInvalid()
            row = None if plan else self.store.record(record_id)
            if not plan and row is None:
                fail("REFERENCE_NOT_FOUND", path, "record missing")
            object_id = plan["object_id"] if plan else row["object_id"]
            kind = plan["kind"] if plan else row["kind"]
            status = plan["status"] if plan else row["status"]
            data = (plan["data"] or plan["raw"]["data"]) if plan else json.loads(row["data_json"])
        if kind == "node":
            kind += ":" + data.get("node_kind", "")
        if allowed and kind not in allowed:
            fail("REFERENCE_TYPE_MISMATCH", path, "target has wrong kind")
        if not fixed and status == "withdrawn" and not allow_withdrawn:
            fail("WITHDRAWN_TARGET", path, "business target is withdrawn")
        if fixed and key == "object_id":
            fail("INVALID_ARGUMENT", path, "fixed reference requires record ID")
        if not fixed and key == "record_id" and "value_path" not in ref:
            fail("INVALID_ARGUMENT", path, "business reference requires object ID")
        if "value_path" in ref:
            if kind not in {"detail", "node:defined_value"} or key == "object_id":
                fail("INVALID_ARGUMENT", path + "/value_path", "value path requires fixed value record")
            pointer = ref["value_path"]
            if pointer != "/value" and not (isinstance(pointer, str) and pointer.startswith("/value/")):
                fail("INVALID_ARGUMENT", path + "/value_path")
            pointer_get(data, pointer)
            return {"record_id": record_id, "value_path": pointer}, {"kind": kind, "data": data, "object_id": object_id, "record_id": record_id}
        normalized = {"record_id": record_id} if fixed else {"object_id": object_id}
        return normalized, {"kind": kind, "data": data, "object_id": object_id, "record_id": record_id}

    def _business(self, ref, path, allowed=None):
        return self._target(ref, path, allowed=allowed)[0]

    def _fixed(self, ref, path, allowed=None):
        return self._target(ref, path, fixed=True, allowed=allowed)[0]

    def _business_fixed(self, ref, path, allowed=None):
        normalized, target = self._target(ref, path, fixed=True, allowed=allowed)
        candidate = self.by_object.get(target["object_id"])
        current = candidate if candidate else self.store.current(target["object_id"])
        if current and current["status"] == "withdrawn":
            fail("WITHDRAWN_TARGET", path, "fixed business target is withdrawn")
        return normalized, target

    def _value_resolver(self, ref, path):
        fixed = "record_id" in ref or "value_path" in ref
        return (self._business_fixed(ref, path) if fixed else self._target(ref, path))[1]

    def validate_data(self):
        failures = []
        self.failed_objects = set()
        order = {"clause": 0, "anchor": 1, "node": 2, "relation": 3, "detail": 4, "reference": 5, "gap": 6, "no_content": 7}
        for plan in sorted(self.plans, key=lambda item: order[item["kind"]]):
            try:
                self._validate_data_plan(plan)
            except DependentInvalid:
                self.failed_objects.add(plan["object_id"])
            except Invalid as exc:
                failures.append(exc.item())
                self.failed_objects.add(plan["object_id"])
        if failures:
            raise InvalidBatch(failures)

    def _validate_data_plan(self, plan):
        path = plan["path"] + "/data"
        raw = plan["raw"]["data"]
        if plan["status"] == "withdrawn":
            plan["data"] = raw
            return
        kind = plan["kind"]
        if kind == "clause":
            fields(raw, ["text_version", "sequence", "text", "start_offset", "end_offset", "tags", "classification"], ["original_number"], path)
            if "original_number" in raw and raw["original_number"] is not None and not isinstance(raw["original_number"], str):
                fail("INVALID_ARGUMENT", path + "/original_number", "expected string or null")
            source = self._business(raw["text_version"], path + "/text_version", {"text_version"})
            text_row = self.store.current(source["object_id"])
            full_text = self.store.db.execute("SELECT text FROM text_versions WHERE record_id=?", (text_row["record_id"],)).fetchone()[0]
            start, end = integer(raw["start_offset"], path + "/start_offset", 0), integer(raw["end_offset"], path + "/end_offset", 0)
            integer(raw["sequence"], path + "/sequence", 1)
            if end < start or end > len(full_text) or raw["text"] != full_text[start:end]:
                fail("INVALID_VALUE", path, "clause slice differs from registered text")
            if not isinstance(raw["tags"], list) or any(not isinstance(tag, str) for tag in raw["tags"]) or len(raw["tags"]) != len(set(raw["tags"])) or any(tag not in self.units for tag in raw["tags"]):
                fail("INVALID_VALUE", path + "/tags")
            classification = raw["classification"]
            if not isinstance(classification, str) or classification not in {"unclassified", "ordinary", "no_content", "unmatched"} or (classification == "ordinary") != bool(raw["tags"]):
                fail("INVALID_VALUE", path + "/classification")
            old = self.store.current(plan["object_id"]) if plan["previous"] else None
            if old:
                prior = json.loads(old["data_json"])
                for field in ("text_version", "sequence", "text", "start_offset", "end_offset", "original_number"):
                    if raw.get(field) != prior.get(field):
                        if self.document["phase"] != "correction":
                            fail("IMMUTABLE_RECORD", path + "/" + field, "text identity change requires correction")
            plan["data"] = {**raw, "text_version": source, "original_number": raw.get("original_number")}
        elif kind == "anchor":
            fields(raw, ["clause", "quote"], ["occurrence"], path)
            clause = self._fixed(raw["clause"], path + "/clause", {"clause"})
            quote = raw["quote"]
            if not isinstance(quote, str) or not quote:
                fail("INVALID_ARGUMENT", path + "/quote", "empty quote")
            clause_plan = next((p for p in self.plans if p["record_id"] == clause["record_id"]), None)
            clause_row = None if clause_plan else self.store.record(clause["record_id"])
            clause_data = clause_plan["data"] if clause_plan else json.loads(clause_row["data_json"])
            found = []
            index = clause_data["text"].find(quote)
            while index >= 0:
                found.append(index)
                index = clause_data["text"].find(quote, index + 1)
            if not found:
                fail("ANCHOR_NOT_FOUND", path + "/quote", "quote absent from clause")
            occurrence = raw["occurrence"] if "occurrence" in raw else None
            if "occurrence" not in raw and len(found) > 1:
                fail("ANCHOR_AMBIGUOUS", path + "/occurrence", "occurrence required")
            if "occurrence" not in raw:
                occurrence = 1
            integer(occurrence, path + "/occurrence", 1)
            if occurrence > len(found):
                fail("ANCHOR_OCCURRENCE", path + "/occurrence", "occurrence outside matches")
            if len(found) == 1 and occurrence != 1:
                fail("ANCHOR_OCCURRENCE", path + "/occurrence")
            plan["data"] = {"clause": clause, "quote": quote, "occurrence": occurrence}
            plan["anchor_start"], plan["anchor_end"] = found[occurrence - 1], found[occurrence - 1] + len(quote)
        elif kind == "node":
            node_kind = raw.get("node_kind")
            if node_kind == "subject":
                fields(raw, ["node_kind", "canonical_name"], ["identifiers"], path)
                nonempty(raw["canonical_name"], path + "/canonical_name")
                identifiers = raw.get("identifiers", [])
                if not isinstance(identifiers, list):
                    fail("INVALID_ARGUMENT", path + "/identifiers")
                for i, entry in enumerate(identifiers):
                    fields(entry, ["scheme", "value"], [], f"{path}/identifiers/{i}")
                    nonempty(entry["scheme"], path)
                    nonempty(entry["value"], path)
                plan["data"] = {**raw, "identifiers": identifiers}
            elif node_kind == "event":
                fields(raw, ["node_kind", "name", "description", "participants"], ["object", "batch_or_stage"], path)
                nonempty(raw["name"], path + "/name")
                nonempty(raw["description"], path + "/description")
                if not isinstance(raw["participants"], list):
                    fail("INVALID_ARGUMENT", path + "/participants")
                participants = []
                for i, entry in enumerate(raw["participants"]):
                    fields(entry, ["subject", "role"], [], f"{path}/participants/{i}")
                    participants.append({"subject": self._business(entry["subject"], f"{path}/participants/{i}/subject", {"node:subject"}),
                                         "role": nonempty(entry["role"], f"{path}/participants/{i}/role")})
                plan["data"] = {**raw, "participants": participants}
                if "object" in raw:
                    validate_value(raw["object"], self.unit_config, self._value_resolver, path + "/object")
                    if raw["object"] is not None and raw["object"].get("form") not in {"text", "reference"}:
                        fail("INVALID_VALUE", path + "/object")
                if "batch_or_stage" in raw:
                    nonempty(raw["batch_or_stage"], path + "/batch_or_stage")
            elif node_kind == "defined_value":
                fields(raw, ["node_kind", "name", "value"], ["scope"], path)
                nonempty(raw["name"], path + "/name")
                validate_value(raw["value"], self.unit_config, self._value_resolver, path + "/value")
                scope = raw.get("scope", [])
                if not isinstance(scope, list) or "scope" in raw and not scope:
                    fail("INVALID_ARGUMENT", path + "/scope")
                resolved_scope = [self._business(x, f"{path}/scope/{i}") for i, x in enumerate(scope)]
                if len({_json(x) for x in resolved_scope}) != len(resolved_scope):
                    fail("DUPLICATE_ID", path + "/scope", "duplicate scope target")
                plan["data"] = {**raw, "scope": resolved_scope}
            elif node_kind == "external_benchmark":
                fields(raw, ["node_kind", "name", "description"], [], path)
                nonempty(raw["name"], path + "/name")
                nonempty(raw["description"], path + "/description")
                plan["data"] = dict(raw)
            elif node_kind == "contract":
                fields(raw, ["node_kind"], ["name"], path)
                if "name" in raw:
                    nonempty(raw["name"], path + "/name")
                if plan["object_id"] != self.store.info["contract_object_id"]:
                    fail("KIND_CHANGE", path, "only one contract container")
                plan["data"] = dict(raw)
            else:
                fail("INVALID_ARGUMENT", path + "/node_kind")
        elif kind == "relation":
            relation_kind = raw.get("relation_kind")
            if relation_kind == "party":
                fields(raw, ["relation_kind", "unit_id", "parties"], ["modality"], path)
                if not isinstance(raw["parties"], list) or len(raw["parties"]) != 2:
                    fail("INVALID_ARGUMENT", path + "/parties")
                parties = []
                for i, party in enumerate(raw["parties"]):
                    fields(party, ["subject", "nature"], ["functional_labels"], f"{path}/parties/{i}")
                    if not isinstance(party["nature"], str) or party["nature"] not in NATURES:
                        fail("INVALID_VALUE", f"{path}/parties/{i}/nature")
                    labels = party.get("functional_labels", [])
                    if not isinstance(labels, list) or any(not isinstance(label, str) for label in labels) or len(labels) != len(set(labels)):
                        fail("INVALID_VALUE", f"{path}/parties/{i}/functional_labels")
                    for label in labels:
                        nonempty(label, f"{path}/parties/{i}/functional_labels")
                    parties.append({"subject": self._business(party["subject"], f"{path}/parties/{i}/subject", {"node:subject"}),
                                    "nature": party["nature"], "functional_labels": labels})
                if parties[0]["subject"] == parties[1]["subject"]:
                    fail("INVALID_VALUE", path + "/parties", "party endpoints must differ")
                plan["data"] = {**raw, "parties": parties, "modality": raw.get("modality")}
            elif relation_kind == "contract":
                fields(raw, ["relation_kind", "unit_id", "subject"], ["modality"], path)
                subject = self._business(raw["subject"], path + "/subject", {"node:contract"})
                if subject["object_id"] != self.store.info["contract_object_id"]:
                    fail("REFERENCE_TYPE_MISMATCH", path + "/subject")
                plan["data"] = {**raw, "subject": subject, "modality": raw.get("modality")}
            else:
                fail("INVALID_ARGUMENT", path + "/relation_kind")
            if not isinstance(raw["unit_id"], str) or raw["unit_id"] not in self.units:
                fail("REFERENCE_NOT_FOUND", path + "/unit_id", "unit missing")
            if plan["data"]["modality"] is not None and (not isinstance(plan["data"]["modality"], str) or plan["data"]["modality"] not in MODALITIES):
                fail("INVALID_VALUE", path + "/modality")
        elif kind == "detail":
            fields(raw, ["owner", "slot_id", "value"], [], path)
            owner = self._business(raw["owner"], path + "/owner", {"relation"})
            slot = self.slots.get(raw["slot_id"]) if isinstance(raw["slot_id"], str) else None
            if not slot:
                fail("REFERENCE_NOT_FOUND", path + "/slot_id", "slot missing")
            owner_plan = self.by_object.get(owner["object_id"])
            owner_data = owner_plan["data"] if owner_plan and owner_plan["data"] else json.loads(self.store.current(owner["object_id"])["data_json"])
            if self.assignments and not ((owner_data["unit_id"], raw["slot_id"]) in self.assignments or raw["slot_id"] not in {s for _, s in self.assignments}):
                fail("SLOT_NOT_APPLICABLE", path + "/slot_id", "slot is not assigned to relation unit")
            matches_schema(raw["value"], slot["value_schema"], self.unit_config, self._value_resolver, path + "/value")
            plan["data"] = {**raw, "owner": owner}
        elif kind == "reference":
            plan["data"] = self._reference_data(raw, path)
        elif kind == "gap":
            fields(raw, ["clause", "gap_kind", "description", "reported_by"], ["suggested_unit_id", "related_object"], path)
            if not isinstance(raw["gap_kind"], str) or raw["gap_kind"] not in {"unmatched_unit", "missing_slot", "structure_anomaly"}:
                fail("INVALID_VALUE", path + "/gap_kind")
            nonempty(raw["description"], path + "/description")
            nonempty(raw["reported_by"], path + "/reported_by")
            data = {**raw, "clause": self._fixed(raw["clause"], path + "/clause", {"clause"})}
            if "suggested_unit_id" in raw and (not isinstance(raw["suggested_unit_id"], str) or raw["suggested_unit_id"] not in self.units):
                fail("REFERENCE_NOT_FOUND", path + "/suggested_unit_id")
            if "related_object" in raw:
                data["related_object"] = self._fixed(raw["related_object"], path + "/related_object")
            plan["data"] = data
        else:
            fields(raw, ["clause", "reason"], [], path)
            nonempty(raw["reason"], path + "/reason")
            plan["data"] = {**raw, "clause": self._business(raw["clause"], path + "/clause", {"clause"})}

    def _reference_data(self, raw, path):
        kind = raw.get("reference_kind")
        if not isinstance(kind, str) or kind not in REFERENCES:
            fail("INVALID_VALUE", path + "/reference_kind")
        extra = {"appellation": ["label", "scope"], "role": ["label"],
                 "composition": ["label"], "definition": ["term"], "scope": ["exclude"]}.get(kind, [])
        fields(raw, ["reference_kind", "from", "to"] + (["label"] if kind in {"appellation", "role", "composition"} else []) + (["term"] if kind == "definition" else []),
               [x for x in extra if x not in {"label", "term"}], path)
        data = dict(raw)
        def either(ref, at, allowed):
            return (self._business_fixed(ref, at, allowed) if "record_id" in ref or "value_path" in ref else self._target(ref, at, allowed=allowed))[0]
        if kind == "appellation":
            data["from"] = self._fixed(raw["from"], path + "/from", {"clause"})
            data["to"] = self._business(raw["to"], path + "/to", {"node:subject"})
            nonempty(raw["label"], path + "/label")
            if "scope" in raw:
                data["scope"] = self._business(raw["scope"], path + "/scope", {"material", "node:contract"})
        elif kind in {"role", "composition"}:
            data["from"] = self._business(raw["from"], path + "/from", {"node:contract"})
            data["to"] = self._business(raw["to"], path + "/to", {"node:subject"} if kind == "role" else {"material"})
            nonempty(raw["label"], path + "/label")
        elif kind == "definition":
            data["from"] = either(raw["from"], path + "/from", {"relation", "detail", "clause"})
            data["to"] = self._business(raw["to"], path + "/to", {"node:defined_value"})
            nonempty(raw["term"], path + "/term")
        elif kind == "event_of":
            data["from"] = self._business(raw["from"], path + "/from", {"node:event"})
            data["to"] = self._business(raw["to"], path + "/to", {"relation"})
        elif kind == "scope":
            data["from"] = self._business(raw["from"], path + "/from", {"relation", "detail"})
            if not isinstance(raw["to"], list) or not isinstance(raw.get("exclude", []), list):
                fail("INVALID_ARGUMENT", path + "/to")
            allowed = {"relation", "detail", "clause", "node:subject", "node:event", "node:defined_value", "node:external_benchmark", "node:contract"}
            data["to"] = [either(item, f"{path}/to/{i}", allowed) for i, item in enumerate(raw["to"])]
            data["exclude"] = [either(item, f"{path}/exclude/{i}", allowed) for i, item in enumerate(raw.get("exclude", []))]
            if not data["to"] and not data["exclude"] or len({_json(x) for x in data["to"] + data["exclude"]}) != len(data["to"] + data["exclude"]):
                fail("INVALID_VALUE", path, "scope targets must be nonempty and distinct")
        elif kind in {"priority", "amendment"}:
            allowed = {"relation", "detail", "clause"}
            data["from"] = either(raw["from"], path + "/from", allowed)
            data["to"] = either(raw["to"], path + "/to", allowed)
        elif kind == "redirect":
            data["from"], from_target = self._target(raw["from"], path + "/from")
            data["to"], to_target = self._target(raw["to"], path + "/to")
            if not from_target["kind"].startswith("node:") or from_target["kind"] != to_target["kind"] or data["from"] == data["to"]:
                fail("REFERENCE_TYPE_MISMATCH", path, "redirect needs distinct nodes of same kind")
        else:
            data["from"], from_target = self._target(raw["from"], path + "/from")
            data["to"], to_target = self._target(raw["to"], path + "/to")
            if not from_target["kind"].startswith("node:") or not to_target["kind"].startswith("node:") or data["from"] == data["to"]:
                fail("REFERENCE_TYPE_MISMATCH", path, "distinct needs two node targets")
        return data

    def normalize_values(self):
        def walk(node, path):
            if isinstance(node, list):
                return [walk(item, f"{path}/{i}") for i, item in enumerate(node)]
            if not isinstance(node, dict):
                return node
            if node.get("form") == "reference" and "target" in node:
                fixed = "record_id" in node["target"] or "value_path" in node["target"]
                return {"form": "reference", "target": (self._business_fixed(node["target"], path + "/target") if fixed else self._target(node["target"], path + "/target"))[0]}
            if node.get("form") == "time" and node.get("kind") == "relative":
                return {**node, "event": self._business(node["event"], path + "/event", {"node:event"}),
                        "offset": walk(node["offset"], path + "/offset")}
            if node.get("form") == "condition" and node.get("operator") == "event":
                return {**node, "event": self._business(node["event"], path + "/event", {"node:event"})}
            return {key: walk(value, path + "/" + key) for key, value in node.items()}
        for plan in self.plans:
            if plan["status"] == "withdrawn":
                continue
            data = plan["data"]
            if plan["kind"] == "detail":
                data["value"] = walk(data["value"], plan["path"] + "/data/value")
            elif plan["kind"] == "node" and data["node_kind"] in {"defined_value", "event"}:
                for key in ("value", "object"):
                    if key in data:
                        data[key] = walk(data[key], plan["path"] + "/data/" + key)

    def validate_evidence(self):
        by_record = {plan["record_id"]: plan for plan in self.plans}
        def sources_for(record_id):
            plan = by_record.get(record_id)
            if plan:
                return plan["evidence"]
            return [{"path": row["path"], "source": json.loads(row["source_json"])}
                    for row in self.store.db.execute("SELECT * FROM assertion_sources WHERE record_id=?", (record_id,))]
        def roots(record_id, stack):
            if record_id in stack:
                fail("SOURCE_CYCLE", "", "circular source premises")
            plan = by_record.get(record_id)
            kind = plan["kind"] if plan else self.store.record(record_id)["kind"]
            if kind == "anchor":
                return {record_id}
            evidence = sources_for(record_id)
            if not evidence:
                fail("MISSING_SOURCE", "", "premise has no source")
            found = set()
            for entry in evidence:
                source = entry["source"]
                if source["level"] in {1, 2}:
                    found.update(item["record_id"] for item in source["anchors"])
                else:
                    for item in source["premises"]:
                        found.update(roots(item["record_id"], stack | {record_id}))
            return found
        for plan in self.plans:
            path = plan["path"] + "/evidence"
            raw = plan["raw"]["evidence"]
            if not isinstance(raw, list):
                fail("INVALID_ARGUMENT", path, "expected array")
            if plan["kind"] == "anchor" and raw:
                fail("INVALID_ARGUMENT", path, "anchor cannot have evidence")
            normalized = []
            seen = set()
            for i, item in enumerate(raw):
                p = f"{path}/{i}"
                fields(item, ["path", "source"], [], p)
                pointer = item["path"]
                pointer_get(plan["data"], pointer)
                if pointer in seen:
                    fail("DUPLICATE_ID", p + "/path", "duplicate evidence path")
                seen.add(pointer)
                source = item["source"]
                level = source.get("level") if isinstance(source, dict) else None
                if type(level) is not int:
                    fail("INVALID_ARGUMENT", p + "/source/level", "source level must be an integer")
                if level == 1:
                    fields(source, ["level", "anchors"], [], p + "/source")
                elif level == 2:
                    fields(source, ["level", "anchors", "surface", "format_contract", "format_parameters"], [], p + "/source")
                elif level == 3:
                    fields(source, ["level", "premises", "explanation", "asserted_by"], [], p + "/source")
                else:
                    fail("INVALID_ARGUMENT", p + "/source/level", "source level must be 1, 2 or 3")
                source = dict(source)
                if level in {1, 2}:
                    if not isinstance(source["anchors"], list) or not source["anchors"]:
                        fail("MISSING_SOURCE", p + "/source/anchors")
                    source["anchors"] = [self._fixed(ref, f"{p}/source/anchors/{j}", {"anchor"})
                                         for j, ref in enumerate(source["anchors"])]
                    if level == 2:
                        quotes = []
                        for ref in source["anchors"]:
                            anchor_plan = by_record.get(ref["record_id"])
                            data = anchor_plan["data"] if anchor_plan else json.loads(self.store.record(ref["record_id"])["data_json"])
                            quotes.append(data["quote"])
                        target = pointer_get(plan["data"], pointer)
                        if not any(source["surface"] in quote for quote in quotes):
                            fail("ROUNDTRIP_FAILED", p + "/source/surface", "surface absent from anchors")
                        check_contract(target, source, next(quote for quote in quotes if source["surface"] in quote), p + "/source")
                else:
                    if not isinstance(source["premises"], list) or not source["premises"]:
                        fail("MISSING_SOURCE", p + "/source/premises")
                    nonempty(source["explanation"], p + "/source/explanation")
                    nonempty(source["asserted_by"], p + "/source/asserted_by")
                    source["premises"] = [self._fixed(ref, f"{p}/source/premises/{j}") for j, ref in enumerate(source["premises"])]
                    for ref in source["premises"]:
                        kind = by_record[ref["record_id"]]["kind"] if ref["record_id"] in by_record else self.store.record(ref["record_id"])["kind"]
                        if kind in {"material", "text_version"} or ref["record_id"] == self.store.current(self.store.info["contract_object_id"])["record_id"]:
                            fail("MISSING_SOURCE", p + "/source/premises", "invalid premise")
                normalized.append({"path": pointer, "source": source})
            plan["evidence"] = sorted(normalized, key=lambda e: e["path"])
        for plan in self.plans:
            if plan["kind"] in {"anchor", "clause"} and plan["data"].get("classification") == "unclassified":
                continue
            if plan["kind"] == "node" and plan["data"] == {"node_kind": "contract"}:
                continue
            if plan["kind"] not in {"anchor"} and not plan["evidence"]:
                fail("MISSING_SOURCE", plan["path"] + "/evidence", "record has no source")
            paths = [entry["path"] for entry in plan["evidence"]]
            for required in self._required_source_paths(plan):
                if not any(path == "" or required == path or required.startswith(path + "/") for path in paths):
                    fail("MISSING_SOURCE", plan["path"] + "/data" + required, "assertion field lacks source")
            for entry in plan["evidence"]:
                source = entry["source"]
                if source["level"] == 3:
                    for ref in source["premises"]:
                        roots(ref["record_id"], {plan["record_id"]})

    def _required_source_paths(self, plan):
        data, kind = plan["data"], plan["kind"]
        if kind == "anchor":
            return []
        if kind == "clause":
            return (["/classification"] if data["classification"] != "unclassified" else []) + (["/tags"] if data["tags"] else [])
        if kind == "node":
            node_kind = data["node_kind"]
            if node_kind == "contract":
                return ["/name"] if "name" in data else []
            if node_kind == "subject":
                return ["/canonical_name"] + [f"/identifiers/{i}/{field}" for i in range(len(data["identifiers"])) for field in ("scheme", "value")]
            if node_kind == "event":
                return ["/name", "/description"] + [f"/participants/{i}/{field}" for i in range(len(data["participants"])) for field in ("subject", "role")] + ["/" + key for key in ("object", "batch_or_stage") if key in data]
            if node_kind == "defined_value":
                return ["/name", "/value"] + [f"/scope/{i}" for i in range(len(data["scope"]))]
            return ["/name", "/description"]
        if kind == "relation":
            return ["/unit_id"] + ([f"/parties/{i}/{field}" for i in range(2) for field in ("subject", "nature")] + [f"/parties/{i}/functional_labels/{j}" for i, party in enumerate(data["parties"]) for j in range(len(party["functional_labels"]))] if data["relation_kind"] == "party" else ["/subject"]) + (["/modality"] if data["modality"] is not None else [])
        if kind == "detail":
            return ["/owner", "/slot_id", "/value"]
        if kind == "reference":
            return ["/from", "/to"] + ["/" + key for key in ("label", "term", "scope", "exclude") if key in data and data[key] not in ([], None)]
        if kind == "gap":
            return ["/clause", "/gap_kind", "/description"] + ["/" + key for key in ("suggested_unit_id", "related_object") if key in data]
        return ["/clause", "/reason"]

    def anchor_clause(self, anchor_record_id):
        plan = next((p for p in self.plans if p["record_id"] == anchor_record_id), None)
        data = plan["data"] if plan else json.loads(self.store.record(anchor_record_id)["data_json"])
        clause_record = data["clause"]["record_id"]
        clause_plan = next((p for p in self.plans if p["record_id"] == clause_record), None)
        clause_id = clause_plan["object_id"] if clause_plan else self.store.record(clause_record)["object_id"]
        return clause_id, clause_record

    def evidence_clauses(self, plan):
        found = set()
        visited = set()
        def walk(record_id):
            if record_id in visited:
                return
            visited.add(record_id)
            inner = next((p for p in self.plans if p["record_id"] == record_id), None)
            stored = None if inner else self.store.record(record_id)
            if (inner and inner["kind"] == "anchor") or (stored and stored["kind"] == "anchor"):
                found.add(self.anchor_clause(record_id))
                return
            rows = inner["evidence"] if inner else [{"source": json.loads(row[0])} for row in self.store.db.execute("SELECT source_json FROM assertion_sources WHERE record_id=?", (record_id,))]
            for entry in rows:
                source = entry["source"]
                if source["level"] in {1, 2}:
                    for ref in source["anchors"]:
                        found.add(self.anchor_clause(ref["record_id"]))
                else:
                    for ref in source["premises"]:
                        walk(ref["record_id"])
        walk(plan["record_id"])
        return found

    def validate_coverage(self):
        covered = []
        for i, item in enumerate(self.document["covered_clauses"]):
            path = f"/covered_clauses/{i}"
            fields(item, ["object_id", "record_id"], [], path)
            object_id = uuid_value(item["object_id"], path + "/object_id")
            record_id = uuid_value(item["record_id"], path + "/record_id")
            row = self.store.record(record_id)
            if row is None or row["kind"] != "clause" or row["object_id"] != object_id:
                fail("COVERAGE_INVALID", path, "clause version mismatch")
            current_plan = self.by_object.get(object_id)
            current = current_plan["data"] if current_plan else json.loads(self.store.current(object_id)["data_json"])
            prior = json.loads(row["data_json"])
            for field in ("text_version", "sequence", "text", "start_offset", "end_offset", "original_number"):
                if current.get(field) != prior.get(field):
                    fail("COVERAGE_INVALID", path, "clause text identity changed")
            if current["classification"] == "unclassified":
                fail("UNCLASSIFIED_CLAUSE", path, "clause is unclassified")
            if object_id in covered:
                fail("COVERAGE_INVALID", path, "duplicate covered clause")
            covered.append(object_id)
            matching = [p for p in self.plans if p["kind"] in {"node", "relation", "detail", "reference", "gap", "no_content"}
                        and p["status"] == "active" and any(clause_id == object_id for clause_id, _ in self.evidence_clauses(p))]
            if not matching:
                fail("COVERAGE_INVALID", path, "no modeled content in this submission")
            prior_gap = any(json.loads(row["data_json"]).get("gap_kind") == "unmatched_unit" and
                            self.store.record(json.loads(row["data_json"])["clause"]["record_id"])["object_id"] == object_id
                            for row in self.store.db.execute("SELECT r.data_json FROM active_records r JOIN objects o USING(object_id) WHERE o.kind='gap'"))
            prior_no_content = any(json.loads(row["data_json"])["clause"]["object_id"] == object_id
                                   for row in self.store.db.execute("SELECT r.data_json FROM active_records r JOIN objects o USING(object_id) WHERE o.kind='no_content'"))
            if current["classification"] == "unmatched" and not (prior_gap or any(p["kind"] == "gap" and p["data"]["gap_kind"] == "unmatched_unit" for p in matching)):
                fail("COVERAGE_INVALID", path, "unmatched clause needs gap")
            if current["classification"] == "no_content" and not (prior_no_content or any(p["kind"] == "no_content" for p in matching)):
                fail("COVERAGE_INVALID", path, "no-content clause needs record")
        return covered

    def validate_appellations(self):
        for plan in self.plans:
            if plan["kind"] != "reference" or plan["status"] != "active" or plan["data"].get("reference_kind") != "appellation":
                continue
            data = plan["data"]
            clause_record = data["from"]["record_id"]
            clause_plan = next((p for p in self.plans if p["record_id"] == clause_record), None)
            clause_row = None if clause_plan else self.store.record(clause_record)
            clause_data = clause_plan["data"] if clause_plan else json.loads(clause_row["data_json"])
            clause_id = clause_plan["object_id"] if clause_plan else clause_row["object_id"]
            if data["label"] not in clause_data["text"] or not any(cid == clause_id for cid, _ in self.evidence_clauses(plan)):
                fail("APPELLATION_INVALID", plan["path"] + "/data/label", "label or occurrence source missing")

    def check_dependencies(self):
        def object_refs(value):
            if isinstance(value, dict):
                if set(value) == {"object_id"}:
                    yield value["object_id"]
                else:
                    for item in value.values():
                        yield from object_refs(item)
            elif isinstance(value, list):
                for item in value:
                    yield from object_refs(item)
        active = {row["object_id"]: json.loads(row["data_json"]) for row in self.store.db.execute("SELECT * FROM active_records")}
        kinds = {row["object_id"]: row["kind"] for row in self.store.db.execute("SELECT object_id,kind FROM objects")}
        for plan in self.plans:
            if plan["status"] == "withdrawn":
                active.pop(plan["object_id"], None)
            else:
                active[plan["object_id"]] = plan["data"]
                kinds[plan["object_id"]] = plan["kind"]
        for object_id, data in active.items():
            for target in object_refs(data):
                if target not in active:
                    fail("WITHDRAWN_TARGET", "", "active record depends on withdrawn target", target_object_id=target)
            def fixed_business_refs(value):
                if isinstance(value, dict):
                    if value.get("form") == "reference" and isinstance(value.get("target"), dict) and "record_id" in value["target"]:
                        yield value["target"]["record_id"]
                    for child in value.values():
                        yield from fixed_business_refs(child)
                elif isinstance(value, list):
                    for child in value:
                        yield from fixed_business_refs(child)
            fixed = list(fixed_business_refs(data))
            if kinds.get(object_id) == "reference" and data.get("reference_kind") in {"scope", "priority", "amendment", "definition"}:
                def refs(node):
                    if isinstance(node, dict):
                        if "record_id" in node:
                            yield node["record_id"]
                        else:
                            for child in node.values():
                                yield from refs(child)
                    elif isinstance(node, list):
                        for child in node:
                            yield from refs(child)
                fixed.extend(refs(data.get("to")))
                fixed.extend(refs(data.get("exclude", [])))
                if data.get("reference_kind") != "definition" or not (isinstance(data.get("from"), dict) and "record_id" in data["from"]):
                    fixed.extend(refs(data.get("from")))
            for target_record in fixed:
                row = self.store.record(target_record)
                plan = next((p for p in self.plans if p["record_id"] == target_record), None)
                target_object = plan["object_id"] if plan else row["object_id"] if row else None
                if target_object not in active:
                    fail("WITHDRAWN_TARGET", "", "fixed business target is withdrawn", target_record_id=target_record)
        assigned_slots = {slot for _, slot in self.assignments}
        clause_addresses = set()
        for object_id, data in active.items():
            if kinds.get(object_id) == "clause":
                key = (data["text_version"]["object_id"], data["sequence"])
                if key in clause_addresses:
                    fail("INVALID_VALUE", "", "current clauses share an address", target_object_id=object_id)
                clause_addresses.add(key)
            elif kinds.get(object_id) == "detail":
                owner = active.get(data["owner"]["object_id"])
                if owner is None:
                    fail("WITHDRAWN_TARGET", "", "detail owner withdrawn", target_object_id=data["owner"]["object_id"])
                slot = data["slot_id"]
                if slot in assigned_slots and (owner["unit_id"], slot) not in self.assignments:
                    fail("SLOT_NOT_APPLICABLE", "", "existing detail slot does not fit revised relation", target_object_id=object_id)

    def validate_redirects(self):
        edges = {}
        for row in self.store.db.execute("SELECT r.object_id,r.data_json FROM active_records r JOIN objects o USING(object_id) WHERE o.kind='reference'"):
            if row["object_id"] in self.by_object:
                continue
            data = json.loads(row["data_json"])
            if data.get("reference_kind") == "redirect":
                edges.setdefault(data["from"]["object_id"], set()).add(data["to"]["object_id"])
        for plan in self.plans:
            if plan["kind"] == "reference" and plan["status"] == "active" and plan["data"]["reference_kind"] == "redirect":
                edges.setdefault(plan["data"]["from"]["object_id"], set()).add(plan["data"]["to"]["object_id"])
        def visit(node, stack, done):
            if node in stack:
                fail("REDIRECT_CYCLE", "", "redirect cycle")
            if node in done:
                return
            for target in edges.get(node, ()):
                visit(target, stack | {node}, done)
            done.add(node)
        done = set()
        for node in edges:
            visit(node, set(), done)

    def validate_value_cycles(self):
        by_record = {p["record_id"]: p for p in self.plans}
        def get_data(record_id):
            plan = by_record.get(record_id)
            if plan:
                return plan["data"], plan["kind"]
            row = self.store.record(record_id)
            if not row:
                fail("REFERENCE_NOT_FOUND", "", "value record missing")
            return json.loads(row["data_json"]), row["kind"]
        def targets(value):
            if isinstance(value, dict):
                if value.get("form") == "reference":
                    ref = value["target"]
                    if "record_id" in ref:
                        yield ref["record_id"]
                    else:
                        plan = self.by_object.get(ref["object_id"])
                        row = self.store.current(ref["object_id"])
                        if plan or row:
                            yield plan["record_id"] if plan else row["record_id"]
                else:
                    for item in value.values():
                        yield from targets(item)
            elif isinstance(value, list):
                for item in value:
                    yield from targets(item)
        done = set()
        def visit(record_id, stack):
            if record_id in stack:
                fail("VALUE_CYCLE", "", "value references form a cycle", target_record_id=record_id)
            if record_id in done:
                return
            data, kind = get_data(record_id)
            if kind != "detail" and not (kind == "node" and data.get("node_kind") == "defined_value"):
                done.add(record_id)
                return
            for target in targets(data.get("value")):
                visit(target, stack | {record_id})
            done.add(record_id)
        for plan in self.plans:
            if plan["status"] == "active" and (plan["kind"] == "detail" or plan["kind"] == "node" and plan["data"]["node_kind"] == "defined_value"):
                visit(plan["record_id"], set())

    def persist(self, content_hash, covered):
        submission_id = new_id()
        id_map = {p["local_id"]: {"object_id": p["object_id"], "record_id": p["record_id"], "revision": p["revision"]} for p in self.plans}
        overview_id = new_id() if "overview" in self.document else None
        response = {"ok": True, "submission_id": submission_id, "content_hash": content_hash,
                    "replayed": False, "id_map": id_map, "counts": dict(Counter(p["kind"] for p in self.plans)),
                    "covered_clauses": covered, "issues": self.document["issues"], "overview_id": overview_id}
        self.store.add_submission(self.document["phase"], content_hash, self.document, response, self.document["submitted_by"])
        for plan in self.plans:
            if plan["revision"] == 1:
                self.store.db.execute("INSERT INTO objects VALUES(?,?,?)", (plan["object_id"], plan["kind"], submission_id))
        for plan in self.plans:
            self.store.db.execute("INSERT INTO record_versions VALUES(?,?,?,?,?,?,?,?)",
                                  (plan["record_id"], plan["object_id"], plan["revision"], plan["previous"],
                                   submission_id, plan["status"], plan["reason"], _json(plan["data"])))
        typed_order = {"clause": 0, "anchor": 1, "node": 2, "relation": 3,
                       "detail": 4, "reference": 5, "gap": 6, "no_content": 7}
        for plan in sorted(self.plans, key=lambda item: typed_order[item["kind"]]):
            for entry in plan["evidence"]:
                self.store.db.execute("INSERT INTO assertion_sources VALUES(?,?,?,?)",
                                      (plan["record_id"], entry["path"], entry["source"]["level"], _json(entry["source"])))
            self._typed(plan)
        for plan in self.plans:
            self._links(plan)
        if overview_id:
            overview = self.document["overview"]
            versions = [self._business(ref, f"/overview/text_versions/{i}", {"text_version"}) for i, ref in enumerate(overview["text_versions"])]
            if len({_json(v) for v in versions}) != len(versions):
                fail("DUPLICATE_ID", "/overview/text_versions")
            self.store.db.execute("INSERT INTO case_overviews VALUES(?,?,?,?,?)",
                                  (overview_id, submission_id, _json(versions), overview["body"], overview["authored_by"]))
        for item in self.document["covered_clauses"]:
            self.store.db.execute("INSERT INTO extraction_completions VALUES(?,?,?)",
                                  (submission_id, item["object_id"], item["record_id"]))
        return response

    def _typed(self, plan):
        data, record, kind = plan["data"], plan["record_id"], plan["kind"]
        if kind == "clause":
            table, values = "clauses", dict(record_id=record, text_version_id=data["text_version"]["object_id"],
                                            sequence=data["sequence"], original_number=data["original_number"],
                                            text=data["text"], start_offset=data["start_offset"], end_offset=data["end_offset"],
                                            tags_json=_json(data["tags"]), classification=data["classification"])
        elif kind == "anchor":
            if "anchor_start" not in plan:
                old = self.store.record(plan["previous"])
                previous = self.store.db.execute("SELECT start_offset,end_offset FROM anchors WHERE record_id=?", (old["record_id"],)).fetchone()
                plan["anchor_start"], plan["anchor_end"] = previous
            table, values = "anchors", dict(record_id=record, clause_record_id=data["clause"]["record_id"],
                                            quote=data["quote"], occurrence=data["occurrence"],
                                            start_offset=plan["anchor_start"], end_offset=plan["anchor_end"])
        elif kind == "node":
            table, values = "nodes", dict(record_id=record, node_kind=data["node_kind"],
                                          name=data.get("canonical_name", data.get("name")))
        elif kind == "relation":
            parties = data.get("parties", [])
            table, values = "relations", dict(record_id=record, relation_kind=data["relation_kind"], unit_id=data["unit_id"],
                                               party_0_id=parties[0]["subject"]["object_id"] if parties else None,
                                               party_1_id=parties[1]["subject"]["object_id"] if parties else None,
                                               contract_id=data["subject"]["object_id"] if not parties else None,
                                               modality=data["modality"])
        elif kind == "detail":
            table, values = "details", dict(record_id=record, owner_id=data["owner"]["object_id"],
                                             slot_id=data["slot_id"], value_json=_json(data["value"]))
        elif kind == "reference":
            table, values = "references_data", dict(record_id=record, reference_kind=data["reference_kind"],
                                                     from_json=_json(data["from"]), to_json=_json(data["to"]))
        elif kind == "gap":
            table, values = "gaps", dict(record_id=record, clause_record_id=data["clause"]["record_id"],
                                          gap_kind=data["gap_kind"], description=data["description"], reported_by=data["reported_by"])
        else:
            table, values = "no_content_records", dict(record_id=record, clause_id=data["clause"]["object_id"], reason=data["reason"])
        self.store.db.execute(f"INSERT INTO {table} ({','.join(values)}) VALUES ({','.join('?' for _ in values)})", tuple(values.values()))

    def _links(self, plan):
        def walk(value, path):
            if isinstance(value, dict):
                if "object_id" in value and set(value) == {"object_id"}:
                    self.store.db.execute("INSERT OR IGNORE INTO record_links VALUES(?,?,?,NULL)", (plan["record_id"], path, value["object_id"]))
                elif "record_id" in value and set(value) <= {"record_id", "value_path"}:
                    self.store.db.execute("INSERT OR IGNORE INTO record_links VALUES(?,?,NULL,?)", (plan["record_id"], path, value["record_id"]))
                else:
                    for key, item in value.items():
                        walk(item, path + "/" + str(key).replace("~", "~0").replace("/", "~1"))
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    walk(item, f"{path}/{i}")
        walk(plan["data"], "/data")
        walk(plan["evidence"], "/evidence")


def write(db_path, document):
    store = CaseStore(db_path)
    try:
        store.begin()
        content_hash = hash_json(document)
        if receipt := store.replay(content_hash):
            store.db.rollback()
            return receipt
        writer = ModelWriter(store, document)
        writer.prepare()
        writer.validate_data()
        writer.normalize_values()
        writer.validate_evidence()
        writer.validate_appellations()
        covered = writer.validate_coverage()
        writer.check_dependencies()
        writer.validate_redirects()
        writer.validate_value_cycles()
        response = writer.persist(content_hash, covered)
        store.db.commit()
        return response
    except Exception:
        store.db.rollback()
        raise
    finally:
        store.close()
