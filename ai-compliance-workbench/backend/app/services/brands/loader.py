"""品牌配置加载：从 data/brand_profiles 读取（只读，演示品牌明确标记 is_demo）。"""
import json
import os
from app.core import config

DEFAULT_BRANDS = ["guangnian18", "vyno", "qiyue"]


def list_brands() -> list[dict]:
    brands = []
    if os.path.isdir(config.BRAND_DIR):
        for fn in os.listdir(config.BRAND_DIR):
            if fn.endswith(".json"):
                try:
                    with open(os.path.join(config.BRAND_DIR, fn), encoding="utf-8") as f:
                        brands.append(json.load(f))
                except Exception:
                    continue
    if not brands:
        brands = [
            {"brand_id": "guangnian18", "brand_name": "光年拾捌", "active": True, "is_demo": True},
            {"brand_id": "vyno", "brand_name": "VYNO", "active": True, "is_demo": True},
            {"brand_id": "qiyue", "brand_name": "启月文化", "active": True, "is_demo": True},
        ]
    return brands


def get_brand(brand_id: str) -> dict | None:
    if not brand_id:
        return None
    value = str(brand_id).strip()
    for brand in list_brands():
        if value in {str(brand.get("brand_id") or ""), str(brand.get("brand_name") or "")}:
            return brand
    return None
