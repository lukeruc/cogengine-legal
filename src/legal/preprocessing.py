"""Uniform adapter for explicitly configured document converters."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from .formats import (digest, fail, fields, file_bytes,
                      file_text, read_json, version, nonempty)


def _validate_metadata(metadata, text):
    fields(metadata, ["name", "media_type", "conversion_method", "converter_version", "anomalies"], [], "/converter_output/metadata")
    for field in ("name", "media_type", "conversion_method", "converter_version"):
        nonempty(metadata[field], "/converter_output/metadata/" + field)
    if not isinstance(metadata["anomalies"], list):
        fail("CONVERTER_OUTPUT_INVALID", "/converter_output/metadata/anomalies", "expected array")
    for i, item in enumerate(metadata["anomalies"]):
        path = f"/converter_output/metadata/anomalies/{i}"
        fields(item, ["code", "message"], ["start_offset", "end_offset"], path)
        nonempty(item["code"], path + "/code")
        nonempty(item["message"], path + "/message")
        if ("start_offset" in item) != ("end_offset" in item):
            fail("CONVERTER_OUTPUT_INVALID", path, "both offsets required")
        if "start_offset" in item:
            start, end = item["start_offset"], item["end_offset"]
            if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text):
                fail("CONVERTER_OUTPUT_INVALID", path, "invalid anomaly interval")


def convert(input_path, output_dir, converter_config):
    original = Path(input_path).absolute()
    target = Path(output_dir).absolute()
    config_file = Path(converter_config).absolute()
    if not original.is_file():
        fail("FILE_ERROR", "/arguments/input", "original is not a regular file")
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        fail("FILE_EXISTS", "/arguments/output-dir", "output directory is not empty")
    config = read_json(config_file)
    fields(config, ["format_version", "argv"], [], "/converter_config")
    version(config["format_version"], "/converter_config/format_version")
    argv = config["argv"]
    if not isinstance(argv, list) or len(argv) < 3:
        fail("INVALID_ARGUMENT", "/converter_config/argv", "expected executable and two placeholders")
    for i, item in enumerate(argv):
        nonempty(item, f"/converter_config/argv/{i}")
    executable = Path(argv[0])
    if not executable.is_absolute() or not executable.is_file():
        fail("INVALID_ARGUMENT", "/converter_config/argv/0", "executable must be an existing absolute path")
    if argv.count("{input}") != 1 or argv.count("{output_dir}") != 1:
        fail("INVALID_ARGUMENT", "/converter_config/argv", "each placeholder required exactly once")
    if any("{" in part or "}" in part for part in argv if part not in {"{input}", "{output_dir}"}):
        fail("INVALID_ARGUMENT", "/converter_config/argv", "unsupported placeholder")
    original_hash = digest(file_bytes(original))
    with tempfile.TemporaryDirectory(prefix="legal-convert-") as temporary:
        staging = Path(temporary)
        command = []
        for part in argv:
            if part == "{input}":
                command.append(str(original))
            elif part == "{output_dir}":
                command.append(str(staging))
            elif not command:
                command.append(part)
            elif part.startswith("-") or Path(part).is_absolute() or "/" not in part and not part.startswith("."):
                command.append(part)
            else:
                command.append(str((config_file.parent / part).absolute()))
        try:
            completed = subprocess.run(command, cwd=config_file.parent, capture_output=True, check=False)
        except OSError as exc:
            fail("FILE_ERROR", "/converter_config/argv/0", str(exc))
        for stream in (completed.stdout, completed.stderr):
            if stream:
                sys.stderr.buffer.write(stream)
                if not stream.endswith(b"\n"):
                    sys.stderr.buffer.write(b"\n")
        if completed.returncode:
            fail("CONVERTER_FAILED", "/converter", "converter returned nonzero", converter_exit_code=completed.returncode)
        text_file, metadata_file = staging / "text.txt", staging / "metadata.json"
        if not text_file.is_file():
            fail("CONVERTER_OUTPUT_INVALID", "/converter_output/text", "text.txt missing")
        if not metadata_file.is_file():
            fail("CONVERTER_OUTPUT_INVALID", "/converter_output/metadata", "metadata.json missing")
        try:
            text_bytes = text_file.read_bytes()
            if text_bytes.startswith(b"\xef\xbb\xbf"):
                raise UnicodeError("UTF-8 BOM forbidden")
            text = text_bytes.decode("utf-8")
        except UnicodeError as exc:
            fail("CONVERTER_OUTPUT_INVALID", "/converter_output/text", str(exc))
        try:
            metadata = read_json(metadata_file)
            _validate_metadata(metadata, text)
        except Exception as exc:
            from .formats import Invalid
            if isinstance(exc, Invalid) and exc.code == "FILE_ERROR":
                raise
            fail("CONVERTER_OUTPUT_INVALID", "/converter_output/metadata", str(exc))
        if digest(file_bytes(original)) != original_hash:
            fail("ORIGINAL_CHANGED", "/arguments/input", "original changed during conversion")
        target.mkdir(parents=True, exist_ok=True)
        published = []
        try:
            for name, data in (("text.txt", text_bytes), ("metadata.json", json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))):
                destination = target / name
                try:
                    with destination.open("xb") as stream:
                        published.append(destination)
                        stream.write(data)
                        stream.flush()
                        os.fsync(stream.fileno())
                except FileExistsError:
                    fail("FILE_EXISTS", str(destination), "output already exists")
                except OSError as exc:
                    fail("FILE_ERROR", str(destination), str(exc))
            published_text_hash = digest(file_bytes(target / "text.txt"))
        except Exception:
            for item in published:
                try:
                    item.unlink()
                except OSError:
                    pass
            raise
    return {"ok": True, "input": str(original), "output_dir": str(target),
            "text": str(target / "text.txt"), "metadata": str(target / "metadata.json"),
            "original_hash": original_hash, "text_hash": published_text_hash,
            "anomalies": metadata["anomalies"]}
