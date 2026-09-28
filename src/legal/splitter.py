"""Lossless article ranges using contract_v3 structure candidates."""

from __future__ import annotations

import re

from .scan_structure_reference import (RE_CN_ARTICLE, RE_CN_CHAPTER, RE_DECIMAL,
                                       RE_EN_ARTICLE, RE_EN_CLAUSE, RE_EN_SECTION,
                                       _normalize_heading_line, scan_structure)

ALGORITHM_VERSION = "contract_v3.article.2"
MARKDOWN_HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)\s*$")
NUMBERED = (RE_CN_ARTICLE, RE_DECIMAL, RE_EN_ARTICLE, RE_EN_SECTION, RE_EN_CLAUSE)
NON_CONTRACT_HEADINGS = re.compile(
    r"^(?:contents|table of contents|table schedules|conditions of contract|目录|附表目录)$",
    re.IGNORECASE,
)
SENTENCE_END = re.compile(r"[.!?。！？;；:]\s*$")
PREAMBLE_TITLE = re.compile(r"^\*\*[^*]*\bContract Agreement\*\*\s*$", re.I)
PREAMBLE_COVER = re.compile(r"^\*\*(?![^*]*\bAgreement\b)[^*]*\bContract\b\*\*\s*$", re.I)
PREAMBLE_TRANSITION = re.compile(r"^\*\*\[?(?:Whereas|Now Therefore|In Witness Whereof)\]?", re.I)
PREAMBLE_NUMBER = re.compile(r"^([1-9][0-9]?|[A-Z])\.\s{2,}\S")


def _physical_lines(text):
    chunks = text.split("\n")
    lines = [chunk + "\n" for chunk in chunks[:-1]]
    if chunks[-1]:
        lines.append(chunks[-1])
    starts, position = [], 0
    for line in lines:
        starts.append(position)
        position += len(line)
    if position != len(text):
        raise ValueError("physical line coverage differs from source")
    return lines, starts


def _heading_number(title):
    for pattern in NUMBERED:
        if match := pattern.match(title):
            return match.group(0).strip()
    return None


def _heading_candidates(lines, starts):
    headings = []
    fenced = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            fenced = not fenced
            continue
        if fenced:
            continue
        match = MARKDOWN_HEADING.match(line.rstrip("\r\n"))
        if not match:
            continue
        raw = match.group(2)
        unnumbered = ".unnumbered" in raw
        title = re.sub(r"\s*\{[^}]*\}\s*$", "", raw).strip()
        headings.append({"line": index + 1, "start": starts[index],
                         "level": len(match.group(1)), "title": title,
                         "number": _heading_number(title),
                         "special": unnumbered or bool(NON_CONTRACT_HEADINGS.fullmatch(title))})
    return headings


def _markdown_roles(headings):
    """Classify logical article boundaries without fixing a Markdown level."""
    regular = [heading for heading in headings if not heading["special"]]
    if not regular:
        return {heading["start"]: ("context", None) for heading in headings}
    top_level = min(item["level"] for item in regular)
    top = [item for item in regular if item["level"] == top_level]
    children = [item for item in regular if item["level"] == top_level + 1]
    explicit_chapter = any(RE_CN_CHAPTER.match(item["title"]) or
                           re.match(r"^CHAPTER\b", item["title"], re.I)
                           for item in top)
    explicit_article = any(RE_CN_ARTICLE.match(item["title"]) or
                           RE_EN_ARTICLE.match(item["title"]) or
                           RE_EN_CLAUSE.match(item["title"]) or
                           RE_EN_SECTION.match(item["title"])
                           for item in top)
    numbered_children = any(RE_CN_ARTICLE.match(item["title"]) or
                            RE_EN_ARTICLE.match(item["title"]) or
                            RE_EN_CLAUSE.match(item["title"]) or
                            RE_EN_SECTION.match(item["title"])
                            for item in children)
    owners = set()
    for child in children:
        preceding = [item for item in top if item["start"] < child["start"]]
        if preceding:
            owners.add(preceding[-1]["start"])
    chaptered = bool(children and not explicit_article and
                     (explicit_chapter or numbered_children or len(owners) >= 2))
    article_level = top_level + 1 if chaptered else top_level
    roles = {}
    for heading in headings:
        if heading["special"] and heading["level"] <= article_level:
            roles[heading["start"]] = ("context", None)
        elif chaptered and heading["level"] == top_level:
            roles[heading["start"]] = ("chapter", heading["number"])
        elif heading["level"] == article_level:
            roles[heading["start"]] = ("article", heading["number"])
        elif heading["level"] < article_level:
            roles[heading["start"]] = ("context", heading["number"])
    return roles


def _plain_roles(scan, lines, starts):
    """Accept scanner candidates only where the line can start a provision."""
    explicit_chapters = [item for item in scan["chapters"]
                         if RE_CN_CHAPTER.match(item["num"]) or
                         re.match(r"^CHAPTER\b", item["num"], re.I)]
    explicit_chapters.extend({"line_start": index + 1, "num": line.strip()}
                             for index, line in enumerate(lines)
                             if re.match(r"^\s*CHAPTER\s+(?:[IVXLCDM]+|\d+)\b", line, re.I))
    if explicit_chapters:
        source = explicit_chapters + scan["articles"]
    else:
        parents = [item for item in scan["chapters"]
                   if item.get("is_decimal") or
                   str(item.get("num", "")).upper().startswith("ARTICLE ")]
        first_parent = min((item["line_start"] for item in parents), default=10 ** 9)
        source = parents + [item for item in scan["articles"]
                            if item["line_start"] < first_parent]
        if not parents:
            source = scan["articles"]
    attachment = scan.get("attachment_list")
    if attachment:
        source.append({"line_start": attachment["line_start"], "num": "", "is_attachment": True})
    candidates = {}
    for item in sorted(source, key=lambda entry: entry["line_start"]):
        line_no = item["line_start"]
        if not 1 <= line_no <= len(lines):
            continue
        index = line_no - 1
        previous = lines[index - 1].strip() if index else ""
        previous_candidate = index and starts[index - 1] in candidates
        if previous and not previous_candidate and not SENTENCE_END.search(previous) and not previous.startswith("|"):
            continue
        title = _normalize_heading_line(lines[index].strip())
        number = _heading_number(title) or str(item.get("num") or "")
        role = "context" if item.get("is_attachment") else "chapter" if item in explicit_chapters else "article"
        candidates[starts[index]] = (role, number)
    return candidates


def _preamble_roles(lines, starts, limit):
    """Separate expressly marked agreement provisions before the first heading."""
    roles = {}
    in_agreement = False
    pending_number = None
    for index, line in enumerate(lines):
        if starts[index] >= limit:
            break
        stripped = line.strip()
        if not in_agreement and PREAMBLE_COVER.match(stripped):
            roles[starts[index]] = ("context", None)
        elif PREAMBLE_TITLE.match(stripped):
            roles[starts[index]] = ("context", None)
            in_agreement = True
        elif in_agreement and PREAMBLE_TRANSITION.match(stripped):
            expected = "A" if re.search(r"Whereas", stripped, re.I) else "1" if re.search(r"Now Therefore", stripped, re.I) else None
            next_number = None
            for following in range(index + 1, len(lines)):
                if starts[following] >= limit or PREAMBLE_TRANSITION.match(lines[following].strip()):
                    break
                if found := PREAMBLE_NUMBER.match(lines[following]):
                    next_number = found.group(1)
                    break
            pending_number = expected if next_number == expected else None
            roles[starts[index]] = ("exception", expected + ".") if pending_number else ("context", None)
        elif in_agreement and (match := PREAMBLE_NUMBER.match(line)):
            if match.group(1) != pending_number:
                roles[starts[index]] = ("exception", match.group(1) + ".")
            pending_number = None
    return roles


def split_text(text):
    scan = scan_structure(text=text)
    lines, starts = _physical_lines(text)
    headings = _heading_candidates(lines, starts)
    roles = _markdown_roles(headings) if headings else _plain_roles(scan, lines, starts)
    if headings and headings[0]["start"] > 0:
        roles.update(_preamble_roles(lines, starts, headings[0]["start"]))
    boundaries = sorted({0, len(text), *roles})
    clauses = []
    for start, end in zip(boundaries, boundaries[1:]):
        if start == end:
            continue
        role, number = roles.get(start, ("context", None))
        clauses.append({"sequence": len(clauses) + 1,
                        "original_number": number if role in {"article", "exception"} else None,
                        "text": text[start:end], "start_offset": start,
                        "end_offset": end, "anomalies": []})
    if clauses and not any(role == "article" for role, _ in roles.values()) and text.strip():
        clauses[0]["anomalies"].append({"type": "unrecognized_article",
                                         "detail": "未能可靠识别 article 层级，原文完整保留",
                                         "line": 1})
    accepted = set(roles)
    for item in scan["anomalies"]:
        line = item.get("at_line") or item.get("lines", [1])[0]
        if not 1 <= line <= len(starts) or starts[line - 1] not in accepted:
            continue
        offset = starts[line - 1]
        if roles[offset][0] != "article" or roles[offset][1] is None:
            continue
        for clause in clauses:
            if clause["start_offset"] <= offset < clause["end_offset"]:
                clause["anomalies"].append({"type": item["type"],
                                            "detail": item["detail"], "line": line})
                break
    if "".join(clause["text"] for clause in clauses) != text:
        raise ValueError("character coverage failed")
    return clauses
