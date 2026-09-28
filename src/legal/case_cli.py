"""Command line entry for one-contract SQLite cases."""

from __future__ import annotations

import argparse
import sys

from .formats import exception_result, fail, loads, output, read_json
from .group import group
from .model import write
from .query import query
from .reconcile import reconcile
from .storage import CaseStore, initialize, register, split


class Parser(argparse.ArgumentParser):
    def error(self, message):
        fail("INVALID_ARGUMENT", "/arguments", message)


def _add_db(parser):
    parser.add_argument("--db", required=True)


def _check_duplicates(argv):
    repeat = {"--kind", "--party", "--unit", "--slot", "--source-level", "--clause"}
    seen = set()
    for part in argv:
        if part.startswith("--"):
            key = part.split("=", 1)[0]
            if key in seen and key not in repeat:
                fail("INVALID_ARGUMENT", "/arguments/" + key[2:], "argument repeated")
            seen.add(key)


def main(argv=None):
    parser = Parser(prog="legal-case")
    commands = parser.add_subparsers(dest="command", required=True, parser_class=Parser)
    init = commands.add_parser("init")
    _add_db(init)
    init.add_argument("--vocabulary", required=True)
    reg = commands.add_parser("register")
    _add_db(reg)
    for name in ("original", "text", "metadata"):
        reg.add_argument("--" + name, required=True)
    spl = commands.add_parser("split")
    _add_db(spl)
    spl.add_argument("--text-version", required=True)
    wr = commands.add_parser("write")
    _add_db(wr)
    wr.add_argument("--input")
    for name in ("kind", "local-id", "data-json", "evidence-json", "submitted-by",
                 "object-id", "previous-record-id", "status", "withdrawal-reason"):
        wr.add_argument("--" + name)
    qry = commands.add_parser("query")
    _add_db(qry)
    for name in ("kind", "party", "unit", "slot", "source-level", "clause"):
        qry.add_argument("--" + name, action="append")
    for name in ("object", "record", "view", "format", "output"):
        qry.add_argument("--" + name)
    for name in ("history", "include-withdrawn"):
        qry.add_argument("--" + name, action="store_true")
    qry.add_argument("--limit", type=int, default=100)
    qry.add_argument("--offset", type=int, default=0)
    grp = commands.add_parser("group")
    _add_db(grp)
    grp.add_argument("--output-dir", required=True)
    grp.add_argument("--text-version")
    rec = commands.add_parser("reconcile")
    _add_db(rec)
    rec.add_argument("--text-version")
    rec.add_argument("--history", action="store_true")
    try:
        actual = list(sys.argv[1:] if argv is None else argv)
        _check_duplicates(actual)
        args = parser.parse_args(actual)
        if args.command == "init":
            return output(initialize(args.db, args.vocabulary))
        if args.command == "register":
            return output(register(args.db, args.original, args.text, args.metadata))
        if args.command == "split":
            return output(split(args.db, args.text_version))
        if args.command == "write":
            if args.input:
                if any(getattr(args, name.replace("-", "_")) is not None for name in ("kind", "local-id", "data-json", "evidence-json", "submitted-by", "object-id", "previous-record-id", "status", "withdrawal-reason")):
                    fail("INVALID_ARGUMENT", "/arguments/input", "file and direct record arguments are exclusive")
                doc = read_json(args.input)
            else:
                if not all((args.kind, args.local_id, args.data_json, args.evidence_json, args.submitted_by)):
                    fail("INVALID_ARGUMENT", "/arguments", "direct write needs kind, local ID, data, evidence and submitter")
                store = CaseStore(args.db)
                try:
                    doc = {"format_version": 1, "case_id": store.case_id(),
                           "vocabulary_hash": store.info["vocabulary_hash"], "submitted_by": args.submitted_by,
                           "phase": "correction", "covered_clauses": [], "issues": [],
                           "records": [{"local_id": args.local_id, "kind": args.kind,
                                        "data": loads(args.data_json, "/arguments/data-json"),
                                        "evidence": loads(args.evidence_json, "/arguments/evidence-json")}]}
                    record = doc["records"][0]
                    for arg, key in ((args.object_id, "object_id"), (args.previous_record_id, "previous_record_id"),
                                     (args.status, "status"), (args.withdrawal_reason, "withdrawal_reason")):
                        if arg is not None:
                            record[key] = arg
                finally:
                    store.close()
            return output(write(args.db, doc))
        if args.command == "query":
            levels = None
            if args.source_level:
                try:
                    levels = [int(x) for x in args.source_level]
                except ValueError:
                    fail("INVALID_ARGUMENT", "/arguments/source-level", "expected 1, 2 or 3")
                if any(x not in {1, 2, 3} for x in levels):
                    fail("INVALID_ARGUMENT", "/arguments/source-level", "expected 1, 2 or 3")
            opts = {"kinds": args.kind, "parties": args.party, "units": args.unit, "slots": args.slot,
                    "source_levels": levels,
                    "clauses": args.clause, "object": args.object, "record": args.record,
                    "view": args.view or "records", "format": args.format or "json", "output": args.output,
                    "history": args.history, "include_withdrawn": args.include_withdrawn,
                    "limit": args.limit, "offset": args.offset}
            result = query(args.db, opts)
            if isinstance(result, str):
                print(result, end="")
                return 0
            return output(result)
        if args.command == "group":
            return output(group(args.db, args.output_dir, args.text_version))
        result = reconcile(args.db, args.text_version, args.history)
        return output(result, 0 if result["passed"] else 4)
    except Exception as exc:
        return exception_result(exc)


if __name__ == "__main__":
    raise SystemExit(main())
