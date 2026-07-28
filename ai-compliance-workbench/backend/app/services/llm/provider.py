"""大模型适配层。

MockProvider 负责无密钥演示与确定性降级；OpenAICompatibleProvider 兼容 OpenAI 风格接口。
任何模型解析失败都必须显式上报，不能静默当作“无风险”。
"""
from __future__ import annotations

import json
import re

from app.core import config
from app.core.data_loader import get_store


class LLMProvider:
    name = "base"

    def generate(self, platform, content_type, inputs, prompt_template, brand_profile, versions) -> list[str]:
        raise NotImplementedError

    def semantic_check(self, text, platform, content_type, semantic_rules, matched_rules) -> dict:
        raise NotImplementedError

    def rewrite(self, text, matched_rules, platform, content_type) -> dict:
        raise NotImplementedError

    def adjust(self, text, adjust_type, platform, content_type, tone) -> str:
        raise NotImplementedError

    def prompt_draft(self, context: dict) -> str:
        raise NotImplementedError


class MockProvider(LLMProvider):
    name = "mock"

    def __init__(self):
        self._semantic_map = self._build_semantic_map()

    def _build_semantic_map(self) -> dict[str, str]:
        semantic_rules = get_store().semantic_rules

        def find(*keywords: str) -> str:
            for rule in semantic_rules:
                name = str(rule.get("semantic_rule_name") or "")
                if any(keyword in name for keyword in keywords):
                    return str(rule.get("semantic_rule_id") or "")
            return str(semantic_rules[0].get("semantic_rule_id") or "") if semantic_rules else ""

        return {
            "effect_guarantee": find("保证", "效果"),
            "absolute_safe": find("无风险", "安全"),
            "case_to_general": find("个案", "案例", "普遍"),
            "appearance_anxiety": find("焦虑", "容貌"),
            "no_treatment_threat": find("不治疗", "后果", "焦虑"),
            "unverified_data": find("数据", "无法验证"),
            "disguised_ad": find("变相广告", "广告"),
            "undiagnosed": find("诊断", "判断"),
            "evasion": find("谐音", "拆字", "拼音", "规避"),
            "time_commit": find("时间", "持续"),
            "rank": find("排名", "绝对化"),
            "scarcity": find("价格", "诱导", "稀缺"),
        }

    def generate(self, platform, content_type, inputs, prompt_template, brand_profile, versions) -> list[str]:
        topic = inputs.get("topic") or "项目体验"
        selling_points = inputs.get("selling_points") or ""
        audience = inputs.get("target_audience") or "关注品质的用户"
        campaign = inputs.get("campaign_info") or ""
        brand_name = (brand_profile or {}).get("brand_name", "")
        length = inputs.get("length") or "中"
        extra = inputs.get("extra_requirements") or ""

        scaffolds = self._scaffolds(platform)
        copies: list[str] = []
        for index in range(max(1, min(int(versions or 1), 5))):
            body = scaffolds[index % len(scaffolds)].format(
                brand=brand_name,
                topic=topic,
                selling_points=selling_points,
                audience=audience,
                campaign=campaign,
                extra=extra,
            ).strip()
            if length == "短":
                body = body[: max(40, int(len(body) * 0.65))].rstrip("，,；; ") + "。"
            elif length == "长":
                body += "\n\n发布前请再次核验项目资质、活动条件、素材授权与数据来源。"
            copies.append(body)
        return copies

    @staticmethod
    def _scaffolds(platform: str) -> list[str]:
        if platform == "小红书":
            return [
                "{topic}｜先了解流程、适用情况和注意事项\n\n{selling_points}。适合{audience}作为信息参考。{campaign}。\n\n具体方案、风险和恢复情况存在个体差异，需由专业医师评估。",
                "关于{topic}，建议先把适用人群、操作流程与注意事项了解清楚。{selling_points}。{campaign}。是否适合个人情况，应以专业面诊为准。",
                "理性了解{topic}：不只看宣传，也要确认机构资质、项目限制和风险说明。{selling_points}。{campaign}。{extra}",
            ]
        if platform == "朋友圈":
            return [
                "【{brand}｜{topic}】\n{selling_points}。{campaign}。具体方案、风险及恢复情况需结合个人情况进行专业评估。",
                "最近在整理{topic}相关信息：{selling_points}。{campaign}。有需要可以先了解流程和注意事项，再决定是否预约评估。",
            ]
        if platform == "微信社群":
            return [
                "【群通知】{topic}\n{selling_points}。{campaign}。如需了解，请先确认活动条件，并由专业医师评估是否适合。",
                "各位伙伴，关于{topic}补充说明：{selling_points}。{campaign}。群内仅提供一般信息，不替代专业诊断。",
            ]
        if platform == "微信公众号":
            return [
                "# {topic}\n\n本文介绍相关流程、适用情况与注意事项：{selling_points}。{campaign}。\n\n具体方案与风险需由专业医师结合个人情况评估。",
                "# 理性了解{topic}\n\n{selling_points}。本文仅作一般信息介绍，不构成个体化诊疗建议。{campaign}。",
            ]
        return [
            "您好，关于{topic}，可以先为您介绍基本流程和注意事项：{selling_points}。{campaign}。具体是否适合，需要由专业医师评估。",
            "感谢咨询{topic}。每个人的情况不同，我可以协助您了解一般信息和预约流程，但不能代替专业诊断。{selling_points}。",
        ]

    def semantic_check(self, text, platform, content_type, semantic_rules, matched_rules) -> dict:
        patterns = [
            ("effect_guarantee", r"(保证|确保|肯定|一定|必然|百分之百|100%|绝对).{0,12}(效果|见效|恢复|年轻|变美|治好|有效|成功)", "critical"),
            ("absolute_safe", r"(零风险|绝对安全|无任何风险|无副作用|绝不会出问题|百分之百安全)", "critical"),
            ("rank", r"(全城|全网|全国|全市|行业).{0,8}(最好|最佳|第一|最强|顶尖|领先|TOP\s*1|NO\.?\s*1)", "high"),
            ("time_commit", r"(\d+|一|三|七)\s*(天|周|月|年).{0,10}(年轻|见效|恢复|变美|瘦|白|治好|逆龄)", "high"),
            ("scarcity", r"(仅剩\d+|最后一天|错过不再|名额有限|立刻抢|马上交定金)", "high"),
            ("unverified_data", r"\d+(?:\.\d+)?\s*(万|千|%|％).{0,8}(人|用户|顾客|服务|案例|好评|成功|满意)", "high"),
            ("case_to_general", r"(我朋友|我同事|顾客|客户|姐妹).{0,20}(好了|见效|恢复|成功).{0,20}(都|一定|证明|说明)", "high"),
            ("appearance_anxiety", r"(丑|黄脸婆|脸垮|显老|没人喜欢|被淘汰).{0,16}(必须|赶紧|快去|不做|医美|项目)", "high"),
            ("no_treatment_threat", r"(不做|不整|不治疗|不改善).{0,12}(越来越|更严重|恶化|毁|垮|没人要)", "high"),
            ("disguised_ad", r"(本文|分享|科普|笔记|探店|日记).{0,30}(购买|下单|预约|到店|私信|二维码|链接)", "medium"),
            ("undiagnosed", r"(你这就是|你属于|你肯定是|看照片就知道|一定适合做|必须做).{0,20}", "critical"),
            ("evasion", r"(热\W+玛\W+吉|瘦脸[真Z]|bo尿酸|zheng形|整\W+形)", "high"),
        ]
        findings: list[dict] = []
        for key, pattern, risk_level in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            semantic_id = self._semantic_map.get(key) or ""
            semantic_name = next(
                (rule.get("semantic_rule_name") for rule in semantic_rules if rule.get("semantic_rule_id") == semantic_id),
                key,
            )
            findings.append({
                "semantic_rule_id": semantic_id,
                "semantic_rule_name": semantic_name,
                "risk_level": risk_level,
                "matched_text": match.group(0),
                "risk_reason": f"疑似{semantic_name}，需要结合发布主体和上下文确认。",
                "manual_review": risk_level in {"critical", "high"},
                "system_action": ["mandatory_human_review"] if risk_level in {"critical", "high"} else ["warning"],
            })
        needs_review = any(item["manual_review"] for item in findings)
        return {
            "semantic_findings": findings,
            "needs_manual_review": needs_review,
            "manual_review_reason": "文案存在需要结合上下文确认的语义风险。" if needs_review else "",
            "analysis_failed": False,
        }

    def rewrite(self, text, matched_rules, platform, content_type) -> dict:
        spans: list[tuple[int, int]] = []
        unresolved: list[str] = []
        for matched_rule in matched_rules:
            if not matched_rule.get("auto_rewrite_allowed"):
                unresolved.append(f"{matched_rule['rule_id']} {matched_rule['rule_name']}（需人工复核或补充材料）")
                continue
            spans.extend(
                (int(span["start_index"]), int(span["end_index"]))
                for span in matched_rule.get("spans", [])
            )

        merged: list[list[int]] = []
        for start, end in sorted(set(spans)):
            if not merged or start > merged[-1][1]:
                merged.append([start, end])
            else:
                merged[-1][1] = max(merged[-1][1], end)
        revised = text
        for start, end in reversed(merged):
            revised = revised[:start] + revised[end:]
        revised = re.sub(r"[，,；;、\s]+([。！？!?])", r"\1", revised)
        revised = re.sub(r"([，,。；;]){2,}", r"\1", revised)
        revised = re.sub(r"\s{2,}", " ", revised).strip(" ，,；;")
        if revised and revised[-1] not in "。！？!?":
            revised += "。"
        if revised:
            revised += "具体风险、适用情况和注意事项需结合个人情况进行专业评估。"
        return {
            "suggested_revision": revised,
            "auto_rewrite": not unresolved,
            "unresolved_items": unresolved,
        }

    def adjust(self, text, adjust_type, platform, content_type, tone) -> str:
        source = str(text or "").strip()
        if adjust_type == "缩短":
            target = max(40, int(len(source) * 0.65))
            if len(source) <= target:
                return source
            sentences = [
                item.strip()
                for item in re.split(r"(?<=[。！？!?])\s*", source)
                if item.strip()
            ]
            selected: list[str] = []
            for sentence in sentences:
                candidate = "".join(selected) + sentence
                if selected and len(candidate) > target:
                    break
                selected.append(sentence)
                if len(candidate) >= target:
                    break
            shortened = "".join(selected).strip()
            if not shortened or len(shortened) >= len(source):
                shortened = source[:target].rstrip("，,；;、 ")
                if shortened and shortened[-1] not in "。！？!?":
                    shortened += "。"
            return shortened
        if adjust_type == "扩写":
            addition = "发布前建议进一步确认操作流程、适用条件、注意事项及可能风险，并结合个人情况进行专业评估。"
            if addition in source:
                return source
            return f"{source}\n\n{addition}"
        return source

    def prompt_draft(self, context: dict) -> str:
        raise ValueError("AI 生成提示词仅支持真实模型。请先在设置中启用并配置真实 LLM。")


class OpenAICompatibleProvider(LLMProvider):
    name = "openai_compatible"

    def __init__(self, api_key, base_url, model, temperature, max_tokens):
        self.api_key = api_key
        self.base_url = str(base_url).rstrip("/")
        self.model = model
        self.temperature = float(temperature)
        self.max_tokens = int(max_tokens)
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=60.0)
            except Exception:
                self._client = False
        return self._client if self._client is not False else None

    def _chat(self, system_prompt: str, user_prompt: str) -> str:
        client = self._get_client()
        if client is not None:
            response = client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return response.choices[0].message.content or ""

        import requests
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def generate(self, platform, content_type, inputs, prompt_template, brand_profile, versions) -> list[str]:
        profile = brand_profile or {}
        preferred_terms = profile.get("preferred_terms") or []
        prohibited_terms = profile.get("prohibited_terms") or []
        user_prompt = (
            f"平台：{platform}\n内容类型：{content_type}\n"
            f"品牌：{profile.get('brand_name', '')}\n品牌调性：{profile.get('tone', '')}\n"
            f"偏好用词：{preferred_terms}\n禁用词：{prohibited_terms}\n"
            f"主题：{inputs.get('topic', '')}\n卖点：{inputs.get('selling_points', '')}\n"
            f"目标人群：{inputs.get('target_audience', '')}\n活动信息：{inputs.get('campaign_info', '')}\n"
            f"语气：{inputs.get('tone', '')}\n长度：{inputs.get('length', '中')}\n"
            f"补充要求：{inputs.get('extra_requirements', '')}\n"
            f"生成 {max(1, min(int(versions or 1), 5))} 个不同版本，以单独一行 === 分隔。"
        )
        output = self._chat((prompt_template or "") + "\n\n不得编造事实、资质、数据或医疗效果。", user_prompt)
        parts = [part.strip() for part in re.split(r"^\s*={3,}\s*$", output, flags=re.MULTILINE) if part.strip()]
        if not parts and output.strip():
            parts = [output.strip()]
        return parts[: max(1, int(versions or 1))]

    def semantic_check(self, text, platform, content_type, semantic_rules, matched_rules) -> dict:
        prompt_path = config.PROMPTS_DIR / "compliance_semantic_check.md"
        system_prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else "请进行审慎的医美文案语义风险判断，并严格返回JSON。"
        rules_text = "\n".join(
            f"- {rule.get('semantic_rule_id')} {rule.get('semantic_rule_name')}: {rule.get('detection_description', '')}"
            for rule in semantic_rules
        )
        matched_text = ";".join(rule.get("rule_id", "") for rule in matched_rules)
        user_prompt = (
            f"文案：{text}\n平台：{platform}\n内容类型：{content_type}\n"
            f"候选语义规则：\n{rules_text}\n已命中确定性规则：{matched_text}\n"
            "仅判断候选规则；不确定时标记 needs_manual_review=true。严格返回JSON。"
        )
        raw = self._chat(system_prompt, user_prompt)
        try:
            data = json.loads(self._extract_json(raw))
            findings = data.get("semantic_findings", [])
            if not isinstance(findings, list):
                raise ValueError("semantic_findings 不是数组")
            return {
                "semantic_findings": findings,
                "needs_manual_review": bool(data.get("needs_manual_review", False)),
                "manual_review_reason": str(data.get("manual_review_reason") or ""),
                "analysis_failed": False,
            }
        except Exception as exc:
            return {
                "semantic_findings": [],
                "needs_manual_review": True,
                "manual_review_reason": "模型语义检测结果无法解析，不能据此直接判断内容安全。",
                "analysis_failed": True,
                "failure_reason": f"语义检测解析失败：{exc}",
            }

    def rewrite(self, text, matched_rules, platform, content_type) -> dict:
        prompt_path = config.PROMPTS_DIR / "compliance_rewrite.md"
        system_prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else "请删除无法证明的合规风险主张，不得用近义词规避。严格返回JSON。"
        rules_text = "\n".join(
            f"- {item['rule_id']} {item['rule_name']}；策略：{';'.join(item.get('replacement_strategy', []))}；允许自动改写：{item.get('auto_rewrite_allowed')}"
            for item in matched_rules
        )
        raw = self._chat(
            system_prompt,
            f"原文：{text}\n平台：{platform}\n内容类型：{content_type}\n命中规则：\n{rules_text}\n严格返回JSON。",
        )
        try:
            data = json.loads(self._extract_json(raw))
            unresolved = data.get("unresolved_items", [])
            return {
                "suggested_revision": str(data.get("suggested_revision") or ""),
                "auto_rewrite": bool(data.get("auto_rewrite", False)),
                "unresolved_items": unresolved if isinstance(unresolved, list) else [],
            }
        except Exception as exc:
            return {
                "suggested_revision": "",
                "auto_rewrite": False,
                "unresolved_items": [f"改写结果解析失败，请人工复核：{exc}"],
            }

    def adjust(self, text, adjust_type, platform, content_type, tone) -> str:
        requirements = {
            "缩短": "压缩篇幅，保留核心事实，删除重复内容，不新增任何事实主张。",
            "扩写": "扩展必要的流程、适用条件、注意事项和风险提示，不编造数据、资质或效果。",
            "调整语气": f"仅将表达调整为“{tone}”语气，不改变事实含义。",
        }
        system_prompt = (
            "你只负责调整一份现有医美文案。不得重复展示原文，不得把原文与修改稿并列，"
            "不得套用新的标题或营销模板，不得引入请求中没有的事实。"
            "严格返回 JSON，格式为 {\"text\":\"调整后的完整文案\"}。"
        )
        raw = self._chat(
            system_prompt,
            f"调整类型：{adjust_type}\n平台：{platform}\n内容类型：{content_type}\n"
            f"要求：{requirements[adjust_type]}\n待调整文案：\n{text}",
        )
        try:
            data = json.loads(self._extract_json(raw))
            adjusted = str(data.get("text") or "").strip()
        except Exception as exc:
            raise ValueError(f"调整结果无法解析：{exc}") from exc
        if not adjusted:
            raise ValueError("模型没有返回调整后的文案。")
        return adjusted

    def prompt_draft(self, context: dict) -> str:
        target_type = str(context.get("target_type") or "scene")
        target_labels = {"base": "公共基础", "platform": "平台级", "scene": "场景级"}
        system_prompt = (
            "你是内容生成系统的提示词设计助手。请根据用户约束编写一段可复用的中文系统提示词，"
            "目标层级是“" + target_labels.get(target_type, target_type) + "”。"
            "只输出提示词正文，不输出示例文案、分析过程、Markdown 代码块或保存说明。"
            "提示词必须要求模型不虚构事实，但不要罗列大批具体禁词；具体合规规则由运行时规则库注入。"
            "不得写入关闭、绕过、弱化合规检测的指令，也不要使用品牌、主题等模板占位符。"
        )
        user_prompt = (
            f"平台名称：{context.get('platform_name', '')}\n"
            f"平台用途：{context.get('platform_description', '')}\n"
            f"合规画像：{context.get('rule_profile', '通用')}\n"
            f"场景名称：{context.get('scene_name', '')}\n"
            f"场景用途：{context.get('scene_description', '')}\n"
            f"合规内容类型：{context.get('rule_content_type', '通用')}\n"
            f"上层有效提示词：{context.get('parent_prompt', '')}\n"
            f"用户需求约束：{context.get('requirements', '')}\n"
            f"待优化的现有提示词：{context.get('current_prompt', '')}\n"
            "请输出完整、可直接保存的提示词正文。"
        )
        output = self._chat(system_prompt, user_prompt).strip()
        output = re.sub(r"^```(?:text|markdown)?\s*", "", output, flags=re.IGNORECASE)
        output = re.sub(r"\s*```$", "", output).strip()
        if not output:
            raise ValueError("模型没有返回可用的提示词草稿。")
        return output

    @staticmethod
    def _extract_json(raw: str) -> str:
        text = (raw or "").strip()
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        start, end = text.find("{"), text.rfind("}")
        return text[start:end + 1] if start != -1 and end != -1 and end >= start else text


def build_provider(settings: dict) -> LLMProvider:
    settings = settings or {}
    provider_name = settings.get("model_provider", "mock")
    if provider_name == "mock":
        return MockProvider()
    if provider_name != "openai_compatible":
        raise ValueError(f"不支持的模型 Provider：{provider_name}")
    api_key = config.get_llm_api_key()
    if not api_key:
        raise ValueError(
            "已选择真实模型，但未读取到 LLM_API_KEY。请填写项目根目录 .env 后重试。"
        )
    return OpenAICompatibleProvider(
        api_key=api_key,
        base_url=settings.get("api_base") or config.LLM_BASE_URL,
        model=settings.get("model_name") or config.LLM_MODEL,
        temperature=settings.get("temperature", config.LLM_TEMPERATURE),
        max_tokens=settings.get("max_tokens", config.LLM_MAX_TOKENS),
    )
