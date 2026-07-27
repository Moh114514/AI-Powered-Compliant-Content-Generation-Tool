"""Pydantic 请求模型。"""
from pydantic import BaseModel, Field
from typing import Any, Optional


class GenerateRequest(BaseModel):
    brand: Optional[str] = None
    platform: str
    content_type: str
    topic: Optional[str] = ""
    selling_points: Optional[str] = ""
    target_audience: Optional[str] = ""
    campaign_info: Optional[str] = ""
    tone: Optional[str] = "亲切专业"
    length: Optional[str] = "中"
    extra_requirements: Optional[str] = ""
    use_brand_profile: bool = True
    versions: int = Field(3, ge=1, le=5)


class RewriteRequest(BaseModel):
    text: str
    platform: str
    content_type: str
    brand: Optional[str] = None


class AdjustRequest(BaseModel):
    text: str
    platform: str
    content_type: str
    brand: Optional[str] = None
    adjust_type: str = "缩短"
    topic: Optional[str] = ""
    target_audience: Optional[str] = ""
    campaign_info: Optional[str] = ""
    tone: Optional[str] = "专业温和"
    length: Optional[str] = "中"
    extra_requirements: Optional[str] = ""


class ComplianceCheckRequest(BaseModel):
    text: str
    platform: str
    content_type: str
    brand: Optional[str] = None
    publisher_identity: Optional[str] = None
    business_domain: Optional[str] = None
    content_legal_nature: Optional[str] = None
    is_paid_ad: bool = False
    context_note: Optional[str] = None


class SettingsPatch(BaseModel):
    patch: dict = Field(default_factory=dict)


class ExportRequest(BaseModel):
    result: dict = Field(default_factory=dict)
    format: str = "txt"  # txt | md | json
