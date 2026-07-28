"""Pydantic 请求模型与基础输入校验。"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

def _resolve_scene(platform: str, content_type: str, platform_id: str | None, scene_id: str | None):
    from app.services.prompts.catalog import resolve_scene
    return resolve_scene(platform, content_type, platform_id, scene_id)


class GenerateRequest(BaseModel):
    brand: Optional[str] = None
    platform: str
    content_type: str
    platform_id: Optional[str] = None
    scene_id: Optional[str] = None
    topic: str = Field("", max_length=300)
    selling_points: str = Field("", max_length=3000)
    target_audience: str = Field("", max_length=500)
    campaign_info: str = Field("", max_length=1000)
    tone: str = Field("亲切专业", max_length=100)
    length: Literal["短", "中", "长"] = "中"
    extra_requirements: str = Field("", max_length=2000)
    use_brand_profile: bool = True
    versions: int = Field(3, ge=1, le=5)

    @model_validator(mode="after")
    def validate_request(self):
        platform, scene = _resolve_scene(self.platform, self.content_type, self.platform_id, self.scene_id)
        self.platform, self.content_type = platform["name"], scene["name"]
        self.platform_id, self.scene_id = platform["id"], scene["id"]
        if not self.topic.strip() and not self.selling_points.strip():
            raise ValueError("请至少填写主题或核心卖点")
        return self


class RewriteRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    platform: str
    content_type: str
    platform_id: Optional[str] = None
    scene_id: Optional[str] = None
    brand: Optional[str] = None

    @model_validator(mode="after")
    def validate_request(self):
        platform, scene = _resolve_scene(self.platform, self.content_type, self.platform_id, self.scene_id)
        self.platform, self.content_type = platform["name"], scene["name"]
        self.platform_id, self.scene_id = platform["id"], scene["id"]
        return self


class AdjustRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    platform: str
    content_type: str
    platform_id: Optional[str] = None
    scene_id: Optional[str] = None
    brand: Optional[str] = None
    adjust_type: Literal["缩短", "扩写", "调整语气"] = "缩短"
    topic: str = Field("", max_length=300)
    target_audience: str = Field("", max_length=500)
    campaign_info: str = Field("", max_length=1000)
    tone: str = Field("专业温和", max_length=100)
    length: Literal["短", "中", "长"] = "中"
    extra_requirements: str = Field("", max_length=2000)

    @model_validator(mode="after")
    def validate_request(self):
        platform, scene = _resolve_scene(self.platform, self.content_type, self.platform_id, self.scene_id)
        self.platform, self.content_type = platform["name"], scene["name"]
        self.platform_id, self.scene_id = platform["id"], scene["id"]
        return self


class ComplianceCheckRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    platform: str
    content_type: str
    platform_id: Optional[str] = None
    scene_id: Optional[str] = None
    brand: Optional[str] = None
    publisher_identity: Optional[str] = Field(None, max_length=100)
    business_domain: Optional[str] = Field(None, max_length=100)
    content_legal_nature: Optional[str] = Field(None, max_length=100)
    is_paid_ad: bool = False
    context_note: Optional[str] = Field(None, max_length=2000)

    @field_validator("text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("待检测文本不能为空")
        return value

    @model_validator(mode="after")
    def validate_request(self):
        platform, scene = _resolve_scene(self.platform, self.content_type, self.platform_id, self.scene_id)
        self.platform, self.content_type = platform["name"], scene["name"]
        self.platform_id, self.scene_id = platform["id"], scene["id"]
        return self


class SettingsPatch(BaseModel):
    patch: dict[str, Any] = Field(default_factory=dict)


class ExportRequest(BaseModel):
    result: dict[str, Any] = Field(default_factory=dict)
    format: Literal["txt", "md", "json"] = "txt"
