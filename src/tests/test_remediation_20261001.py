"""Mechanism regressions and explicit modeling examples, not semantic approval.

LEGAL_CONTRACT_TEXT selects an external Markdown fixture. Private contract
content is not packaged with this source. All example databases are temporary.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from legal.formats import Invalid, exclusive_write, new_id
from legal.group import group
from legal.handoff import export_extraction_tasks
from legal.model import write
from legal.query import query
from legal.splitter import split_text
from legal.storage import initialize, register, split

SRC = Path(__file__).resolve().parents[1]
RESOURCE_ROOT = Path(os.environ.get("LEGAL_RESOURCE_ROOT", SRC))


class ArticleRegression(unittest.TestCase):
    def check(self, text, numbers):
        clauses = split_text(text)
        self.assertEqual([c["original_number"] for c in clauses], numbers)
        self.assertEqual("".join(c["text"] for c in clauses), text)
        self.assertEqual([c["start_offset"] for c in clauses], [0] + [c["end_offset"] for c in clauses[:-1]])
        return clauses

    def test_clause_overrides_list_heading_styles(self):
        text = "前言\n\n**CLAUSE 1 -- PRICE**\n\n# 1.1 金额\n100。\n## 1.2 条件\n付清。\n**[CLAUSE 2 -- DELIVERY]{.mark}**\n交付。\n"
        clauses = self.check(text, [None, "CLAUSE 1", "CLAUSE 2"])
        self.assertIn("1.2 条件", clauses[1]["text"])
        self.assertTrue(clauses[2]["text"].startswith("**[CLAUSE 2"))

    def test_decimal_parent_ownership(self):
        self.check("# 1. 价款\n## 1.1 金额\n## 1.2 条件\n# 2. 交付\n## 2.1 时间\n", ["1.", "2."])

    def test_labelled_article_retains_internal_section_and_clause(self):
        self.check("# ARTICLE 1 -- PRICE\n## Section 1 -- Amount\n100。\n## Clause 2 -- Condition\n付清。\n# ARTICLE 2 -- DELIVERY\n交付。\n", ["ARTICLE 1", "ARTICLE 2"])
        self.check("ARTICLE I -- PROVISIONS\nSection 1 -- Scope\n正文。\nClause 2 -- Price\n价款。\n", ["ARTICLE I"])

    def test_contract_title_above_explicit_chapters(self):
        self.check("# 供货合同\n## 第一章 价款\n### 第一条 金额\n100元。\n### 第二条 时间\n次月。\n## 第二章 交付\n### 第三条 地点\n上海。\n", [None, None, "第一条", "第二条", None, "第三条"])

    def test_preamble_is_one_region(self):
        self.check("**Contract Agreement**\n**Whereas**\nA.  原因\nB.  原因\n**Now Therefore**\n1.  约定\n2.  约定\n**CLAUSE 1 -- WORKS**\n工作。\n", [None, "CLAUSE 1"])

    def test_signature_and_appendix_regions(self):
        text = "**CLAUSE 1 -- ORIGINALS**\n两份。\n\nIN WITNESS WHEREOF, parties sign.\n\n|代表|签字|\n|甲|____|\n\n**APPENDIX 1 -- PRICES**\n总价与三分项。\n1. 总价\n2. 分项\n"
        clauses = self.check(text, ["CLAUSE 1", None, None])
        self.assertIn("|代表|签字|", clauses[1]["text"])
        self.assertIn("2. 分项", clauses[2]["text"])

    def test_cross_references_and_fences_do_not_split(self):
        text = "**CLAUSE 1 -- WORKS**\n参见\nClause 7 of this Contract.\n\nAppendix 1 to the Contract governs.\n\n```text\n**CLAUSE 99 -- EXAMPLE**\n```\n\n**CLAUSE 2 -- PRICE**\n价款。\n"
        self.check(text, ["CLAUSE 1", "CLAUSE 2"])

    def test_number_series_and_parent_scoping(self):
        text = "**CLAUSE 12 -- DUTIES**\n1. 内部条目。\n4. 内部条目。\n\n**CLAUSE 13 -- MORE DUTIES**\n2. 内部条目。\n"
        clauses = self.check(text, ["CLAUSE 12", "CLAUSE 13"])
        self.assertFalse(any(c["anomalies"] for c in clauses))
        clauses = self.check("第一条 付款。\n第三条 交付。\n第三条 验收。\n", ["第一条", "第三条", "第三条"])
        self.assertEqual([a["type"] for c in clauses for a in c["anomalies"]], ["skip", "duplicate"])
        clauses = self.check("> 1.1 条文。\n> 2.1 条文。\n", ["1.1", "2.1"])
        self.assertFalse(any(c["anomalies"] for c in clauses))

    def test_real_contract_has_42_complete_clauses(self):
        path = os.environ.get("LEGAL_CONTRACT_TEXT")
        if not path:
            self.skipTest("set LEGAL_CONTRACT_TEXT to the external Markdown fixture")
        text = Path(path).read_bytes().decode("utf-8")
        clauses = split_text(text)
        articles = [c for c in clauses if c["original_number"] is not None]
        self.assertEqual([c["original_number"].upper() for c in articles], [f"CLAUSE {i}" for i in range(1, 43)])
        self.assertEqual(len(clauses), 45)  # pre-article + 42 + signature + appendix
        self.assertEqual("".join(c["text"] for c in clauses), text)
        # Expectations come from independent standalone source titles, not
        # the splitter's scanner, Word styles or a rewritten source string.
        expected = list(re.finditer(r"^\*\*\[?CLAUSE (\d+) --", text, re.M))
        self.assertEqual(len(expected), 42)
        for article, marker in zip(articles, expected):
            self.assertEqual(article["start_offset"], marker.start())
        self.assertTrue(articles[24]["text"].startswith("**[CLAUSE 25"))
        self.assertTrue(articles[29]["text"].startswith("**CLAUSE 30"))
        self.assertNotIn("IN WITNESS WHEREOF", articles[-1]["text"])
        self.assertTrue(clauses[-1]["text"].startswith("**APPENDIX 1"))
        self.assertFalse(any(c["anomalies"] for c in clauses))
        evidence = os.environ.get("LEGAL_REMEDIATION_OUTPUT")
        if evidence:
            destination = Path(evidence) / "real-contract-split.json"
            destination.write_text(json.dumps(clauses, ensure_ascii=False, indent=2) + "\n")

    def test_real_register_split_query_and_replay(self):
        path = os.environ.get("LEGAL_CONTRACT_TEXT")
        if not path:
            self.skipTest("set LEGAL_CONTRACT_TEXT to the external Markdown fixture")
        with tempfile.TemporaryDirectory(prefix="legal-article-pipeline-") as temporary:
            root = Path(temporary)
            text_file = root / "text.txt"
            text_file.write_bytes(Path(path).read_bytes())
            vocabulary = root / "vocabulary.json"
            vocabulary.write_text(json.dumps({"format_version": 1, "units": [], "slots": [], "assignments": []}))
            metadata = root / "metadata.json"
            metadata.write_text(json.dumps({"name": "已转换 Markdown 切分回归", "media_type": "text/markdown", "conversion_method": "identity", "converter_version": "test.1", "anomalies": []}))
            database = root / "contract.sqlite"
            initialize(database, vocabulary)
            registered = register(database, text_file, text_file, metadata)
            receipt = split(database, registered["text_version"]["object_id"])
            replay = split(database, registered["text_version"]["object_id"])
            self.assertTrue(replay["replayed"])
            result = query(database, {"view": "clauses", "limit": 100})
            self.assertEqual(len(result["items"]), 45)
            ordered = sorted(result["items"], key=lambda item: item["data"]["sequence"])
            self.assertEqual("".join(item["data"]["text"] for item in ordered), text_file.read_bytes().decode("utf-8"))
            self.assertEqual([item["data"]["original_number"] for item in ordered if item["data"]["original_number"]], [f"CLAUSE {i}" for i in range(1, 43)])
            if os.environ.get("LEGAL_REMEDIATION_OUTPUT"):
                for name, value in (("register-receipt.json", registered), ("split-receipt.json", receipt), ("split-replay.json", replay), ("query.json", result)):
                    (root / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
                shutil.copytree(root, Path(os.environ["LEGAL_REMEDIATION_OUTPUT"]) / "contract-markdown-regression", dirs_exist_ok=True)


class ExampleFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="legal-remediation-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for folder in ("tasks", "submissions", "groups"):
            (self.root / folder).mkdir()
        self.db = self.root / "contract.sqlite"
        self.unit, self.text_slot, self.condition_slot, self.time_slot = (new_id() for _ in range(4))
        vocabulary = {"format_version": 1, "units": [{"id": self.unit, "name": "测试关系", "description": "机制实例，不是正式词表治理"}],
                      "slots": [{"id": self.text_slot, "name": "完整文字", "description": "示例", "value_schema": {"form": "text"}},
                                {"id": self.condition_slot, "name": "条件", "description": "示例", "value_schema": {"form": "condition"}},
                                {"id": self.time_slot, "name": "期间", "description": "示例", "value_schema": {"form": "time"}}],
                      "assignments": []}
        vocabulary = self.vocabulary_document(vocabulary)
        self.vocabulary = self.put("vocabulary.json", vocabulary)
        self.initial = initialize(self.db, self.vocabulary)
        self.text = ("第一条 甲为承包商，乙为雇主。甲的责任上限保护甲并限制乙的请求。"
                     "甲每月25日提出月度申请，乙在同月30日批准付款安排。"
                     "两个包的技术支持各自从该包验收起持续24个月。"
                     "若原水参数变化导致处理产品用量增加超过10%，甲可以向乙请求调价。"
                     "包1总价100 USD，由货物60 USD、境外服务20 USD、境内服务20 USD组成；"
                     "包2总价200 USD，由货物100 USD、境外服务40 USD、境内服务60 USD组成。\n")
        original = self.root / "text.txt"; original.write_text(self.text)
        metadata = self.put("metadata.json", {"name": "机制实例", "media_type": "text/plain", "conversion_method": "identity", "converter_version": "test.1", "anomalies": []})
        reg = register(self.db, original, original, metadata)
        self.clause = split(self.db, reg["text_version"]["object_id"])["clauses"][0]
        prep = [self.anchor("a"), self.subject("p", "甲"), self.subject("q", "乙")]
        for identifier, name, description in (
            ("e1", "包1验收", "包1验收合格，作为包1技术支持的起点。"),
            ("e2", "包2验收", "包2验收合格，作为包2技术支持的起点。"),
            ("increase", "处理产品用量变化", "原水参数变化导致处理产品用量增加超过10%，作为甲请求乙调价的条件；未断言已实际发生。"),
        ):
            prep.append({"local_id": identifier, "kind": "node", "data": {"node_kind": "event", "name": name, "description": description,
                          "participants": [{"subject": {"local_id": "p"}, "role": "承包商"}], "batch_or_stage": name}, "evidence": self.ev()})
        receipt = write(self.db, self.doc(prep, "preparation", overview={"text_versions": [{"object_id": reg["text_version"]["object_id"]}], "body": "机制实例的阅读背景。", "authored_by": "test"}))
        self.ids = receipt["id_map"]
        raw = query(self.db, {"object": self.clause["object_id"]})["items"][0]
        data = copy.deepcopy(raw["data"]); data.update(tags=[self.unit], classification="ordinary")
        tagged = write(self.db, self.doc([{"local_id": "c", "kind": "clause", "object_id": raw["object_id"], "previous_record_id": raw["record_id"], "data": data,
                                        "evidence": self.ev(fixed=True)}], "tagging"))
        self.clause = {key: tagged["id_map"]["c"][key] for key in ("object_id", "record_id")}

    def vocabulary_document(self, document):
        return document

    def tearDown(self):
        evidence = os.environ.get("LEGAL_REMEDIATION_OUTPUT")
        if evidence:
            destination = Path(evidence) / "examples" / self.id().split(".")[-2] / self.id().split(".")[-1]
            shutil.copytree(self.root, destination, dirs_exist_ok=True)

    def put(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2))
        return path

    def ev(self, fixed=False):
        ref = {"record_id": self.ids["a"]["record_id"]} if fixed else {"local_id": "a"}
        return [{"path": "", "source": {"level": 1, "anchors": [ref]}}]

    def anchor(self, name):
        return {"local_id": name, "kind": "anchor", "data": {"clause": {"record_id": self.clause["record_id"]}, "quote": self.text}, "evidence": []}

    def subject(self, name, display):
        return {"local_id": name, "kind": "node", "data": {"node_kind": "subject", "canonical_name": display, "identifiers": [{"scheme": "地址", "value": "示例地址"}]}, "evidence": self.ev()}

    def doc(self, records, phase="correction", **extra):
        return {"format_version": 1, "case_id": self.initial["case_id"], "vocabulary_hash": self.initial["vocabulary_hash"], "submitted_by": "regression-example",
                "phase": phase, "covered_clauses": [], "records": records, "issues": [], **extra}

    def relation(self, identifier, natures=("obligor", "recipient"), labels=None):
        return {"local_id": identifier, "kind": "relation", "data": {"relation_kind": "party", "unit_id": self.unit,
                "parties": [{"subject": {"object_id": self.ids[p]["object_id"]}, "nature": nature, "functional_labels": labels or []} for p, nature in zip(("p", "q"), natures)]}, "evidence": self.ev(fixed=True)}

    def detail(self, identifier, owner, slot, value):
        return {"local_id": identifier, "kind": "detail", "data": {"owner": {"local_id": owner}, "slot_id": slot, "value": value}, "evidence": self.ev(fixed=True)}

    def roundtrip(self, document):
        input_file = self.put("submissions/example.json", document)
        argv = [sys.executable, "-B", "-m", "legal.case_cli", "write", "--db", str(self.db), "--input", str(input_file)]
        cli_cwd = self.root if os.environ.get("LEGAL_RESOURCE_ROOT") else SRC
        cli_env = dict(os.environ)
        if os.environ.get("LEGAL_RESOURCE_ROOT"):
            cli_env.pop("PYTHONPATH", None)
        first = subprocess.run(argv, cwd=cli_cwd, env=cli_env, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        receipt = json.loads(first.stdout)
        replay_env = cli_env if os.environ.get("LEGAL_RESOURCE_ROOT") else {**os.environ, "PYTHONPATH": str(SRC)}
        replay = subprocess.run(argv, cwd=self.root, env=replay_env, capture_output=True, text=True)
        self.assertEqual(replay.returncode, 0, replay.stdout + replay.stderr)
        self.assertTrue(json.loads(replay.stdout)["replayed"])
        result = subprocess.run([sys.executable, "-B", "-m", "legal.case_cli", "query", "--db", str(self.db), "--view", "records", "--limit", "1000"], cwd=cli_cwd, env=cli_env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        items = {item["object_id"]: item for item in json.loads(result.stdout)["items"]}
        self.put("write-receipt.json", receipt)
        self.put("replay-receipt.json", json.loads(replay.stdout))
        self.put("query.json", json.loads(result.stdout))
        return receipt, items


class ModelingExamples(ExampleFixture):
    def test_correct_protection_direction_and_monthly_text(self):
        text = "甲每月25日提出月度申请，乙在同月30日批准付款安排。"
        records = [self.relation("limit", ("protected_party", "restricted_party")), self.relation("payment"),
                   self.detail("monthly", "payment", self.text_slot, {"form": "text", "surface": text})]
        receipt, items = self.roundtrip(self.doc(records))
        limit = items[receipt["id_map"]["limit"]["object_id"]]["data"]
        self.assertEqual([party["nature"] for party in limit["parties"]], ["protected_party", "restricted_party"])
        self.assertEqual(items[receipt["id_map"]["monthly"]["object_id"]]["data"]["value"], {"form": "text", "surface": text})

    def test_package_conditions_and_duration(self):
        records = []
        for package, event in (("1", "e1"), ("2", "e2")):
            relation = "r" + package
            records.extend([self.relation(relation, labels=["包" + package]),
                            self.detail("c" + package, relation, self.condition_slot, {"form": "condition", "operator": "event", "event": {"object_id": self.ids[event]["object_id"]}}),
                            self.detail("t" + package, relation, self.time_slot, {"form": "time", "kind": "duration", "length": {"form": "quantity", "amount": "24", "unit": "month"}, "boundary_text": "从该包验收起持续24个月"})])
        receipt, items = self.roundtrip(self.doc(records))
        for package, event in (("1", "e1"), ("2", "e2")):
            condition = items[receipt["id_map"]["c" + package]["object_id"]]["data"]["value"]
            self.assertEqual(condition["event"]["object_id"], self.ids[event]["object_id"])
            self.assertEqual(items[receipt["id_map"]["t" + package]["object_id"]]["data"]["value"]["kind"], "duration")

    def test_future_quantity_condition_uses_complete_event_without_null(self):
        relation = self.relation("adjustment", ("power_holder", "power_subject"))
        detail = self.detail("trigger", "adjustment", self.condition_slot, {"form": "condition", "operator": "event", "event": {"object_id": self.ids["increase"]["object_id"]}})
        receipt, items = self.roundtrip(self.doc([relation, detail]))
        value = items[receipt["id_map"]["trigger"]["object_id"]]["data"]["value"]
        event = items[value["event"]["object_id"]]["data"]
        self.assertEqual(event["description"], "原水参数变化导致处理产品用量增加超过10%，作为甲请求乙调价的条件；未断言已实际发生。")
        self.assertNotIn('"amount": null', json.dumps(value))

    def plans(self):
        groups = self.root / "groups/0001"
        group(self.db, groups)
        return [{"task_id": "0003-extraction", "unit_id": self.unit, "responsible_clauses": [self.clause], "context_clauses": [],
                 "group_file": str(groups / f"unit-{self.unit}.json"), "output_file": str(self.root / "submissions/0003-extraction.json")}]

    def test_task_inputs_are_complete_and_formal(self):
        result = export_extraction_tasks(self.db, self.plans(), self.root / "tasks/0003", RESOURCE_ROOT)
        task = result["tasks"][0]
        self.assertEqual(set(task), {"format_version", "task_id", "unit_id", "responsible_clauses", "context_clauses", "input_files", "output_file"})
        events = json.loads((self.root / "tasks/0003/events.json").read_text())["items"]
        self.assertEqual(len(events), 3)
        self.assertTrue(all(item["data"]["description"] and item["evidence"] and item["provenance"] for item in events))
        nodes = json.loads((self.root / "tasks/0003/shared-objects.json").read_text())["items"]
        self.assertTrue(any(item["data"].get("identifiers") for item in nodes))
        vocab = json.loads((self.root / "tasks/0003/frozen-vocabulary.json").read_text())["items"][0]
        self.assertIn("description", vocab["units"][0])
        self.assertEqual((self.root / "tasks/0003/extraction.md").read_bytes(), (RESOURCE_ROOT / "skills/legal-case/references/extraction.md").read_bytes())

    def test_task_overlap_and_stale_versions_are_rejected(self):
        plans = self.plans()
        duplicate = copy.deepcopy(plans[0]); duplicate.update(task_id="0004-extraction", output_file=str(self.root / "submissions/0004-extraction.json"))
        with self.assertRaises(Invalid) as caught:
            export_extraction_tasks(self.db, plans + [duplicate], self.root / "tasks/0003", RESOURCE_ROOT)
        self.assertEqual(caught.exception.code, "COVERAGE_INVALID")
        self.assertFalse((self.root / "tasks/0003").exists())
        plans[0]["responsible_clauses"][0]["record_id"] = new_id()
        with self.assertRaises(Invalid) as caught:
            export_extraction_tasks(self.db, plans, self.root / "tasks/0003", RESOURCE_ROOT)
        self.assertEqual(caught.exception.code, "STALE_REVISION")

    def test_stale_group_text_and_incomplete_responsibility_are_rejected(self):
        plans = self.plans()
        path = Path(plans[0]["group_file"])
        original = path.read_bytes()
        document = json.loads(original)
        document["clauses"][0]["text"] += "伪造内容"
        path.write_text(json.dumps(document, ensure_ascii=False))
        with self.assertRaises(Invalid) as caught:
            export_extraction_tasks(self.db, plans, self.root / "tasks/0003", RESOURCE_ROOT)
        self.assertEqual(caught.exception.code, "STALE_REVISION")
        path.write_bytes(original)
        with self.assertRaises(Invalid) as caught:
            export_extraction_tasks(self.db, plans, self.root / "tasks/0003", RESOURCE_ROOT, clause_ids=[])
        self.assertEqual(caught.exception.code, "COVERAGE_INVALID")
        self.assertFalse((self.root / "tasks/0003").exists())

    def second_clause(self):
        source = self.root / "second.txt"
        source.write_text("第二条 第二份材料规定付款。\n")
        metadata = self.put("second-metadata.json", {"name": "第二份测试材料", "media_type": "text/plain", "conversion_method": "identity", "converter_version": "test.1", "anomalies": []})
        registered = register(self.db, source, source, metadata)
        ref = split(self.db, registered["text_version"]["object_id"])["clauses"][0]
        item = query(self.db, {"object": ref["object_id"]})["items"][0]
        data = copy.deepcopy(item["data"])
        data.update(tags=[self.unit], classification="ordinary")
        receipt = write(self.db, self.doc([
            {"local_id": "second_anchor", "kind": "anchor", "data": {"clause": {"record_id": item["record_id"]}, "quote": source.read_text()}, "evidence": []},
            {"local_id": "second", "kind": "clause", "object_id": item["object_id"], "previous_record_id": item["record_id"], "data": data,
             "evidence": [{"path": "", "source": {"level": 1, "anchors": [{"local_id": "second_anchor"}]}}]},
        ], "tagging"))
        return {key: receipt["id_map"]["second"][key] for key in ("object_id", "record_id")}

    def test_task_union_must_cover_every_selected_clause(self):
        second = self.second_clause()
        plans = self.plans()
        with self.assertRaises(Invalid) as caught:
            export_extraction_tasks(self.db, plans, self.root / "tasks/0003", RESOURCE_ROOT)
        self.assertEqual(caught.exception.code, "COVERAGE_INVALID")
        self.assertFalse((self.root / "tasks/0003").exists())
        plans[0]["responsible_clauses"].append(second)
        result = export_extraction_tasks(self.db, plans, self.root / "tasks/0003", RESOURCE_ROOT)
        self.assertEqual(result["tasks"][0]["responsible_clauses"], [self.clause, second])

    def test_group_material_text_and_classification_are_verified(self):
        plans = self.plans()
        path = Path(plans[0]["group_file"])
        original = path.read_bytes()
        for field, value, code in (("material_id", new_id(), "STALE_REVISION"), ("text_version_id", new_id(), "STALE_REVISION"),
                                   ("context_clauses", None, "INVALID_ARGUMENT")):
            with self.subTest(field=field):
                document = json.loads(original)
                document["clauses"][0][field] = value
                path.write_text(json.dumps(document))
                with self.assertRaises(Invalid) as caught:
                    export_extraction_tasks(self.db, plans, self.root / "tasks/0003", RESOURCE_ROOT)
                self.assertEqual(caught.exception.code, code)
        document = json.loads(original)
        document["classification"] = "no_content"
        path.write_text(json.dumps(document))
        with self.assertRaises(Invalid) as caught:
            export_extraction_tasks(self.db, plans, self.root / "tasks/0003", RESOURCE_ROOT)
        self.assertEqual(caught.exception.code, "INVALID_ARGUMENT")
        path.write_bytes(original)

    def test_task_and_group_filename_collisions_are_rejected(self):
        second = self.second_clause()
        first = self.plans()[0]
        for first_id, second_id in (("item-group", "item"), ("item", "item-group")):
            with self.subTest(first=first_id):
                a, b = copy.deepcopy(first), copy.deepcopy(first)
                a.update(task_id=first_id, output_file=str(self.root / "submissions/a.json"))
                b.update(task_id=second_id, responsible_clauses=[second], output_file=str(self.root / "submissions/b.json"))
                with self.assertRaises(Invalid) as caught:
                    export_extraction_tasks(self.db, [a, b], self.root / "tasks/0003", RESOURCE_ROOT)
                self.assertEqual(caught.exception.code, "INVALID_ARGUMENT")
                self.assertFalse((self.root / "tasks/0003").exists())

    def test_partial_publication_is_removed_without_writing_database(self):
        plans = self.plans()
        before = self.db.read_bytes()
        calls = 0
        def fail_third(path, data):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise Invalid("FILE_ERROR", str(path), "simulated write failure")
            return exclusive_write(path, data)
        with patch("legal.handoff.exclusive_write", side_effect=fail_third):
            with self.assertRaises(Invalid) as caught:
                export_extraction_tasks(self.db, plans, self.root / "tasks/0003", RESOURCE_ROOT)
        self.assertEqual(caught.exception.code, "FILE_ERROR")
        self.assertEqual(list((self.root / "tasks/0003").iterdir()), [])
        self.assertEqual(self.db.read_bytes(), before)
        self.assertFalse(Path(plans[0]["output_file"]).exists())

    def test_changed_snapshot_is_rejected_before_publication(self):
        plans = self.plans()
        for changed in ("case", "sequence"):
            with self.subTest(changed=changed):
                calls = 0
                def query_changed(database, options):
                    nonlocal calls
                    result = query(database, options)
                    if options.get("view") == "progress":
                        calls += 1
                        if calls == 2:
                            if changed == "case":
                                result["case_id"] = new_id()
                            else:
                                result["quality"]["current_sequence"] += 1
                    return result
                with patch("legal.handoff.query", side_effect=query_changed):
                    with self.assertRaises(Invalid) as caught:
                        export_extraction_tasks(self.db, plans, self.root / "tasks/0003", RESOURCE_ROOT)
                self.assertEqual(caught.exception.code, "STALE_REVISION")
                self.assertFalse((self.root / "tasks/0003").exists())

    def test_existing_outputs_and_invalid_input_formats_are_rejected(self):
        plans = self.plans()
        output = Path(plans[0]["output_file"])
        output.write_text("existing submission")
        with self.assertRaises(Invalid) as caught:
            export_extraction_tasks(self.db, plans, self.root / "tasks/0003", RESOURCE_ROOT)
        self.assertEqual(caught.exception.code, "FILE_EXISTS")
        self.assertEqual(output.read_text(), "existing submission")
        output.unlink()
        with self.assertRaises(Invalid) as caught:
            export_extraction_tasks(self.db, plans, self.root / "reports", RESOURCE_ROOT)
        self.assertEqual(caught.exception.code, "INVALID_ARGUMENT")
        with self.assertRaises(Invalid) as caught:
            export_extraction_tasks(self.db, plans, self.root / "tasks/0003", RESOURCE_ROOT, clause_ids=[{}])
        self.assertEqual(caught.exception.code, "INVALID_ARGUMENT")
        path = Path(plans[0]["group_file"])
        original = path.read_bytes()
        path.write_text('{"format_version":1,"format_version":1}')
        with self.assertRaises(Invalid) as caught:
            export_extraction_tasks(self.db, plans, self.root / "tasks/0003", RESOURCE_ROOT)
        self.assertEqual(caught.exception.code, "INVALID_JSON")
        path.write_bytes(original)

    def test_null_unit_tasks_accept_formal_classification_names(self):
        # Exercise enum transfer, not a legal finding about this fixture text.
        # The clause classification is "unmatched"; "unmatched_unit" is a
        # gap kind and must not be confused with the classification enum.
        for number, classification in enumerate(("unmatched", "no_content"), 2):
            with self.subTest(classification=classification):
                item = query(self.db, {"object": self.clause["object_id"]})["items"][0]
                data = copy.deepcopy(item["data"])
                data.update(tags=[], classification=classification)
                receipt = write(self.db, self.doc([{"local_id": "c", "kind": "clause", "object_id": item["object_id"],
                                "previous_record_id": item["record_id"], "data": data, "evidence": self.ev(fixed=True)}], "tagging"))
                self.clause = {key: receipt["id_map"]["c"][key] for key in ("object_id", "record_id")}
                groups = self.root / "groups" / f"{number:04d}"
                group(self.db, groups)
                task_id = f"{number:04d}-classification"
                plans = [{"task_id": task_id, "unit_id": None, "responsible_clauses": [self.clause], "context_clauses": [],
                          "group_file": str(groups / (classification + ".json")), "output_file": str(self.root / "submissions" / (task_id + ".json"))}]
                result = export_extraction_tasks(self.db, plans, self.root / "tasks" / f"{number:04d}", RESOURCE_ROOT)
                self.assertIsNone(result["tasks"][0]["unit_id"])
                copied = json.loads((self.root / "tasks" / f"{number:04d}" / (task_id + "-group.json")).read_text())
                self.assertEqual(copied["classification"], classification)

    def test_event_pages_and_empty_event_lists(self):
        # A handoff must retain every page, rather than the first 100 objects.
        records = [self.anchor("a")]
        for i in range(105):
            records.append({"local_id": f"event{i}", "kind": "node", "data": {"node_kind": "event", "name": f"事项{i}",
                            "description": "分页导出机制实例", "participants": [], "batch_or_stage": "测试"}, "evidence": self.ev()})
        write(self.db, self.doc(records))
        result = export_extraction_tasks(self.db, self.plans(), self.root / "tasks/0003", RESOURCE_ROOT)
        events = json.loads((self.root / "tasks/0003/events.json").read_text())["items"]
        self.assertEqual(len(events), 108)
        self.assertEqual(len({event["object_id"] for event in events}), 108)
        # Explicitly withdraw unused fixture events; do not invent placeholders.
        revoked = []
        for item in events:
            revoked.append({"local_id": "withdraw" + str(len(revoked)), "kind": "node", "object_id": item["object_id"], "previous_record_id": item["record_id"],
                            "status": "withdrawn", "withdrawal_reason": "测试空事件交接", "data": item["data"], "evidence": item["evidence"]})
        write(self.db, self.doc(revoked))
        result = export_extraction_tasks(self.db, self.plans_again(), self.root / "tasks/0004", RESOURCE_ROOT)
        self.assertEqual(json.loads((self.root / "tasks/0004/events.json").read_text())["items"], [])

    def plans_again(self):
        path = self.root / "groups/0001" / f"unit-{self.unit}.json"
        return [{"task_id": "0004-extraction", "unit_id": self.unit, "responsible_clauses": [self.clause], "context_clauses": [],
                 "group_file": str(path), "output_file": str(self.root / "submissions/0004-extraction.json")}]


class FrozenFixture(ExampleFixture):
    def vocabulary_document(self, document):
        path = os.environ.get("LEGAL_FROZEN_VOCABULARY")
        if not path:
            self.skipTest("set LEGAL_FROZEN_VOCABULARY to an external vocabulary fixture")
        document = json.loads(Path(path).read_text())
        self.frozen_units = {u["name"]: u["id"] for u in document["units"]}
        slots = {s["name"]: s["id"] for s in document["slots"]}
        self.unit = self.frozen_units["付款"]
        self.text_slot = slots["付款安排"]
        self.condition_slot = slots["适用条件"]
        self.time_slot = slots["时点或期间"]
        return document


class FrozenVocabularyExamples(FrozenFixture):
    def test_monthly_rule_in_existing_payment_arrangement(self):
        text = "甲每月25日提出月度申请，乙在同月30日批准付款安排。"
        receipt, items = self.roundtrip(self.doc([self.relation("payment"), self.detail("monthly", "payment", self.text_slot, {"form": "text", "surface": text})]))
        self.assertEqual(items[receipt["id_map"]["monthly"]["object_id"]]["data"]["value"], {"form": "text", "surface": text})

    def test_future_quantity_trigger_in_existing_change_unit(self):
        self.unit = self.frozen_units["变更"]
        receipt, items = self.roundtrip(self.doc([self.relation("adjustment", ("power_holder", "power_subject")),
                                                self.detail("trigger", "adjustment", self.condition_slot, {"form": "condition", "operator": "event", "event": {"object_id": self.ids["increase"]["object_id"]}})]))
        value = items[receipt["id_map"]["trigger"]["object_id"]]["data"]["value"]
        self.assertEqual(items[value["event"]["object_id"]]["data"]["description"], "原水参数变化导致处理产品用量增加超过10%，作为甲请求乙调价的条件；未断言已实际发生。")
        self.assertNotIn("amount", value)


class CandidatePriceFixture(FrozenFixture):
    """Test a proposed slot in a private snapshot; do not govern the global vocabulary."""

    def vocabulary_document(self, document):
        document = copy.deepcopy(super().vocabulary_document(document))
        self.price_slot = new_id()
        quantity = {"form": "quantity", "allowed_units": ["USD"]}
        document["slots"].append({"id": self.price_slot, "name": "候选价款明细", "description": "只用于验证待审定词表结构，不是已批准条目", "value_schema": {
            "type": "object", "fields": {"包": {"form": "text"}, "总价": quantity, "计价说明": {"form": "text"}, "组成": {"type": "list", "items": {
                "type": "object", "fields": {"类别": {"form": "text"}, "金额": quantity}, "required_fields": ["类别", "金额"]}}}, "required_fields": ["包", "总价", "组成"]}})
        document["assignments"].append({"unit_id": self.unit, "slot_id": self.price_slot})
        return document


class CandidatePriceExamples(CandidatePriceFixture):
    def test_package_prices_and_components_roundtrip(self):
        records = []
        expected = {}
        for package, total, amounts in (("1", "100", ("60", "20", "20")), ("2", "200", ("100", "40", "60"))):
            value = {"type": "object", "fields": {"包": {"form": "text", "surface": "包" + package},
                     "总价": {"form": "quantity", "amount": total, "unit": "USD"}, "组成": {"type": "list", "items": [
                         {"type": "object", "fields": {"类别": {"form": "text", "surface": category}, "金额": {"form": "quantity", "amount": amount, "unit": "USD"}}}
                         for category, amount in zip(("货物", "境外服务", "境内服务"), amounts)]}}}
            expected[package] = value
            records.extend([self.relation("r" + package, labels=["包" + package]), self.detail("price" + package, "r" + package, self.price_slot, value)])
        receipt, items = self.roundtrip(self.doc(records))
        for package in expected:
            item = items[receipt["id_map"]["price" + package]["object_id"]]
            self.assertEqual(item["data"]["value"], expected[package])
            self.assertEqual(items[item["data"]["owner"]["object_id"]]["data"]["parties"][0]["functional_labels"], ["包" + package])
        # Candidate schema is frozen only in this temporary test database.
        self.assertEqual(query(self.db, {"view": "vocabulary"})["items"][0]["hash"], self.initial["vocabulary_hash"])


class RealPriceExamples(CandidatePriceFixture):
    """A bounded example using the actual Markdown; not complete modeling."""

    def setUp(self):
        path = os.environ.get("LEGAL_CONTRACT_TEXT")
        if not path:
            self.skipTest("set LEGAL_CONTRACT_TEXT to the external Markdown fixture")
        self.temp = tempfile.TemporaryDirectory(prefix="legal-real-prices-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for folder in ("tasks", "submissions", "groups"):
            (self.root / folder).mkdir()
        self.db = self.root / "contract.sqlite"
        self.vocabulary = self.put("vocabulary.json", self.vocabulary_document(None))
        self.initial = initialize(self.db, self.vocabulary)
        original = self.root / "text.txt"
        original.write_bytes(Path(path).read_bytes())
        metadata = self.put("metadata.json", {"name": "真实 Markdown 价款实例", "media_type": "text/markdown", "conversion_method": "identity", "converter_version": "test.1", "anomalies": []})
        reg = register(self.db, original, original, metadata)
        split(self.db, reg["text_version"]["object_id"])
        ordered = sorted(query(self.db, {"view": "clauses", "limit": 100})["items"], key=lambda item: item["data"]["sequence"])
        appendix, front = ordered[-1], ordered[0]
        payment = next(item for item in ordered if item["data"]["original_number"] == "CLAUSE 10")
        self.clause = {key: appendix[key] for key in ("object_id", "record_id")}
        self.text = appendix["data"]["text"]
        records = [self.anchor("a")]
        for name, item in (("parties_anchor", front), ("payment_anchor", payment)):
            records.append({"local_id": name, "kind": "anchor", "data": {"clause": {"record_id": item["record_id"]}, "quote": item["data"]["text"]}, "evidence": []})
        for name, canonical in (("p", "Employer"), ("q", "Contractor")):
            records.append({"local_id": name, "kind": "node", "data": {"node_kind": "subject", "canonical_name": canonical},
                            "evidence": [{"path": "", "source": {"level": 1, "anchors": [{"local_id": "parties_anchor"}]}}]})
        receipt = write(self.db, self.doc(records, "preparation", overview={"text_versions": [{"object_id": reg["text_version"]["object_id"]}],
                         "body": "仅验证现有 Markdown 的价款表达：两包、整体税前总价、三类组成及另加VAT；不据此声称全文完成。", "authored_by": "test"}))
        self.ids = receipt["id_map"]

    def relation(self, identifier, natures=("obligor", "recipient"), labels=None):
        record = super().relation(identifier, natures, labels)
        record["evidence"] = [{"path": "", "source": {"level": 1, "anchors": [{"record_id": self.ids[name]["record_id"]}
                              for name in ("a", "parties_anchor", "payment_anchor")]}}]
        return record

    def test_actual_package_and_combined_prices_preserve_vat_and_difference(self):
        examples = (
            ("1", "Package 1 (Negage Water Supply System)", "92679072.00", ("64875350", "9267907", "18535815")),
            ("2", "Package 2 (Quimbele Water Supply System)", "36108121.00", ("25277920", "3609084", "7221116")),
        )
        records, expected = [], {}
        for identifier, package, total, amounts in examples:
            value = {"type": "object", "fields": {"包": {"form": "text", "surface": package},
                     "总价": {"form": "quantity", "amount": total, "unit": "USD"}, "计价说明": {"form": "text", "surface": "税前价款，另加VAT。"},
                     "组成": {"type": "list", "items": [{"type": "object", "fields": {"类别": {"form": "text", "surface": category},
                                "金额": {"form": "quantity", "amount": amount, "unit": "USD"}}}
                                for category, amount in zip(("Supply of Goods & Materials (Tangible equipment, piping, plants)",
                                                             "Offshore Services (Design, engineering, software, manuals)",
                                                             "Onshore Services (Civil works, installation, training, O&M assistance)"), amounts)]}}}
            expected[identifier] = value
            records.extend([self.relation("r" + identifier, labels=[package]), self.detail("price" + identifier, "r" + identifier, self.price_slot, value)])
        combined = {"type": "object", "fields": {"包": {"form": "text", "surface": "Total Combined Contract Price"},
                    "总价": {"form": "quantity", "amount": "128787193.00", "unit": "USD"}, "计价说明": {"form": "text", "surface": "税前总价，另加VAT。"},
                    "组成": {"type": "list", "items": [{"type": "object", "fields": {"类别": {"form": "text", "surface": package},
                               "金额": {"form": "quantity", "amount": total, "unit": "USD"}}} for _, package, total, _ in examples]}}}
        records.extend([self.relation("overall", labels=["两包整体"]), self.detail("overall_price", "overall", self.price_slot, combined)])
        receipt, items = self.roundtrip(self.doc(records))
        for identifier in expected:
            self.assertEqual(items[receipt["id_map"]["price" + identifier]["object_id"]]["data"]["value"], expected[identifier])
        self.assertEqual(items[receipt["id_map"]["overall_price"]["object_id"]]["data"]["value"], combined)
        self.assertEqual(sum(map(int, examples[1][3])), 36108120)
        self.assertEqual(expected["2"]["fields"]["总价"]["amount"], "36108121.00")
        self.put("price-review.json", {"package_2_component_sum": "36108120", "package_2_stated_total": "36108121.00", "difference_usd": "1.00",
                 "decision": "保留现有Markdown全部金额，不用加总推断擅改；税费和受损公式不补造。", "status": "candidate vocabulary only"})


if __name__ == "__main__":
    unittest.main()
