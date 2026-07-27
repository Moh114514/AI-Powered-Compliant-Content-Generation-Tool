"""大模型适配层：统一 Provider 接口。
- MockProvider：无 API Key 时使用，生成合理演示文案，语义检测用启发式，改写做安全降级。
- OpenAICompatibleProvider：兼容 OpenAI / DeepSeek / 通义 等 OpenAI 接口。
"""
import json
import re
import random
from typing import Any

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


# ---------- MockProvider ----------
class MockProvider(LLMProvider):
    name = "mock"

    def __init__(self):
        self._sem_map = self._build_sem_map()

    def _build_sem_map(self):
        store = get_store()
        by_name = {}
        for sr in store.semantic_rules:
            name = (sr.get("semantic_rule_name") or "")
            sid = sr.get("semantic_rule_id")
            by_name.setdefault(sid, name)
        # 按名称推断各类语义风险的默认 SR
        def find(*keys):
            for sid, nm in by_name.items():
                if any(k in nm for k in keys):
                    return sid
            return next(iter(by_name), "")
        return {
            "effect_guarantee": find("保证", "效果"),
            "absolute_safe": find("无风险", "安全"),
            "case_to_general": find("保证", "效果"),
            "appearance_anxiety": find("焦虑", "诱导"),
            "no_treatment_threat": find("保证", "效果"),
            "unverified_data": find("保证", "效果"),
            "disguised_ad": find("焦虑", "诱导"),
            "anxiety_induce": find("焦虑", "诱导"),
            "undiagnosed": find("诊断", "判断"),
            "evasion": find("谐音", "拆字", "拼音", "符号"),
            "time_commit": find("保证", "效果"),
            "rank": find("保证", "效果"),
            "scarcity": find("焦虑", "诱导"),
        }

    # --- 生成 ---
    def generate(self, platform, content_type, inputs, prompt_template, brand_profile, versions) -> list[str]:
        topic = inputs.get("topic") or "项目体验"
        sp = inputs.get("selling_points") or ""
        audience = inputs.get("target_audience") or "关注品质的用户"
        campaign = inputs.get("campaign_info") or ""
        brand_name = (brand_profile or {}).get("brand_name", "")
        tone = inputs.get("tone") or "亲切专业"
        length = inputs.get("length") or "中"

        copies = []
        scaffolds = self._scaffold(platform, content_type)
        for i in range(max(1, versions)):
            sc = scaffolds[i % len(scaffolds)]
            body = sc.format(
                brand=brand_name, topic=topic, sp=sp, audience=audience,
                campaign=campaign, tone=tone,
            )
            if length == "短":
                body = body[: int(len(body) * 0.6)]
            elif length == "长":
                body = body + "（具体方案与风险以到店专业评估为准。）"
            copies.append(body.strip())
        return copies

    def _scaffold(self, platform, content_type):
        if platform == "小红书":
            return [
                "最近在了解{topic}，想和大家分享一下我的视角。{sp}。适合{audience}了解，{campaign}。具体情况还是要以专业机构面诊评估为准～",
                "关于{topic}的一些科普：项目有它的适用人群和注意事项，{sp}这类说法建议理性看待。{campaign}。个体差异很大，别盲目跟风。",
                "记录了一次{topic}的体验框架：先评估再决定，{sp}。给{audience}参考，{campaign}。是否适合你，需要专业医师判断。",
            ]
        if platform == "朋友圈":
            return [
                "最近在忙{topic}，{sp}。给关心的朋友同步一下，{campaign}。想了解的欢迎私信，到店会有专业评估。",
                "随手记：{topic}这件事，{sp}。{campaign}。效果因人而异，建议先面诊再决定。",
            ]
        if platform == "微信社群":
            return [
                "【群通知】{topic}活动开启，{sp}。{campaign}。请到店由专业医师评估个人情况后再安排。",
                "各位伙伴，关于{topic}：{sp}。{campaign}。如有疑问可在群内提问，我们会客观解答，不替代专业诊断。",
            ]
        if platform == "微信公众号":
            return [
                "# {topic}\n\n本文介绍{topic}的相关信息：{sp}。{campaign}。\n\n需提示：项目效果与风险因个人情况而异，请以正规机构面诊评估为准。",
                "{topic}科普：{sp}。{campaign}。文章为科普性质，不构成诊疗建议，具体方案请咨询专业医师。",
            ]
        # 客服话术
        return [
            "您好，关于{topic}：{sp}。{campaign}。每个人的情况不同，建议您到店由专业医师评估后再确定合适方案。",
            "感谢咨询{topic}。{sp}。具体效果和注意事项需要结合您的实际情况，我不能替代专业诊断，建议预约面诊。",
        ]

    # --- 语义检测（启发式）---
    def semantic_check(self, text, platform, content_type, semantic_rules, matched_rules) -> dict:
        findings = []
        m = self._sem_map
        checks = [
            ("effect_guarantee", r"(保证|确保|肯定|一定|必|100%|绝对).{0,12}(效果|见效|恢复|年轻|变美|治好|有效|成功)", "critical"),
            ("absolute_safe", r"(零风险|绝对安全|无任何风险|无副作用|无风险|绝对放心)", "critical"),
            ("rank", r"(全城|全网|全国|全市|全平台).{0,8}(最好|最佳|第一|最强|顶尖|top|Top|TOP)", "high"),
            ("time_commit", r"(\d+)\s*(天|周|月|年).{0,10}(年轻|见效|恢复|变美|瘦|白|治好|逆龄)", "high"),
            ("scarcity", r"(限时|名额有限|仅剩|最后|速来|抢|疯抢|错过)", "high"),
            ("unverified_data", r"(\d+)\s*(万|w|W|千|w人).{0,8}(人|用户|顾客|服务|案例|好评)", "high"),
            ("case_to_general", r"(我朋友|我同事|我亲戚|身边人|我同学).{0,16}(好了|见效|恢复|成功)", "high"),
            ("appearance_anxiety", r"(丑|缺陷|显老|老了|不好看).{0,10}(必须|赶紧|快去|不整|赶紧做)", "medium"),
            ("no_treatment_threat", r"(不做|不整|不治疗|不改善).{0,12}(越来越|更严重|毁|垮)", "high"),
            ("disguised_ad", r"(本文|分享|科普|笔记).{0,14}(购买|下单|预约|到店|私信)", "medium"),
        ]
        needs = False
        reason = ""
        for key, pat, lvl in checks:
            mm = re.search(pat, text)
            if mm:
                sid = m.get(key) or (semantic_rules[0].get("semantic_rule_id") if semantic_rules else "")
                sr_name = next((s.get("semantic_rule_name") for s in semantic_rules if s.get("semantic_rule_id") == sid), key)
                findings.append({
                    "semantic_rule_id": sid,
                    "semantic_rule_name": sr_name,
                    "risk_level": lvl,
                    "matched_text": mm.group(0),
                    "risk_reason": f"疑似{key}类语义风险，需结合上下文确认。",
                    "manual_review": lvl in ("critical", "high"),
                })
                if lvl in ("critical", "high"):
                    needs = True
        if needs:
            reason = "文案存在需人工判断的语义风险（效果保证/安全承诺/数据来源等），建议复核。"
        return {"semantic_findings": findings, "needs_manual_review": needs, "manual_review_reason": reason}

    # --- 改写 ---
    def rewrite(self, text, matched_rules, platform, content_type) -> dict:
        from app.core.text_normalize import normalize_text, map_span
        # 收集可自动改写的区间（按原文坐标）
        spans = []
        unresolved = []
        for m in matched_rules:
            if not m.get("auto_rewrite_allowed"):
                unresolved.append(f"{m['rule_id']} {m['rule_name']}（不允许自动改写，需人工复核）")
                continue
            for sp in m.get("spans", []):
                spans.append((sp["start_index"], sp["end_index"]))
        spans.sort(reverse=True)  # 从后往前删，避免偏移
        revised = text
        for s, e in spans:
            revised = revised[:s] + "" + revised[e:]
        # 清理多余标点/空格
        revised = re.sub(r"[，,。\.]{2,}", "。", revised)
        revised = re.sub(r"\s{2,}", " ", revised).strip()
        if revised and not revised.endswith(("。", "！", "？", ".", "！", "？")):
            revised += "。"
        revised += "（具体风险、适用情况和注意事项需结合个人情况进行专业评估。）"
        return {
            "suggested_revision": revised,
            "auto_rewrite": len(unresolved) == 0,
            "unresolved_items": unresolved,
        }


# ---------- OpenAICompatibleProvider ----------
class OpenAICompatibleProvider(LLMProvider):
    name = "openai_compatible"

    def __init__(self, api_key, base_url, model, temperature, max_tokens):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            except Exception:
                self._client = None
        return self._client

    def _chat(self, system_prompt: str, user_prompt: str) -> str:
        client = self._get_client()
        if client is not None:
            resp = client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return resp.choices[0].message.content or ""
        # 退化：用 requests
        import requests
        r = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model, "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "messages": [{"role": "system", "content": system_prompt},
                             {"role": "user", "content": user_prompt}],
            },
            timeout=60,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def generate(self, platform, content_type, inputs, prompt_template, brand_profile, versions) -> list[str]:
        bp = brand_profile or {}
        user = (
            f"平台：{platform}\n内容类型：{content_type}\n"
            f"品牌：{bp.get('brand_name','')}（调性：{bp.get('tone','')}；偏好用词：{bp.get('preferred_terms','')}；"
            f"禁用词：{bp.get('preferred_terms','')}）\n"
            f"主题：{inputs.get('topic','')}\n卖点：{inputs.get('selling_points','')}\n"
            f"目标人群：{inputs.get('target_audience','')}\n活动信息：{inputs.get('campaign_info','')}\n"
            f"语气：{inputs.get('tone','')}\n长度：{inputs.get('length','中')}\n"
            f"补充要求：{inputs.get('extra_requirements','')}\n"
            f"请生成 {versions} 个版本，用 === 分隔，每个版本直接输出文案正文。"
        )
        out = self._chat((prompt_template or "") + "\n\n请遵循上述平台模板与合规约束。", user)
        parts = [p.strip() for p in re.split(r"={3,}", out) if p.strip()]
        if not parts:
            parts = [out.strip()]
        return parts[: max(1, versions)]

    def semantic_check(self, text, platform, content_type, semantic_rules, matched_rules) -> dict:
        import os
        prompt_path = os.path.join(config.PROMPTS_DIR, "compliance_semantic_check.md")
        system_prompt = ""
        if os.path.exists(prompt_path):
            with open(prompt_path, encoding="utf-8") as f:
                system_prompt = f.read()
        rules_txt = "\n".join(
            f"- {s.get('semantic_rule_id')} {s.get('semantic_rule_name')}: {s.get('detection_description','')}"
            for s in semantic_rules
        )
        user = (
            f"文案：{text}\n平台：{platform}\n内容类型：{content_type}\n"
            f"语义规则：\n{rules_txt}\n已命中确定性规则："
            + ";".join(m["rule_id"] for m in matched_rules)
            + "\n请严格返回 JSON。"
        )
        raw = self._chat(system_prompt, user)
        try:
            data = json.loads(self._extract_json(raw))
            return {
                "semantic_findings": data.get("semantic_findings", []),
                "needs_manual_review": bool(data.get("needs_manual_review", False)),
                "manual_review_reason": data.get("manual_review_reason", ""),
            }
        except Exception:
            return {"semantic_findings": [], "needs_manual_review": False, "manual_review_reason": ""}

    def rewrite(self, text, matched_rules, platform, content_type) -> dict:
        import os
        prompt_path = os.path.join(config.PROMPTS_DIR, "compliance_rewrite.md")
        system_prompt = ""
        if os.path.exists(prompt_path):
            with open(prompt_path, encoding="utf-8") as f:
                system_prompt = f.read()
        rules_txt = "\n".join(
            f"- {m['rule_id']} {m['rule_name']} 修改策略：{';'.join(m.get('replacement_strategy', []))} "
            f"允许自动改写：{m.get('auto_rewrite_allowed')}"
            for m in matched_rules
        )
        user = f"原文：{text}\n平台：{platform}\n内容类型：{content_type}\n命中规则：\n{rules_txt}\n请严格返回 JSON。"
        raw = self._chat(system_prompt, user)
        try:
            data = json.loads(self._extract_json(raw))
            return {
                "suggested_revision": data.get("suggested_revision", ""),
                "auto_rewrite": bool(data.get("auto_rewrite", False)),
                "unresolved_items": data.get("unresolved_items", []),
            }
        except Exception:
            return {"suggested_revision": "", "auto_rewrite": False, "unresolved_items": ["改写解析失败，请人工复核"]}

    @staticmethod
    def _extract_json(raw: str) -> str:
        s = raw.find("{")
        e = raw.rfind("}")
        if s != -1 and e != -1:
            return raw[s : e + 1]
        return raw


def build_provider(settings: dict) -> LLMProvider:
    """根据设置构建 Provider。无 API Key 时回退 Mock。"""
    provider_name = (settings or {}).get("model_provider", "mock")
    api_key = config.LLM_API_KEY
    if provider_name == "mock" or not api_key:
        return MockProvider()
    return OpenAICompatibleProvider(
        api_key=api_key,
        base_url=settings.get("api_base") or config.LLM_BASE_URL,
        model=settings.get("model_name") or config.LLM_MODEL,
        temperature=float(settings.get("temperature", config.LLM_TEMPERATURE)),
        max_tokens=int(settings.get("max_tokens", config.LLM_MAX_TOKENS)),
    )
