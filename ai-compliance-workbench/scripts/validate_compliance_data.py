"""数据校验脚本：检查合规规则库 JSON 解析与 ID 引用完整性。
用法：python scripts/validate_compliance_data.py
"""
import os
import sys

# 允许从项目根目录或 scripts 目录运行；app 包位于 backend/
BACKEND = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from app.core.data_loader import load_data


def main():
    try:
        store = load_data()
    except Exception as e:
        print(f"[错误] 规则库加载失败：{e}")
        sys.exit(1)
    v = store.validation
    print("=== 医美内容合规规则库 数据校验 ===")
    print(f"规则库版本：{store.metadata.get('version')}")
    print(f"核心规则：{v['rule_count']} 条")
    print(f"表达变体：{v['variant_count']} 条")
    print(f"来源：{v['source_count']} 条")
    print(f"语义规则：{v['semantic_count']} 条")
    print(f"校验结果：{'通过' if v['valid'] else '存在错误'}")
    if v["errors"]:
        print("错误：")
        for e in v["errors"]:
            print(f"  - {e}")
    if v["warnings"]:
        print("警告：")
        for w in v["warnings"]:
            print(f"  - {w}")
    print("=========================")
    sys.exit(0 if v["valid"] else 2)


if __name__ == "__main__":
    main()
