"""真实模型适配层的结构化响应和降级诊断测试。"""
from __future__ import annotations

from types import SimpleNamespace

from app.services.llm.provider import OpenAICompatibleProvider


def response(content: str, finish_reason: str = "stop", request_id: str = "req-test"):
    return SimpleNamespace(
        id=request_id,
        choices=[
            SimpleNamespace(
                finish_reason=finish_reason,
                message=SimpleNamespace(content=content, reasoning_content="不应作为最终结果"),
            )
        ],
    )


class FakeCompletions:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def provider_with(
    responses,
    *,
    base_url="https://api.deepseek.com",
    model="deepseek-v4-flash",
    enable_thinking=False,
):
    provider = OpenAICompatibleProvider(
        "test-key",
        base_url,
        model,
        0.7,
        4096,
        enable_thinking=enable_thinking,
    )
    completions = FakeCompletions(responses)
    provider._client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return provider, completions


def semantic_rules():
    return [{"semantic_rule_id": "SR0001", "semantic_rule_name": "效果保证", "detection_description": "保证效果"}]


def test_semantic_request_uses_json_mode_disables_deepseek_thinking_and_uses_4096():
    provider, completions = provider_with([
        response('{"semantic_findings":[],"needs_manual_review":false,"manual_review_reason":""}')
    ])
    result = provider.semantic_check("普通介绍", "小红书", "项目介绍", semantic_rules(), [])

    assert result["analysis_failed"] is False
    call = completions.calls[0]
    assert call["max_tokens"] == 4096
    assert call["response_format"] == {"type": "json_object"}
    assert call["extra_body"] == {"thinking": {"type": "disabled"}}


def test_non_deepseek_does_not_receive_thinking_parameter():
    provider, completions = provider_with(
        [response("普通文本")],
        base_url="https://compatible.example/v1",
        model="compatible-model",
    )
    assert provider._chat("system", "user") == "普通文本"
    assert "extra_body" not in completions.calls[0]


def test_deepseek_thinking_can_be_enabled_by_user_setting():
    provider, completions = provider_with(
        [response("普通文本")],
        enable_thinking=True,
    )
    assert provider._chat("system", "user") == "普通文本"
    assert completions.calls[0]["extra_body"] == {"thinking": {"type": "enabled"}}


def test_alibaba_model_studio_uses_enable_thinking_boolean():
    provider, completions = provider_with(
        [response("普通文本")],
        base_url="https://workspace.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        model="qwen3.7-flash",
        enable_thinking=True,
    )
    assert provider._chat("system", "user") == "普通文本"
    assert completions.calls[0]["extra_body"] == {"enable_thinking": True}


def test_unknown_compatible_provider_ignores_thinking_setting():
    provider, completions = provider_with(
        [response("普通文本")],
        base_url="https://compatible.example/v1",
        model="compatible-model",
        enable_thinking=True,
    )
    assert provider._chat("system", "user") == "普通文本"
    assert "extra_body" not in completions.calls[0]


def test_semantic_empty_response_retries_once_and_recovers():
    provider, completions = provider_with([
        response("", finish_reason="length", request_id="req-empty"),
        response('{"semantic_findings":[],"needs_manual_review":false,"manual_review_reason":""}'),
    ])
    result = provider.semantic_check("普通介绍", "小红书", "项目介绍", semantic_rules(), [])

    assert result["analysis_failed"] is False
    assert len(completions.calls) == 2


def test_semantic_invalid_json_retries_once_then_reports_format_failure():
    provider, completions = provider_with([response("not json"), response("still not json")])
    result = provider.semantic_check("普通介绍", "小红书", "项目介绍", semantic_rules(), [])

    assert result["analysis_failed"] is True
    assert result["needs_manual_review"] is True
    assert "不是有效 JSON" in result["failure_reason"]
    assert len(completions.calls) == 2


def test_semantic_finish_reason_is_exposed_without_raw_content():
    provider, _ = provider_with([
        response("", finish_reason="content_filter", request_id="req-filter"),
        response("", finish_reason="insufficient_system_resource", request_id="req-resource"),
    ])
    result = provider.semantic_check("普通介绍", "小红书", "项目介绍", semantic_rules(), [])

    assert result["analysis_failed"] is True
    assert "服务资源不足" in result["failure_reason"]
    assert "req-resource" in result["failure_reason"]
    assert "普通介绍" not in result["failure_reason"]
