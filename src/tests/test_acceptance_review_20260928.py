"""Independent acceptance probes; production code is deliberately unchanged.

Run from legal/src:
  python -B -m unittest discover -s tests -p test_acceptance_review_20260928.py -v
Every mutating case uses a temporary database. Failures express spec requirements.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from legal.formats import Invalid, InvalidBatch, canonical, digest, loads, new_id
from legal.model import write
from legal.preprocessing import convert
from legal.query import query
from legal.reconcile import reconcile
from legal.splitter import split_text
from legal.storage import initialize, register, split
from legal.values import check_contract, matches_schema, validate_units
from legal.vocabulary import apply_change, normalize, vocabulary_hash

SRC = Path(__file__).resolve().parents[1]


class AcceptanceReview(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="legal-acceptance-")
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        self.db = self.work / "case.sqlite"
        self.u, self.s, self.t = new_id(), new_id(), new_id()
        self.vocabulary = normalize({
            "format_version": 1,
            "units": [{"id": self.u, "name": "付款", "description": "测试付款"}],
            "slots": [
                {"id": self.s, "name": "金额", "description": "测试金额", "value_schema": {
                    "one_of": [{"form": "quantity", "allowed_units": ["CNY"]},
                               {"form": "reference", "target_kinds": ["node:defined_value"]}]}},
                {"id": self.t, "name": "文字", "description": "测试通用文字", "value_schema": {"form": "text"}},
            ],
            "assignments": [{"unit_id": self.u, "slot_id": self.s}],
        })
        self.vocabfile = self.put("vocabulary.json", self.vocabulary)
        self.initial = initialize(self.db, self.vocabfile)
        self.original = self.work / "original.txt"
        self.original.write_bytes("第一条 甲向乙支付100元。\n".encode())
        self.metadata = self.put("metadata.json", {
            "name": "测试", "media_type": "text/plain", "conversion_method": "identity",
            "converter_version": "test.1", "anomalies": []})
        self.registered = register(self.db, self.original, self.original, self.metadata)
        self.split_result = split(self.db, self.registered["text_version"]["object_id"])
        self.c = self.split_result["clauses"][0]
        prep = self.doc([
            {"local_id": "a", "kind": "anchor", "data": {"clause": {"record_id": self.c["record_id"]},
                "quote": "甲向乙支付100元。"}, "evidence": []},
            {"local_id": "p", "kind": "node", "data": {"node_kind": "subject", "canonical_name": "甲"}, "evidence": self.ev("a")},
            {"local_id": "q", "kind": "node", "data": {"node_kind": "subject", "canonical_name": "乙"}, "evidence": self.ev("a")},
        ], phase="preparation")
        self.prepared = write(self.db, prep)
        self.a = self.prepared["id_map"]["a"]
        self.p = self.prepared["id_map"]["p"]
        self.q = self.prepared["id_map"]["q"]
        old = self.item(self.c["object_id"])
        raw = self.revision(old, "c")
        raw["data"].update(classification="ordinary", tags=[self.u])
        raw["evidence"] = self.ev()
        tagged = write(self.db, self.doc([raw], phase="tagging"))
        self.c = tagged["id_map"]["c"]

    def put(self, name, obj):
        path = self.work / name
        path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
        return path

    def ev(self, local=None):
        ref = {"local_id": local} if local else {"record_id": self.a["record_id"]}
        return [{"path": "", "source": {"level": 1, "anchors": [ref]}}]

    def inferred(self):
        return [{"path": "", "source": {"level": 3,
            "premises": [{"record_id": self.a["record_id"]}],
            "explanation": "独立验收夹具的有根前提", "asserted_by": "acceptance"}}]

    def doc(self, records, phase="correction", covered=None):
        return {"format_version": 1, "case_id": self.initial["case_id"],
            "vocabulary_hash": self.initial["vocabulary_hash"], "submitted_by": "acceptance-review",
            "phase": phase, "covered_clauses": covered or [], "records": records, "issues": []}

    def relation(self, evidence=None):
        return {"local_id": "r", "kind": "relation", "data": {
            "relation_kind": "party", "unit_id": self.u,
            "parties": [{"subject": {"object_id": self.p["object_id"]}, "nature": "obligor"},
                        {"subject": {"object_id": self.q["object_id"]}, "nature": "recipient"}]},
            "evidence": evidence if evidence is not None else self.ev()}

    def extraction(self):
        return self.doc([self.relation(), {"local_id": "d", "kind": "detail", "data": {
            "owner": {"local_id": "r"}, "slot_id": self.s,
            "value": {"form": "quantity", "amount": "100", "unit": "CNY"}}, "evidence": self.ev()}],
            phase="extraction", covered=[{"object_id": self.c["object_id"], "record_id": self.c["record_id"]}])

    def complete(self):
        self.extracted = write(self.db, self.extraction())
        return self.extracted

    def item(self, object_id):
        return query(self.db, {"object": object_id})["items"][0]

    def revision(self, item, local):
        return {"local_id": local, "kind": item["kind"], "object_id": item["object_id"],
            "previous_record_id": item["record_id"], "data": copy.deepcopy(item["data"]),
            "evidence": copy.deepcopy(item["evidence"])}

    def counts(self):
        with sqlite3.connect(self.db) as conn:
            return tuple(conn.execute("select count(*) from " + table).fetchone()[0]
                for table in ("submissions", "objects", "record_versions", "extraction_completions"))

    def reject(self, call, codes):
        try:
            call()
        except Invalid as exc:
            self.assertIn(exc.code, codes)
        except InvalidBatch as exc:
            self.assertTrue({x["code"] for x in exc.items} & set(codes), exc.items)
        else:
            self.fail("规格要求拒绝，但实现返回成功")

    def test_01_seven_entries_and_help(self):
        for name in ["legal-preprocess", "legal-case", "legal-vocab", "legal-initialize"]:
            self.assertTrue((SRC / "skills" / name / "SKILL.md").is_file())
        for module in ["preprocess_cli", "case_cli", "vocab_cli"]:
            result = subprocess.run([sys.executable, "-B", "-m", "legal." + module, "--help"],
                cwd=SRC, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_02_register_split_replay(self):
        before = self.counts()
        self.assertTrue(register(self.db, self.original, self.original, self.metadata)["replayed"])
        self.assertTrue(split(self.db, self.registered["text_version"]["object_id"])["replayed"])
        self.assertEqual(before, self.counts())
        self.assertEqual(self.registered["text_hash"], digest(self.original.read_bytes()))

    def test_03_bad_last_record_is_atomic(self):
        doc = self.extraction()
        doc["records"][-1]["data"]["value"]["unit"] = "UNKNOWN"
        before = self.counts()
        self.reject(lambda: write(self.db, doc), {"INVALID_VALUE", "UNKNOWN_UNIT"})
        self.assertEqual(before, self.counts())

    def test_04_success_replay(self):
        doc = self.extraction()
        first = write(self.db, doc)
        before = self.counts()
        again = write(self.db, loads(json.dumps(doc, indent=4)))
        self.assertEqual({**first, "replayed": True}, again)
        self.assertEqual(before, self.counts())

    def test_05_stale_revision_and_revision_replay(self):
        self.complete()
        detail = self.item(self.extracted["id_map"]["d"]["object_id"])
        a = self.revision(detail, "d")
        a["data"]["value"]["amount"] = "100.0"
        b = copy.deepcopy(a)
        b["data"]["value"]["amount"] = "100.00"
        doc = self.doc([a])
        write(self.db, doc)
        self.assertTrue(write(self.db, doc)["replayed"])
        before = self.counts()
        self.reject(lambda: write(self.db, self.doc([b])), {"STALE_REVISION"})
        self.assertEqual(before, self.counts())

    def test_06_withdraw_dependencies_and_restore(self):
        result = self.complete()
        r, d = [self.revision(self.item(result["id_map"][k]["object_id"]), k) for k in ("r", "d")]
        for rec in (r, d):
            rec.update(status="withdrawn", withdrawal_reason="验收撤销")
        self.reject(lambda: write(self.db, self.doc([r])), {"WITHDRAWN_TARGET"})
        receipt = write(self.db, self.doc([r, d]))
        for rec in (r, d):
            rec.pop("withdrawal_reason")
            rec["status"] = "active"
            rec["previous_record_id"] = receipt["id_map"][rec["local_id"]]["record_id"]
        write(self.db, self.doc([r, d]))
        self.assertEqual(self.item(r["object_id"])["revision"], 3)

    def test_07_historical_details(self):
        self.complete()
        r = self.extracted["id_map"]["r"]
        d = self.revision(self.item(self.extracted["id_map"]["d"]["object_id"]), "d")
        d["data"]["value"]["amount"] = "100.00"
        write(self.db, self.doc([d]))
        old = query(self.db, {"record": r["record_id"]})["items"][0]
        self.assertEqual(old["details"][0]["data"]["value"]["amount"], "100")
        self.assertEqual(self.item(r["object_id"])["details"][0]["data"]["value"]["amount"], "100.00")

    def test_08_inference_from_anchor_has_query_provenance(self):
        rec = self.relation(self.inferred())
        receipt = write(self.db, self.doc([rec]))
        item = self.item(receipt["id_map"]["r"]["object_id"])
        anchors = [a for source in item["provenance"] for a in source["anchors"]]
        self.assertIn(self.a["record_id"], [a["anchor_record_id"] for a in anchors], item["provenance"])

    def test_09_inference_from_anchor_can_complete_clause(self):
        doc = self.doc([self.relation(self.inferred())], phase="extraction", covered=[{
            "object_id": self.c["object_id"], "record_id": self.c["record_id"]}])
        receipt = write(self.db, doc)
        self.assertEqual(receipt["covered_clauses"], [self.c["object_id"]])

    def test_10_current_relation_retains_historical_gap(self):
        self.complete()
        r = self.extracted["id_map"]["r"]
        gap = {"local_id": "g", "kind": "gap", "data": {
            "clause": {"record_id": self.c["record_id"]}, "gap_kind": "missing_slot",
            "description": "验收历史缺口", "reported_by": "acceptance", "related_object": {"record_id": r["record_id"]}},
            "evidence": self.ev()}
        g = write(self.db, self.doc([gap]))["id_map"]["g"]
        self.assertEqual(self.item(r["object_id"])["gaps"][0]["object_id"], g["object_id"])
        revised = self.revision(self.item(r["object_id"]), "r")
        revised["data"]["modality"] = "obligation"
        write(self.db, self.doc([revised]))
        current = self.item(r["object_id"])
        self.assertEqual([x["object_id"] for x in current["gaps"]], [g["object_id"]])
        self.assertTrue(current["gaps"][0]["target_changed"])

    def test_11_canonical_party_filter_includes_details(self):
        self.complete()
        records = [
            {"local_id": "p2", "kind": "node", "data": {"node_kind": "subject", "canonical_name": "甲"}, "evidence": self.ev()},
            {"local_id": "redirect", "kind": "reference", "data": {"reference_kind": "redirect",
                "from": {"object_id": self.p["object_id"]}, "to": {"local_id": "p2"}}, "evidence": self.ev()}]
        mapped = write(self.db, self.doc(records))["id_map"]["p2"]["object_id"]
        output = query(self.db, {"kinds": ["detail"], "parties": [mapped]})
        self.assertEqual(output["total"], 1, output)
        self.assertEqual(output["items"][0]["object_id"], self.extracted["id_map"]["d"]["object_id"])

    def test_12_future_case_versions_are_rejected(self):
        # A database produced by a future version has different header checks.
        # Recreate ONLY this temporary fixture's header without v1-only CHECKs.
        with sqlite3.connect(self.db) as conn:
            conn.execute("create table future_case_info as select * from case_info")
            conn.execute("drop table case_info")
            conn.execute("alter table future_case_info rename to case_info")
        for column in ["schema_version", "value_format_version", "code_version", "vocabulary_format_version"]:
            with self.subTest(column=column):
                with sqlite3.connect(self.db) as conn:
                    conn.execute("update case_info set " + column + "=999")
                try:
                    self.reject(lambda: query(self.db, {"view": "vocabulary"}), {"UNSUPPORTED_VERSION"})
                finally:
                    with sqlite3.connect(self.db) as conn:
                        conn.execute("update case_info set " + column + "=1")

    def test_13_invalid_anchor_occurrence_is_rejected(self):
        for occurrence in (0, False, None):
            with self.subTest(occurrence=occurrence):
                rec = {"local_id": "a", "kind": "anchor", "data": {
                    "clause": {"record_id": self.c["record_id"]}, "quote": "100", "occurrence": occurrence}, "evidence": []}
                self.reject(lambda: write(self.db, self.doc([rec])), {"INVALID_ARGUMENT", "ANCHOR_OCCURRENCE"})

    def test_14_reconcile_rechecks_stored_value_structure(self):
        self.complete()
        self.assertTrue(reconcile(self.db)["passed"])
        rid = self.extracted["id_map"]["d"]["record_id"]
        with sqlite3.connect(self.db) as conn:
            data = json.loads(conn.execute("select data_json from record_versions where record_id=?", (rid,)).fetchone()[0])
            data["value"]["unit"] = "UNKNOWN"
            conn.execute("update record_versions set data_json=? where record_id=?", (json.dumps(data), rid))
            conn.execute("update details set value_json=? where record_id=?", (json.dumps(data["value"]), rid))
        report = reconcile(self.db)
        self.assertFalse(report["passed"], "持久化量值包含未知单位，对账仍返回 passed=true")

    def test_15_original_export_is_self_contained(self):
        original_bytes = self.original.read_bytes()
        self.original.unlink()
        output = self.work / "export.txt"
        result = query(self.db, {"view": "materials", "object": self.registered["material"]["object_id"],
            "format": "original", "output": str(output)})
        self.assertEqual(output.read_bytes(), original_bytes)
        self.assertEqual(result["content_hash"], digest(original_bytes))

    def test_16_quality_failed_then_passed_then_stale(self):
        self.assertFalse(reconcile(self.db)["passed"])
        self.complete()
        self.assertEqual(query(self.db, {"view": "progress"})["quality"]["state"], "stale")
        self.assertTrue(reconcile(self.db)["passed"])
        self.assertEqual(query(self.db, {"view": "progress"})["quality"]["state"], "passed")
        doc = self.doc([], phase="correction")
        write(self.db, doc)
        self.assertEqual(query(self.db, {"view": "progress"})["quality"]["state"], "stale")

    def test_17_vocabulary_orphan_and_hash_conflict(self):
        change = {"format_version": 1, "expected_hash": vocabulary_hash(self.vocabulary),
            "operations": [{"action": "remove", "kind": "unit", "id": self.u}]}
        self.reject(lambda: apply_change(self.vocabulary, change), {"ORPHAN_DISPOSITION_REQUIRED"})
        change["orphan_slots"] = [{"slot_id": self.s, "disposition": "general"}]
        result, _ = apply_change(self.vocabulary, change)
        self.assertEqual(result["assignments"], [])
        change["expected_hash"] = "0" * 64
        self.reject(lambda: apply_change(self.vocabulary, change), {"HASH_CONFLICT"})

    def test_18_strict_json(self):
        for text in ['{"a":1,"a":2}', '{"a":NaN}', '\ufeff{}', '{} {}', '{"a":1,}']:
            with self.subTest(text=text):
                self.reject(lambda: loads(text), {"INVALID_JSON"})

    def test_19_high_precision_decimal(self):
        amount = "123456789012345678901234567890.12"
        surface = amount + "元"
        source = {"format_contract": "decimal.v1", "surface": surface, "format_parameters": {
            "scale": "1", "decimal_places": 2, "group_separator": "", "decimal_separator": ".",
            "sign_style": "minus", "unit_surface": "元", "unit_position": "after",
            "number_unit_separator": "", "prefix": "", "suffix": ""}}
        value = {"form": "quantity", "amount": amount, "unit": "CNY"}
        check_contract(value, source, surface, "/value")
        value["amount"] = amount[:-1] + "3"
        self.reject(lambda: check_contract(value, source, surface, "/value"), {"ROUNDTRIP_FAILED"})

    def test_20_frozen_vocabulary(self):
        self.put("vocabulary.json", {"format_version": 1, "units": [], "slots": [], "assignments": []})
        v = query(self.db, {"view": "vocabulary"})["items"][0]
        self.assertEqual(v["hash"], self.initial["vocabulary_hash"])
        self.assertEqual(len(v["units"]), 1)

    def test_21_one_of_overlap_rejected(self):
        units = validate_units(json.loads((SRC / "legal/config/units.v1.json").read_text()))
        self.reject(lambda: matches_schema({"form": "text", "surface": "甲"},
            {"one_of": [{"form": "text"}, {"form": "text"}]}, units, lambda *_: None), {"INVALID_VALUE"})

    def test_22_redirect_cycle_rejected(self):
        records = []
        for n, a, b in [("x", self.p, self.q), ("y", self.q, self.p)]:
            records.append({"local_id": n, "kind": "reference", "data": {"reference_kind": "redirect",
                "from": {"object_id": a["object_id"]}, "to": {"object_id": b["object_id"]}}, "evidence": self.ev()})
        self.reject(lambda: write(self.db, self.doc(records)), {"REDIRECT_CYCLE"})

    def test_23_value_null_keeps_evidence(self):
        doc = self.extraction()
        doc["records"][1]["data"]["value"] = None
        receipt = write(self.db, doc)
        self.assertIsNone(self.item(receipt["id_map"]["d"]["object_id"])["data"]["value"])
        self.assertNotIn(self.s, self.item(receipt["id_map"]["r"]["object_id"])["missing_slots"])

    def test_24_scanner_fixed_samples(self):
        samples = [
            ("第一条 付款。\n第三条 交付。\n第三条 验收。\n", ["第一条 付款。\n", "第三条 交付。\n", "第三条 验收。\n"]),
            ("1. 合同价款\n1.1 支付价款。\n1.3 结算。\n", ["1. 合同价款\n", "1.1 支付价款。\n", "1.3 结算。\n"]),
            ("ARTICLE I PAYMENT\nSection 1 Amount\nBuyer pays.\nClause 2 Delivery\n", ["ARTICLE I PAYMENT\n", "Section 1 Amount\nBuyer pays.\n", "Clause 2 Delivery\n"]),
            ("合同名称\n甲方：甲\n\n双方另有约定。\n", ["合同名称\n甲方：甲\n\n", "双方另有约定。\n"]),
            ("> **1.1 付款。**\r\n> 1.2\r\n收到后付款。\r\n", ["> **1.1 付款。**\r\n", "> 1.2\r\n收到后付款。\r\n"]),
            ("第一条 正文。\n附件一 清单 附件二 图纸\n第二条 后续。\n", ["第一条 正文。\n", "附件一 清单 附件二 图纸\n", "第二条 后续。\n"]),
            ("提前\n60\n天通知。\n", ["提前\n60\n天通知。\n"]),
            ("第一条 价格。\n\n|品名|金额|\n|A|100|\n第二条 交付。", ["第一条 价格。\n\n", "|品名|金额|\n|A|100|\n", "第二条 交付。"]),
            ("", []), (" \r\n\n", [" \r\n\n"]),
        ]
        for text, expected in samples:
            with self.subTest(text=text):
                clauses = split_text(text)
                self.assertEqual([c["text"] for c in clauses], expected)
                self.assertEqual("".join(c["text"] for c in clauses), text)

    def converter_config(self, mode="ok"):
        return self.put("converter.json", {"format_version": 1, "argv": [sys.executable,
            str(SRC / "tests/fixtures/acceptance_converter_20260928.py"), mode, "{input}", "{output_dir}"]})

    def test_25_preprocessor_bytes_and_stdout(self):
        self.original.write_bytes("甲\r\n乙\n".encode())
        target = self.work / "中文 输出"
        result = subprocess.run([sys.executable, "-B", "-m", "legal.preprocess_cli", "--input", str(self.original),
            "--output-dir", str(target), "--converter-config", str(self.converter_config())], cwd=SRC,
            capture_output=True, timeout=10, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(result.returncode, 0, result.stdout)
        receipt = json.loads(result.stdout)
        self.assertEqual((target / "text.txt").read_bytes(), self.original.read_bytes())
        self.assertEqual(receipt["text_hash"], digest(self.original.read_bytes()))
        self.assertIn(b"converter stdout", result.stderr)

    def test_26_preprocessor_rejects_bad_outputs(self):
        for mode, code in [("missing", "CONVERTER_OUTPUT_INVALID"), ("utf8", "CONVERTER_OUTPUT_INVALID"),
                           ("interval", "CONVERTER_OUTPUT_INVALID"), ("fail", "CONVERTER_FAILED"),
                           ("mutate", "ORIGINAL_CHANGED")]:
            with self.subTest(mode=mode):
                target = self.work / ("out-" + mode)
                self.reject(lambda: convert(self.original, target, self.converter_config(mode)), {code})
                self.assertFalse((target / "text.txt").exists())

    def test_27_preprocessor_output_no_overwrite(self):
        target = self.work / "already"
        target.mkdir()
        sentinel = target / "text.txt"
        sentinel.write_text("keep")
        self.reject(lambda: convert(self.original, target, self.converter_config()), {"FILE_EXISTS"})
        self.assertEqual(sentinel.read_text(), "keep")

    def test_28_preprocessor_cleans_partial_publish(self):
        target = self.work / "publish"
        original_open = Path.open
        def broken(path, *args, **kwargs):
            if path == target / "metadata.json" and args and args[0] == "xb":
                raise OSError("simulated metadata publish failure")
            return original_open(path, *args, **kwargs)
        with patch.object(Path, "open", broken):
            self.reject(lambda: convert(self.original, target, self.converter_config()), {"FILE_ERROR"})
        self.assertFalse((target / "text.txt").exists())


if __name__ == "__main__":
    unittest.main()
