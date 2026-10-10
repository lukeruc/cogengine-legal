"""Acceptance of optional file helpers and independent formal write checks."""

from __future__ import annotations

import copy
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from legal.formats import Invalid, InvalidBatch, new_id
from legal.reader_helpers import (CHECKED, DEFERRED, FileChecksFailed,
                                  build_submission_files, find_quote_files, main)
from legal.model import write
from legal.query import query
from legal.storage import initialize, register, split


class TaskFileHelpers(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="reader helpers 中文-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case, self.clause, self.record, self.text_version = [new_id() for _ in range(4)]
        self.header = {"format_version": 1, "case_id": self.case, "vocabulary_hash": "a" * 64,
                       "submitted_by": "reader", "phase": "preparation", "covered_clauses": [], "issues": []}
        self.header_file = self.put("header.json", self.header)
        self.snapshot("甲😀e\u0301\r\naaaa\n甲应付款。")
        self.output = self.root / "new output.json"

    def put(self, name, value):
        file = self.root / name
        file.write_bytes((json.dumps(value, ensure_ascii=False) + "\n").encode("utf-8"))
        return file

    def snapshot(self, text):
        self.snapshot_doc = {"case_id": self.case, "checked_sequence": 7, "items": [{
            "object_id": self.clause, "record_id": self.record, "kind": "clause",
            "data": {"text_version": {"object_id": self.text_version}, "sequence": 1, "text": text,
                     "start_offset": 40, "end_offset": 40 + len(text), "tags": [], "classification": "unclassified"},
            "evidence": [], "provenance": {}}]}
        self.clauses_file = self.put("clauses.json", self.snapshot_doc)

    def quote(self, quote, **extra):
        return {"local_id": "a", "clause_record_id": self.record, "quote": quote, **extra}

    def find(self, requests):
        return find_quote_files(self.clauses_file, self.put("requests.json", requests), self.output)

    def record_input(self, identifier="r", kind="node", data=None, **extra):
        return {"local_id": identifier, "kind": kind, "data": data if data is not None else {"node_kind": "subject", "canonical_name": "甲"},
                "evidence": [], **extra}

    def build(self, *arrays, header=None):
        if header is not None:
            self.put("header.json", header)
        files = [self.put(f"records-{i}.json", array) for i, array in enumerate(arrays)]
        return build_submission_files(self.header_file, files, self.output)

    def assert_error(self, code, function, *args):
        with self.assertRaises((Invalid, FileChecksFailed)) as caught:
            function(*args)
        exc = caught.exception
        items = [exc.item()] if isinstance(exc, Invalid) else exc.errors
        self.assertIn(code, [item["code"] for item in items], items)
        self.assertFalse(self.output.exists())
        return items

    def test_unique_quote_preserves_unicode_and_crlf(self):
        quote = "😀e\u0301\r\n"
        result = self.find([self.quote(quote)])
        self.assertEqual(result["scope"], "task_files")
        self.assertEqual(result["checked_sequence"], 7)
        self.assertEqual((result["matches"][0]["start_offset"], result["matches"][0]["end_offset"]), (1, 6))
        anchor = json.loads(self.output.read_bytes())[0]
        self.assertEqual(anchor, {"local_id": "a", "kind": "anchor", "data": {
            "clause": {"record_id": self.record}, "quote": quote, "occurrence": 1}, "evidence": []})

    def test_overlap_selection(self):
        self.snapshot("aaaa")
        result = self.find([self.quote("aa", occurrence=2)])
        self.assertEqual((result["matches"][0]["start_offset"], result["matches"][0]["end_offset"]), (1, 3))

    def test_ambiguous_candidates(self):
        self.snapshot("aaaa")
        errors = self.assert_error("ANCHOR_AMBIGUOUS", self.find, [self.quote("aa")])
        self.assertEqual(errors[0]["match_count"], 3)
        self.assertEqual([item["start_offset"] for item in errors[0]["candidates"]], [0, 1, 2])

    def test_candidates_truncated_but_late_occurrence_selectable(self):
        self.snapshot("a" * 150)
        errors = self.assert_error("ANCHOR_AMBIGUOUS", self.find, [self.quote("a")])
        self.assertEqual(errors[0]["match_count"], 150)
        self.assertEqual(len(errors[0]["candidates"]), 100)
        self.assertTrue(errors[0]["candidates_truncated"])
        self.assertEqual(self.find([self.quote("a", occurrence=150)])["matches"][0]["start_offset"], 149)

    def test_occurrence_errors(self):
        for occurrence in (0, -1, True, "1", 4, None):
            with self.subTest(occurrence=occurrence):
                self.assert_error("ANCHOR_OCCURRENCE", self.find, [self.quote("aa", occurrence=occurrence)])

    def test_unique_out_of_range(self):
        self.assert_error("ANCHOR_OCCURRENCE", self.find, [self.quote("甲应付款。", occurrence=2)])

    def test_no_normalization_or_whitespace_repair(self):
        for quote in ("é", "😀e\u0301\n", "甲 应付款。", "甲应付款。..."):
            with self.subTest(quote=quote):
                self.assert_error("ANCHOR_NOT_FOUND", self.find, [self.quote(quote)])

    def test_whitespace_quote_is_not_stripped(self):
        self.snapshot("a  b")
        self.find([self.quote("  ")])
        self.assertEqual(json.loads(self.output.read_bytes())[0]["data"]["quote"], "  ")

    def test_unknown_version_is_input_scoped_and_atomic(self):
        errors = self.assert_error("REFERENCE_NOT_FOUND", self.find,
                                   [self.quote("甲应付款。"), self.quote("甲", local_id="b", clause_record_id=new_id())])
        self.assertIn("input snapshot", errors[0]["message"])

    def test_conflicting_snapshot_versions(self):
        conflicting = copy.deepcopy(self.snapshot_doc["items"][0])
        conflicting["data"]["text"] = conflicting["data"]["text"].replace("甲", "乙")
        self.snapshot_doc["items"].append(conflicting)
        self.put("clauses.json", self.snapshot_doc)
        self.assert_error("INVALID_ARGUMENT", self.find, [self.quote("甲")])

    def test_duplicate_request_local_id(self):
        self.assert_error("DUPLICATE_LOCAL_ID", self.find, [self.quote("甲应付款。"), self.quote("aa", occurrence=1)])

    def test_multiple_arrays_forward_references_and_content_preserved(self):
        forward = self.record_input("d", "detail", {"owner": {"local_id": "r"}, "slot_id": new_id(),
                                  "value": {"form": "text", "surface": "local_id 和其他普通原文", "normalized": "原文"}})
        relation = self.record_input("r", "relation", {"relation_kind": "contract", "unit_id": new_id(), "subject": {"object_id": new_id()}})
        self.build([forward], [relation])
        document = json.loads(self.output.read_bytes())
        self.assertEqual(document, {**self.header, "records": [forward, relation]})
        self.assertNotIn("modality", document["records"][1]["data"])

    def test_duplicate_local_ids(self):
        self.assert_error("DUPLICATE_LOCAL_ID", self.build, [self.record_input()], [self.record_input()])

    def test_duplicate_revised_objects(self):
        revision = self.record_input(object_id=new_id(), previous_record_id=new_id())
        other = {**revision, "local_id": "r2"}
        self.assert_error("DUPLICATE_ID", self.build, [revision, other])

    def test_missing_local_target(self):
        record = self.record_input("d", "detail", {"owner": {"local_id": "missing"}, "slot_id": new_id(), "value": None})
        self.assert_error("REFERENCE_NOT_FOUND", self.build, [record])

    def test_value_reference_positions(self):
        missing = {"local_id": "missing"}
        ref = {"form": "reference", "target": missing}
        condition = {"form": "condition", "operator": "event", "event": missing}
        values = [ref, {"form": "time", "kind": "relative", "event": missing},
                  {"form": "time", "kind": "interval", "start": ref},
                  condition, {"form": "condition", "operator": "all", "operands": [condition]},
                  {"form": "condition", "operator": "any", "operands": [condition]},
                  {"form": "condition", "operator": "not", "operand": condition},
                  {"form": "condition", "operator": "compare", "left": ref},
                  {"form": "condition", "operator": "count", "condition": condition},
                  {"form": "formula", "operands": [ref]},
                  {"type": "object", "fields": {"a/b": ref}}, {"type": "list", "items": [ref]}]
        for value in values:
            with self.subTest(value=value):
                self.assert_error("REFERENCE_NOT_FOUND", self.build, [self.record_input("d", "detail", {"value": value})])

    def test_all_defined_record_and_evidence_reference_positions(self):
        missing = {"local_id": "missing"}
        examples = [("clause", {"text_version": missing}), ("anchor", {"clause": missing}),
                    ("node", {"node_kind": "event", "participants": [{"subject": missing}]}),
                    ("node", {"node_kind": "defined_value", "scope": [missing]}),
                    ("relation", {"relation_kind": "party", "parties": [{"subject": missing}]}),
                    ("relation", {"relation_kind": "contract", "subject": missing}),
                    ("gap", {"related_object": missing}), ("gap", {"clause": missing}),
                    ("no_content", {"clause": missing})]
        for reference_kind in ("appellation", "role", "composition", "definition", "event_of", "scope", "priority", "amendment", "redirect", "distinct"):
            examples.append(("reference", {"reference_kind": reference_kind, "from": missing}))
            examples.append(("reference", {"reference_kind": reference_kind, "to": [missing] if reference_kind == "scope" else missing}))
        examples.extend([("reference", {"reference_kind": "scope", "exclude": [missing]}),
                         ("reference", {"reference_kind": "appellation", "scope": missing})])
        for kind, data in examples:
            with self.subTest(kind=kind, data=data):
                self.assert_error("REFERENCE_NOT_FOUND", self.build, [self.record_input(kind=kind, data=data)])
        for level, field in ((1, "anchors"), (2, "anchors"), (3, "premises")):
            record = self.record_input(evidence=[{"path": "", "source": {"level": level, field: [missing]}}])
            self.assert_error("REFERENCE_NOT_FOUND", self.build, [record])

    def test_unknown_structures_and_ordinary_local_id_keys_are_deferred(self):
        unknown = self.record_input(data={"node_kind": "future", "local_id": "missing", "nested": {"local_id": "missing"}})
        text = self.record_input("d", "detail", {"value": {"form": "text", "surface": "local_id=missing", "local_id": "missing"}})
        object_value = self.record_input("e", "detail", {"value": {"type": "object", "fields": {"local_id": {"form": "text", "surface": "missing"}}}})
        result = self.build([unknown, text, object_value])
        self.assertEqual(result["checked"], CHECKED)
        self.assertEqual(result["deferred_checks"], DEFERRED)

    def test_missing_fields_not_defaulted(self):
        for field in ("issues", "covered_clauses", "phase", "submitted_by"):
            with self.subTest(field=field):
                header = {key: value for key, value in self.header.items() if key != field}
                self.put("header.json", header)
                self.assert_error("INVALID_ARGUMENT", self.build, [])

    def test_header_cannot_include_records_or_unknown_fields(self):
        for key in ("records", "extra"):
            self.put("header.json", {**self.header, key: []})
            self.assert_error("UNKNOWN_FIELD", self.build, [])

    def test_envelope_phase_and_coverage_constraints(self):
        ref = {"object_id": new_id(), "record_id": new_id()}
        for header, code in (({**self.header, "phase": "other"}, "INVALID_ARGUMENT"),
                             ({**self.header, "phase": "extraction"}, "COVERAGE_INVALID"),
                             ({**self.header, "covered_clauses": [ref]}, "COVERAGE_INVALID"),
                             ({**self.header, "phase": "extraction", "covered_clauses": [ref, ref]}, "COVERAGE_INVALID"),
                             ({**self.header, "phase": "tagging", "overview": {}}, "INVALID_ARGUMENT"),
                             ({**self.header, "format_version": True}, "UNSUPPORTED_VERSION"),
                             ({**self.header, "vocabulary_hash": "bad"}, "INVALID_ARGUMENT")):
            with self.subTest(header=header):
                self.put("header.json", header)
                self.assert_error(code, self.build, [])

    def test_overview_shapes_uniqueness_and_local_targets(self):
        overview = {"body": "概要", "authored_by": "reader", "text_versions": [{"local_id": "missing"}]}
        self.put("header.json", {**self.header, "overview": overview})
        self.assert_error("REFERENCE_NOT_FOUND", self.build, [])
        overview["text_versions"] = [{"object_id": self.text_version}] * 2
        self.put("header.json", {**self.header, "overview": overview})
        self.assert_error("DUPLICATE_ID", self.build, [])

    def test_outer_record_and_withdrawal_rules(self):
        cases = [(self.record_input(kind="material"), "INVALID_ARGUMENT"),
                 (self.record_input(data=[]), "INVALID_ARGUMENT"),
                 (self.record_input(evidence={}), "INVALID_ARGUMENT"),
                 (self.record_input(object_id=new_id()), "INVALID_ARGUMENT"),
                 (self.record_input(status="withdrawn"), "INVALID_ARGUMENT"),
                 (self.record_input(withdrawal_reason="why"), "UNKNOWN_FIELD"),
                 (self.record_input(status="withdrawn", object_id=new_id(), previous_record_id=new_id()), "INVALID_ARGUMENT")]
        for record, code in cases:
            with self.subTest(record=record):
                self.assert_error(code, self.build, [record])

    def test_explicit_null_and_revision_are_preserved(self):
        record = self.record_input("d", "detail", {"value": None}, object_id=new_id(), previous_record_id=new_id())
        self.build([record])
        self.assertEqual(json.loads(self.output.read_bytes())["records"], [record])

    def test_strict_json_and_array_shape(self):
        records_file = self.root / "array.json"
        for data in (b'{"x":1,"x":2}', b'[NaN]', b'[Infinity]', b'\xff', b'\xef\xbb\xbf[]', b'[1e999]'):
            with self.subTest(data=data):
                records_file.write_bytes(data)
                self.assert_error("INVALID_JSON", build_submission_files, self.header_file, [records_file], self.output)
        for obj in (None, {}, "text"):
            self.put("array.json", obj)
            self.assert_error("INVALID_ARGUMENT", build_submission_files, self.header_file, [records_file], self.output)

    def test_duplicate_paths_after_normalization(self):
        file = self.put("r.json", [])
        alias = self.root / "alias.json"
        alias.symlink_to(file)
        self.assert_error("INVALID_ARGUMENT", build_submission_files, self.header_file, [file, alias], self.output)

    def test_existing_output_and_inputs_preserved(self):
        file = self.put("r.json", [self.record_input()])
        before = {path: path.read_bytes() for path in (file, self.header_file, self.clauses_file)}
        self.output.write_bytes(b"existing")
        with self.assertRaises(Invalid) as caught:
            build_submission_files(self.header_file, [file], self.output)
        self.assertEqual(caught.exception.code, "FILE_EXISTS")
        self.assertEqual(self.output.read_bytes(), b"existing")
        self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_write_failure_removes_partial_file_and_keeps_inputs(self):
        file = self.put("r.json", [])
        before = {p: p.read_bytes() for p in (file, self.header_file)}
        with patch("legal.formats.os.fsync", side_effect=OSError("simulated disk failure")):
            self.assert_error("FILE_ERROR", build_submission_files, self.header_file, [file], self.output)
        self.assertEqual({p: p.read_bytes() for p in before}, before)

    def test_errors_are_capped_and_in_array_order(self):
        file = self.put("bad.json", [self.record_input(str(i), "detail", {"owner": {"local_id": "missing"}}) for i in range(105)])
        output = io.StringIO()
        with redirect_stdout(output):
            code = main("build_submission", ["--header", str(self.header_file), "--records", str(file), "--output", str(self.output)])
        result = json.loads(output.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(len(result["errors"]), 100)
        self.assertTrue(result["errors_truncated"])
        self.assertEqual([item["path"] for item in result["errors"]], [f"/{i}/data/owner" for i in range(100)])

    def test_error_order_follows_files_then_array_not_reference_pass(self):
        first = self.record_input("d", "detail", {"owner": {"local_id": "missing"}})
        invalid = self.record_input("bad", "material")
        later = self.record_input("r", "detail", {"owner": {"local_id": "later"}})
        errors = self.assert_error("REFERENCE_NOT_FOUND", self.build, [first, invalid], [later])
        self.assertEqual([error["path"] for error in errors], ["/0/data/owner", "/1/kind", "/0/data/owner"])
        self.assertTrue(errors[0]["file"].endswith("records-0.json"))
        self.assertTrue(errors[-1]["file"].endswith("records-1.json"))

    def test_file_only_paths_with_forbidden_database_and_process_calls(self):
        sentinel = self.root / "contract.sqlite"
        sentinel.write_bytes(b"untouched test library")
        with patch.object(sqlite3, "connect", side_effect=AssertionError("database access")), \
             patch.object(subprocess, "Popen", side_effect=AssertionError("external process")), \
             patch("legal.storage.CaseStore", side_effect=AssertionError("CaseStore access")):
            self.find([self.quote("甲应付款。")])
            self.output.unlink()
            self.build([self.record_input()])
            self.output.unlink()
            self.assert_error("REFERENCE_NOT_FOUND", self.build, [self.record_input("d", "detail", {"owner": {"local_id": "missing"}})])
        self.assertEqual(sentinel.read_bytes(), b"untouched test library")

    def test_argument_and_file_exit_codes_and_json_stdout(self):
        cases = [("find_quote", ["--db", "x"], 2),
                 ("find_quote", ["--clauses", str(self.clauses_file), "--clauses", str(self.clauses_file), "--input", "x", "--output", "y"], 2),
                 ("build_submission", ["--header", "relative.json", "--records", "relative.json", "--output", "relative.json"], 2),
                 ("build_submission", ["--header", str(self.header_file), "--records", str(self.root / "absent.json"), "--output", str(self.output)], 3)]
        for tool, argv, expected in cases:
            with self.subTest(tool=tool, argv=argv):
                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    code = main(tool, argv)
                self.assertEqual(code, expected)
                self.assertFalse(json.loads(stdout.getvalue())["ok"])
                self.assertFalse(self.output.exists())

    def test_help_reads_no_inputs(self):
        for tool in ("find_quote", "build_submission"):
            with patch("legal.reader_helpers._read", side_effect=AssertionError("input read")), redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    main(tool, ["--help"])
                self.assertEqual(caught.exception.code, 0)


class FormalWriteIntegration(unittest.TestCase):
    def test_generated_files_still_undergo_formal_slot_source_and_version_checks(self):
        with tempfile.TemporaryDirectory(prefix="reader-formal-") as temporary:
            root = Path(temporary)

            def put(name, value):
                path = root / name
                path.write_bytes(json.dumps(value, ensure_ascii=False).encode("utf-8"))
                return path

            unit, slot = new_id(), new_id()
            vocabulary = put("vocabulary.json", {"format_version": 1,
                "units": [{"id": unit, "name": "付款", "description": "测试"}],
                "slots": [{"id": slot, "name": "安排", "description": "测试", "value_schema": {"form": "text"}}],
                "assignments": [{"unit_id": unit, "slot_id": slot}]})
            db = root / "contract.sqlite"
            init = initialize(db, vocabulary)
            text = root / "text.txt"
            text.write_bytes("第一条 甲应向乙付款。\r\n".encode("utf-8"))
            metadata = put("metadata.json", {"name": "夹具", "media_type": "text/plain", "conversion_method": "identity", "converter_version": "test.1", "anomalies": []})
            registered = register(db, text, text, metadata)
            split(db, registered["text_version"]["object_id"])
            clauses = query(db, {"view": "clauses"})
            snapshot = put("clauses.json", {"case_id": init["case_id"], "checked_sequence": clauses["quality"]["current_sequence"], "items": clauses["items"]})
            clause = clauses["items"][0]
            anchors = root / "anchors.json"
            find_quote_files(snapshot, put("requests.json", [{"local_id": "a", "clause_record_id": clause["record_id"], "quote": clause["data"]["text"]}]), anchors)
            evidence = [{"path": "", "source": {"level": 1, "anchors": [{"local_id": "a"}]}}]
            subjects = [{"local_id": identifier, "kind": "node", "data": {"node_kind": "subject", "canonical_name": name}, "evidence": evidence}
                        for identifier, name in (("p", "甲"), ("q", "乙"))]
            header = {"format_version": 1, "case_id": init["case_id"], "vocabulary_hash": init["vocabulary_hash"],
                      "submitted_by": "reader", "phase": "preparation", "covered_clauses": [], "issues": []}
            header_file = put("header.json", header)
            output = root / "preparation.json"
            build_submission_files(header_file, [anchors, put("subjects.json", subjects)], output)
            receipt = write(db, json.loads(output.read_bytes()))
            self.assertTrue(receipt["ok"])
            relation = {"local_id": "r", "kind": "relation", "data": {"relation_kind": "party", "unit_id": unit,
                        "parties": [{"subject": {"object_id": receipt["id_map"][identifier]["object_id"]}, "nature": nature}
                                    for identifier, nature in (("p", "obligor"), ("q", "recipient"))]}, "evidence": evidence}
            detail = {"local_id": "d", "kind": "detail", "data": {"owner": {"local_id": "r"}, "slot_id": slot,
                      "value": {"form": "text", "surface": "甲应向乙付款。"}}, "evidence": evidence}
            wrong_slot = copy.deepcopy(detail)
            wrong_slot["data"]["slot_id"] = new_id()
            no_source = copy.deepcopy(detail)
            no_source["evidence"] = []
            stale = copy.deepcopy(subjects[0])
            stale.update(object_id=receipt["id_map"]["p"]["object_id"], previous_record_id=new_id())
            for i, records in enumerate(([relation, wrong_slot], [relation, no_source], [stale])):
                output = root / f"bad-{i}.json"
                build_submission_files(header_file, [anchors, put(f"bad-records-{i}.json", records)], output)
                before = db.read_bytes()
                with self.assertRaises((Invalid, InvalidBatch)):
                    write(db, json.loads(output.read_bytes()))
                self.assertEqual(db.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
