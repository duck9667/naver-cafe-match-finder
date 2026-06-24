"""Best-effort, regex-based parsing of Korean cafe-post text into
(date, time range, location, team size). This is a heuristic stand-in for
the LLM-based reading a human (or Claude) would normally do — date formats
in these posts are wildly inconsistent ("26.6.28", "6월19일", "26년 6월 21일",
"6/19" ...), so this will sometimes miss or fail to find a field. When it
can't confidently extract something, it returns None for that field and the
caller should render it as "파악불가" rather than guessing wrong.
"""
import re

WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]

_DATE_PATTERNS_WITH_YEAR = [
    re.compile(r"(20\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})"),
    re.compile(r"(\d{2,4})년\s*(\d{1,2})월\s*(\d{1,2})일"),
    re.compile(r"(?<!\d)(\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})(?!\d)"),
]
_DATE_PATTERNS_NO_YEAR = [
    re.compile(r"(\d{1,2})월\s*(\d{1,2})일"),
    re.compile(r"(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)"),
]

_TIME_PATTERN = re.compile(
    r"(\d{1,2})(?::(\d{2}))?\s*시?\s*[~\-]\s*(\d{1,2})(?::(\d{2}))?\s*시?"
)

_TEAM_SIZE_PATTERN = re.compile(
    r"(?<!\d)([1-9])\s*(?::|대|vs|VS|v)\s*([1-9])(?!\d)"
)


def _normalize_year(y):
    y = int(y)
    if y < 100:
        y += 2000
    return y


def extract_field(text, label):
    """Pull the value following a numbered template label like
    '지역+구장명 》 용산 더베이스 5구장 5. 매치날짜+시간 》 ...' -> '용산 더베이스 5구장'."""
    pattern = re.compile(re.escape(label) + r"\s*[》:]\s*(.+?)(?:\s*\d+\.|$)")
    m = pattern.search(text)
    return m.group(1).strip() if m else None


def parse_date(text, today):
    """Returns (date_or_None, is_estimated)."""
    from datetime import date

    for pat in _DATE_PATTERNS_WITH_YEAR:
        m = pat.search(text)
        if m:
            y, mo, d = m.groups()
            try:
                return date(_normalize_year(y), int(mo), int(d)), False
            except ValueError:
                continue

    for pat in _DATE_PATTERNS_NO_YEAR:
        m = pat.search(text)
        if m:
            mo, d = m.groups()
            try:
                return date(today.year, int(mo), int(d)), True
            except ValueError:
                continue

    return None, False


def parse_time(text):
    """Returns (start_h, start_m, end_h, end_m) or None."""
    m = _TIME_PATTERN.search(text)
    if not m:
        return None
    sh, sm, eh, em = m.groups()
    try:
        return int(sh), int(sm or 0), int(eh), int(em or 0)
    except ValueError:
        return None


def parse_team_size(text):
    m = _TEAM_SIZE_PATTERN.search(text)
    if not m:
        return None
    return f"{m.group(1)}:{m.group(2)}"


_TRAILING_PHRASES = re.compile(
    r"(매칭\s*팀\s*구합니다|매치\s*구합니다|매칭\s*구합니다|모집합니다|구합니다)\s*[!.:)]*\s*$"
)


def location_from_title(title):
    """Fallback when there's no labeled '지역+구장명' field: strip date/time
    tokens and trailing boilerplate ('매칭 구합니다' etc) from the title."""
    text = title
    for pat in _DATE_PATTERNS_WITH_YEAR + _DATE_PATTERNS_NO_YEAR:
        text = pat.sub(" ", text)
    text = _TIME_PATTERN.sub(" ", text)
    text = re.sub(r"\([일월화수목금토]\)", " ", text)
    text = _TRAILING_PHRASES.sub("", text)
    text = re.sub(r"[./~\-]+", " ", text)
    text = re.sub(r"\s{2,}", " ", text).strip(" /·.!:")
    return text or None


def format_entry(item, today):
    """Build the structured Slack line for one item, or None if it should
    be dropped by the date filter (match date is before `today`)."""
    full_text = f"{item['title']} {item['description']}"

    date_field = extract_field(full_text, "매치날짜+시간") or extract_field(full_text, "매치시간") or full_text
    location_field = extract_field(full_text, "지역+구장명") or location_from_title(item["title"])
    size_field = extract_field(full_text, "몇 대 몇") or full_text

    match_date, estimated = parse_date(date_field, today)
    if match_date is not None and match_date < today:
        return None

    time_range = parse_time(date_field)
    team_size = parse_team_size(size_field) or parse_team_size(full_text)

    if match_date is not None:
        weekday = WEEKDAY_KR[match_date.weekday()]
        date_str = f"{match_date.year % 100}년 {match_date.month}월 {match_date.day}일"
        if estimated:
            date_str += "(추정)"
    else:
        weekday = None
        date_str = "파악불가"

    ampm = None
    if time_range:
        ampm = "오전" if time_range[0] < 12 else "오후"
        time_str = f"{time_range[0]:02d}:{time_range[1]:02d}-{time_range[2]:02d}:{time_range[3]:02d}"
    else:
        time_str = "파악불가"

    tag_parts = [p for p in (weekday, ampm) if p]
    tag = f"[{'-'.join(tag_parts)}] " if tag_parts else ""

    location_str = (location_field or "파악불가").strip() or "파악불가"
    size_str = team_size or "파악불가"

    return f"{tag}{date_str} {time_str} / {location_str} / {size_str} - <{item['link']}|링크>"
