"""Complete revision from delivered snapshot; inferred classification uses III."""
from legal.reader_helpers import assemble, clause_revision, evidence, header, ref, source


def build(*, snapshot, anchors, unit_id, case_id, vocabulary_hash, submitted_by):
    inferred = [evidence(path="", source=source(level=3, premises=[ref(local_id="a")],
                explanation="该条规定采购人付款，按冻结单元的完整定义归为付款。", asserted_by=submitted_by))]
    revision = clause_revision(local_id="tag", clause=snapshot["items"][0], tags=[unit_id],
                               classification="ordinary", evidence=inferred)
    envelope = header(format_version=1, case_id=case_id, vocabulary_hash=vocabulary_hash,
                      submitted_by=submitted_by, phase="tagging", covered_clauses=[], issues=[])
    return assemble(header=envelope, record_groups=[anchors, [revision]])
