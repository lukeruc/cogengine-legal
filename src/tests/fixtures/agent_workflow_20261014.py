"""Host-only isolated fixture with complete argv/stdout/stderr/time receipts."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess


def call(root, label, argv, payload=None, expected_exit=0):
    root = Path(root)
    start = datetime.now(timezone.utc).isoformat()
    proc = subprocess.run([str(a) for a in argv], input=None if payload is None else json.dumps(payload, ensure_ascii=False),
                          cwd=root, text=True, capture_output=True, check=False)
    result = {"argv": [str(a) for a in argv], "input": payload, "start": start,
              "end": datetime.now(timezone.utc).isoformat(), "stdout": proc.stdout, "stderr": proc.stderr, "exit_code": proc.returncode}
    (root / "logs").mkdir(exist_ok=True)
    (root / "logs" / (label + ".json")).write_text(json.dumps(result, ensure_ascii=False, indent=2))
    if proc.returncode != expected_exit:
        raise RuntimeError(proc.stdout + proc.stderr)
    return json.loads(proc.stdout)


def put(file, value):
    file = Path(file)
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def setup(root):
    root = Path(root); install = root / "安装 install"
    workspace = root / "会话 workspace"; workspace.mkdir()
    inputs = root / "fixture-inputs"; inputs.mkdir()
    runtime = json.loads((install / "runtime.json").read_text())
    vocabulary = inputs / "词表 vocabulary.json"
    call(root, "01-vocabulary", [runtime["commands"]["legal-vocab"], "init", "--vocabulary", vocabulary])
    listing = install / "vocabularies/workspace.txt"
    listing.write_bytes((str(vocabulary) + "\r\n").encode())
    config = {"format_version": 1, "workspaces": [{"workspace_root": str(workspace),
              "contract_root": str(root / "contracts"), "vocabulary_list": str(listing)}]}
    (install / "workspaces.json").write_text(json.dumps(config, ensure_ascii=False, indent=2))
    # Fictional contract: distinct package baselines and a stated shared condition.
    original = inputs / "虚构采购合同.MD"
    original.write_bytes(('前言：甲公司为采购方，乙公司为供应方，甲的代表为李甲。\r\n'
        '# 第一条 项目范围\r\n本合同分为东区包和西区包，各包独立交付、独立验收。附件一列明设备清单，但本次未提供附件一。\r\n'
        '# 第二条 交付\r\n乙公司应将设备分别交给甲公司。东区包交付和西区包交付分别构成各包交付事项。\r\n'
        '# 第三条 验收\r\n甲公司应在收到对应包设备后进行检验。各包验收合格后甲公司签发该包验收证书；验收合格与证书签发不是同一事项。\r\n'
        '# 第四条 付款\r\n每包货款为100元。甲公司应在该包验收证书签发且收到该包有效发票后十日内付款；若该包有未修复缺陷，付款义务暂停至缺陷修复。不得将付款本身作为其起算基准。\r\n'
        '# 第五条 共同限定\r\n第四条暂停条件分别适用于各包，不因另一包的缺陷暂停已无缺陷包的付款。收到发票和签发证书均须按包区分。\r\n').encode())
    host = root / "host/skills/legal-case"; host.parent.mkdir(parents=True)
    host.symlink_to(install / "skills/legal-case", target_is_directory=True)
    prepared = call(root, "02-runtime", ["/usr/bin/python3", install / "scripts/prepare_task.py", "runtime", "--input", "-"],
        {"format_version": 1, "skill_file": str(host / "SKILL.md"), "workspace_root": str(workspace)})
    case = call(root, "03-case", [runtime["python"], install / "scripts/prepare_task.py", "case", "--input", "-"],
        {"format_version": 1, "runtime_file": str(install / "runtime.json"), "workspace_root": str(workspace), "materials": [{"path": str(original)}]})
    contract = Path(case["result"]["contract_dir"]); db = contract / "contract.sqlite"
    copied = case["result"]["copied"]
    vocab_copy = next(c["target"] for c in copied if c["source"] == str(vocabulary))
    original_copy = next(c["target"] for c in copied if c["source"] == str(original))
    call(root, "04-init", [runtime["commands"]["legal-case"], "init", "--db", db, "--vocabulary", vocab_copy])
    converted = call(root, "05-preprocess", [runtime["commands"]["legal-preprocess"], "--input", original_copy, "--output-dir", contract / "converted/001/0001"])
    registered = call(root, "06-register", [runtime["commands"]["legal-case"], "register", "--db", db,
        "--original", original_copy, "--text", converted["text"], "--metadata", converted["metadata"]])
    call(root, "07-split", [runtime["commands"]["legal-case"], "split", "--db", db, "--text-version", registered["text_version"]["object_id"]])
    context = contract / "tasks/context.md"
    context.write_text("对本次已提供的合同完整建模；这是虚构工程测试，不是实际履行事实。原文、实际读范围和输入限制均如实交接。分工为 reader 顺序阅读，两个 summarizer 各自形成正式主体/事件与六栏目概要，随后由主会话写入。", encoding="utf-8")
    exported = call(root, "08-reading", [runtime["python"], install / "scripts/prepare_task.py", "reading", "--input", "-"],
        {"format_version": 1, "db_path": str(db), "output_dir": str(contract / "tasks/0001-reading"), "task_context_file": str(context),
         "preparation_files": {"records": str(contract / "submissions/0001-records.json"), "overview": str(contract / "submissions/0002-overview.json")}})
    put(root / "fixture.json", {"install": str(install), "contract": str(contract), "workspace": str(workspace), "reading": exported})
    return exported


def synthesis(root, reader_reports):
    root = Path(root); state = json.loads((root / "fixture.json").read_text()); install = Path(state["install"])
    contract = Path(state["contract"]); runtime = json.loads((install / "runtime.json").read_text())
    exported = call(root, "09-synthesis", [runtime["python"], install / "scripts/prepare_task.py", "synthesis", "--input", "-"],
        {"format_version": 1, "db_path": str(contract / "contract.sqlite"), "manifest_file": str(contract / "tasks/0001-reading/manifest.json"),
         "output_dir": str(contract / "tasks/0002-synthesis"), "reader_reports": reader_reports})
    put(root / "synthesis.json", exported)
    return exported


def submit(root, purpose):
    root = Path(root); state = json.loads((root / "fixture.json").read_text()); install = Path(state["install"])
    contract = Path(state["contract"]); runtime = json.loads((install / "runtime.json").read_text())
    name = "0001-records.json" if purpose == "records" else "0002-overview.json"
    result = call(root, "write-" + purpose, [runtime["commands"]["legal-case"], "write", "--db", contract / "contract.sqlite", "--input", contract / "submissions" / name])
    put(contract / "receipts" / ("write-" + purpose + ".json"), result)
    return result
