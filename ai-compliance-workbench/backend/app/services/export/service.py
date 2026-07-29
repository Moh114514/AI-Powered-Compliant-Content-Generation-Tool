"""导出服务：人工复核摘要（TXT/Markdown）与完整检测报告（Markdown/JSON）。"""
from app.core import config


def build_review_summary(result: dict) -> str:
    lines = ["【医美文案人工复核摘要】", f"平台：{result.get('platform','')}",
             f"内容类型：{result.get('content_type','')}"]
    risk_label = config.RISK_LABELS.get(result.get("overall_risk_level"), result.get("overall_risk_level"))
    rec = result.get("publish_recommendation")
    rec_label = {"block": "暂停发布", "manual_review": "人工复核后发布",
                 "request_evidence": "补充材料后发布", "warning": "修改后发布",
                 "pass": "可发布"}.get(rec, rec)
    lines += [f"总体风险：{risk_label}", f"处理建议：{rec_label}", ""]
    if result.get("manual_review_issues"):
        lines.append("需要确认：")
        for i, iss in enumerate(result["manual_review_issues"], 1):
            ev = iss.get("required_evidence")
            extra = f"（需材料：{ev}）" if ev else ""
            lines.append(f"{i}. {iss.get('question','')}{extra}")
        lines.append("")
    if result.get("matched_rules"):
        lines.append("命中规则：")
        for m in result["matched_rules"]:
            lines.append(f"- {m['rule_id']} {m['rule_name']}")
        lines.append("")
    if result.get("banned_word_hits"):
        lines.append("小红书专项词：")
        for hit in result["banned_word_hits"]:
            suggestion = "；".join(hit.get("replacements") or []) or "请删除或改写"
            lines.append(f"- {hit.get('matched_text', '')}：{suggestion}")
        lines.append("")
    contacts = sorted({iss.get("recommended_contact") for iss in result.get("manual_review_issues", []) if iss.get("recommended_contact")})
    if contacts:
        lines.append("建议对接：" + "、".join(contacts) + "。")
    lines.append("")
    lines.append("本工具不记录复核结果。")
    return "\n".join(lines)


def build_report_markdown(result: dict) -> str:
    r = result
    L = []
    L.append(f"# 医美内容合规检测报告\n")
    L.append(f"- 平台：**{r.get('platform','')}**　内容类型：**{r.get('content_type','')}**")
    risk_label = config.RISK_LABELS.get(r.get("overall_risk_level"), r.get("overall_risk_level"))
    L.append(f"- 总体风险：**{risk_label}**　复核等级：{r.get('review_level') or '—'}")
    L.append(f"- 发布建议：**{_rec_label(r.get('publish_recommendation'))}**　需人工复核：{'是' if r.get('manual_review_required') else '否'}")
    if r.get("platform_rules_incomplete"):
        L.append(f"- ⚠️ 平台专项规则覆盖可能不完整，已执行通用法律规则。")
    L.append("")
    L.append("## 原文与高亮\n")
    L.append("> " + r.get("input_text", "").replace("\n", "  \n> "))
    L.append("")
    if r.get("matched_rules"):
        L.append("## 命中规则\n")
        L.append("| rule_id | 规则名称 | 风险等级 | 命中内容 | 系统动作 |")
        L.append("| --- | --- | --- | --- | --- |")
        for m in r["matched_rules"]:
            acts = "、".join(config.SYSTEM_ACTION_LABELS.get(a, a) for a in m.get("system_action", []))
            L.append(f"| {m['rule_id']} | {m['rule_name']} | {config.RISK_LABELS.get(m['risk_level'], m['risk_level'])} | {m['matched_text']} | {acts} |")
        L.append("")
    if r.get("banned_word_hits"):
        L.append("## 小红书违禁/敏感词\n")
        L.append("| 命中内容 | 标准词 | 风险等级 | 语境 | 替换建议 | 来源 |")
        L.append("| --- | --- | --- | --- | --- | --- |")
        for hit in r["banned_word_hits"]:
            replacements = "；".join(hit.get("replacements") or []) or "请删除或改写"
            sources = "；".join(hit.get("sources") or [])
            L.append(
                f"| {hit.get('matched_text', '')} | {hit.get('canonical_word', '')} | "
                f"{config.RISK_LABELS.get(hit.get('risk_level'), hit.get('risk_level'))} | "
                f"{hit.get('context_classification', '')} | {replacements} | {sources} |"
            )
        L.append("")
    if r.get("semantic_findings"):
        L.append("## 语义风险\n")
        for sf in r["semantic_findings"]:
            L.append(f"- **{sf.get('semantic_rule_name')}**（{config.RISK_LABELS.get(sf.get('risk_level'), sf.get('risk_level'))}）：{sf.get('matched_text','')} — {sf.get('risk_reason','')}")
        L.append("")
    if r.get("manual_review_issues"):
        L.append("## 需人工复核事项\n")
        for iss in r["manual_review_issues"]:
            L.append(f"- [{iss.get('issue_type','')}] {iss.get('question','')}（建议对接：{iss.get('recommended_contact','')}）")
        L.append("")
    if r.get("suggested_revision"):
        L.append("## 建议修改稿\n")
        L.append(r["suggested_revision"])
        L.append("")
    L.append("## 免责声明\n")
    L.append(r.get("disclaimer", config.DISCLAIMER))
    return "\n".join(L)


def build_report_json(result: dict) -> dict:
    return result


def _rec_label(rec):
    return {"block": "暂停发布", "manual_review": "人工复核后发布",
            "request_evidence": "补充材料后发布", "warning": "修改后发布",
            "pass": "可发布"}.get(rec, rec or "")
