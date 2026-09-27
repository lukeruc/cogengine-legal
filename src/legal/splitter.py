"""Lossless clause slices adapted from the pinned contract_v3 scanner."""

from __future__ import annotations

from .scan_structure_reference import (RE_ATTACHMENT_TOKEN, RE_CN_ARTICLE, RE_CN_CHAPTER,
                                       RE_CN_PART, RE_CN_SECTION, RE_DECIMAL,
                                       RE_EN_ARTICLE, RE_EN_SECTION, RE_EN_CLAUSE,
                                       _normalize_heading_line, scan_structure)

ALGORITHM_VERSION = "contract_v3.adapted.1"


def split_text(text):
    scan = scan_structure(text=text)
    chunks = text.split("\n")
    lines = [chunk + "\n" for chunk in chunks[:-1]]
    if chunks[-1]:
        lines.append(chunks[-1])
    starts = []
    position = 0
    for line in lines:
        starts.append(position)
        position += len(line)
    if position != len(text):
        raise ValueError("physical line coverage differs from source")
    numbered = {}
    for item in scan["chapters"] + scan["articles"]:
        line = item["line_start"]
        if 1 <= line <= len(starts):
            visible = _normalize_heading_line(lines[line - 1].strip())
            match = next((found for pattern in (RE_CN_PART, RE_CN_CHAPTER, RE_CN_SECTION,
                                                 RE_CN_ARTICLE, RE_DECIMAL, RE_EN_ARTICLE,
                                                 RE_EN_SECTION, RE_EN_CLAUSE)
                          if (found := pattern.match(visible))), None)
            numbered[starts[line - 1]] = match.group(0).strip() if match else str(item.get("num") or "")
    boundaries = {0, len(text)}
    boundaries.update(numbered)
    previous_blank = True
    previous_table = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        table = stripped.startswith("|")
        if stripped and previous_blank:
            boundaries.add(starts[i])
        if table and not previous_table:
            boundaries.add(starts[i])
        if previous_table and not table:
            boundaries.add(starts[i])
        normalized = _normalize_heading_line(stripped)
        match = RE_ATTACHMENT_TOKEN.match(normalized)
        if match:
            boundaries.add(starts[i])
            numbered[starts[i]] = match.group(0)
        previous_blank = not bool(stripped)
        previous_table = table
    ordered = sorted(boundaries)
    clauses = []
    for index, (start, end) in enumerate(zip(ordered, ordered[1:]), start=1):
        if start == end:
            continue
        fragment = text[start:end]
        clauses.append({"sequence": index, "original_number": numbered.get(start),
                        "text": fragment, "start_offset": start, "end_offset": end,
                        "anomalies": []})
        if clauses[-1]["original_number"] is None and fragment.strip():
            clauses[-1]["anomalies"].append({"type": "unnumbered", "detail": "未识别编号，需按原文阅读", "line": _line_for(starts, start)})
    for item in scan["anomalies"]:
        line = item.get("at_line") or item.get("lines", [1])[0]
        if not 1 <= line <= len(starts):
            continue
        offset = starts[line - 1]
        for clause in clauses:
            if clause["start_offset"] <= offset < clause["end_offset"]:
                clause["anomalies"].append({"type": item["type"], "detail": item["detail"], "line": line})
                break
    if "".join(c["text"] for c in clauses) != text:
        raise ValueError("character coverage failed")
    return clauses


def _line_for(starts, offset):
    return sum(1 for start in starts if start <= offset)
