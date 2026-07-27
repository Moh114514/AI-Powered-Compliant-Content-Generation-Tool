"""确定性匹配：exact / contains / fuzzy / regex。
所有匹配在归一化文本上进行，返回 [start, end)（归一化坐标）与命中文本；
由引擎通过 index_map 映射回原文，保证高亮位置准确。
"""
import re
import difflib
from app.core.text_normalize import normalize_text

_REGEX_CACHE: dict[str, re.Pattern] = {}


def _compile(pattern: str) -> re.Pattern | None:
    if not pattern:
        return None
    if pattern in _REGEX_CACHE:
        return _REGEX_CACHE[pattern]
    try:
        rx = re.compile(pattern)
    except re.error:
        try:
            rx = re.compile(pattern, re.IGNORECASE)
        except re.error:
            _REGEX_CACHE[pattern] = None
            return None
    _REGEX_CACHE[pattern] = rx
    return rx


def _find_substring(norm_text: str, needle: str) -> list[tuple[int, int, str]]:
    if not needle:
        return []
    out = []
    start = 0
    while True:
        idx = norm_text.find(needle, start)
        if idx == -1:
            break
        out.append((idx, idx + len(needle), needle))
        start = idx + len(needle)
    return out


def _find_fuzzy(norm_text: str, variant_text: str) -> list[tuple[int, int, str]]:
    vt = variant_text.strip()
    L = len(vt)
    if L == 0 or len(norm_text) == 0:
        return []
    win = max(L + 2, int(L * 1.6))
    step = max(1, L // 2)
    out = []
    seen = set()
    for i in range(0, max(1, len(norm_text) - L + 1), step):
        window = norm_text[i : i + win]
        if not window:
            continue
        ratio = difflib.SequenceMatcher(None, vt, window).ratio()
        if ratio >= 0.72:
            key = (i, i + len(window))
            if key not in seen:
                seen.add(key)
                out.append((i, i + len(window), window))
    return out


def match_variant(norm_text: str, variant: dict) -> list[tuple[int, int, str]]:
    method = (variant.get("matching_method") or "contains").lower()
    vtext = variant.get("variant_text") or ""
    regex_pattern = variant.get("regex_pattern")

    if regex_pattern:
        rx = _compile(regex_pattern)
        if rx:
            out = []
            for m in rx.finditer(norm_text):
                out.append((m.start(), m.end(), m.group(0)))
            return out

    nv = normalize_text(vtext)[0] if vtext else ""

    if method == "exact":
        return _find_substring(norm_text, nv)
    if method == "contains":
        return _find_substring(norm_text, nv)
    if method == "fuzzy":
        return _find_fuzzy(norm_text, nv)
    if method == "semantic":
        return []
    return _find_substring(norm_text, nv)
