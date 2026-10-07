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
            for name in ("build_release.py", "install_release.py", "verify_registration.py"):
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
                self.assertNotIn("README", body)
                snippet = re.search(r"^```python\n(.*?)^```", body, re.M | re.S).group(1)
                snippet = snippet.replace(f'"/host/skills/{name}/SKILL.md"', json.dumps(str(skill)))
                paths = run(runtime["python"], "-c", snippet).splitlines()
                self.assertEqual(paths, [str(install / "runtime.json"), str(install / "references")])
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
            receipt(commands["legal-case"], "init", "--db", database, "--vocabulary", vocabulary)
            receipt(commands["legal-case"], "query", "--db", database, "--view", "progress")
            self.assertTrue(database.is_file())

            original = work / "合同原文.txt"
            original.write_text("第一条 甲方向乙方交付货物。\n", encoding="utf-8")
            config = work / "converter.json"
            config.write_text(json.dumps({"format_version": 1, "argv": [runtime["python"], str(converter),
                              "ok", "{input}", "{output_dir}"]}), encoding="utf-8")
            converted = receipt(commands["legal-preprocess"], "--input", original,
                                "--output-dir", work / "converted", "--converter-config", config)
            self.assertEqual(Path(converted["text"]).read_bytes(), original.read_bytes())
            receipt(commands["legal-case"], "register", "--db", database, "--original", original,
                    "--text", converted["text"], "--metadata", converted["metadata"])


if __name__ == "__main__":
    unittest.main()
