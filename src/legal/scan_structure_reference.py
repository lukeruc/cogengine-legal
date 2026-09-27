#!/usr/bin/env python3
"""Pre-scan a contract Markdown file to extract clause numbering structure.

Replaces the Structure Agent's first-pass read. Outputs a JSON map of all
clauses with line ranges, hierarchy, and anomaly flags.

Usage:
    python scan-structure.py contract.md [_internal/scan-result.json]
    python scan-structure.py template.md

Supports both Chinese (第X条) and English (ARTICLE/Section/Clause) numbering.
"""

import json
import re
import sys
from pathlib import Path

# ── Chinese numeral conversion ──────────────────────────────────────────

_CN_NUM = {
    "零": 0, "〇": 0, "一": 1, "二": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    "百": 100, "千": 1000, "万": 10000, "亿": 100000000,
}


def cn2int(s: str) -> int:
    """Convert a Chinese numeral string to integer.  '三百二十五' -> 325."""
    s = s.strip()
    if s.isdigit():
        return int(s)

    result, section, digit = 0, 0, 0
    for ch in s:
        if ch not in _CN_NUM:
            if ch.isdigit():
                digit = int(ch)
            continue
        v = _CN_NUM[ch]
        if v >= 10000:                  # 万、亿
            result = (result + section + digit) * v
            section = digit = 0
        elif v >= 10:                   # 十、百、千
            section += (digit or 1) * v
            digit = 0
        else:
            digit = v
    return result + section + digit


# ── Roman numeral conversion ────────────────────────────────────────────

_ROMAN_VAL = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}


def roman2int(s: str) -> int:
    """Convert Roman numeral string to integer.  'xiv' -> 14."""
    s = s.strip().lower()
    result = 0
    prev = 0
    for ch in reversed(s):
        if ch not in _ROMAN_VAL:
            continue
        cur = _ROMAN_VAL[ch]
        if cur < prev:
            result -= cur
        else:
            result += cur
        prev = cur
    return result


# ── Language detection ──────────────────────────────────────────────────

def detect_language(text: str) -> str:
    """Detect contract language by CJK character proportion in first 100 lines."""
    lines = text.split("\n")[:100]
    sample = "\n".join(lines)
    if not sample.strip():
        return "en"

    cjk = sum(1 for ch in sample if "一" <= ch <= "鿿" or "㐀" <= ch <= "䶿")
    total = len(sample.replace("\n", "").replace(" ", ""))
    if total == 0:
        return "en"
    ratio = cjk / total
    if ratio > 0.3:
        return "zh"
    if ratio < 0.1:
        return "en"
    return "bilingual"


# ── Regex patterns ──────────────────────────────────────────────────────

# Chinese patterns
RE_CN_PART = re.compile(r"^\s*第([一二三四五六七八九十百千\d]+)(编|部分)\s*")
RE_CN_CHAPTER = re.compile(r"^\s*第([一二三四五六七八九十百千\d]+)章\s*")
RE_CN_SECTION = re.compile(r"^\s*第([一二三四五六七八九十百千\d]+)节\s*")
RE_CN_ARTICLE = re.compile(r"^\s*第([一二三四五六七八九十百千\d]+)条\s*")
RE_CN_SUBITEM = re.compile(r"^\s*[（(]([一二三四五六七八九十\d]+)[）)]\s*")
RE_CN_NUMITEM = re.compile(r"^\s*(\d+)\s*[、,]")
# Inline reference (not a clause start)
RE_CN_INLINE_REF = re.compile(r".{2,}第[一二三四五六七八九十百千\d]+条")

# Decimal hierarchical numbering — "1." / "1.1" / "2.1.1". Language-agnostic;
# the dominant scheme in Chinese commercial (procurement / supply / EPC)
# contracts. The boundary guard (?![\d.]) rejects years ("2026"), large
# amounts and dotted codes ("46.113.620.00.000.099"). Trailing separator dot
# is consumed separately so "1." (group "1") and "1.1" (group "1.1") both work.
RE_DECIMAL = re.compile(r"^(\d{1,3}(?:\.\d{1,3}){0,3})\.?(?![\d.])")

# English patterns
RE_EN_ARTICLE = re.compile(r"^\s*ARTICLE\s+([IVXLCDM\d]+)\b", re.IGNORECASE)
RE_EN_SECTION = re.compile(r"^\s*Section\s+([\d.]+)\b", re.IGNORECASE)
RE_EN_CLAUSE = re.compile(r"^\s*Clause\s+([\d.]+)\b", re.IGNORECASE)
RE_EN_NUMPARA = re.compile(r"^\s*(\d+)\.\s+")
RE_EN_DOTTED = re.compile(r"^\s*(\d+\.\d+)\s+")
RE_EN_LETTER = re.compile(r"^\s*\(([a-zA-Z])\)\s+")
RE_EN_ROMAN = re.compile(r"^\s*\(([ivxlcdm]+)\)\s+", re.IGNORECASE)

# Continuation words — if text after "ARTICLE X" starts with these, it's inline text
_INLINE_CONTINUATION = {
    "of", "to", "the", "in", "for", "and", "or", "this", "that",
    "such", "herein", "hereby", "hereunder", "thereto", "thereof",
    "shall", "will", "may", "must", "not", "any", "all", "each",
    "is", "be", "are", "was", "were", "has", "have", "had",
    "by", "on", "at", "with", "from", "as", "it", "its",
    "a", "an", "no", "nor", "but", "if", "so", "yet",
}

# Attachment token — 附件X / Appendix N / Exhibit A / Schedule A / Annex A.
# Used both to detect attachment-list lines and to split several attachments
# that pandoc may join onto a single line. NOTE: callers match this against a
# line that has already had its leading '#' Markdown heading markers stripped,
# so the pattern is anchored on the clause text itself, not on line start.
RE_ATTACHMENT_TOKEN = re.compile(
    r"(附件[一二三四五六七八九十百零\d]+"
    # Label word is case-insensitive (Appendix/APPENDIX/appendix), but the
    # identifier must be an UPPERCASE letter or digit, so a description like
    # "Schedule of Values" is NOT mis-tokenised at "of". Scope the flag so it
    # does not weaken the [A-Z\d] identifier class.
    r"|(?i:Appendix|Exhibit|Schedule|Annex)\s+[A-Z\d]+)"
)


def normalize_article_num(raw: str, fmt: str) -> int:
    """Normalize article number to integer for comparison."""
    raw = raw.strip()
    if fmt == "chinese" and not raw.isdigit():
        try:
            return cn2int(raw)
        except (ValueError, KeyError):
            return -1
    elif fmt == "roman":
        try:
            return roman2int(raw)
        except (ValueError, KeyError):
            return -1
    try:
        # "1.1" -> just the first part for ordering
        if "." in raw:
            return int(raw.split(".")[0])
        return int(raw)
    except ValueError:
        return -1


def _normalize_heading_line(s: str) -> str:
    """Strip the pandoc formatting layers a Word heading can acquire when
    converted to Markdown: leading '#' heading markers, '>' blockquote markers
    (indented styles), and a full-line bold/italic wrap (bold-as-heading)."""
    s = re.sub(r"^#{0,6}\s*", "", s)
    s = re.sub(r"^\s*>+\s*", "", s)
    m = re.match(r"^\*{1,3}\s*(.+?)\s*\*{1,3}$", s)
    if m:
        s = m.group(1)
    return s


def _following_nonblank(lines: list, idx: int, limit: int = 8):
    """Recover the body text of a clause whose number sits alone on its line
    (e.g. "> 1.3"), or whose first line ends mid-sentence and pandoc wrapped
    the rest onto following lines. Returns (last_line_no, accumulated_text).

    Starts at the first non-blank line after `idx` and keeps accumulating while
    the continuation is mid-sentence (ends in a clause-internal punctuation
    like ，：；、) AND the next line is not itself a new clause heading (a
    decimal number, 第X编/章/节/条, or an attachment token). Stops at the first
    line that closes the sentence (。！？) or begins a new clause."""
    collected = []
    last_j = None
    started = False
    for j in range(idx + 1, min(idx + 1 + limit, len(lines))):
        t = _normalize_heading_line(lines[j]).strip()
        if not t:
            if started:
                break  # blank line ends a wrapped fragment run
            continue
        # A new clause heading means the previous clause's body is complete.
        if RE_DECIMAL.match(t) or RE_CN_ARTICLE.match(t) or RE_CN_CHAPTER.match(t) \
                or RE_CN_SECTION.match(t) or RE_CN_PART.match(t) \
                or RE_ATTACHMENT_TOKEN.match(t):
            break
        collected.append(t)
        last_j = j
        started = True
        # Sentence-closing punctuation → body is complete.
        if t.rstrip().endswith(("。", "！", "？", ".", "!", "?")):
            break
        # Clause-internal punctuation → likely wraps to another line; keep going.
        if not t.rstrip().endswith(("，", "：", "；", "、", ",", ":", ";")):
            break
    if not collected:
        return None, ""
    return (last_j + 1), "".join(collected)


def _nearest_preceding_chapter(chapters: list, line_no: int):
    """Return the .num of the chapter whose line_start is the largest value
    <= line_no, else None. Used to re-home sub-clauses whose original chapter
    attribution pointed at a dropped decimal chapter."""
    best_num, best_line = None, -1
    for c in chapters:
        ls = c.get("line_start")
        if ls is not None and ls <= line_no and ls > best_line:
            best_num, best_line = c["num"], ls
    return best_num


# ── Post-processing stages (pure functions over scan accumulators) ──────

def _resolve_decimal_chapters(chapters: list, articles: list) -> None:
    """Resolve ambiguous decimal depth-1 chapters in place.

    A decimal "1." line is: a TOC/section marker when the contract ALSO uses
    第X章 (drop it, re-home its sub-clauses to the nearest 第X章); the clause
    itself in a flat decimal contract (1./2./3. with no sub-clauses → promote
    to article); otherwise a real grouping chapter (keep)."""
    has_non_decimal_chapter = any(not c.get("is_decimal") for c in chapters)
    decimal_chapters = [c for c in chapters if c.get("is_decimal")]
    decimal_articles = [a for a in articles if a.get("_is_decimal")]
    if has_non_decimal_chapter and decimal_chapters:
        real_chapters = [c for c in chapters if not c.get("is_decimal")]
        decimal_nums = {c["num"] for c in decimal_chapters}
        for a in articles:
            if a.get("chapter") in decimal_nums:
                a["chapter"] = _nearest_preceding_chapter(real_chapters, a["line_start"])
                a["chapter_num_int"] = None
        chapters[:] = real_chapters
    elif decimal_chapters and not decimal_articles:
        for c in decimal_chapters:
            articles.append({
                "num": c["num"].rstrip("."),
                "num_int": c["num_int"],
                "num_raw": c["num"].rstrip("."),
                "title": c["title"],
                "line_start": c["line_start"],
                "line_end": None,
                "chapter": None,
                "chapter_num_int": None,
            })
        chapters[:] = []
    articles.sort(key=lambda a: a["line_start"])


def _apply_party_restart(articles: list, preamble_lines: list) -> None:
    """English party listing: when numbering restarts at 1 after a party
    listing, move the party items into the preamble."""
    if len(articles) < 4 or articles[0]["num_int"] != 1:
        return
    clause_keywords = ["confidential", "purpose", "agreement", "project",
                       "definition", "obligation", "term", "condition",
                       "represent", "warrant", "indemnif", "liability",
                       "terminat", "govern", "dispute", "notice", "payment"]
    for i in range(3, len(articles)):
        cur, prev = articles[i], articles[i - 1]
        if cur["num_int"] == 1 and prev["num_int"] >= 3:
            if any(kw in cur["title"].lower() for kw in clause_keywords):
                moved = articles[:i]
                articles[:] = articles[i:]
                for m in moved:
                    for ln in range(m["line_start"], (m["line_end"] or m["line_start"]) + 1):
                        if ln not in preamble_lines:
                            preamble_lines.append(ln)
                preamble_lines.sort()
                break


def _finalize_line_ends(articles: list, attachment_start, n_lines: int) -> None:
    """Set each article's line_end: mid-list articles end just before the next;
    the last article extends to end of file, or to the attachment list if one
    actually follows it (never below its own line_start)."""
    for i, art in enumerate(articles):
        if i + 1 < len(articles):
            art["line_end"] = articles[i + 1]["line_start"] - 1
        elif attachment_start and attachment_start > art["line_start"]:
            art["line_end"] = attachment_start - 1
        else:
            art["line_end"] = n_lines


def _detect_anomalies(articles: list) -> list:
    """Flag numbering skips / duplicates / format switches between consecutive
    same-chapter articles. Returns a new list of anomaly dicts."""
    anomalies = []

    def _record(num, cur, nxt, gap):
        if gap > 1:
            anomalies.append({
                "type": "skip",
                "level": "error" if gap > 2 else "warning",
                "detail": f'{cur["num"]} → {nxt["num"]}，间隔 {gap - 1} 条，疑似缺失',
                "after_article": cur["num"],
                "at_line": cur["line_start"],
            })
        elif gap == 0:
            anomalies.append({
                "type": "duplicate",
                "level": "error",
                "detail": f'{cur["num"]} 重复出现（行 {cur["line_start"]} 和行 {nxt["line_start"]}）',
                "lines": [cur["line_start"], nxt["line_start"]],
            })

    for i in range(len(articles) - 1):
        cur, nxt = articles[i], articles[i + 1]
        if cur.get("chapter") != nxt.get("chapter"):
            continue
        cur_raw, nxt_raw = cur.get("num_raw", ""), nxt.get("num_raw", "")
        is_dotted = "." in cur_raw and "." in nxt_raw
        if not is_dotted and nxt["num_int"] > 0 and cur["num_int"] > 0:
            _record(cur["num"], cur, nxt, nxt["num_int"] - cur["num_int"])
        elif is_dotted:
            cur_parts, nxt_parts = cur_raw.split("."), nxt_raw.split(".")
            if len(cur_parts) == len(nxt_parts):
                try:
                    _record(cur["num"], cur, nxt, int(nxt_parts[-1]) - int(cur_parts[-1]))
                except ValueError:
                    pass

    chinese_articles = [a for a in articles if "条" in a["num"]]
    digit_articles = [a for a in articles if a["num_raw"].isdigit() and "条" not in a["num"]]
    if chinese_articles and digit_articles:
        mid_line = (chinese_articles[-1]["line_start"] + digit_articles[0]["line_start"]) // 2
        anomalies.append({
            "type": "format_mix",
            "level": "warning",
            "detail": f"编号在第{mid_line}行附近从中文格式切换为数字格式",
            "at_line": mid_line,
        })
    return anomalies


def _detect_numbering_space(chapters: list, articles: list) -> str:
    """Per-chapter iff some real chapter's first article is numbered lower than
    the previous chapter's last article (a reset); otherwise monotonic → global."""
    real_chapters = [c for c in chapters if not c.get("is_part") and not c.get("is_section")]
    for i in range(1, len(real_chapters)):
        prev_arts = [a for a in articles if a.get("chapter") == real_chapters[i - 1]["num"]]
        cur_arts = [a for a in articles if a.get("chapter") == real_chapters[i]["num"]]
        if prev_arts and cur_arts and cur_arts[0]["num_int"] < prev_arts[-1]["num_int"]:
            return "per_chapter"
    return "global"


# ── Scan state + per-line clause handlers ───────────────────────────────

class ScanState:
    """Mutable state threaded through the main scan loop. Grouped here so each
    clause handler can be a plain method that reads/mutates shared accumulators
    instead of every variable being a closure-local in one giant function."""

    def __init__(self, lines: list):
        self.lines = lines
        self.chapters = []
        self.articles = []
        self.current_chapter = None      # dict of the active chapter, or None
        self.current_chapter_num = None  # num_int of active chapter
        self.article_idx = 0
        self.in_preamble = True
        self.in_attachment = False
        self.attachment_start = None
        self.attachment_items = []
        self.preamble_lines = []

    def open_chapter(self, num, num_int, title, line_no, takes_articles=True, **flags):
        """Record a chapter/part/section heading. Only headings that actually
        own articles (第X章, ARTICLE, decimal sections) become the active
        `current_chapter`; parts and 第X节 are recorded but do NOT take over
        article attribution (sub-clauses stay under the enclosing 第X章)."""
        entry = {
            "num": num,
            "num_int": num_int,
            "title": title,
            "line_start": line_no,
            "article_range_start": None,
            **flags,
        }
        self.chapters.append(entry)
        self.in_preamble = False
        if takes_articles:
            self.current_chapter = entry
            self.current_chapter_num = num_int

    def add_article(self, num, num_int, num_raw, title, line_no, is_decimal=False):
        """Record a leaf clause under the active chapter."""
        self.articles.append({
            "num": num,
            "num_int": num_int,
            "num_raw": num_raw,
            "title": title,
            "line_start": line_no,
            "line_end": None,
            "chapter": self.current_chapter["num"] if self.current_chapter else None,
            "chapter_num_int": self.current_chapter_num,
            **({"_is_decimal": True} if is_decimal else {}),
        })
        self.article_idx += 1
        if self.current_chapter:
            if self.current_chapter["article_range_start"] is None:
                self.current_chapter["article_range_start"] = num
            self.current_chapter["article_range_end"] = num
            self.current_chapter["article_count"] = self.current_chapter.get("article_count", 0) + 1
        self.in_preamble = False


def _try_chinese_heading(state: ScanState, stripped: str, line_no: int) -> bool:
    """Match 第X章/编/部分/节/条. Returns True if the line was consumed."""
    ch = RE_CN_CHAPTER.match(stripped)
    if ch:
        num_raw = ch.group(1)
        state.open_chapter(f"第{num_raw}章", normalize_article_num(num_raw, "chinese"),
                           stripped[ch.end():].strip(), line_no)
        return True
    part = RE_CN_PART.match(stripped)
    if part:
        num_raw, suffix = part.group(1), part.group(2)
        state.open_chapter(f"第{num_raw}{suffix}", normalize_article_num(num_raw, "chinese"),
                           stripped[part.end():].strip(), line_no,
                           takes_articles=False, is_part=True)
        return True
    sec = RE_CN_SECTION.match(stripped)
    if sec:
        num_raw = sec.group(1)
        state.open_chapter(f"第{num_raw}节", normalize_article_num(num_raw, "chinese"),
                           stripped[sec.end():].strip(), line_no,
                           takes_articles=False, is_section=True)
        return True
    art = RE_CN_ARTICLE.match(stripped)
    if art:
        num_raw = art.group(1)
        title = stripped[art.end():].strip()
        if not title or title.rstrip().endswith(("，", "：", "；", "、", ",", ":", ";")):
            _, more = _following_nonblank(state.lines, line_no - 1)
            title = (title + more) if title else more
        state.add_article(f"第{num_raw}条", normalize_article_num(num_raw, "chinese"),
                          num_raw, title, line_no)
        return True
    return False


def _try_decimal_clause(state: ScanState, stripped: str, line_no: int) -> bool:
    """Match decimal hierarchical numbering (1. / 1.1 / 2.1.1). depth-1 is a
    tentative chapter (resolved later); depth>=2 is an article. Returns True if
    consumed as a clause (a bare number alone is body text → False)."""
    dec = RE_DECIMAL.match(stripped)
    if not dec:
        return False
    num = dec.group(1)
    depth = num.count(".") + 1
    after = stripped[dec.end():]
    # Reject dates / numeric noise: number glued to a date/time unit. (NB: the
    # empty-title case must NOT match — "" in "..." is True in Python.)
    if after[:1] and after[:1] in "年月日号点时分秒":
        return False
    if depth == 1:
        # A bare depth-1 number with its title inline ("1. 合同标的") is a real
        # chapter; a bare number ALONE on its line is body text split off by
        # Word/pandoc ("...提前\n60\n天通知"). Real decimal chapters carry their
        # title inline, so do not borrow the next line here.
        d1_title = after.strip()
        if not d1_title:
            return False
        state.open_chapter(f"{num}.", int(num), d1_title, line_no, is_decimal=True)
        return True
    # depth >= 2 → article
    title = after.strip()
    if not title or title.rstrip().endswith(("，", "：", "；", "、", ",", ":", ";")):
        _, more = _following_nonblank(state.lines, line_no - 1)
        title = (title + more) if title else more
    state.add_article(num, int(num.split(".")[-1]), num, title, line_no, is_decimal=True)
    return True


def _is_decimal_heading(stripped: str) -> bool:
    """True iff this line would be consumed as a decimal clause by
    _try_decimal_clause (depth-1 with a title, or depth>=2; never a date or a
    bare number). Kept in lock-step with that function's acceptance criteria so
    the attachment-zone exit check agrees with clause detection."""
    dec = RE_DECIMAL.match(stripped)
    if not dec:
        return False
    num = dec.group(1)
    after = stripped[dec.end():]
    if after[:1] and after[:1] in "年月日号点时分秒":
        return False
    if num.count(".") == 0 and not after.strip():
        return False  # bare depth-1 number alone → body, not a clause
    return True


def _is_inline_continuation(after: str) -> bool:
    """True if the text after an English ARTICLE/Section/Clause keyword looks
    like inline prose rather than a heading title."""
    if not after or after in ("", ";", "."):
        return True
    first_word = after.split()[0].strip("—-_.,;:()[]{}").lower() if after.split() else ""
    return first_word in _INLINE_CONTINUATION


def _try_english_heading(state: ScanState, stripped: str, line_no: int) -> bool:
    """Match ARTICLE / Section / Clause / numbered paragraph. Returns True if
    consumed as a clause heading or article."""
    en_art = RE_EN_ARTICLE.match(stripped)
    if en_art:
        num_raw = en_art.group(1)
        after = stripped[en_art.end():].strip()
        if not _is_inline_continuation(after):
            num_int = normalize_article_num(num_raw, "roman" if num_raw.isalpha() else "arabic")
            state.open_chapter(f"ARTICLE {num_raw}", num_int, after, line_no)
            return True
    en_sec = RE_EN_SECTION.match(stripped)
    if en_sec:
        num_raw = en_sec.group(1)
        after = stripped[en_sec.end():].strip()
        if not _is_inline_continuation(after):
            state.add_article(f"Section {num_raw}", normalize_article_num(num_raw, "arabic"),
                              num_raw, after, line_no)
            return True
    en_cl = RE_EN_CLAUSE.match(stripped)
    if en_cl:
        num_raw = en_cl.group(1)
        after = stripped[en_cl.end():].strip()
        if not _is_inline_continuation(after):
            state.add_article(f"Clause {num_raw}", normalize_article_num(num_raw, "arabic"),
                              num_raw, after, line_no)
            return True
    en_np = RE_EN_NUMPARA.match(stripped)
    if en_np and not RE_EN_DOTTED.match(stripped):
        num_raw = en_np.group(1)
        num_int = int(num_raw)
        # Detect clause restart: numbering drops back to 1 after party listing.
        if state.articles and num_int == 1 and state.articles[-1]["num_int"] > 3:
            state.preamble_lines = list(range(1, line_no))
            state.in_preamble = False
        if num_int >= 2 or (state.articles and num_int == 1):
            state.in_preamble = False
        state.add_article(f"{num_raw}.", num_int, num_raw,
                          stripped[en_np.end():].strip(), line_no)
        return True
    return False


# ── Main scan logic ─────────────────────────────────────────────────────

def scan_structure(filepath: str = None, *, text: str = None) -> dict:
    # The adapter supplies the exact registered text, preserving CR and LF.
    if text is None:
        text = Path(filepath).read_text(encoding="utf-8")
    lines = text.split("\n")
    lang = detect_language(text)
    state = ScanState(lines)

    for line_no, line in enumerate(lines, start=1):
        raw = line.strip()
        if not raw:
            continue
        # Strip pandoc heading layers (# heading, > blockquote, **bold**) so
        # clause regexes anchored at line start match the conceptual heading.
        stripped = _normalize_heading_line(raw)

        # Attachment detection — a line that begins with an attachment token.
        # pandoc may join several attachments onto one line, so capture each
        # token-to-token segment as a separate item.
        if RE_ATTACHMENT_TOKEN.match(stripped):
            if not state.in_attachment:
                state.in_attachment = True
                state.attachment_start = line_no
            token_spans = list(RE_ATTACHMENT_TOKEN.finditer(stripped))
            for i, m in enumerate(token_spans):
                seg_end = token_spans[i + 1].start() if i + 1 < len(token_spans) else len(stripped)
                state.attachment_items.append(stripped[m.start():seg_end].strip())
            continue

        if state.in_attachment:
            # Exit attachment zone when any clause-level heading resumes —
            # including decimal clauses, otherwise an inline attachment list
            # (e.g. "> 附件十一 …" inside a clause) would swallow the decimal
            # clauses that follow it.
            if (RE_CN_PART.match(stripped) or RE_CN_CHAPTER.match(stripped) or
                    RE_CN_SECTION.match(stripped) or RE_CN_ARTICLE.match(stripped) or
                    RE_EN_ARTICLE.match(stripped) or RE_EN_SECTION.match(stripped) or
                    RE_EN_CLAUSE.match(stripped) or _is_decimal_heading(stripped)):
                state.in_attachment = False
            else:
                continue

        handled = False
        if lang in ("zh", "bilingual"):
            handled = _try_chinese_heading(state, stripped, line_no) \
                or _try_decimal_clause(state, stripped, line_no)
        if not handled and lang in ("en", "bilingual"):
            handled = _try_english_heading(state, stripped, line_no)

        # Track preamble (only narrative lines not consumed as a clause).
        if not handled and state.in_preamble and not raw.startswith("#"):
            state.preamble_lines.append(line_no)

    chapters, articles = state.chapters, state.articles
    preamble_lines, attachment_start = state.preamble_lines, state.attachment_start
    attachment_items = state.attachment_items

    # ── Post-processing pipeline ──
    _resolve_decimal_chapters(chapters, articles)
    _apply_party_restart(articles, preamble_lines)
    _finalize_line_ends(articles, attachment_start, len(lines))
    anomalies = _detect_anomalies(articles)
    numbering_space = _detect_numbering_space(chapters, articles)

    # ── Build result ──
    # Strip internal tracking flags before serialising.
    for c in chapters:
        c.pop("is_decimal", None)
    for a in articles:
        a.pop("_is_decimal", None)
    scheme = {
        "language": lang,
        "numbering_space": numbering_space,
    }
    if lang in ("zh", "bilingual"):
        scheme.update({
            "has_part": any(c.get("is_part") for c in chapters),
            "has_chapter": any(c for c in chapters if not c.get("is_part") and not c.get("is_section")),
            "has_section": any(c.get("is_section") for c in chapters),
            "article_format": "chinese" if any("条" in a["num"] for a in articles) else "arabic",
            "sub_item_format": "chinese_paren",
        })
    if lang in ("en", "bilingual"):
        scheme.update({
            "has_article": any("ARTICLE" in c.get("num", "") for c in chapters),
            "section_format": "dotted" if any("." in a.get("num_raw", "") for a in articles) else "numeric",
        })

    preamble_out = None
    if preamble_lines:
        p_start = min(preamble_lines)
        p_end = max(preamble_lines)
        p_text = " ".join(lines[p_start - 1:p_end]).strip()[:200]
        preamble_out = {"line_start": p_start, "line_end": p_end, "preview": p_text}

    attachment_out = None
    if attachment_items:
        attachment_out = {"line_start": attachment_start, "items": attachment_items}

    return {
        "file": Path(filepath).name if filepath else "registered-text",
        "total_chars": len(text),
        "total_lines": len(lines),
        "numbering_scheme": scheme,
        "chapters": chapters,
        "articles": articles,
        "total_articles": len(articles),
        "anomalies": anomalies,
        "preamble": preamble_out,
        "attachment_list": attachment_out,
    }


def main(argv: list = None):
    """命令行入口。

    argv: 参数列表（不含程序名）。None 时从 sys.argv 读，便于
    `python -m contract_core.scripts.scan_structure` 与 cli.py 两种调用方式。
    """
    if argv is None:
        argv = sys.argv[1:]
    if len(argv) < 1 or argv[0] in ("-h", "--help", "help"):
        print("Usage: contract-core scan-structure <contract.md> [output.json]", file=sys.stderr)
        sys.exit(0 if (len(argv) >= 1 and argv[0] in ("-h", "--help", "help")) else 1)

    filepath = argv[0]
    result = scan_structure(filepath)

    output_path = argv[1] if len(argv) > 1 else None
    json_str = json.dumps(result, ensure_ascii=False, indent=2)

    if output_path:
        Path(output_path).write_text(json_str, encoding="utf-8")
        print(f"Written to {output_path}", file=sys.stderr)
    else:
        print(json_str)


if __name__ == "__main__":
    main()
