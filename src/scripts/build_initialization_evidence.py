"""Build a source-addressed clause index for the first vocabulary reading.

This is a reading aid. Clause themes and candidate units still require semantic review.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "work" / "vocab-init-2026-09-27"
IGNORE = (
    "This document is restricted for distribution",
    "© FIDIC 2017",
    "FORMS",
    "GUIDANCE",
    "GENERAL",
    "CONDITIONS",
    "ICC Model Contracts |",
    "ICC Model Contract |",
    "[p.",
)
PARTIES = re.compile(
    r"\b(?:Party|Parties|Employer|Contractor|Seller|Buyer|Supplier|Distributor|"
    r"Principal|Agent|Franchisor|Franchisee|Intermediary|Counterpart|Investor|"
    r"Entrepreneur|Company|Consultant|Employee|Receiving Party|Disclosing Party|DAAB)\b",
    re.I,
)
MODALITY = re.compile(
    r"\b(?:shall|must|may|should|will|is entitled to|agrees to|undertakes to|"
    r"has the right to|is obliged to)\b",
    re.I,
)


def line_offsets(lines: list[str]) -> list[int]:
    starts = []
    point = 0
    for line in lines:
        starts.append(point)
        point += len(line)
    return starts


def fidic_title(lines: list[str], number_line: int):
    parts = []
    body_line = number_line + 1
    for j in range(number_line + 1, min(number_line + 5, len(lines))):
        part = lines[j].strip()
        if not part:
            body_line = j + 1
            break
        if len(part) > 58 or re.search(r"\b(?:shall|means|may|must|will|is entitled)\b", part, re.I):
            body_line = j
            break
        if part.endswith((".", ";", ":")) and parts:
            body_line = j
            break
        parts.append(part)
        body_line = j + 1
    return " ".join(parts), body_line


def headings(source_id: str, lines: list[str]):
    for i, line in enumerate(lines):
        n = i + 1
        value = line.strip()
        section = None
        body_line = i + 1
        if source_id == "fidic-silver-2017":
            if 985 <= n <= 9655 and re.fullmatch(r"(?:[1-9]|1[0-9]|2[0-1])\.\d+(?:\.\d+)?", value):
                section = "Main conditions"
            elif 9670 <= n < 10445 and re.fullmatch(r"(?:[1-9]|1[0-2])", value):
                section = "DAAB agreement"
            elif 10458 <= n < 11045 and re.fullmatch(r"Rule (?:[1-9]|10)", value):
                section = "DAAB procedural rules"
            if section:
                is_definition = section == "Main conditions" and value.startswith("1.1.")
                if is_definition:
                    value += " Definition"
                else:
                    title, body_line = fidic_title(lines, i)
                    value += " " + title
        elif source_id == "icc-agency-distribution-634":
            if 37 <= n < 195:
                section = "Agency"
            elif 217 <= n < 396:
                section = "Distributorship"
            if section and (re.match(r"^### \d+\.", value) or re.match(r"^\*\*A[–-]\d+\b", value)):
                value = re.sub(r"^### |^\*\*|\*\*$", "", value)
            else:
                section = None
        elif source_id == "icc-franchising-712":
            if 156 <= n < 694 and (value == "### PREAMBLE" or re.match(r"^### Article \d+", value)):
                section = "Franchising"
                value = value.removeprefix("### ")
        elif source_id == "icc-intermediary-619":
            if 160 <= n < 336 and re.match(r"^\*\*A-\d+", value):
                section = "Intermediary special conditions"
                value = value.strip("*")
            elif 336 <= n < 459 and re.match(r"^\*\*Art\. \d+", value):
                section = "Intermediary general conditions"
                value = value.strip("*")
        elif source_id == "icc-sale-general":
            if n >= 13 and re.match(r"^### Article \d+", value):
                section = "Sale general conditions"
                value = value.removeprefix("### ")
        elif source_id == "icc-startups-827":
            for start, end, label in (
                (225, 550, "Term sheet"),
                (675, 1620, "Shareholders agreement"),
                (1883, 2273, "Directors services agreement"),
                (2465, 2760, "Employment agreement"),
                (3037, 3238, "Confidentiality agreement"),
            ):
                if start <= n <= end and re.match(r"^Article \d+\s+\S", value):
                    section = label
                    break
        if section:
            yield i, section, value, body_line


def first_quote(lines: list[str], first_line: int, stop: int, starts: list[int]):
    for i in range(first_line, min(stop, first_line + 18, len(lines))):
        raw = lines[i]
        stripped = raw.strip()
        if not stripped or stripped.startswith((">", "[^", "---")):
            continue
        if any(stripped.startswith(prefix) for prefix in IGNORE):
            continue
        if stripped in {"A.", "B.", "(a)", "(b)", "Articles", "Parties"}:
            continue
        if re.fullmatch(r"\d{1,3}", stripped):
            continue
        if len(stripped) < 12:
            continue
        quote = stripped[:180]
        left = starts[i] + raw.index(stripped)
        return quote, left, left + len(quote)
    return None, None, None


def main() -> None:
    manifest = json.loads((WORK / "corpus.json").read_text(encoding="utf-8"))
    out = WORK / "first-pass-clause-index.jsonl"
    counts = {}
    with out.open("w", encoding="utf-8") as stream:
        for material in manifest["materials"]:
            source_id = material["id"]
            path = Path(material["text_path"])
            text = path.read_text(encoding="utf-8")
            lines = text.splitlines(keepends=True)
            starts = line_offsets(lines)
            found = list(headings(source_id, lines))
            counts[source_id] = len(found)
            for k, (i, section, theme, body_line) in enumerate(found):
                stop = found[k + 1][0] if k + 1 < len(found) else len(lines)
                quote, left, right = first_quote(lines, body_line, stop, starts)
                if quote is None:
                    continue
                sample = "".join(lines[i: min(stop, i + 25)])
                item = {
                    "source_id": source_id,
                    "contract_section": section,
                    "heading": theme,
                    "theme_draft": re.sub(r"\s+", " ", theme),
                    "contracting_point_draft": quote,
                    "party_mentions": sorted(set(PARTIES.findall(sample)), key=str.casefold),
                    "modal_words": sorted(set(MODALITY.findall(sample)), key=str.casefold),
                    "evidence": {
                        "file": str(path),
                        "text_hash": material["text_hash"],
                        "start_offset": left,
                        "end_offset": right,
                        "quote": quote,
                    },
                    "status": "first_pass_draft_needs_semantic_review",
                }
                stream.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(json.dumps({"output": str(out), "headings": counts}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
