"""文本标准化：全角半角、大小写、空白与常见符号归一化。
返回 (normalized_text, index_map)，index_map[i] = 归一化后第 i 个字符在原文中的索引，
用于把检测命中位置映射回原文，保证前端高亮准确。
"""
import re
import unicodedata

# 全角 -> 半角（字母数字与常用符号）
def _full_to_half(ch: str) -> str:
    code = ord(ch)
    if code == 0x3000:  # 全角空格
        return " "
    if 0xFF01 <= code <= 0xFF5E:  # 全角标点字母数字
        return chr(code - 0xFEE0)
    return ch

# 常见中文标点统一为半角等价，便于正则匹配（如把 。！？ 归一为 .!?）
_PUNCT_MAP = {
    "。": ".", "！": "!", "？": "?", "，": ",", "、": ",",
    "；": ";", "：": ":", "“": '"', "”": '"', "‘": "'", "’": "'",
    "（": "(", "）": ")", "【": "[", "】": "]", "《": "<", "》": ">",
    "　": " ", "\u00a0": " ", "\t": " ", "\n": " ", "\r": " ",
}

# 拼音/缩写归一：去掉空格与分隔符，统一小写（用于检测 "no.1" / "No 1" 等）
def normalize_text(text: str) -> tuple[str, list[int]]:
    if text is None:
        return "", []
    norm_chars = []
    index_map = []
    for i, ch in enumerate(text):
        # 基础归一
        c = _full_to_half(ch)
        c = _PUNCT_MAP.get(c, c)
        # 大小写
        c = c.lower()
        norm_chars.append(c)
        index_map.append(i)
    norm = "".join(norm_chars)
    # 合并多余空格（但保留 index_map 对应到空格前字符）
    out_chars = []
    out_map = []
    prev_space = False
    for c, idx in zip(norm, index_map):
        is_space = c == " "
        if is_space:
            if prev_space:
                continue
            prev_space = True
        else:
            prev_space = False
        out_chars.append(c)
        out_map.append(idx)
    return "".join(out_chars), out_map


def map_span(index_map: list[int], start: int, end: int) -> tuple[int, int]:
    """把归一化文本中的 [start, end) 映射回原文索引区间 [orig_start, orig_end)。"""
    if not index_map:
        return start, end
    orig_start = index_map[start]
    # end 是开区间：取 end 前一个字符的原文索引 +1
    if end - 1 < len(index_map):
        orig_end = index_map[end - 1] + 1
    else:
        orig_end = len(index_map)  # 退化
    return orig_start, orig_end


def simple_normalize(text: str) -> str:
    """无索引映射的轻量归一（用于模糊匹配窗口比较）。"""
    t, _ = normalize_text(text)
    return t
