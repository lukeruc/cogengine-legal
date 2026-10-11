"""Fictional payment; formal shared identities must already be written."""
from legal.reader_helpers import assemble, detail, evidence, header, ref, relation, source


def build(*, snapshot, anchors, shared_ids, unit_id, slot_id, case_id, vocabulary_hash, submitted_by):
    clause = snapshot["items"][0]
    direct = [evidence(path="", source=source(level=1, anchors=[ref(local_id="a")]))]
    payment = relation(local_id="payment", relation_kind="party", fields={
        "unit_id": unit_id, "parties": [
            {"subject": ref(object_id=shared_ids["p"]), "nature": "obligor"},
            {"subject": ref(object_id=shared_ids["q"]), "nature": "recipient"}]}, evidence=direct)
    # All format parameters are explicit; conversion never guesses units/scale.
    amount = detail(local_id="amount", owner=ref(local_id="payment"), slot_id=slot_id,
                    value={"form": "quantity", "amount": "100", "unit": "CNY"}, evidence=[
        evidence(path="/owner", source=source(level=1, anchors=[ref(local_id="a")])),
        evidence(path="/slot_id", source=source(level=3, premises=[ref(local_id="a")],
                 explanation="按已交付槽定义，将支付100元表达为金额。", asserted_by=submitted_by)),
        evidence(path="/value", source=source(level=2, anchors=[ref(local_id="a")], surface="100元",
                 format_contract="decimal.v1", format_parameters={"decimal_places": 0,
                     "group_separator": "", "decimal_separator": ".", "sign_style": "minus", "scale": "1",
                     "unit_surface": "元", "unit_position": "after", "prefix": "", "suffix": "",
                     "number_unit_separator": ""})),
    ])
    # The example requires a condition slot: keep the delivery prerequisite.
    condition = detail(local_id="condition", owner=ref(local_id="payment"), slot_id=shared_ids["condition_slot"],
                       value={"form": "condition", "operator": "event", "event": ref(object_id=shared_ids["delivery"])},
                       evidence=direct)
    envelope = header(format_version=1, case_id=case_id, vocabulary_hash=vocabulary_hash,
                      submitted_by=submitted_by, phase="extraction", covered_clauses=[
                          {"object_id": clause["object_id"], "record_id": clause["record_id"]}], issues=[])
    return assemble(header=envelope, record_groups=[anchors, [payment, amount, condition]])
