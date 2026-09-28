"""Command line entry for globally governed vocabularies."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .formats import exception_result, exclusive_write, fail, loads, output, read_json
from .query import quality, record_item
from .storage import CaseStore
from .vocabulary import EMPTY, apply_change, diff, load, save, vocabulary_hash


class Parser(argparse.ArgumentParser):
    def error(self, message):
        fail("INVALID_ARGUMENT", "/arguments", message)


def aggregate(vocabulary, cases_file, output_file):
    manifest = read_json(cases_file)
    from .formats import fields, version
    fields(manifest, ["format_version", "cases"])
    version(manifest["format_version"])
    if not isinstance(manifest["cases"], list) or any(not isinstance(path, str) or not path for path in manifest["cases"]) or len(manifest["cases"]) != len(set(manifest["cases"])):
        fail("INVALID_ARGUMENT", "/cases", "case paths must be a unique array")
    entries = []
    gap_count = 0
    for i, path in enumerate(manifest["cases"]):
        source = Path(cases_file).absolute().parent / path
        store = CaseStore(source)
        try:
            vocabulary_old = store.vocabulary()
            old_units = {e["id"]: e for e in vocabulary_old["units"]}
            old_slots = {e["id"]: e for e in vocabulary_old["slots"]}
            gaps = []
            for row in store.db.execute("""SELECT r.*,o.kind FROM active_records r JOIN objects o USING(object_id)
                JOIN submissions s ON s.submission_id=r.submission_id WHERE o.kind='gap' ORDER BY s.sequence,r.object_id"""):
                item = record_item(store, row)
                data = item["data"]
                unit_ids = {data["suggested_unit_id"]} if "suggested_unit_id" in data else set()
                slot_ids = set()
                related = data.get("related_object", {}).get("record_id")
                if related:
                    target = store.record(related)
                    if target:
                        target_data = json.loads(target["data_json"])
                        if "unit_id" in target_data:
                            unit_ids.add(target_data["unit_id"])
                        if "slot_id" in target_data:
                            slot_ids.add(target_data["slot_id"])
                gaps.append({"record": item,
                             "related_units": [old_units[u] for u in sorted(unit_ids) if u in old_units],
                             "related_slots": [old_slots[s] for s in sorted(slot_ids) if s in old_slots]})
            gap_count += len(gaps)
            entries.append({"path": str(source), "case_id": store.case_id(),
                            "vocabulary_hash": store.info["vocabulary_hash"], "quality": quality(store),
                            "gaps": gaps})
        finally:
            store.close()
    report = {"format_version": 1, "current_vocabulary_hash": vocabulary_hash(vocabulary), "cases": entries}
    exclusive_write(output_file, (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return {"ok": True, "output": str(Path(output_file).absolute()), "case_count": len(entries), "gap_count": gap_count}


def _extract_vocabulary(argv):
    indexes = [i for i, part in enumerate(argv) if part == "--vocabulary" or part.startswith("--vocabulary=")]
    if len(indexes) > 1:
        fail("INVALID_ARGUMENT", "/arguments/vocabulary", "argument repeated")
    if not indexes:
        return None, argv
    i = indexes[0]
    if argv[i] == "--vocabulary":
        if i + 1 >= len(argv):
            fail("INVALID_ARGUMENT", "/arguments/vocabulary", "path required")
        return argv[i + 1], argv[:i] + argv[i + 2:]
    return argv[i].split("=", 1)[1], argv[:i] + argv[i + 1:]


def main(argv=None):
    parser = Parser(prog="legal-vocab")
    parser.add_argument("--input")
    commands = parser.add_subparsers(dest="command", parser_class=Parser)
    commands.add_parser("init")
    listing = commands.add_parser("list")
    listing.add_argument("--kind", required=True, choices=["unit", "slot", "assignment"])
    show = commands.add_parser("show")
    show.add_argument("--kind", required=True, choices=["unit", "slot"])
    show.add_argument("--id", required=True)
    add = commands.add_parser("add")
    add.add_argument("--kind", required=True, choices=["unit", "slot"])
    add.add_argument("--entry-json", required=True)
    add.add_argument("--unit", action="append")
    remove = commands.add_parser("remove")
    remove.add_argument("--kind", required=True, choices=["unit", "slot"])
    remove.add_argument("--id", required=True)
    compare = commands.add_parser("diff")
    compare.add_argument("--left", required=True)
    compare.add_argument("--right", required=True)
    aggregate_parser = commands.add_parser("aggregate")
    aggregate_parser.add_argument("--cases", required=True)
    aggregate_parser.add_argument("--output", required=True)
    try:
        actual = list(sys.argv[1:] if argv is None else argv)
        seen = set()
        for part in actual:
            if part.startswith("--"):
                key = part.split("=", 1)[0]
                if key in seen and key not in {"--unit"}:
                    fail("INVALID_ARGUMENT", "/arguments/" + key[2:], "argument repeated")
                seen.add(key)
        vocabulary_path, remaining = _extract_vocabulary(actual)
        args = parser.parse_args(remaining)
        if args.input and args.command:
            fail("INVALID_ARGUMENT", "/arguments/input", "mixed change takes no subcommand")
        if not args.input and not args.command:
            fail("INVALID_ARGUMENT", "/arguments", "command or input required")
        if args.command == "diff":
            if vocabulary_path:
                fail("INVALID_ARGUMENT", "/arguments/vocabulary", "diff uses left and right paths")
            left, _ = load(args.left)
            right, _ = load(args.right)
            changes = diff(left, right)
            return output({"ok": True, "left_hash": vocabulary_hash(left),
                           "right_hash": vocabulary_hash(right), **changes}, 2 if changes["illegal_content_changes"] else 0)
        if not vocabulary_path:
            fail("INVALID_ARGUMENT", "/arguments/vocabulary", "vocabulary path required")
        if args.command == "init":
            save(vocabulary_path, EMPTY, exclusive=True)
            return output({"ok": True, "vocabulary_hash": vocabulary_hash(EMPTY)})
        current, _ = load(vocabulary_path)
        if args.input:
            change = read_json(args.input)
            updated, receipt = apply_change(current, change)
            save(vocabulary_path, updated)
            return output(receipt)
        if args.command == "list":
            return output({"ok": True, "kind": args.kind, "items": current[args.kind + "s"] if args.kind != "assignment" else current["assignments"]})
        if args.command == "show":
            found = next((e for e in current[args.kind + "s"] if e["id"] == args.id), None)
            if not found:
                fail("NOT_FOUND", "/arguments/id", "entry missing")
            return output({"ok": True, "kind": args.kind, "items": [found]})
        if args.command in {"add", "remove"}:
            if args.command == "add":
                operation = {"action": "add", "kind": args.kind, "local_id": "direct",
                             "entry": loads(args.entry_json, "/arguments/entry-json")}
                if args.kind == "slot":
                    operation["unit_ids"] = args.unit or []
                elif args.unit:
                    fail("INVALID_ARGUMENT", "/arguments/unit")
            else:
                operation = {"action": "remove", "kind": args.kind, "id": args.id}
            updated, receipt = apply_change(current, {"format_version": 1,
                                                      "expected_hash": vocabulary_hash(current),
                                                      "operations": [operation], "orphan_slots": []})
            save(vocabulary_path, updated)
            return output(receipt)
        return output(aggregate(current, args.cases, args.output))
    except Exception as exc:
        return exception_result(exc)


if __name__ == "__main__":
    raise SystemExit(main())
