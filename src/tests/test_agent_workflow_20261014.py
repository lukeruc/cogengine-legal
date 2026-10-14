"""W01-W18 configuration, dual handoff and fixed construction regression."""
import copy
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from legal.formats import Invalid, InvalidBatch, digest, exclusive_write, new_id, read_json
from legal import reader_helpers as h
from legal.storage import initialize, register, split
from legal.model import write
from legal.query import query
from legal.preprocessing import convert
from legal.task_preparation import prepare, workspace_selection, prepare_case
from legal.task_completion import complete, main as complete_main
from legal.task_files import publish
from legal.vocabulary import load, vocabulary_hash, apply_change, save
from workflow_inputs import reports

SRC = Path(__file__).resolve().parents[1]


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="工作流 中文 space-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.install = self.root / "install"
        (self.install / "vocabularies").mkdir(parents=True)
        self.workspace = self.root / "会话目录"; self.workspace.mkdir()
        self.other = self.root / "其他工作区"; self.other.mkdir()
        self.contract_root = self.root / "contracts"
        self.unit = new_id()
        self.vocab = self.root / "词表 a.json"
        h.write_json(self.vocab, {"format_version": 1, "units": [{"id": self.unit, "name": "交付", "description": "货物交付及相关安排"}],
                                 "slots": [], "assignments": []})
        self.second = self.root / "词表 b.json"; self.second.write_bytes(self.vocab.read_bytes())
        self.list = self.install / "vocabularies/workspace.txt"
        self.list.write_bytes((str(self.vocab) + "\r\n\r\n" + str(self.second) + "\r\n").encode())
        self.config = {"format_version": 1, "workspaces": [{"workspace_root": str(self.workspace),
                       "contract_root": str(self.contract_root), "vocabulary_list": str(self.list)}]}
        h.write_json(self.install / "workspaces.json", self.config)

    def bad(self, code, fn, *args, **kwargs):
        with self.assertRaises((Invalid, InvalidBatch)) as caught:
            fn(*args, **kwargs)
        items = [caught.exception.item()] if isinstance(caught.exception, Invalid) else caught.exception.items
        self.assertIn(code, [i["code"] for i in items])
        return items

    def contract(self, chars=20000):
        contract = self.root / "contract"
        contract.mkdir()
        for name in ("tasks", "submissions", "groups"):
            (contract / name).mkdir()
        db = contract / "contract.sqlite"
        self.identity = initialize(db, self.vocab)
        original = contract / "original.md"
        original.write_bytes('# 第一条 主体\r\n甲方为采购人，乙方为供货人。\r\n# 第二条 交付\r\n乙方应交付货物。\r\n# 第三条 付款\r\n甲方应在交付后支付100元；附件一未提供。\r\n'.encode())
        received = convert(original, contract / "converted")
        material = register(db, original, received["text"], received["metadata"])
        split(db, material["text_version"]["object_id"])
        self.text_id = material["text_version"]["object_id"]
        context = contract / "tasks/context.md"; context.write_text("对已提供的虚构合同做完整建模，缺材料如实报告。")
        self.input = {"format_version": 1, "db_path": str(db), "output_dir": str(contract / "tasks/reading"),
                      "task_context_file": str(context), "preparation_files": {
                      "records": str(contract / "submissions/0001-records.json"),
                      "overview": str(contract / "submissions/0002-overview.json")}, "target_chars": chars, "window_chars": 9}
        exported = prepare("reading", self.input, SRC)
        self.manifest = read_json(exported["result"]["manifest_file"])
        self.db, self.contract_dir = db, contract
        return exported

    def synthesize(self, output="synthesis"):
        for t in self.manifest["tasks"]:
            Path(t["output_file"]).write_text("阅读范围：已读分配主责全部窗口，无未读/截断。\n本段线索：附件一未提供。\n")
        return prepare("synthesis", {"format_version": 1, "db_path": str(self.db),
            "manifest_file": str(self.contract_dir / "tasks/reading/manifest.json"),
            "output_dir": str(self.contract_dir / ("tasks/" + output)), "reader_reports": reports(self.manifest)}, SRC)


class WorkspaceTests(Fixture):
    def case_input(self):
        material = self.root / "原件.md"; material.write_text("# 第一条\n甲方交付。")
        return {"format_version": 1, "runtime_file": str(self.install / "runtime.json"), "workspace_root": str(self.workspace),
                "materials": [{"path": str(material)}]}

    def test_W05_missing_configuration_before_directory_creation(self):
        data = self.case_input()
        (self.install / "workspaces.json").unlink()
        fake = {"runtime": lambda _: {"result": {"workspace_root": str(self.workspace)}}}
        with patch("legal.task_preparation.runpy.run_path", return_value=fake), patch.object(sys, "prefix", str(self.install / ".venv")):
            self.bad("FILE_ERROR", prepare_case, data, self.install)
        self.assertFalse(self.contract_root.exists())

    def test_W06_exclusive_collision_copy_hash_and_mid_copy_failure(self):
        data = self.case_input()
        fake = {"runtime": lambda _: {"result": {"workspace_root": str(self.workspace)}}}
        clock = unittest.mock.Mock()
        clock.now.return_value = datetime(2026, 10, 14, 0, 0, 0, tzinfo=timezone.utc)
        self.contract_root.mkdir()
        old = self.contract_root / "contract-20261014T000000Z"; old.mkdir(); (old / "keep").write_text("keep")
        with patch("legal.task_preparation.runpy.run_path", return_value=fake), patch.object(sys, "prefix", str(self.install / ".venv")), patch("legal.task_preparation.datetime", clock):
            result = prepare_case(data, self.install)
            self.assertTrue(result["result"]["contract_dir"].endswith("-02"))
            for c in result["result"]["copied"]:
                self.assertEqual(digest(Path(c["target"]).read_bytes()), c["sha256"])
                self.assertEqual(Path(c["target"]).read_bytes(), Path(c["source"]).read_bytes())
            calls = 0
            def fault(path, content):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise Invalid("FILE_ERROR", str(path), "copy fault")
                exclusive_write(path, content)
            with patch("legal.task_preparation.exclusive_write", side_effect=fault):
                self.bad("FILE_ERROR", prepare_case, data, self.install)
        self.assertFalse((self.contract_root / "contract-20261014T000000Z-03").exists())
        self.assertEqual((old / "keep").read_text(), "keep")

    def test_converter_code_reused_assets_copy_and_config_resolution(self):
        data = self.case_input()
        converter_dir = self.root / "converter"; converter_dir.mkdir()
        code = converter_dir / "adapter.py"; code.write_text("# fixture")
        asset = converter_dir / "layout.txt"; asset.write_text("fixture layout")
        config = converter_dir / "config.json"
        config.write_text(json.dumps({"format_version": 1, "argv": [sys.executable, "./adapter.py", "./layout.txt", "{input}", "{output_dir}"]}))
        data["materials"][0]["converter_config"] = str(config)
        fake = {"runtime": lambda _: {"result": {"workspace_root": str(self.workspace)}}}
        with patch("legal.task_preparation.runpy.run_path", return_value=fake), patch.object(sys, "prefix", str(self.install / ".venv")):
            result = prepare_case(data, self.install)
        directory = Path(result["result"]["contract_dir"])
        copied_config = read_json(directory / "inputs/converters/001/0001/config.json")
        self.assertEqual(copied_config["argv"][1], str(code))
        self.assertEqual((directory / "inputs/converters/001/0001/layout.txt").read_bytes(), asset.read_bytes())
        self.assertFalse((directory / "inputs/converters/001/0001/adapter.py").exists())

    def test_W01_exact_session_workspace_not_contract_or_parent(self):
        self.assertEqual(workspace_selection(self.install, self.workspace)[0], self.vocab)
        self.bad("WORKSPACE_NOT_REGISTERED", workspace_selection, self.install, self.other)
        nested = self.workspace / "nested"; nested.mkdir()
        self.bad("WORKSPACE_NOT_REGISTERED", workspace_selection, self.install, nested)

    def test_W02_list_order_and_path_characters(self):
        self.list.write_bytes(("\r\n \r\n" + str(self.second) + "\r\n" + str(self.vocab) + "\r\n").encode())
        before = self.list.read_bytes()
        self.assertEqual(workspace_selection(self.install, self.workspace)[0], self.second)
        self.assertEqual(workspace_selection(self.install, self.workspace, self.vocab)[0], self.vocab)
        self.assertEqual(self.list.read_bytes(), before)
        # A final space is a legitimate path character, not whitespace to strip.
        spaced = self.root / "带尾空格.json "; spaced.write_bytes(self.vocab.read_bytes())
        self.list.write_bytes((str(spaced) + "\n").encode())
        self.assertEqual(workspace_selection(self.install, self.workspace)[0], spaced)

    def test_W03_duplicate_relative_comment_and_bad_default(self):
        for content in (str(self.vocab) + "\n" + str(self.vocab), "relative.json", "# comment", "~/a", '"/a"'):
            self.list.write_text(content)
            errors = self.bad("VOCABULARY_LIST_INVALID", workspace_selection, self.install, self.workspace)
            self.assertIn("/lines/", errors[0]["path"])
        missing = self.root / "missing.json"
        self.list.write_text(str(missing) + "\n" + str(self.second))
        self.bad("FILE_ERROR", workspace_selection, self.install, self.workspace)
        self.assertEqual(workspace_selection(self.install, self.workspace, self.second)[0], self.second)

    def test_config_strict_fields_duplicates_and_list_escape(self):
        for mutation in (lambda c: c.update(extra=1), lambda c: c["workspaces"].append(c["workspaces"][0]),
                         lambda c: c["workspaces"][0].update(vocabulary_list=str(self.list.parent.parent / "bad.txt"))):
            c = copy.deepcopy(self.config); mutation(c)
            (self.install / "workspaces.json").write_text(json.dumps(c))
            self.bad("WORKSPACE_CONFIG_INVALID", workspace_selection, self.install, self.workspace)

    def test_selected_only_and_unregistered(self):
        self.second.write_text("invalid vocabulary")
        self.assertEqual(workspace_selection(self.install, self.workspace)[0], self.vocab)
        self.bad("VOCABULARY_NOT_REGISTERED", workspace_selection, self.install, self.workspace, self.root / "draft.json")
        self.list.write_text("\n \n")
        self.bad("VOCABULARY_NOT_CONFIGURED", workspace_selection, self.install, self.workspace)

    def test_W04_governance_copy_source_and_registration_unchanged(self):
        before = self.vocab.read_bytes(), self.list.read_bytes()
        target = self.root / "governed.json"
        exclusive_write(target, before[0])
        current, _ = load(target)
        changed, result = apply_change(current, {"format_version": 1, "expected_hash": vocabulary_hash(current),
                  "operations": [{"action": "add", "kind": "unit", "local_id": "new", "entry": {"name": "付款", "description": "付款规定"}}]})
        save(target, changed)
        self.assertEqual((self.vocab.read_bytes(), self.list.read_bytes()), before)
        self.assertEqual(vocabulary_hash(load(target)[0]), result["after_hash"])
        self.list.write_text(str(self.second) + "\n")
        self.assertTrue(self.vocab.exists())


class HandoffTests(Fixture):
    def test_W07_reader_minimal_input_and_raw_window_roundtrip(self):
        exported = self.contract(chars=1)
        self.assertEqual(self.manifest["format_version"], 2)
        self.assertEqual(len(exported["result"]["tasks"]), 3)
        for task in self.manifest["tasks"]:
            self.assertEqual(task["role"], "reader")
            self.assertNotIn("preparation_file", task)
            self.assertFalse(any(Path(f).name in {"manifest.json", "vocabulary.json", "overview.json", "shared-objects.json", "data-formats.md"} for f in task["input_files"]))
            raw = "".join(Path(w["file"]).read_bytes().decode() for w in task["windows"])
            expected = "".join(Path(e["text_file"]).read_bytes().decode() for e in self.manifest["directory"] if e["object_id"] in {c["object_id"] for c in task["main_reading_clauses"]})
            self.assertEqual(raw, expected)
            body = Path(task["instructions_file"]).read_text()
            self.assertEqual(sum(body.count(s) for s in ("## 一、固定角色信息", "## 二、共享任务总体上下文", "## 三、个别任务要求")), 3)

    def test_W08_missing_blank_unread_and_incomplete_reports(self):
        self.contract(chars=1)
        base = {"format_version": 1, "db_path": str(self.db), "manifest_file": str(self.contract_dir / "tasks/reading/manifest.json"),
                "output_dir": str(self.contract_dir / "tasks/synthesis"), "reader_reports": reports(self.manifest)}
        self.bad("FILE_ERROR", prepare, "synthesis", base, SRC)
        for t in self.manifest["tasks"]:
            Path(t["output_file"]).write_text(" \n")
        self.bad("INVALID_ARGUMENT", prepare, "synthesis", base, SRC)
        self.assertFalse((self.contract_dir / "tasks/synthesis").exists())
        for t in self.manifest["tasks"]:
            Path(t["output_file"]).write_text("有效笔记")
        base = {"format_version": 1, "db_path": str(self.db), "manifest_file": str(self.contract_dir / "tasks/reading/manifest.json"),
                "output_dir": str(self.contract_dir / "tasks/synthesis"), "reader_reports": reports(self.manifest)}
        for mutate in (lambda x: x["reader_reports"].pop(), lambda x: x["reader_reports"][0]["read_ranges"].clear(),
                       lambda x: x["reader_reports"][0].update(unread_ranges=x["reader_reports"][0]["read_ranges"]),
                       lambda x: x["reader_reports"][0].update(issues={})):
            value = copy.deepcopy(base); mutate(value)
            self.bad("INVALID_ARGUMENT", prepare, "synthesis", value, SRC)
            self.assertFalse((self.contract_dir / "tasks/synthesis").exists())

    def test_W09_W10_dual_independent_purposes_and_single_reader_reuse(self):
        self.contract()
        exported = self.synthesize()
        tasks = [read_json(t["task_file"]) for t in exported["result"]["tasks"]]
        self.assertEqual([t["purpose"] for t in tasks], ["records", "overview"])
        self.assertEqual(tasks[0]["continue_reader_task_id"], self.manifest["tasks"][0]["task_id"])
        self.assertIsNone(tasks[1]["continue_reader_task_id"])
        self.assertFalse(any("data-formats" in p or "helper-tools" in p or "shared-identities" in p for p in tasks[1]["input_files"]))
        self.assertNotEqual(tasks[0]["binding_file"], tasks[1]["binding_file"])
        self.assertTrue(all(t["output_file"] not in other["input_files"] for t, other in ((tasks[0], tasks[1]), (tasks[1], tasks[0]))))
        shared = read_json(Path(tasks[0]["binding_file"]).parent / "shared-identities.json")
        self.assertEqual(shared["events"]["items"], [])
        self.assertEqual(shared["shared-objects"]["items"][0]["data"]["node_kind"], "contract")

    def test_W08_fixed_input_tampering_and_v1_manifest_rejected(self):
        self.contract()
        path = self.contract_dir / "tasks/reading/manifest.json"
        changed = copy.deepcopy(self.manifest); changed["format_version"] = 1
        path.write_text(json.dumps(changed))
        self.bad("UNSUPPORTED_VERSION", self.synthesize)
        path.write_text(json.dumps(self.manifest))
        Path(self.manifest["directory"][0]["text_file"]).write_text("changed")
        self.bad("STALE_REVISION", self.synthesize)

    def test_W11_W12_two_write_orders_and_independent_failure_replay(self):
        for order in (("records", "overview"), ("overview", "records")):
            with self.subTest(order=order):
                # Independent database copies preserve fixed record versions.
                if not hasattr(self, "db"):
                    self.contract()
                    exported = self.synthesize()
                    bindings = {t["purpose"]: t["binding_file"] for t in exported["result"]["tasks"]}
                    issues = self.contract_dir / "tasks/issues.json"; h.write_json(issues, [])
                    body = self.contract_dir / "tasks/body.txt"; body.write_bytes('材料范围：虚构。\r\n主体与称谓：甲乙。\r\n交易及履行结构：货物。\r\n关键安排：100元。\r\n共同定义与限定：交付后。\r\n未解决事项：附件一。'.encode())
                    records = self.contract_dir / "tasks/records.json"
                    clause = min(query(self.db, {"view": "clauses"})["items"], key=lambda c: c["data"]["sequence"])
                    h.write_json(records, [h.record(local_id="a", kind="anchor", data={"clause": {"record_id": clause["record_id"]}, "quote": "甲方"}, evidence=[]),
                        h.node(local_id="p", node_kind="subject", fields={"canonical_name": "甲方", "identifiers": []}, evidence=[h.evidence(path="", source=h.source(level=1, anchors=[{"local_id": "a"}]))])])
                    complete(bindings["records"], issues, [records])
                    complete(bindings["overview"], issues, body_file=body)
                    self.documents = {p: read_json(self.input["preparation_files"][p]) for p in ("records", "overview")}
                db = self.root / (order[0] + ".sqlite"); db.write_bytes(self.db.read_bytes())
                first = write(db, self.documents[order[0]])
                invalid = copy.deepcopy(self.documents[order[1]]); invalid["vocabulary_hash"] = "0" * 64
                before = db.read_bytes()
                self.bad("VOCABULARY_MISMATCH", write, db, invalid)
                self.assertEqual(db.read_bytes(), before)
                second = write(db, self.documents[order[1]])
                self.assertTrue(first["ok"] and second["ok"])
                replay = write(db, self.documents[order[0]])
                self.assertTrue(replay["replayed"])
                self.assertEqual(replay["submission_id"], first["submission_id"])
                self.assertEqual(query(db, {"view": "overview"})["items"][0]["body"], self.documents["overview"]["overview"]["body"])
                self.assertTrue(query(db, {"view": "progress"})["items"][0]["uncompleted_clauses"])

    def test_W14_tagger_background_exact_body_responsibility_and_fixed_fields(self):
        self.contract()
        body = '六栏目概要原样\r\n"\\😀e\u0301"\r\n'
        doc = h.header(format_version=1, case_id=self.identity["case_id"], vocabulary_hash=self.identity["vocabulary_hash"],
                       submitted_by="overview", phase="preparation", covered_clauses=[], issues=[],
                       overview={"text_versions": [{"object_id": self.text_id}], "body": body, "authored_by": "overview"})
        write(self.db, {**doc, "records": []})
        clauses = query(self.db, {"view": "clauses"})["items"]
        plan = {"task_id": "tagger-1", "responsible_clauses": [{"object_id": clauses[0]["object_id"], "record_id": clauses[0]["record_id"]}],
                "context_clauses": [], "output_file": str(self.contract_dir / "submissions/tagging.json")}
        data = {"format_version": 1, "db_path": str(self.db), "output_dir": str(self.contract_dir / "tasks/tagging"),
                "task_context_file": self.input["task_context_file"], "plans": [plan]}
        exported = prepare("tagging", data, SRC)
        task = read_json(exported["result"]["tasks"][0]["task_file"])
        text = Path(task["instructions_file"]).read_bytes().decode()
        self.assertIn(body, text)
        snapshot = read_json(self.contract_dir / "tasks/tagging/tagger-1-work/clauses.json")
        self.assertEqual(len(snapshot["items"]), 1)
        self.assertEqual(snapshot["items"][0], clauses[0])
        data["output_dir"] = str(self.contract_dir / "tasks/overlap")
        data["plans"].append({**plan, "task_id": "tagger-2", "output_file": str(self.contract_dir / "submissions/tagging2.json")})
        self.bad("INVALID_ARGUMENT", prepare, "tagging", data, SRC)
        self.assertFalse((self.contract_dir / "tasks/overlap").exists())

    def test_W17_completion_deferred_stale_predecessor_rejected_by_write(self):
        self.contract()
        clause = min(query(self.db, {"view": "clauses"})["items"], key=lambda c: c["data"]["sequence"])
        anchor = h.record(local_id="a", kind="anchor", data={"clause": {"record_id": clause["record_id"]},
                         "quote": clause["data"]["text"]}, evidence=[])
        ev = [h.evidence(path="", source=h.source(level=3, premises=[{"local_id": "a"}],
              explanation="按交付单元完整定义判断本条主体及交付背景。", asserted_by="tagger-1"))]
        revision = h.clause_revision(local_id="tag", clause=clause, tags=[self.unit], classification="ordinary", evidence=ev)
        records = self.contract_dir / "tasks/tagging-records.json"; h.write_json(records, [anchor, revision])
        issues = self.contract_dir / "tasks/tagging-issues.json"; h.write_json(issues, [])
        fixed = {"format_version": 1, "mode": "tagging", "case_id": self.identity["case_id"],
                 "vocabulary_hash": self.identity["vocabulary_hash"], "submitted_by": "tagger-1",
                 "output_file": str(self.contract_dir / "submissions/tagging1.json")}
        b1 = self.contract_dir / "tasks/tagging-binding1.json"; h.write_json(b1, fixed)
        complete(b1, issues, [records])
        write(self.db, read_json(fixed["output_file"]))
        fixed.update(output_file=str(self.contract_dir / "submissions/tagging-stale.json"), submitted_by="tagger-retry")
        b2 = self.contract_dir / "tasks/tagging-binding2.json"; h.write_json(b2, fixed)
        self.assertTrue(complete(b2, issues, [records])["ok"])
        before = self.db.read_bytes()
        self.bad("STALE_REVISION", write, self.db, read_json(fixed["output_file"]))
        self.assertEqual(self.db.read_bytes(), before)

    def test_shared_context_mutation_requires_explicit_new_handoff(self):
        self.contract()
        Path(self.input["task_context_file"]).write_text("silently changed")
        self.bad("STALE_REVISION", self.synthesize)
        self.assertFalse((self.contract_dir / "tasks/synthesis").exists())


class CompletionTests(Fixture):
    def test_bootstrap_error_from_separate_runpy_instance_is_structured(self):
        first = runpy.run_path(str(SRC / "scripts/prepare_task.py"))
        second = runpy.run_path(str(SRC / "scripts/prepare_task.py"))
        error = first["BootstrapError"]("FILE_ERROR", "/python", "broken runtime", "runtime.json")
        class Input:
            buffer = io.BytesIO(b'{"format_version":1}')
        from contextlib import redirect_stdout
        output = io.StringIO()
        with patch.object(sys, "argv", ["prepare_task.py", "case", "--input", "-"]), patch.object(sys, "stdin", Input()), \
             patch("legal.task_preparation.prepare", side_effect=error), redirect_stdout(output):
            code = second["main"]()
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output.getvalue())["errors"][0]["path"], "/python")

    def bound(self, mode="preparation_overview"):
        file = self.root / "binding.json"
        value = {"format_version": 1, "mode": mode, "case_id": new_id(), "vocabulary_hash": "a" * 64,
                 "submitted_by": "summarizer-2", "output_file": str(self.root / "submission.json")}
        if mode == "preparation_overview":
            value.update(overview_text_versions=[{"object_id": new_id()}], overview_authored_by="summarizer-2")
        file.write_text(json.dumps(value))
        self.issues = self.root / "issues.json"; self.issues.write_text("[]")
        self.body = self.root / "body.txt"; self.body.write_bytes(' 原文 "\\😀e\u0301"\r\n末尾 \r\n'.encode())
        self.records = self.root / "records.json"; self.records.write_text("[]")
        return file

    def test_W15_overview_exact_body_and_explicit_empty_issues(self):
        file = self.bound()
        complete(file, self.issues, body_file=self.body)
        doc = read_json(self.root / "submission.json")
        self.assertEqual(doc["overview"]["body"], self.body.read_bytes().decode())
        self.assertEqual(doc["records"], [])
        self.assertEqual(doc["issues"], [])
        self.assertEqual(doc["submitted_by"], "summarizer-2")

    def test_W15_all_modes_and_explicit_extraction_coverage(self):
        for mode in ("preparation_records", "tagging", "extraction"):
            with self.subTest(mode=mode):
                file = self.bound(mode)
                covered = self.root / "covered.json"; covered.write_text(json.dumps([{"object_id": new_id(), "record_id": new_id()}]))
                complete(file, self.issues, [self.records], covered_file=covered if mode == "extraction" else None)
                result = read_json(self.root / "submission.json")
                self.assertNotIn("overview", result)
                self.assertEqual(result["phase"], "preparation" if mode == "preparation_records" else mode)
                (self.root / "submission.json").unlink()

    def test_W16_missing_issues_coverage_bad_mode_unknown_version_existing_output(self):
        file = self.bound()
        self.bad("FILE_ERROR", complete, file, self.root / "missing.json", body_file=self.body)
        self.bad("INVALID_ARGUMENT", complete, file, self.issues, [self.records], self.body)
        value = read_json(file); value["format_version"] = 2; file.write_text(json.dumps(value))
        self.bad("UNSUPPORTED_VERSION", complete, file, self.issues, body_file=self.body)
        file = self.bound("extraction")
        self.bad("INVALID_ARGUMENT", complete, file, self.issues, [self.records])
        file = self.bound()
        complete(file, self.issues, body_file=self.body)
        before = (self.root / "submission.json").read_bytes()
        self.bad("FILE_EXISTS", complete, file, self.issues, body_file=self.body)
        self.assertEqual((self.root / "submission.json").read_bytes(), before)

    def test_repeated_unknown_output_cli_and_blank_body(self):
        file = self.bound()
        from contextlib import redirect_stdout
        for arguments in (["--binding", str(file), "--issues", str(self.issues), "--output", str(self.root / "other")],
                          ["--binding", str(file), "--binding", str(file), "--issues", str(self.issues)]):
            stream = io.StringIO()
            with redirect_stdout(stream):
                code = complete_main(arguments)
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(stream.getvalue())["scope"], "task_files")
        self.body.write_text(" \r\n")
        self.bad("INVALID_ARGUMENT", complete, file, self.issues, body_file=self.body)
        errors = self.bad("INVALID_ARGUMENT", complete, file, '["a"]', body_file=self.body)
        self.assertEqual(errors[0]["path"], "--issues")
        self.assertNotIn("file", errors[0])

    def test_output_failure_cleanup_reports_real_residual(self):
        target = self.root / "tasks/new"
        existing = self.root / "keep"; existing.write_text("keep")
        calls = 0
        def fail_second(path, data):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise Invalid("FILE_ERROR", str(path), "injected")
            exclusive_write(path, data)
        with patch("legal.task_files.exclusive_write", side_effect=fail_second):
            self.bad("FILE_ERROR", publish, target, {"a.txt": b"a", "b.txt": b"b"})
        self.assertFalse(target.exists())
        self.assertEqual(existing.read_text(), "keep")
        calls = 0
        with patch("legal.task_files.exclusive_write", side_effect=fail_second), patch.object(Path, "unlink", side_effect=OSError("cleanup denied")):
            with self.assertRaises(Invalid) as caught:
                publish(target, {"a.txt": b"a", "b.txt": b"b"})
        self.assertIn(str(target / "a.txt"), caught.exception.remaining_paths)


if __name__ == "__main__":
    unittest.main()
