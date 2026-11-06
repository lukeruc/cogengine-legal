"""Lossless frozen-file reading and the actual generated role handoffs."""
import base64
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout

from legal.context_reading import main, read_context
from legal.formats import Invalid, canonical, digest, new_id
from legal.group import group
from legal.handoff import export_extraction_tasks
from legal.query import query
from test_remediation_20261001 import ExampleFixture
from test_agent_workflow_20261014 import Fixture

SRC = Path(__file__).resolve().parents[1]


class ContextReading(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="共享资料 中文-")
        self.addCleanup(self.tmp.cleanup)
        self.file = Path(self.tmp.name) / "snapshot.json"
        self.case_id = new_id()

    def save(self, items):
        self.doc = {"case_id": self.case_id, "checked_sequence": 7, "items": items}
        self.file.write_bytes((json.dumps(self.doc, ensure_ascii=False, indent=2) + "\n").encode())
        self.sha = digest(self.file.read_bytes())

    def node(self, name="证书签发", stage="包一", kind="event"):
        data = {"node_kind": kind, "name": name, "description": "原文\"\\\r\n😀" * 250,
                "participants": [{"subject": {"object_id": new_id()}, "role": "签发方"}], "batch_or_stage": stage}
        return {"object_id": new_id(), "record_id": new_id(), "kind": "node", "status": "active", "data": data,
                "evidence": [{"path": "/description", "source": {"level": 1, "anchors": [{"record_id": new_id()}]}}],
                "provenance": [{"path": "/description", "anchors": [{"clause_record_id": new_id(), "quote": "完整依据",
                                 "start_offset": 123, "end_offset": 456}]}],
                "identity": {"resolution": {"canonical_id": new_id()}}, "extra_snapshot_field": [1, None, "保持"]}

    def read(self, operation, **options):
        return read_context(self.file, self.sha, operation, **options)

    def pages(self, operation, **options):
        cursor, parts, expected_start = None, [], 0
        while True:
            page = self.read(operation, cursor=cursor, max_chars=137, **options)
            self.assertEqual(page, self.read(operation, cursor=cursor, max_chars=137, **options))
            content = page["content"]
            self.assertEqual(content["start"], expected_start)
            self.assertEqual(len(content["text"]), content["end"] - content["start"])
            self.assertLessEqual(len(content["text"]), 137)
            parts.append(content["text"])
            expected_start = content["end"]
            cursor = page["next_cursor"]
            if cursor is None:
                self.assertEqual(expected_start, content["total_chars"])
                if len(parts) > 1:
                    self.assertFalse(content["complete"])
                break
        return json.loads("".join(parts))

    def bad(self, code, operation, **options):
        with self.assertRaises(Invalid) as caught:
            self.read(operation, **options)
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_same_names_distinct_identity_and_lossless_large_record(self):
        a, b, c = self.node(), self.node(stage="包二"), self.node(name="证书收到")
        self.save([c, a, b, copy.deepcopy(a)])
        catalog = self.pages("list")
        self.assertEqual({n["record_id"] for n in catalog}, {n["record_id"] for n in (a, b, c)})
        self.assertEqual(len(catalog), 3)
        entry = next(n for n in catalog if n["record_id"] == a["record_id"])
        self.assertEqual(entry["data"]["participants"], a["data"]["participants"])
        self.assertEqual(entry["source_positions"][0]["start_offset"], 123)
        self.assertEqual(self.pages("show", record_id=a["record_id"]), a)
        self.assertEqual(self.pages("list", kind="subject"), [])
        self.assertEqual(self.file.read_bytes().decode(), json.dumps(self.doc, ensure_ascii=False, indent=2) + "\n")

    def test_conflicting_versions_and_content_never_silently_selected(self):
        a = self.node()
        for change in ({"record_id": new_id()}, {"data": {**a["data"], "name": "changed"}}, {"object_id": new_id()}):
            with self.subTest(change=change):
                self.save([a, {**a, **change}])
                self.bad("SNAPSHOT_CONFLICT", "list")

    def test_long_catalog_fields_are_explicitly_deferred_and_sources_bounded(self):
        item = self.node(stage="很长的实际包描述" * 80)
        item["data"]["participants"] *= 12
        anchors = item["provenance"][0]["anchors"]
        anchors.extend({**anchors[0], "start_offset": i, "end_offset": i + 1} for i in range(30))
        self.save([item])
        entry = self.pages("list")[0]
        self.assertNotIn("batch_or_stage", entry["data"])
        self.assertNotIn("participants", entry["data"])
        self.assertEqual(set(entry["unexpanded_fields"]), {"/data/batch_or_stage", "/data/participants", "/provenance"})
        self.assertEqual(entry["source_position_count"], 31)
        self.assertEqual(len(entry["source_positions"]), 2)
        self.assertEqual(self.pages("show", record_id=item["record_id"]), item)

    def test_empty_missing_bad_wrappers_and_unknown_id(self):
        self.save([])
        self.assertEqual(self.pages("list"), [])
        self.bad("REFERENCE_NOT_FOUND", "show", record_id=new_id())
        self.bad("INVALID_ARGUMENT", "list", kind="unit")
        for value, path in (({"case_id": self.case_id, "checked_sequence": 7}, "/items"),
                            ({"case_id": self.case_id, "checked_sequence": 7, "items": None}, "/items")):
            self.file.write_bytes(canonical(value)); self.sha = digest(self.file.read_bytes())
            self.assertEqual(self.bad("INVALID_ARGUMENT", "list").path, path)
        a = self.node(); del a["evidence"]
        self.save([a])
        self.assertEqual(self.bad("INVALID_ARGUMENT", "list").path, "/items/0/evidence")

    def test_cursor_binding_replay_and_changed_budget(self):
        self.save([self.node()])
        page = self.read("list", max_chars=120)
        cursor = page["next_cursor"]
        self.assertIsNotNone(cursor)
        shorter = self.read("list", cursor=cursor, max_chars=40)
        longer = self.read("list", cursor=cursor, max_chars=80)
        self.assertEqual(shorter["content"]["start"], 120)
        self.assertTrue(longer["content"]["text"].startswith(shorter["content"]["text"]))
        self.bad("INVALID_CURSOR", "list", cursor=cursor, kind="event")
        self.bad("INVALID_CURSOR", "show", record_id=self.doc["items"][0]["record_id"], cursor=cursor)
        token = json.loads(base64.urlsafe_b64decode(cursor))
        for offset in (-1, True, page["content"]["total_chars"], "5"):
            token["offset"] = offset
            invalid = base64.urlsafe_b64encode(canonical(token)).decode()
            self.bad("INVALID_CURSOR", "list", cursor=invalid)
        self.bad("INVALID_CURSOR", "list", cursor="not a cursor")
        old_sha = self.sha
        self.file.write_bytes(self.file.read_bytes() + b"\n")
        self.bad("SNAPSHOT_CHANGED", "list", cursor=cursor)
        self.sha = digest(self.file.read_bytes())
        self.assertNotEqual(self.sha, old_sha)
        self.bad("INVALID_CURSOR", "list", cursor=cursor)

    def test_vocabulary_full_definitions_assignments_and_general_slots(self):
        u1, u2, s1, s2 = (new_id() for _ in range(4))
        vocab = {"format_version": 1, "hash": "a" * 64,
                 "units": [{"id": u, "name": "同名单元", "description": u, "aliases": ["原称"], "examples": ["例子"]} for u in (u2, u1)],
                 "slots": [{"id": s, "name": "同名槽", "description": "完整定义" * 200,
                            "value_schema": {"type": "object", "fields": {"期间": {"form": "time"}, "条件": {"form": "condition"}}},
                            "examples": ["原样"]} for s in (s2, s1)],
                 "assignments": [{"unit_id": u, "slot_id": s1} for u in (u1, u2)]}
        self.save([vocab])
        units = self.pages("list", kind="unit")
        self.assertEqual([u["item"] for u in units], vocab["units"])
        slots = self.pages("list", kind="slot")
        self.assertEqual([s["id"] for s in slots], [s2, s1])
        self.assertTrue(slots[0]["general"])
        self.assertFalse(slots[1]["general"])
        full = self.pages("show", kind="slot", item_id=s1)
        self.assertEqual(full, {"item": vocab["slots"][1], "assignments": vocab["assignments"]})
        self.assertEqual(self.read("list", kind="unit")["source"]["vocabulary_hash"], vocab["hash"])
        self.bad("REFERENCE_NOT_FOUND", "show", kind="slot", item_id=new_id())
        del vocab["slots"][0]["value_schema"]; self.save([vocab])
        self.assertEqual(self.bad("INVALID_ARGUMENT", "list", kind="slot").path, "/items/0/slots/0/value_schema")

    def test_empty_vocabulary_and_argument_errors(self):
        self.save([{"format_version": 1, "hash": "a" * 64, "units": [], "slots": [], "assignments": []}])
        self.assertEqual(self.pages("list", kind="unit"), [])
        self.assertEqual(self.pages("list", kind="slot"), [])
        for opts in ({"record_id": new_id()}, {"max_chars": True}, {"max_chars": 0}, {"max_chars": 60001}):
            self.bad("INVALID_ARGUMENT", "list", **opts)
        self.bad("INVALID_ARGUMENT", "show", kind="unit", item_id=new_id(), record_id=new_id())

    def test_command_errors_are_structured(self):
        self.save([])
        for args, status, code in ((["list", "--input", str(self.file), "--sha256", self.sha], 0, None),
                                   (["show", "--input", str(self.file), "--sha256", self.sha], 2, "INVALID_ARGUMENT"),
                                   (["list", "--input", str(self.file) + "missing", "--sha256", self.sha], 3, "FILE_ERROR"),
                                   (["list", "--unknown"], 2, "INVALID_ARGUMENT")):
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(args), status)
            result = json.loads(output.getvalue())
            if code:
                self.assertEqual(result["errors"][0]["code"], code)
            else:
                self.assertEqual(json.loads(result["content"]["text"]), [])


class ExtractionHandoff(ExampleFixture):
    def test_generated_commands_read_actual_snapshots_without_duplicate_event_source(self):
        directory = self.root / "groups/export"
        group(self.db, directory)
        plan = {"task_id": "0003-extraction", "unit_id": self.unit, "responsible_clauses": [self.clause],
                "context_clauses": [self.clause], "group_file": str(directory / f"unit-{self.unit}.json"),
                "output_file": str(self.root / "submissions/extraction.json")}
        context = self.root / "tasks/context.md"; context.write_text("测试合同")
        output = self.root / "tasks/extraction"
        exported = export_extraction_tasks(self.db, [plan], output, SRC, task_context_file=context)
        task = exported["tasks"][0]
        filenames = {Path(p).name for p in task["input_files"]}
        self.assertNotIn("events.json", filenames)
        self.assertNotIn("overview.json", filenames)
        # Compatible machine exports remain complete and separate from reading.
        self.assertEqual(len(json.loads((output / "events.json").read_text())["items"]), 3)
        original = query(self.db, {"view": "clauses"})["items"][0]["data"]["text"]
        self.assertEqual((output / "0003-extraction-clauses.md").read_text().count(original), 1)
        body = (output / "0003-extraction-instructions.md").read_text()
        commands = [json.loads(line.split("：", 1)[1]) for line in body.splitlines()
                    if line.startswith(("完整身份目录", "全部单元完整定义及归属", "全部槽目录及归属"))]
        self.assertEqual(len(commands), 3)
        for command in commands:
            self.assertTrue(Path(command[1]).is_file())
            with redirect_stdout(io.StringIO()) as buffer:
                self.assertEqual(main(command[2:]), 0)
            self.assertTrue(json.loads(buffer.getvalue())["ok"])


class SynthesisHandoff(Fixture):
    def test_current_nodes_are_the_only_shared_identity_input(self):
        self.contract(chars=1)
        exported = self.synthesize()
        tasks = [json.loads(Path(t["task_file"]).read_text()) for t in exported["result"]["tasks"]]
        self.assertTrue(all(t["continue_reader_task_id"] is None for t in tasks))
        inputs = {Path(p).name for p in tasks[0]["input_files"]}
        self.assertIn("shared-objects.json", inputs)
        self.assertNotIn("shared-identities.json", inputs)
        self.assertNotIn("events.json", inputs)
        self.assertNotIn("shared-objects.json", {Path(p).name for p in tasks[1]["input_files"]})
        source = Path(tasks[0]["binding_file"]).parent / "shared-objects.json"
        catalog = read_context(source, digest(source.read_bytes()), "list")
        self.assertEqual(len(json.loads(catalog["content"]["text"])), 1)


if __name__ == "__main__":
    unittest.main()
