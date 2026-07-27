import json, os
DATA = r"C:/Users/TFKJ/Desktop/AI工具/医美内容合规规则库_v1.1/02_系统调用数据"
def L(f):
    p=os.path.join(DATA,f)
    with open(p,encoding="utf-8") as fh: d=json.load(fh)
    if isinstance(d,dict):
        for k in ("rules","items","data","records"):
            if isinstance(d.get(k),list): return d[k]
    return d
rules=L("rules.json"); variants=L("rule_variants.json")

# a full rule sample
print("=== 完整 rules[0] ===")
print(json.dumps(rules[0], ensure_ascii=False, indent=2))

# system_action distinct raw values (as strings)
print("\n=== distinct system_action raw (前20) ===")
from collections import Counter
sa_raw = Counter(str(r.get("system_action")) for r in rules)
for k,v in sa_raw.most_common(20):
    print(repr(k), v)

# regex_pattern present?
print("\n=== 含 regex_pattern 的 variant 数 ===", sum(1 for v in variants if v.get("regex_pattern")))
print("=== 含 regex_pattern 的样本 ===")
for v in variants:
    if v.get("regex_pattern"):
        print(repr(v.get("regex_pattern")), "| method=", v.get("matching_method"), "| rule=", v.get("rule_id"))
        if sum(1 for x in variants if x.get("regex_pattern"))>6: break
