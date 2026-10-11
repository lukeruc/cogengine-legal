"""Use fixed Unicode clause offsets; hand requests to find_quote.py."""
from legal.reader_helpers import quote_from_span


def build(*, snapshot, local_id, clause_record_id, start, end):
    return [quote_from_span(snapshot, local_id=local_id, clause_record_id=clause_record_id,
                            start=start, end=end)]
