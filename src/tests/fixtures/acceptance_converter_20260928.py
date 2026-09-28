"""Controlled external converter for acceptance tests; never uses real contracts."""
import json
from pathlib import Path
import sys

mode, input_path, output_path = sys.argv[1:]
source, target = Path(input_path), Path(output_path)
if mode == "fail":
    raise SystemExit(7)
text = source.read_bytes()
(target / "text.txt").write_bytes(b"\xff" if mode == "utf8" else text)
if mode != "missing":
    metadata = {"name": source.name, "media_type": "text/plain", "conversion_method": "identity",
        "converter_version": "acceptance.1", "anomalies": []}
    if mode == "interval":
        metadata["anomalies"] = [{"code": "test", "message": "test", "start_offset": 0, "end_offset": len(text) + 100}]
    (target / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
if mode == "mutate":
    source.write_bytes(text + b"changed")
print("converter stdout")
print("converter stderr", file=sys.stderr)
