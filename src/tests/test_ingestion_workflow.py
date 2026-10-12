"""2026-10-12 text reception, input contracts and dispatch resource acceptance."""
import copy
import io
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from legal import __version__
from legal.formats import Invalid, InvalidBatch, digest
from legal import preprocessing as p
from legal.preprocess_cli import main
from legal.reader_helpers import read_json, write_json
from legal.initial_reading import export_initial_reading_tasks, export_initial_synthesis_task
from legal.storage import initialize, register, split

SRC = Path(__file__).resolve().parents[1]
EXAMPLES = SRC / "skills/legal-case/examples"


class TextReception(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="入库回归 空格-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.original = self.root / "合同.MD"
        self.raw = ('# 第一条 交付\r\n甲方向乙方交付“货物”。\r\n'
                    '| 字段 | 值 |\r\n| --- | --- |\r\n| 标识 | "\\😀e\u0301" |\r\n').encode("utf-8")
        self.original.write_bytes(self.raw)

    def error(self, code, fn, *args, path=None):
        with self.assertRaises(Invalid) as caught:
            fn(*args)
        self.assertEqual(caught.exception.code, code)
        if path is not None:
            self.assertEqual(caught.exception.path, path)
        return caught.exception

    def config(self, mode="ok"):
        config = self.root / (mode + ".json")
        write_json(config, {"format_version": 1, "argv": [sys.executable,
            str(SRC / "tests/fixtures/acceptance_converter_20260928.py"), mode, "{input}", "{output_dir}"]})
        return config

    def test_suffixes_bytes_hashes_metadata_without_process(self):
        with patch.object(p.subprocess, "run", side_effect=AssertionError("external process")):
            for i, suffix in enumerate((".txt", ".md", ".markdown", ".TXT", ".MD", ".MARKDOWN")):
                with self.subTest(suffix=suffix):
                    original = self.root / ("合同" + suffix)
                    original.write_bytes(self.raw)
                    receipt = p.convert(original, self.root / str(i))
                    self.assertEqual(Path(receipt["text"]).read_bytes(), self.raw)
                    self.assertEqual(receipt["original_hash"], digest(self.raw))
                    self.assertEqual(receipt["text_hash"], receipt["original_hash"])
                    self.assertEqual(read_json(receipt["metadata"]), {"name": original.name,
                        "media_type": "text/plain" if suffix.lower() == ".txt" else "text/markdown",
                        "conversion_method": "identity", "converter_version": "cogengine-legal/" + __version__, "anomalies": []})
                    self.assertEqual(set(receipt), {"ok", "input", "output_dir", "text", "metadata", "original_hash", "text_hash", "anomalies"})
                    self.assertEqual(sorted(f.name for f in Path(receipt["output_dir"]).iterdir()), ["metadata.json", "text.txt"])

    def test_register_split_conserves_original_full_text(self):
        receipt = p.convert(self.original, self.root / "converted")
        vocabulary = self.root / "vocabulary.json"
        write_json(vocabulary, {"format_version": 1, "units": [], "slots": [], "assignments": []})
        db = self.root / "contract.sqlite"
        initialize(db, vocabulary)
        material = register(db, receipt["input"], receipt["text"], receipt["metadata"])
        result = split(db, material["text_version"]["object_id"])
        from legal.query import query
        clauses = query(db, {"view": "clauses", "limit": 100})["items"]
        self.assertEqual("".join(c["data"]["text"] for c in sorted(clauses, key=lambda c: c["data"]["sequence"])), self.raw.decode("utf-8"))
        self.assertTrue(result["ok"])

    def test_empty_input_is_preserved_without_completion_claim(self):
        self.original.write_bytes(b"")
        receipt = p.convert(self.original, self.root / "empty")
        self.assertEqual(Path(receipt["text"]).read_bytes(), b"")
        self.assertNotIn("reading_completed", receipt)
        self.assertEqual(receipt["anomalies"], [])

    def test_invalid_utf8_bom_and_renamed_binary_are_rejected(self):
        for i, raw in enumerate((b"\xff", b"\xef\xbb\xbfhello", b"PK\x03\x04\xff\x00")):
            with self.subTest(raw=raw):
                self.original.write_bytes(raw)
                target = self.root / str(i)
                self.error("INVALID_ARGUMENT", p.convert, self.original, target, path="/arguments/input")
                self.assertFalse(target.exists())

    def test_nonempty_target_never_overwritten(self):
        target = self.root / "occupied"
        target.mkdir(); sentinel = target / "text.txt"; sentinel.write_bytes(b"old")
        self.error("FILE_EXISTS", p.convert, self.original, target)
        self.assertEqual(sentinel.read_bytes(), b"old")

    def test_second_publish_failure_cleans_first(self):
        target = self.root / "broken"; original_open = Path.open
        def broken(file, *args, **kwargs):
            if file == target / "metadata.json" and args and args[0] == "xb":
                raise OSError("metadata publish failure")
            return original_open(file, *args, **kwargs)
        with patch.object(Path, "open", broken):
            self.error("FILE_ERROR", p.convert, self.original, target)
        self.assertFalse((target / "text.txt").exists())
        self.assertFalse((target / "metadata.json").exists())

    def test_identity_staging_io_error_is_file_error(self):
        target = self.root / "staging-failure"
        original_write = Path.write_bytes
        def broken(file, data):
            if file.name == "metadata.json":
                raise OSError("staging I/O failure")
            return original_write(file, data)
        with patch.object(Path, "write_bytes", broken):
            self.error("FILE_ERROR", p.convert, self.original, target)
        self.assertFalse(target.exists())

    def test_cleanup_failure_is_reported_and_cli_exits_three(self):
        target = self.root / "residue"; original_open = Path.open; original_unlink = Path.unlink
        def broken(file, *args, **kwargs):
            if file == target / "metadata.json" and args and args[0] == "xb":
                raise OSError("publish failed")
            return original_open(file, *args, **kwargs)
        def no_cleanup(file, *args, **kwargs):
            if file == target / "text.txt":
                raise OSError("cleanup failed")
            return original_unlink(file, *args, **kwargs)
        with patch.object(Path, "open", broken), patch.object(Path, "unlink", no_cleanup), redirect_stdout(io.StringIO()) as output:
            exit_code = main(["--input", str(self.original), "--output-dir", str(target)])
        receipt = json.loads(output.getvalue())
        self.assertEqual(exit_code, 3)
        self.assertFalse(receipt["ok"])
        self.assertEqual(len(receipt["errors"]), 2)
        self.assertTrue(any("cleanup failed" in e["message"] for e in receipt["errors"]))
        self.assertTrue((target / "text.txt").exists())

    def test_original_changed_before_publish_rejected(self):
        target = self.root / "changed"; original_file_bytes = p.file_bytes; calls = 0
        def changed(path):
            nonlocal calls
            if Path(path) == self.original:
                calls += 1
                if calls == 2:
                    self.original.write_bytes(self.raw + b"changed")
            return original_file_bytes(path)
        with patch.object(p, "file_bytes", changed):
            self.error("ORIGINAL_CHANGED", p.convert, self.original, target)
        self.assertFalse(target.exists())

    def test_binary_suffix_missing_config_no_process_or_outputs(self):
        with patch.object(p.subprocess, "run", side_effect=AssertionError("process")):
            for i, suffix in enumerate((".pdf", ".docx", ".png", "")):
                original = self.root / ("binary" + suffix); original.write_bytes(b"binary")
                target = self.root / str(i)
                self.error("INVALID_ARGUMENT", p.convert, original, target, path="/arguments/converter-config")
                self.assertFalse(target.exists())

    def test_explicit_markdown_converter_wins_and_errors_do_not_fallback(self):
        result = p.convert(self.original, self.root / "external", self.config())
        self.assertEqual(read_json(result["metadata"])["converter_version"], "acceptance.1")
        for mode, code in (("fail", "CONVERTER_FAILED"), ("utf8", "CONVERTER_OUTPUT_INVALID"), ("missing", "CONVERTER_OUTPUT_INVALID")):
            target = self.root / mode
            self.error(code, p.convert, self.original, target, self.config(mode))
            self.assertFalse(target.exists())

    def test_missing_program_and_start_failure_keep_existing_errors(self):
        config = self.root / "missing.json"
        write_json(config, {"format_version": 1, "argv": [str(self.root / "no-program"), "{input}", "{output_dir}"]})
        self.error("INVALID_ARGUMENT", p.convert, self.original, self.root / "missing", config)
        config = self.config()
        with patch.object(p.subprocess, "run", side_effect=OSError("cannot launch")):
            self.error("FILE_ERROR", p.convert, self.original, self.root / "launch", config)

    def test_repeat_arguments_rejected_without_running(self):
        with patch.object(p.subprocess, "run", side_effect=AssertionError("process")), redirect_stdout(io.StringIO()) as out:
            code = main(["--input", str(self.original), "--input", str(self.original), "--output-dir", str(self.root / "output")])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(out.getvalue())["errors"][0]["path"], "/arguments/input")

    def test_fail_diagnostics_and_original_exit_are_preserved(self):
        fixture = self.root / "fail.py"
        fixture.write_text("import sys\nprint('complete stdout diagnostic')\nprint('complete stderr diagnostic', file=sys.stderr)\nsys.exit(9)\n")
        config = self.root / "fail-config.json"
        write_json(config, {"format_version": 1, "argv": [sys.executable, str(fixture), "{input}", "{output_dir}"]})
        result = subprocess.run([sys.executable, "-m", "legal.preprocess_cli", "--input", str(self.original),
            "--output-dir", str(self.root / "fail-output"), "--converter-config", str(config)], cwd=SRC, capture_output=True)
        self.assertEqual(result.returncode, 3)
        self.assertIn(b"complete stdout diagnostic", result.stderr)
        self.assertIn(b"complete stderr diagnostic", result.stderr)
        self.assertEqual(json.loads(result.stdout)["errors"][0]["converter_exit_code"], 9)


class FixedInputContracts(unittest.TestCase):
    def test_exact_vocabulary_and_shared_shapes_missing_is_not_empty(self):
        fixture = read_json(EXAMPLES / "fixture.json")
        self.assertTrue(fixture["vocabulary_snapshot"]["items"][0]["units"])
        vocab = fixture["synthesis_shared"]["vocabulary"]["items"][0]
        for field in ("units", "slots", "assignments", "hash"):
            self.assertEqual(vocab[field], fixture["vocabulary_snapshot"]["items"][0][field])
        empty = copy.deepcopy(vocab); empty["units"] = []
        self.assertEqual(empty["units"], [])
        missing = copy.deepcopy(vocab); del missing["units"]
        with self.assertRaises(KeyError):
            missing["units"]
        with self.assertRaises(KeyError):
            {"source": vocab}["units"]
        with self.assertRaises(IndexError):
            {"items": []}["items"][0]
        shared = fixture["synthesis_shared"]
        self.assertEqual(shared["events"]["items"], [])
        self.assertEqual(shared["overview"]["items"], [])
        event = copy.deepcopy(fixture["snapshot"]["items"][0])
        event["kind"] = "node"
        event["data"] = {"node_kind": "event", "name": "交付货物", "description": "乙方交付货物"}
        shared["events"]["items"] = [event]
        self.assertIn("evidence", shared["events"]["items"][0])
        self.assertIn("provenance", shared["events"]["items"][0])
        self.assertNotIn("evidence", shared["events"]["items"][0]["data"])

    def test_batch_example_only_organizes_data_preserving_exact_quotes(self):
        build = runpy.run_path(str(EXAMPLES / "quote_requests.py"))["build_many"]
        chosen = [("a", "fixed-record", '"\\直\'弯’\r\n😀e\u0301'), ("a", "missing-version", "aa")]
        # Even repeated IDs and missing versions remain data for the real helper.
        result = build(chosen_quotes=chosen)
        self.assertEqual(result, [{"local_id": i, "clause_record_id": r, "quote": q} for i, r, q in chosen])

    def test_five_segments_only_reader_resources_and_no_template_rereading(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); vocabulary = root / "vocabulary.json"
            write_json(vocabulary, {"format_version": 1, "units": [], "slots": [], "assignments": []})
            db = root / "contract.sqlite"; initialize(db, vocabulary)
            original = root / "contract.md"
            original.write_bytes("".join(f"# 第{i}条 交付\r\n甲方向乙方交付第{i}批货物。\r\n" for i in range(1, 6)).encode())
            converted = p.convert(original, root / "converted")
            material = register(db, original, converted["text"], converted["metadata"])
            split(db, material["text_version"]["object_id"]); (root / "submissions").mkdir()
            exported = export_initial_reading_tasks(db, root / "tasks/reading", SRC, root / "submissions/preparation.json", target_chars=1)
            self.assertEqual(len(exported["tasks"]), 5)
            for task in exported["tasks"]:
                self.assertFalse(any("templates/" in name or "/examples/" in name for name in task["input_files"]))
                self.assertTrue(all(w["file"] in task["input_files"] for w in task["windows"]))
                Path(task["output_file"]).write_text("阅读范围：主读范围全部已读，无未读/截断。\n")
            summary = export_initial_synthesis_task(db, exported["manifest_file"], root / "tasks/reading/synthesis.json")
            self.assertFalse(any("templates/" in name for name in summary["input_files"]))
            self.assertFalse(any(name.endswith("tagging.py") or name.endswith("extraction.py") for name in summary["input_files"]))
            self.assertTrue(all(Path(task["output_file"]).as_posix() in summary["input_files"] for task in exported["tasks"]))


if __name__ == "__main__":
    unittest.main()
