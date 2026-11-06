"""Bounded, lossless reading of explicit frozen files; no case/database access."""
from __future__ import annotations

import argparse
import base64
import binascii
import json
from pathlib import Path
import re
import sys

from .formats import (Invalid, canonical, digest, errors, fail, file_bytes,
                      integer, loads, uuid_value)
from .vocabulary import normalize

NODE_KINDS = ("contract", "subject", "event", "defined_value", "external_benchmark")
KINDS = (*NODE_KINDS, "unit", "slot")


def _required(value, names, path):
    if not isinstance(value, dict):
        fail("INVALID_ARGUMENT", path, "object required")
    for name in names:
        if name not in value:
            fail("INVALID_ARGUMENT", path + "/" + name, "required field missing")


def _array(value, path):
    if not isinstance(value, list):
        fail("INVALID_ARGUMENT", path, "array required")


def _nodes(items):
    by_object, by_record = {}, {}
    for index, item in enumerate(items):
        at = f"/items/{index}"
        _required(item, ("object_id", "record_id", "kind", "status", "data", "evidence", "provenance"), at)
        for key in ("object_id", "record_id"):
            uuid_value(item[key], at + "/" + key)
        if item["kind"] != "node" or item["status"] != "active":
            fail("INVALID_ARGUMENT", at, "active node snapshot required")
        _required(item["data"], ("node_kind",), at + "/data")
        kind = item["data"]["node_kind"]
        if kind not in NODE_KINDS:
            fail("INVALID_ARGUMENT", at + "/data/node_kind", "unsupported node kind")
        # The contract name is optional. Other node names and event fields are
        # required by the formal record contract; never invent absent values.
        required = {"subject": ("canonical_name",), "event": ("name", "description", "participants"),
                    "defined_value": ("name", "value"), "external_benchmark": ("name", "description")}.get(kind, ())
        _required(item["data"], required, at + "/data")
        if kind == "event":
            _array(item["data"]["participants"], at + "/data/participants")
        for field in ("evidence", "provenance"):
            _array(item[field], at + "/" + field)
        for j, root in enumerate(item["provenance"]):
            pos = f"{at}/provenance/{j}"
            _required(root, ("anchors",), pos)
            _array(root["anchors"], pos + "/anchors")
            for k, anchor in enumerate(root["anchors"]):
                _required(anchor, ("clause_record_id", "start_offset", "end_offset"), f"{pos}/anchors/{k}")
        oid, rid = item["object_id"], item["record_id"]
        if oid in by_object and by_object[oid] != item or rid in by_record and by_record[rid] != item:
            fail("SNAPSHOT_CONFLICT", at, "conflicting object version or record content")
        by_object[oid], by_record[rid] = item, item
    return sorted(by_record.values(), key=lambda r: (r["data"]["node_kind"], r["object_id"], r["record_id"]))


def _catalog(item):
    data = item["data"]
    result = {key: item[key] for key in ("object_id", "record_id")}
    result["data"], unexpanded = {}, []
    for key in ("node_kind", "name", "canonical_name", "participants", "batch_or_stage"):
        if key not in data:
            continue
        # Omit a long field explicitly, never truncate it into an apparent fact.
        if len(canonical(data[key]).decode("utf-8")) > 256:
            unexpanded.append("/data/" + key)
        else:
            result["data"][key] = data[key]
    positions = {}
    for root in item["provenance"]:
        for anchor in root["anchors"]:
            position = {key: anchor[key] for key in
                        ("clause_record_id", "sequence", "start_offset", "end_offset") if key in anchor}
            positions[canonical(position)] = position
    result["source_positions"] = list(positions.values())[:2]
    result["source_position_count"] = len(positions)
    if len(positions) > 2:
        unexpanded.append("/provenance")
    result["unexpanded_fields"] = unexpanded
    result["requires_show"] = True
    return result


def _vocabulary(items):
    if len(items) != 1:
        fail("INVALID_ARGUMENT", "/items", "one frozen vocabulary item required, even when empty")
    vocab = items[0]
    _required(vocab, ("format_version", "units", "slots", "assignments", "hash"), "/items/0")
    # Validate through the existing format implementation, preserving the
    # original arrays, optional-field presence and order in the returned data.
    try:
        normalize({key: vocab[key] for key in ("format_version", "units", "slots", "assignments")})
    except Invalid as exc:
        exc.path = "/items/0" + exc.path
        raise
    if not isinstance(vocab["hash"], str) or not re.fullmatch(r"[0-9a-f]{64}", vocab["hash"]):
        fail("INVALID_ARGUMENT", "/items/0/hash", "SHA-256 required")
    return vocab


def _selection(snapshot, operation, kind, record_id, item_id):
    if kind in ("unit", "slot"):
        vocab = _vocabulary(snapshot["items"])
        entries = vocab[kind + "s"]
        if operation == "show":
            entries = [e for e in entries if e["id"] == item_id]
            if not entries:
                fail("REFERENCE_NOT_FOUND", "/item_id", "item absent from frozen vocabulary")
        result = []
        for entry in entries:
            assignments = [a for a in vocab["assignments"] if a[kind + "_id"] == entry["id"]]
            if operation == "list" and kind == "slot":
                result.append({**{k: entry[k] for k in ("id", "name", "aliases") if k in entry},
                               "assignments": assignments, "general": not assignments, "requires_show": True})
            else:
                result.append({"item": entry, "assignments": assignments})
        return (result if operation == "list" else result[0]), vocab["hash"]
    nodes = _nodes(snapshot["items"])
    if operation == "list":
        return [_catalog(n) for n in nodes if kind is None or n["data"]["node_kind"] == kind], None
    found = [n for n in nodes if n["record_id"] == record_id]
    if not found:
        fail("REFERENCE_NOT_FOUND", "/record_id", "fixed record absent from snapshot")
    return found[0], None


def read_context(input_file, sha256, operation, *, kind=None, record_id=None, item_id=None,
                 cursor=None, max_chars=6000):
    """Return a character window of deterministic JSON, including full records.

    Concatenate content.text across every page before parsing. A catalog is a
    locator only. No returned flag claims that the model read or understood it.
    """
    if operation not in ("list", "show") or kind is not None and kind not in KINDS:
        fail("INVALID_ARGUMENT", "/operation", "unsupported operation or kind")
    if operation == "list":
        if record_id is not None or item_id is not None:
            fail("INVALID_ARGUMENT", "/selection", "list takes only optional kind")
    elif record_id is not None:
        if kind is not None or item_id is not None:
            fail("INVALID_ARGUMENT", "/selection", "record_id excludes vocabulary kind/item_id")
        uuid_value(record_id, "/record_id")
    else:
        if kind not in ("unit", "slot") or item_id is None:
            fail("INVALID_ARGUMENT", "/selection", "show needs record_id or vocabulary kind/item_id")
        uuid_value(item_id, "/item_id")
    integer(max_chars, "/max_chars", 1)
    if max_chars > 60000:
        fail("INVALID_ARGUMENT", "/max_chars", "maximum 60000 characters per content window")
    if not isinstance(input_file, (str, Path)) or "\x00" in str(input_file) or not Path(input_file).is_absolute():
        fail("INVALID_ARGUMENT", "/input", "explicit absolute file path required")
    if not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
        fail("INVALID_ARGUMENT", "/sha256", "expected frozen file SHA-256")
    path = Path(input_file)
    raw = file_bytes(path)
    if digest(raw) != sha256:
        fail("SNAPSHOT_CHANGED", "/sha256", "file differs from assigned snapshot", file=str(path))
    snapshot = loads(raw, str(path))
    _required(snapshot, ("case_id", "checked_sequence", "items"), "")
    uuid_value(snapshot["case_id"], "/case_id")
    integer(snapshot["checked_sequence"], "/checked_sequence", 0)
    _array(snapshot["items"], "/items")
    value, vocab_hash = _selection(snapshot, operation, kind, record_id, item_id)
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
    selection = {"kind": kind, "record_id": record_id, "item_id": item_id}
    binding = digest(canonical({"version": 1, "file": str(path), "sha256": sha256,
                                "operation": operation, "selection": selection}))
    start = 0
    if cursor is not None:
        try:
            if not isinstance(cursor, str) or len(cursor) > 2048:
                raise ValueError("invalid cursor")
            decoded = base64.b64decode(cursor.encode("ascii"), altchars=b"-_", validate=True)
            token = loads(decoded)
            if not isinstance(token, dict) or set(token) != {"binding", "offset"} or token["binding"] != binding:
                raise ValueError("cursor belongs to another file or selection")
            start = token["offset"]
            if type(start) is not int or not 0 <= start < len(rendered):
                raise ValueError("cursor offset out of range")
        except (Invalid, ValueError, UnicodeError, binascii.Error) as exc:
            fail("INVALID_CURSOR", "/cursor", str(exc))
    end = min(start + max_chars, len(rendered))
    next_cursor = None if end == len(rendered) else base64.urlsafe_b64encode(
        canonical({"binding": binding, "offset": end})).decode("ascii")
    source = {"file": str(path), "sha256": sha256, "case_id": snapshot["case_id"],
              "checked_sequence": snapshot["checked_sequence"]}
    if vocab_hash is not None:
        source["vocabulary_hash"] = vocab_hash
    return {"ok": True, "operation": operation, "source": source, "selection": selection,
            "content": {"format": "json", "start": start, "end": end, "total_chars": len(rendered),
                        "complete": start == 0 and end == len(rendered), "text": rendered[start:end]},
            "next_cursor": next_cursor}


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        fail("INVALID_ARGUMENT", "/arguments", message)


def main(argv=None):
    parser = _Parser(description=__doc__)
    parser.add_argument("operation", choices=("list", "show"))
    parser.add_argument("--input", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--kind", choices=KINDS)
    parser.add_argument("--record-id")
    parser.add_argument("--item-id")
    parser.add_argument("--cursor")
    parser.add_argument("--max-chars", type=int, default=6000)
    try:
        args = vars(parser.parse_args(argv))
        args["input_file"] = args.pop("input")
        result = read_context(**args)
    except Invalid as exc:
        print(json.dumps(errors(exc), ensure_ascii=False))
        return 3 if exc.code == "FILE_ERROR" else 2
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
