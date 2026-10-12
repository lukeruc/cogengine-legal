"""Host-only preparation and logging for the observed ingestion acceptance."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

from legal.handoff import _all
from legal.initial_reading import export_initial_reading_tasks, export_initial_synthesis_task
from legal.reader_helpers import assemble, read_json, write_json


def now():
    return datetime.now(timezone.utc).isoformat()


def contract(root):
    return Path(root) / "contract-20261013T000000Z"


def call(root, label, argv, *, allow_failure=False):
    root = Path(root)
    started = now()
    result = subprocess.run(list(map(str, argv)), cwd=contract(root), capture_output=True)
    (root / "logs").mkdir(exist_ok=True)
    (root / "logs" / (label + ".stdout.txt")).write_bytes(result.stdout)
    (root / "logs" / (label + ".stderr.txt")).write_bytes(result.stderr)
    write_json(root / "logs" / (label + ".process.json"), {
        "argv": list(map(str, argv)), "exit_code": result.returncode,
        "started_at": started, "completed_at": now()})
    if result.returncode and not allow_failure:
        raise RuntimeError(result.stdout.decode("utf-8") + result.stderr.decode("utf-8"))
    return json.loads(result.stdout)


def setup(root):
    root = Path(root); work = contract(root); install = root / "install"
    for name in ("inputs/materials", "inputs/vocabulary", "converted", "tasks", "submissions", "receipts", "reports", "groups"):
        (work / name).mkdir(parents=True, exist_ok=True)
    runtime = read_json(install / "runtime.json")
    original = work / "inputs/materials/001-合同.MD"
    original.write_bytes(('''# 第一条 主体\r
甲方为采购人，乙方为供应商。\r
# 第二条 交付\r
乙方应向甲方交付货物，标识为 "don't\\😀é"。\r
# 第三条 验收\r
甲方应在收到货物后验收。\r
# 第四条 付款\r
甲方应在乙方交付货物后向乙方支付100元。\r
# 第五条 文件\r
货物由乙方提供清单；清单格式另见未提供的附件一。\r
''').encode("utf-8"))
    vocabulary = {"format_version": 1, "units": [
        {"id": "10000001-1111-4111-8111-111111111111", "name": "交付", "description": "货物交付、验收、交付清单及签约主体的规定"},
        {"id": "10000002-1111-4111-8111-111111111111", "name": "付款", "description": "采购人支付货款及其条件规定"}], "slots": [], "assignments": []}
    vocab_path = work / "inputs/vocabulary/001-vocabulary.json"; write_json(vocab_path, vocabulary)
    identity = call(root, "01-init", [runtime["commands"]["legal-case"], "init", "--db", work / "contract.sqlite", "--vocabulary", vocab_path])
    direct = call(root, "02-preprocess", [runtime["commands"]["legal-preprocess"], "--input", original, "--output-dir", work / "converted/001/0001"])
    registered = call(root, "03-register", [runtime["commands"]["legal-case"], "register", "--db", work / "contract.sqlite", "--original", direct["input"], "--text", direct["text"], "--metadata", direct["metadata"]])
    call(root, "04-split", [runtime["commands"]["legal-case"], "split", "--db", work / "contract.sqlite", "--text-version", registered["text_version"]["object_id"]])
    exported = export_initial_reading_tasks(work / "contract.sqlite", work / "tasks/0001-reading", install, work / "submissions/0001-preparation.json", target_chars=1, window_chars=80)
    assert len(exported["tasks"]) == 5
    write_json(root / "identity.json", identity); write_json(root / "reading-export.json", exported)
    # Deliberately not handed to any role. A permitted document links here.
    sibling = work / "tasks/sibling"; sibling.mkdir()
    (sibling / "make_requests.py").write_text("raise RuntimeError('PRIVATE-SIBLING-20261012')\n")
    (sibling / "old-example.py").write_text("raise RuntimeError('WRONG-VERSION-20261012')\n")
    extra = work / "tasks/authorized-overview.md"
    extra.write_text("# 阅读背景\n本次是虚构五条款夹具。\n[旧格式示例](" + str(sibling / "old-example.py") + ")\n", encoding="utf-8")
    # A fake DOCX tests protocol selection only, not real DOCX conversion.
    binary = work / "inputs/materials/002-protocol-fixture.docx"; binary.write_bytes(original.read_bytes())
    missing = call(root, "05-converter-missing", [runtime["commands"]["legal-preprocess"], "--input", binary, "--output-dir", work / "converted/002/0001"], allow_failure=True)
    assert missing["ok"] is False
    return exported


def synthesis(root):
    root = Path(root); work = contract(root)
    return export_initial_synthesis_task(work / "contract.sqlite", work / "tasks/0001-reading/manifest.json", work / "tasks/0001-reading/0006-synthesis.json")


def dispatch(root, role, task_id, body):
    root = Path(root)
    template = (root / "install/skills/legal-case/templates" / (role + ".md")).read_text()
    fixed = template.split("## 一、固定内容\n\n", 1)[1].split("\n## 二、本次任务要求", 1)[0]
    text = f"# {role}：{task_id}\n\n## 一、固定内容\n\n{fixed}\n## 二、本次任务要求\n\n{body}\n"
    file = contract(root) / "tasks" / (task_id + "-dispatch.md")
    file.write_text(text, encoding="utf-8")
    return text


def submit(root, label, filename):
    root = Path(root); work = contract(root); runtime = read_json(root / "install/runtime.json")
    receipt = call(root, label + "-write", [runtime["commands"]["legal-case"], "write", "--db", work / "contract.sqlite", "--input", work / "submissions" / filename])
    write_json(work / "receipts" / (label + ".json"), receipt)
    for view in ("overview", "events", "clauses", "vocabulary", "records"):
        basis, items = _all(work / "contract.sqlite", view=view, **({"kinds": ["node"]} if view == "records" else {}))
        write_json(work / "reports" / (label + "-" + view + ".json"), {
            "case_id": basis["case_id"], "checked_sequence": basis["quality"]["current_sequence"], "items": items})
    return receipt


def stale_write_check(root):
    """Show file assembly cannot validate a predecessor against the database."""
    root = Path(root); work = contract(root); runtime = read_json(root / "install/runtime.json")
    original = read_json(work / "submissions/0002-tagging.json")
    envelope = {k: v for k, v in original.items() if k != "records"}
    envelope["submitted_by"] = "host-stale-predecessor-regression"
    document = assemble(header=envelope, record_groups=[original["records"]])
    target = work / "submissions/0003-stale-predecessor-test.json"
    write_json(target, document)
    basis, _ = _all(work / "contract.sqlite", view="progress")
    sequence = basis["quality"]["current_sequence"]
    rejected = call(root, "09-stale-write", [runtime["commands"]["legal-case"], "write",
                    "--db", work / "contract.sqlite", "--input", target], allow_failure=True)
    after, _ = _all(work / "contract.sqlite", view="progress")
    assert not rejected["ok"] and any(e["code"] == "STALE_REVISION" for e in rejected["errors"])
    assert after["quality"]["current_sequence"] == sequence
    write_json(work / "reports/09-stale-write-check.json", {
        "assembled": True, "formal_write_accepted": False, "sequence_unchanged": True,
        "sequence": sequence, "errors": rejected["errors"]})
    return rejected
