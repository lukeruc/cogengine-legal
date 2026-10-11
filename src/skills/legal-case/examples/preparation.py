"""Fictional one-clause example; names/events/sources are explicit judgments."""
from legal.reader_helpers import assemble, evidence, header, node, ref, reference, source


def build(*, snapshot, anchors, case_id, vocabulary_hash, submitted_by):
    clause = snapshot["items"][0]
    direct = [evidence(path="", source=source(level=1, anchors=[ref(local_id="a")]))]
    records = [
        node(local_id="p", node_kind="subject", fields={"canonical_name": "甲方", "identifiers": []}, evidence=direct),
        node(local_id="q", node_kind="subject", fields={"canonical_name": "乙方", "identifiers": []}, evidence=direct),
        node(local_id="delivery", node_kind="event", fields={
            "name": "乙方交付货物", "description": "乙方交付货物",
            "participants": [{"subject": ref(local_id="q"), "role": "交付方"}],
            "object": {"form": "text", "surface": "货物"}}, evidence=direct),
        reference(local_id="p-name", reference_kind="appellation", from_ref=ref(record_id=clause["record_id"]),
                  to_ref=ref(local_id="p"), fields={"label": "甲方"}, evidence=direct),
    ]
    body = ("材料范围：虚构条款，无其他材料。\n主体与称谓：甲方为采购人，乙方为供应商。\n"
            "交易及履行结构：乙方交付货物，甲方付款。\n关键安排：交付后支付100元。\n"
            "共同定义与限定：交付是付款的基准，付款不是交付事件的一部分。\n未解决事项：无。")
    envelope = header(format_version=1, case_id=case_id, vocabulary_hash=vocabulary_hash,
                      submitted_by=submitted_by, phase="preparation", covered_clauses=[], issues=[],
                      overview={"text_versions": [clause["data"]["text_version"]], "body": body, "authored_by": submitted_by})
    return assemble(header=envelope, record_groups=[anchors, records])
