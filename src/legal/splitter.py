"""Lossless article ranges using contract_v3 structure candidates."""

from __future__ import annotations

import re

from .scan_structure_reference import (RE_CN_ARTICLE, RE_CN_CHAPTER, RE_DECIMAL,
                                       RE_EN_ARTICLE, RE_EN_CLAUSE, RE_EN_SECTION,
                                       _is_inline_continuation, _normalize_heading_line,
                                       cn2int, roman2int, scan_structure)

ALGORITHM_VERSION = "contract_v3.article.4"
MARKDOWN_HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)\s*$")
NUMBERED = (RE_CN_ARTICLE, RE_DECIMAL, RE_EN_ARTICLE, RE_EN_SECTION, RE_EN_CLAUSE)
NON_CONTRACT_HEADINGS = re.compile(
    r"^(?:contents|table of contents|table schedules|conditions of contract|目录|附表目录)$",
    re.IGNORECASE,
)
SENTENCE_END = re.compile(r"[.!?。！？;；:]\s*$")
ATTACHMENT = re.compile(r"^(?:附件[一二三四五六七八九十百零\d]+|(?i:Appendix|Exhibit|Schedule|Annex)\s+[A-Z\d]+)(?![A-Za-z\d])")


def _title(line):
    """Read a title through formatting layers without changing source bytes."""
    title = _normalize_heading_line(line.strip())
    title = re.sub(r"\s*\{[^}]*\}", "", title)
    title = re.sub(r"[*_`]", "", title).strip()
    if title.startswith("[") and "]" in title:
        title = title[1:].replace("]", "", 1)
    return title.strip()


def _region_roles(lines, starts, first_article=None):
    """Find independent annex/signature titles, not wrapped cross-references."""
    roles = {}
    fenced = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if fenced or stripped.startswith("|"):
            continue
        title = _title(line)
        attached = ATTACHMENT.match(title)
        signature = re.fullmatch(r"(?:SIGNATURES?|SIGNATURE PAGE|签署页|签署)", title, re.I)
        attestation = re.match(r"^IN WITNESS WHEREOF\b", title, re.I)
        marked = bool(MARKDOWN_HEADING.match(line) or stripped.startswith(("**", "__", "[")))
        if (signature or attestation and first_article is not None and starts[i] > first_article) and (marked or i == 0 or not lines[i - 1].strip()):
            roles[starts[i]] = ("context", None)
        elif attached:
            after = title[attached.end():].strip()
            # Uppercase standalone labels and explicit formatting are useful
            # evidence, but "Appendix 1 to ..." remains a cross-reference.
            if _is_inline_continuation(after):
                continue
            if marked or title.startswith("附件") or not after or after.startswith(("--", "-", "–", "—", ":", "：")):
                roles[starts[i]] = ("context", None)
    return roles


def _explicit_roles(lines, starts):
    """Recognize labelled provisions even when Word supplied misleading styles."""
    found = []
    fenced = False
    for i, line in enumerate(lines):
        if line.strip().startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if fenced or line.lstrip().startswith("|"):
            continue
        title = _title(line)
        pattern = next((p for p in (RE_CN_ARTICLE, RE_EN_CLAUSE, RE_EN_ARTICLE, RE_EN_SECTION)
                        if p.match(title)), None)
        if pattern is None:
            continue
        match = pattern.match(title)
        after = title[match.end():].strip()
        if pattern is not RE_CN_ARTICLE and _is_inline_continuation(after):
            continue
        marked = bool(MARKDOWN_HEADING.match(line) or re.search(r"\*\*|__", line))
        previous = lines[i - 1].strip() if i else ""
        if pattern is not RE_CN_ARTICLE and not marked and previous and not SENTENCE_END.search(previous) and not previous.startswith("|"):
            continue
        found.append((starts[i], match.group(0).strip(), pattern, match.group(1)))
    # Explicit CLAUSE / 第X条 takes precedence over a numbered paragraph's
    # visual level. ARTICLE/Section hierarchies still use the existing rules.
    primary = [f for f in found if f[2] in (RE_EN_CLAUSE, RE_CN_ARTICLE)]
    if not primary:
        return {}
    depths = {}
    for _, _, pattern, raw in primary:
        depths[pattern] = min(depths.get(pattern, 99), raw.count("."))
    return {start: ("article", number) for start, number, pattern, raw in primary
            if raw.count(".") == depths[pattern]}


def _number_anomalies(roles, starts):
    """Compare only accepted articles within the same parent and series."""
    result = []
    previous = {}
    for offset, (role, number) in sorted(roles.items()):
        if role in {"chapter", "context"}:
            previous.clear()
            continue
        if role != "article" or not number:
            continue
        if match := RE_CN_ARTICLE.match(number):
            series, parts = "chinese", (cn2int(match.group(1)),)
        elif match := re.match(r"^(ARTICLE|CLAUSE|Section)\s+([\d.]+|[IVXLCDM]+)\b", number, re.I):
            raw = match.group(2).rstrip(".")
            parts = tuple(map(int, raw.split("."))) if raw[0].isdigit() else (roman2int(raw),)
            series = match.group(1).lower()
        elif match := RE_DECIMAL.match(number):
            series, parts = "decimal", tuple(map(int, match.group(1).split(".")))
        else:
            continue
        key = (series, len(parts), parts[:-1])
        current = (parts[-1], number, starts.index(offset) + 1)
        if key in previous:
            old = previous[key]
            delta = current[0] - old[0]
            if delta > 1 or delta == 0:
                detail = (f"{old[1]} → {number}，间隔 {delta - 1} 条，疑似缺失" if delta > 1
                          else f"{number} 重复出现（行 {old[2]} 和行 {current[2]}）")
                result.append({"type": "skip" if delta > 1 else "duplicate", "detail": detail,
                               "line": old[2] if delta > 1 else current[2]})
        previous[key] = current
    return result


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
        title = _title(raw)
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
    chapter_levels = [item["level"] for item in regular
                      if RE_CN_CHAPTER.match(item["title"]) or
                      re.match(r"^CHAPTER\b", item["title"], re.I)]
    if chapter_levels:
        # A document title above explicit chapters is navigation/context, not
        # another contract chapter that changes the article depth.
        top_level = min(chapter_levels)
    else:
        highest = [item for item in regular if item["level"] == top_level]
        if len(highest) == 1 and highest[0]["number"] is None and re.search(
                r"(?:合同|协议|\bcontract\b|\bagreement\b)", highest[0]["title"], re.I):
            descendants = [item for item in regular if item["level"] > top_level]
            if descendants:
                top_level = min(item["level"] for item in descendants)
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
    decimal_children = []
    for child in children:
        preceding = [item for item in top if item["start"] < child["start"]]
        if preceding:
            owners.add(preceding[-1]["start"])
            parent = RE_DECIMAL.match(preceding[-1]["title"])
            number = RE_DECIMAL.match(child["title"])
            decimal_children.append(bool(parent and number and
                                         number.group(1).startswith(parent.group(1) + ".")))
    internal_numbering = bool(decimal_children) and all(decimal_children)
    chaptered = bool(children and not explicit_article and
                     (explicit_chapter or numbered_children or
                      (len(owners) >= 2 and not internal_numbering)))
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
        # The reference scanner strips is_decimal before returning; recover
        # the numbering from the actual candidate line instead of that flag.
        parents = [item for item in scan["chapters"]
                   if (RE_DECIMAL.match(str(item.get("num", ""))) and
                       RE_DECIMAL.match(str(item.get("num", ""))).group(1).count(".") == 0) or
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


def split_text(text):
    scan = scan_structure(text=text)
    lines, starts = _physical_lines(text)
    headings = _heading_candidates(lines, starts)
    roles = _markdown_roles(headings) if headings else _plain_roles(scan, lines, starts)
    explicit = _explicit_roles(lines, starts)
    # An accepted ARTICLE/Section can own an internal Clause heading. Keep
    # that hierarchy rather than replacing the parent with its last child.
    labelled_parent = any(role == "article" and number and
                          re.match(r"^(?:ARTICLE|Section)\b", number, re.I)
                          for role, number in roles.values())
    if explicit and not labelled_parent:
        roles = {offset: value for offset, value in roles.items()
                 if value[0] == "chapter"}
        roles.update(explicit)
    first_article = min((offset for offset, (role, _) in roles.items() if role == "article"), default=None)
    roles.update(_region_roles(lines, starts, first_article))
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
    for item in _number_anomalies(roles, starts):
        line = item["line"]
        offset = starts[line - 1]
        for clause in clauses:
            if clause["start_offset"] <= offset < clause["end_offset"]:
                clause["anomalies"].append({"type": item["type"],
                                            "detail": item["detail"], "line": line})
                break
    if "".join(clause["text"] for clause in clauses) != text:
        raise ValueError("character coverage failed")
    return clauses
