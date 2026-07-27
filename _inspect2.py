import json, os
from collections import Counter, defaultdict
DATA = r"C:/Users/TFKJ/Desktop/AI工具/医美内容合规规则库_v1.1/02_系统调用数据"
def L(f):
    p=os.path.join(DATA,f)
    with open(p,encoding="utf-8") as fh: d=json.load(fh)
    if isinstance(d,dict):
        for k in ("rules","items","data","records"):
            if isinstance(d.get(k),list): return d[k]
    return d
rules=L("rules.json"); variants=L("rule_variants.json"); plat=L("rule_platforms.json")
sem=L("semantic_rules.json"); rsrc=L("rule_sources.json")

print("=== risk_level 分布 ===", Counter(r.get("risk_level") for r in rules))
print("=== review_level 分布 ===", Counter(r.get("review_level") for r in rules))
print("=== system_action 取值(展开) ===", Counter(sa for r in rules for sa in (r.get("system_action") or [])))
print("=== category_name 分布 ===", Counter(r.get("category_name") for r in rules))
print("=== matching_method 分布 ===", Counter(v.get("matching_method") for v in variants))
print("=== variant_type 分布 ===", Counter(v.get("variant_type") for v in variants))
print("=== rule_platforms.platform 分布 ===", Counter(p.get("platform") for p in plat))
print("=== rule_platforms.content_type 分布 ===", Counter(p.get("content_type") for p in plat))
print("=== rule_platforms.platform_product_line 分布 ===", Counter(p.get("platform_product_line") for p in plat))

# distinct platforms referenced vs our required platforms
required_platforms = ["朋友圈","微信社群","小红书","微信公众号","客服话术"]
present = set(p.get("platform") for p in plat)
print("\n需要的平台:", required_platforms)
print("规则库覆盖平台:", sorted(present))
print("未覆盖(需通用规则兜底):", [p for p in required_platforms if p not in present])

# sample one of each matching_method variant
print("\n=== 各 matching_method 示例 ===")
seen=set()
for v in variants:
    m=v.get("matching_method")
    if m not in seen:
        seen.add(m)
        print(f"[{m}] rule={v.get('rule_id')} variant_text={v.get('variant_text')!r} regex={v.get('regex_pattern')!r} type={v.get('variant_type')}")

# semantic rules structure
print("\n=== semantic_rules[0] ===")
print(json.dumps(sem[0], ensure_ascii=False, indent=2)[:1500])
