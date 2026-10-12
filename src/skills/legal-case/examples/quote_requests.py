"""Use fixed Unicode clause offsets; hand requests to find_quote.py."""
from legal.reader_helpers import quote_from_span


def build(*, snapshot, local_id, clause_record_id, start, end):
    return [quote_from_span(snapshot, local_id=local_id, clause_record_id=clause_record_id,
                            start=start, end=end)]


def build_many(*, chosen_quotes):
    """Organize explicit task data; find_quote alone matches and disambiguates."""
    return [{"local_id": local_id, "clause_record_id": record_id, "quote": quote}
            for local_id, record_id, quote in chosen_quotes]
