# -*- coding: utf-8 -*-
"""合并违禁词数据模块，生成 xhs_banned_words.json（增强结构）。"""
import json
import re
import os

HERE = os.path.dirname(os.path.abspath(__file__))
import importlib.util

def load(path):
    spec = importlib.util.spec_from_file_location("mod", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.ENTRIES

parts = [
    os.path.join(HERE, "_part1_医美医疗.py"),
    os.path.join(HERE, "_part2_引流极限词.py"),
    os.path.join(HERE, "_part3_功效承诺.py"),
]

words = []
seen = set()
for p in parts:
    for row in load(p):
        word, domain, risk, repl, reason, variants, source = row
        if word in seen:
            continue
        seen.add(word)
        words.append({
            "id": "BW%04d" % (len(words) + 1),
            "word": word,
            "domain": domain,
            "risk_level": risk,
            "replacement": repl,
            "reason": reason,
            "variants": variants,
            "source": source,
        })

out = os.path.join(HERE, "xhs_banned_words.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(words, f, ensure_ascii=False, indent=2)

# ---- 校验 ----
errors = []
# 1) U+FFFD 检测
with open(out, "r", encoding="utf-8") as f:
    txt = f.read()
n_fffd = len(re.findall(r"\ufffd", txt))
if n_fffd:
    errors.append("检测到 %d 个 U+FFFD 替换字符（写入损坏）" % n_fffd)

# 2) 字段完整性
for w in words:
    for k in ("id", "word", "domain", "risk_level", "replacement", "reason", "variants", "source"):
        if k not in w or w[k] is None or w[k] == "":
            if k != "variants":  # variants 允许为空列表
                errors.append("条目 %s 缺失字段 %s" % (w.get("id"), k))

# 3) 分类统计
from collections import Counter
dist = Counter(w["domain"] for w in words)
risk = Counter(w["risk_level"] for w in words)

print("生成完成：%s" % out)
print("总词条数：%d" % len(words))
print("按领域：", dict(dist))
print("按风险：", dict(risk))
print("U+FFFD 数：%d" % n_fffd)
if errors:
    print("校验问题：")
    for e in errors:
        print("  -", e)
else:
    print("校验通过：无损坏、字段完整。")
