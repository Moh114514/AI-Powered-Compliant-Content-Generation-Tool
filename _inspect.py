import json, os, sys

DATA = r"C:/Users/TFKJ/Desktop/AI工具/医美内容合规规则库_v1.1/02_系统调用数据"
files = [
    "metadata.json","sources.json","rules.json","rule_variants.json","rule_sources.json",
    "rule_platforms.json","rule_channels.json","rule_examples.json","semantic_rules.json",
    "semantic_rule_sources.json","semantic_rule_examples.json","ad_classification_rules.json",
    "enforcement_cases.json","manual_review_issues.json","risk_scoring.json",
    "compliance_rules.schema.json","changelog.json","test_cases.json","case_leads.json",
    "medical_beauty_compliance_library_v1.0.json",
]
print("=== 文件存在与解析 ===")
loaded = {}
for f in files:
    p = os.path.join(DATA, f)
    if not os.path.exists(p):
        print(f"[缺失] {f}")
        continue
    try:
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        loaded[f] = d
        # report count
        if isinstance(d, list):
            print(f"[OK]   {f}: list  len={len(d)}")
        elif isinstance(d, dict):
            print(f"[OK]   {f}: dict  keys={list(d.keys())[:8]}")
        else:
            print(f"[OK]   {f}: {type(d).__name__}")
    except Exception as e:
        print(f"[解析错误] {f}: {e}")

def lst(d):
    if isinstance(d, list): return d
    if isinstance(d, dict):
        for k in ("rules","items","data","records"):
            if isinstance(d.get(k), list): return d[k]
    return []

print("\n=== 核心统计 ===")
rules = lst(loaded.get("rules.json"))
variants = lst(loaded.get("rule_variants.json"))
sources = lst(loaded.get("sources.json"))
rsrc = lst(loaded.get("rule_sources.json"))
plat = lst(loaded.get("rule_platforms.json"))
chans = lst(loaded.get("rule_channels.json"))
exs = lst(loaded.get("rule_examples.json"))
sem = lst(loaded.get("semantic_rules.json"))
sema = lst(loaded.get("semantic_rule_sources.json"))
seme = lst(loaded.get("semantic_rule_examples.json"))
manual = lst(loaded.get("manual_review_issues.json"))
print("rules:", len(rules))
print("variants:", len(variants))
print("sources:", len(sources))
print("rule_sources:", len(rsrc))
print("rule_platforms:", len(plat))
print("rule_channels:", len(chans))
print("rule_examples:", len(exs))
print("semantic_rules:", len(sem))
print("semantic_rule_sources:", len(sema))
print("semantic_rule_examples:", len(seme))
print("manual_review_issues:", len(manual))
print("risk_scoring.json 存在:", "risk_scoring.json" in loaded)

# sample rule keys
if rules:
    print("\n=== rules[0] 字段 ===")
    print(sorted(rules[0].keys()))
if variants:
    print("\n=== variants[0] 字段 ===")
    print(sorted(variants[0].keys()))
if sources:
    print("\n=== sources[0] 字段 ===")
    print(sorted(sources[0].keys()))

# ID referential integrity
rule_ids = set(r.get("rule_id") for r in rules)
src_ids = set(s.get("source_id") for s in sources if isinstance(s,dict))
print("\n=== ID 引用完整性 ===")
print("rule_id 数量:", len(rule_ids), " 是否有空:", any(not x for x in rule_ids))
# check variants reference rules
vbad=0
for v in variants:
    rid = v.get("rule_id")
    if rid and rid not in rule_ids: vbad+=1
print("variants 引用失效 rule_id 数:", vbad)
# check rule_sources reference
rsbad=0
for x in rsrc:
    rid = x.get("rule_id"); sid=x.get("source_id")
    if rid and rid not in rule_ids: rsbad+=1
    if sid and sid not in src_ids: rsbad+=1
print("rule_sources 引用失效数:", rsbad)
# platform rules
if plat:
    print("rule_platforms[0] 字段:", sorted(plat[0].keys()))

# metadata version
md = loaded.get("metadata.json")
if md:
    print("\n=== metadata 内容 ===")
    print(json.dumps(md, ensure_ascii=False, indent=2)[:1500])
