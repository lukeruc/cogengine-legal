"""Verify installed delivery after removing its build source and README."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


SRC = Path(__file__).resolve().parents[1]
SKILLS = ("legal-case", "legal-vocab", "legal-preprocess", "legal-initialize")


class StandaloneInstallation(unittest.TestCase):
    def test_installed_delivery_without_source_or_readme(self):
        with tempfile.TemporaryDirectory(prefix="legal-install 独立运行-") as temporary:
            root = Path(temporary)
            source = root / "下载源码 source"
            install = root / "安装 install"
            work = root / "合同工作目录 work"
            host = root / "宿主 host" / "skills"
            source.mkdir()
            work.mkdir()
            host.mkdir(parents=True)
            for name in ("legal", "skills", "references"):
                shutil.copytree(SRC / name, source / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            (source / "scripts").mkdir()
            for name in ("build_release.py", "install_release.py", "verify_registration.py", "prepare_task.py"):
                shutil.copy2(SRC / "scripts" / name, source / "scripts" / name)
            for name in ("pyproject.toml", "README.md", "LICENSE"):
                shutil.copy2(SRC / name, source / name)
            converter = work / "converter.py"
            shutil.copy2(SRC / "tests/fixtures/acceptance_converter_20260928.py", converter)

            env = os.environ.copy()
            for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
                env.pop(key, None)
            env.update(PIP_NO_INDEX="1", PIP_DISABLE_PIP_VERSION_CHECK="1", PIP_NO_CACHE_DIR="1")

            def run(*argv):
                result = subprocess.run([str(arg) for arg in argv], cwd=work, env=env,
                                        capture_output=True, text=True, timeout=120)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                return result.stdout

            def receipt(*argv):
                result = json.loads(run(*argv))
                self.assertTrue(result["ok"], result)
                return result

            wheel_dir = root / "wheels"
            run(sys.executable, source / "scripts/build_release.py", "--output-dir", wheel_dir,
                "--python", sys.executable)
            wheels = list(wheel_dir.glob("*.whl"))
            self.assertEqual(len(wheels), 1)
            installed = receipt(sys.executable, source / "scripts/install_release.py",
                                "--install-root", install, "--python", sys.executable, "--wheel", wheels[0])
            self.assertEqual(installed["host_registration"], "pending")
            runtime = json.loads((install / "runtime.json").read_text(encoding="utf-8"))
            self.assertEqual(json.loads((install / "workspaces.json").read_text()), {"format_version": 1, "workspaces": []})
            registry = install / "vocabularies/custom.txt"
            registry.write_bytes((str(work / "vocabulary.json") + "\r\n\r\n").encode())
            configuration = install / "workspaces.json"
            configuration.write_text(json.dumps({"format_version": 1, "workspaces": [{"workspace_root": str(work),
                "contract_root": str(work / "contracts"), "vocabulary_list": str(registry)}]}, ensure_ascii=False))
            preserved = configuration.read_bytes(), registry.read_bytes()
            receipt(sys.executable, source / "scripts/install_release.py", "--install-root", install,
                    "--python", sys.executable, "--wheel", wheels[0], "--upgrade")
            self.assertEqual((configuration.read_bytes(), registry.read_bytes()), preserved)
            for name in SKILLS:
                (host / name).symlink_to(install / "skills" / name, target_is_directory=True)

            # Remove only this test's copied source and build artifacts. All further
            # subprocesses use installed files from an unrelated working directory.
            shutil.rmtree(source)
            shutil.rmtree(wheel_dir)
            (install / "README.md").unlink()
            self.assertFalse(source.exists())
            self.assertFalse((install / "README.md").exists())

            verify = [runtime["python"], install / "scripts/verify_registration.py", "--install-root", install]
            for name in SKILLS:
                verify.extend(("--skill", f"{name}={host / name / 'SKILL.md'}"))
            self.assertEqual(receipt(*verify)["host_registration"], "verified")

            for name in SKILLS:
                skill = host / name / "SKILL.md"
                body = skill.read_text(encoding="utf-8")
                snippet = re.search(r"^```python\n(.*?)^```", body, re.M | re.S).group(1)
                snippet = snippet.replace(f'"/host/skills/{name}/SKILL.md"', json.dumps(str(skill)))
                snippet = snippet.replace("/absolute/session/workspace", str(work))
                boot = json.loads(run(sys.executable, "-c", snippet))
                self.assertEqual(boot["result"]["install_root"], str(install))
                self.assertEqual(boot["result"]["workspace_root"], str(work))
                for relative in re.findall(r"`((?:\.\./)+[^`]+)`", body):
                    self.assertTrue((skill.resolve().parent / relative).exists(), (name, relative))

            probe = run(runtime["python"], "-c",
                        "import json,legal,pathlib,sys; "
                        "p=pathlib.Path(legal.__file__); "
                        "print(json.dumps([str(p),sys.prefix,legal.__version__,"
                        "(p.parent/'schema.sql').is_file(),(p.parent/'config/units.v1.json').is_file()]))")
            module, prefix, version, schema, units = json.loads(probe)
            self.assertTrue(Path(module).resolve().is_relative_to((install / ".venv").resolve()))
            self.assertEqual(Path(prefix).resolve(), (install / ".venv").resolve())
            self.assertEqual(version, runtime["release_version"])
            self.assertTrue(schema and units)

            commands = runtime["commands"]
            for command in commands.values():
                run(command, "--help")
            vocabulary = work / "vocabulary.json"
            database = work / "contract.sqlite"
            receipt(commands["legal-vocab"], "init", "--vocabulary", vocabulary)
            installed_case = receipt(commands["legal-case"], "init", "--db", database, "--vocabulary", vocabulary)
            receipt(commands["legal-case"], "query", "--db", database, "--view", "progress")
            self.assertTrue(database.is_file())

            original = work / "合同原文.txt"
            original.write_text("第一条 甲方向乙方交付货物。\n", encoding="utf-8")
            direct = receipt(commands["legal-preprocess"], "--input", original,
                             "--output-dir", work / "纯文本 direct")
            self.assertEqual(Path(direct["text"]).read_bytes(), original.read_bytes())
            self.assertEqual(direct["original_hash"], direct["text_hash"])
            self.assertEqual(json.loads(Path(direct["metadata"]).read_bytes())["converter_version"],
                             "cogengine-legal/" + version)
            markdown = work / "合同 标记.MARKDOWN"
            markdown.write_bytes('# 第一条\r\n| 字段 | "\\😀e\u0301" |\r\n'.encode("utf-8"))
            md_receipt = receipt(commands["legal-preprocess"], "--input", markdown,
                                 "--output-dir", work / "Markdown direct")
            self.assertEqual(Path(md_receipt["text"]).read_bytes(), markdown.read_bytes())
            config = work / "converter.json"
            config.write_text(json.dumps({"format_version": 1, "argv": [runtime["python"], str(converter),
                              "ok", "{input}", "{output_dir}"]}), encoding="utf-8")
            converted = receipt(commands["legal-preprocess"], "--input", original,
                                "--output-dir", work / "converted", "--converter-config", config)
            self.assertEqual(Path(converted["text"]).read_bytes(), original.read_bytes())
            self.assertEqual(json.loads(Path(converted["metadata"]).read_bytes())["converter_version"], "acceptance.1")
            registered = receipt(commands["legal-case"], "register", "--db", database, "--original", original,
                                 "--text", converted["text"], "--metadata", converted["metadata"])

            # Helper entries live in the installed skill; the module lives in
            # its venv. Neither may recover dependencies from removed source.
            self.assertEqual(set(commands), {"legal-case", "legal-vocab", "legal-preprocess"})
            helpers = install / "skills/legal-case/scripts"
            for name in ("find_quote.py", "build_submission.py", "complete_task.py"):
                self.assertTrue((helpers / name).is_file())
                run(runtime["python"], helpers / name, "--help")
            self.assertTrue((install / "skills/legal-case/references/helper-tools.md").is_file())
            receipt(commands["legal-case"], "split", "--db", database,
                    "--text-version", registered["text_version"]["object_id"])
            clauses = receipt(commands["legal-case"], "query", "--db", database, "--view", "clauses")

            def put(name, obj):
                file = work / name
                file.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
                return file

            snapshot = put("条款快照 clauses.json", {"case_id": clauses["case_id"],
                           "checked_sequence": clauses["quality"]["current_sequence"], "items": clauses["items"]})
            requests = put("引句 requests.json", [{"local_id": "a", "clause_record_id": clauses["items"][0]["record_id"], "quote": "甲方向乙方交付货物。"}])
            header = put("信封 header.json", {"format_version": 1, "case_id": installed_case["case_id"],
                         "vocabulary_hash": installed_case["vocabulary_hash"], "submitted_by": "installed-reader",
                         "phase": "preparation", "covered_clauses": [], "issues": []})
            records = put("记录 records.json", [{"local_id": "p", "kind": "node", "data": {"node_kind": "subject", "canonical_name": "甲方"},
                          "evidence": [{"path": "", "source": {"level": 1, "anchors": [{"local_id": "a"}]}}]}])
            anchors = work / "锚 anchors.json"
            submission = work / "提交 submission.json"
            # Test substitutes forbid database/process/network use even when
            # a helper is launched from a different cwd in the installed venv.
            guard = (
                "import builtins,runpy,sqlite3,subprocess,socket,sys; "
                "deny=lambda *a,**k: (_ for _ in ()).throw(AssertionError('forbidden access')); "
                "sqlite3.connect=deny; subprocess.Popen=deny; socket.socket=deny; "
                "original_import=builtins.__import__; "
                "builtins.__import__=lambda name,*a,**k: deny() if name in "
                "('legal.storage','legal.model','legal.case_cli') else original_import(name,*a,**k); "
                "sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')"
            )
            before = database.read_bytes()
            receipt(runtime["python"], "-c", guard, helpers / "find_quote.py", "--clauses", snapshot, "--input", requests, "--output", anchors)
            assembled = receipt(runtime["python"], "-c", guard, helpers / "build_submission.py", "--header", header,
                                "--records", records, "--records", anchors, "--output", submission)
            self.assertEqual(assembled["scope"], "task_files")
            self.assertEqual(database.read_bytes(), before)
            # Failure paths have the same boundary and leave no output.
            bad_requests = put("无匹配 requests.json", [{"local_id": "b", "clause_record_id": clauses["items"][0]["record_id"], "quote": "不存在的引句"}])
            for script, arguments in (("find_quote.py", ["--clauses", snapshot, "--input", bad_requests]),
                                      ("build_submission.py", ["--header", header, "--records", records])):
                failed_output = work / (script + "-failed.json")
                failed = subprocess.run([runtime["python"], "-c", guard, str(helpers / script),
                                         *map(str, arguments), "--output", str(failed_output)], cwd=work, env=env,
                                        capture_output=True, text=True, timeout=120)
                self.assertEqual(failed.returncode, 2, failed.stderr + failed.stdout)
                self.assertFalse(json.loads(failed.stdout)["ok"])
                self.assertFalse(failed_output.exists())
                self.assertEqual(database.read_bytes(), before)
            receipt(commands["legal-case"], "write", "--db", database, "--input", submission)

            # New templates/examples/API must survive the same source removal.
            case_skill = install / "skills/legal-case"
            for role in ("reader", "summarizer", "tagger", "extractor"):
                self.assertTrue((case_skill / f"templates/{role}.md").is_file())
            example_probe = '''
import builtins,json,runpy,sqlite3,subprocess,socket,sys
deny=lambda *a,**k: (_ for _ in ()).throw(AssertionError('forbidden access'))
sqlite3.connect=deny; subprocess.Popen=deny; socket.socket=deny
original_import=builtins.__import__
builtins.__import__=lambda name,*a,**k: deny() if name in ('legal.storage','legal.model','legal.case_cli') else original_import(name,*a,**k)
from pathlib import Path
from legal.reader_helpers import read_json,write_json,record,ref
examples=Path(sys.argv[1]); work=Path(sys.argv[2])
fixture=read_json(examples/'fixture.json'); snapshot=fixture['snapshot']; clause=snapshot['items'][0]
request=runpy.run_path(str(examples/'quote_requests.py'))['build'](snapshot=snapshot,local_id='a',clause_record_id=clause['record_id'],start=0,end=len(clause['data']['text']))
write_json(work/'installed-requests.json',request)
anchors=[record(local_id='a',kind='anchor',data={'clause':ref(record_id=clause['record_id']),'quote':request[0]['quote'],'occurrence':request[0]['occurrence']},evidence=[])]
common={'snapshot':snapshot,'anchors':anchors,'case_id':fixture['case_id'],'vocabulary_hash':fixture['vocabulary_hash']}
for name in ('preparation','tagging','extraction'):
    args={**common,'submitted_by':{'preparation':'summarizer','tagging':'tagger','extraction':'extractor'}[name]}
    if name!='preparation': args['unit_id']=fixture['unit_id']
    if name=='extraction': args.update(slot_id=fixture['slot_id'],shared_ids=fixture['shared_ids'])
    doc=runpy.run_path(str(examples/(name+'.py')))['build'](**args)
    path=work/('installed-'+name+'.json'); write_json(path,doc)
    assert read_json(path)==doc
print(json.dumps({'ok':True,'examples':4,'source_present':False}))
'''
            before = database.read_bytes()
            self.assertEqual(receipt(runtime["python"], "-c", example_probe, case_skill / "examples", work)["examples"], 4)
            self.assertEqual(database.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
