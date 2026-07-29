import React, { useState } from "react";
import type { BannedWordHit, ComplianceResult } from "../types";
import { copyText } from "../utils/misc";
import { REVIEW_RECOMMENDATION_LABEL, riskMeta, statusOf } from "../utils/risk";
import { ReviewSummaryBox } from "./ReviewSummaryBox";
import { RiskBadge } from "./RiskBadge";
import { RiskHighlight } from "./RiskHighlight";
import { RuleCard } from "./RuleCard";

export function ComplianceReport({ result }: { result: ComplianceResult }) {
  const [selectedRule, setSelectedRule] = useState<string | null>(null);
  const status = statusOf(result);
  const recommendation = REVIEW_RECOMMENDATION_LABEL[result.publish_recommendation] || result.publish_recommendation;

  return <div style={{ display: "grid", gap: 12 }}>
    <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 10 }}>
      <RiskBadge meta={status} size="md" />
      <span style={{ fontSize: 13, color: "#374151" }}>发布建议：<b>{recommendation}</b></span>
      {result.review_level && <span style={{ fontSize: 12, color: "#6b7280" }}>复核等级 {result.review_level}</span>}
      {result.manual_review_required && <span style={{ fontSize: 12, color: "#6d28d9" }}>· 需人工复核</span>}
      {result.stats && <span style={{ fontSize: 12, color: "#9ca3af" }}>检查 {result.stats.applicable_rule_count} 条适用规则 · {result.stats.matched_span_count} 处命中</span>}
    </div>

    {result.platform_findings?.map((finding, index) => <Notice key={index} tone="warning">⚠️ {finding.message || "存在平台专项风险。"}</Notice>)}
    {result.semantic_analysis_failed && <Notice tone="error">
      语义检测未成功完成{result.semantic_failure_reason ? `：${result.semantic_failure_reason}` : "。"}
      当前结果只可作为确定性规则筛查，不能据此直接认定内容低风险。
    </Notice>}

    {result.overall_risk_level === "none" && !result.semantic_analysis_failed && <Notice tone="success">未发现明显高风险表达，但仍需核验主体资质、项目资质、图片和视频素材、数据来源、活动真实性及授权范围。</Notice>}

    <div className="card">
      <div style={{ fontSize: 12, color: "#9ca3af", marginBottom: 6 }}>原文风险高亮</div>
      <div style={{ fontSize: 14, lineHeight: 1.9 }}><RiskHighlight text={result.input_text} spans={result.highlights || []} onSelect={(span) => setSelectedRule(span.hit_id || span.rule_id)} /></div>
    </div>

    {!!result.banned_word_hits?.length && <section>
      <div style={{ fontSize: 13, fontWeight: 600, margin: "4px 0 8px" }}>小红书违禁/敏感词（{result.banned_word_hits.length}）</div>
      <div style={{ display: "grid", gap: 8 }}>
        {result.banned_word_hits.map((hit) => <BannedWordCard key={hit.hit_id} hit={hit} selected={selectedRule === hit.hit_id} />)}
      </div>
    </section>}

    <section>
      <div style={{ fontSize: 13, fontWeight: 600, margin: "4px 0 8px" }}>确定性规则（{result.matched_rules.length}）</div>
      {result.matched_rules.length === 0 ? <div style={{ fontSize: 13, color: "#6b7280" }}>未命中关键词或正则规则。</div> : <div style={{ display: "grid", gap: 8 }}>{result.matched_rules.map((rule) => <RuleCard key={rule.rule_id} rule={rule} selected={selectedRule === rule.rule_id} />)}</div>}
    </section>

    {!!result.semantic_findings?.length && <section>
      <div style={{ fontSize: 13, fontWeight: 600, margin: "4px 0 8px" }}>语义风险（{result.semantic_findings.length}）</div>
      <div style={{ display: "grid", gap: 6 }}>{result.semantic_findings.map((finding, index) => <div key={`${finding.semantic_rule_id}-${index}`} className="card" style={{ padding: 10, borderLeft: `3px solid ${riskMeta(finding.risk_level).border}` }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}><b style={{ fontSize: 13 }}>{finding.semantic_rule_name}</b><span style={{ fontSize: 12, color: "#6b7280" }}>{riskMeta(finding.risk_level).label}</span></div>
        {finding.matched_text && <div style={{ fontSize: 12, color: "#6b7280", marginTop: 3 }}>相关文本：“{finding.matched_text}”</div>}
        {finding.risk_reason && <div style={{ fontSize: 12, marginTop: 3 }}>{finding.risk_reason}</div>}
      </div>)}</div>
    </section>}

    {!!result.manual_review_issues?.length && <section>
      <div style={{ fontSize: 13, fontWeight: 600, margin: "4px 0 8px" }}>需人工复核事项（{result.manual_review_issues.length}）</div>
      <div style={{ display: "grid", gap: 6 }}>{result.manual_review_issues.map((issue, index) => <div key={`${issue.rule_id || issue.semantic_rule_id || issue.issue_type}-${index}`} className="card" style={{ padding: 10, background: "#faf9ff" }}>
        <div style={{ fontSize: 13 }}><b>[{issue.issue_type}]</b> {issue.question}</div>
        <div style={{ fontSize: 12, color: "#6d28d9", marginTop: 3 }}>建议对接：{issue.recommended_contact}</div>
        {issue.required_evidence && <div style={{ fontSize: 12, color: "#6b7280" }}>所需材料：{issue.required_evidence}</div>}
      </div>)}</div>
    </section>}

    {result.suggested_revision && <div className="card" style={{ background: "#f0fdf4", borderColor: "#bbf7d0" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}><strong style={{ fontSize: 14 }}>建议修改稿</strong><button className="btn" style={{ padding: "4px 8px", fontSize: 12 }} onClick={async () => alert((await copyText(result.suggested_revision)) ? "已复制" : "复制失败")}>复制</button></div>
      <div style={{ fontSize: 14, whiteSpace: "pre-wrap", lineHeight: 1.7 }}>{result.suggested_revision}</div>
    </div>}

    {result.review_summary && <ReviewSummaryBox summary={result.review_summary} />}

    <div style={{ fontSize: 12, color: "#9ca3af", borderTop: "1px dashed #e5e7eb", paddingTop: 8 }}>
      {result.disclaimer}<br />当前版本以文本检测为主，不自动验证图片、视频画面、证件真伪或授权文件真实性。
    </div>
  </div>;
}

function BannedWordCard({ hit, selected }: { hit: BannedWordHit; selected: boolean }) {
  const [open, setOpen] = useState(false);
  const meta = riskMeta(hit.risk_level);
  const contextLabel = hit.context_classification === "promotional"
    ? "营销风险语境"
    : hit.context_classification === "neutral"
      ? "中性语境，需复核"
      : "语境不明确，需复核";
  const suggestions = hit.replacements || [];
  const instructionOnly = suggestions.length > 0 && suggestions.every((item) => /删除|禁止|避免/.test(item));
  const copySuggestion = async () => {
    const text = suggestions.join("；") || "建议删除或整体改写该表达";
    alert((await copyText(text)) ? "替换建议已复制" : "复制失败");
  };
  return <div className="card" style={{
    padding: 12,
    borderColor: selected ? meta.border : "#e5e7eb",
    boxShadow: selected ? `0 0 0 2px ${meta.bg}` : "none",
  }}>
    <div style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }} onClick={() => setOpen((value) => !value)}>
      <RiskBadge meta={meta} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 600, fontSize: 14 }}>“{hit.matched_text}” {Number(hit.occurrence_count || 1) > 1 && <span style={{ color: "#6b7280", fontWeight: 400 }}>× {hit.occurrence_count}</span>} <span style={{ color: "#6b7280", fontWeight: 400 }}>· {hit.domain}</span></div>
        <div style={{ fontSize: 12, color: "#6b7280" }}>标准词：{hit.canonical_word} · {contextLabel}</div>
      </div>
      <span style={{ fontSize: 12, color: "#9ca3af" }}>{open ? "收起 ▲" : "展开 ▼"}</span>
    </div>
    <div style={{ marginTop: 8, background: "#f8fafc", borderRadius: 6, padding: "8px 10px", fontSize: 13 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
        <b>{instructionOnly ? "删除/整体改写建议" : "推荐替代表达"}</b>
        <button className="btn" style={{ padding: "2px 8px", fontSize: 12 }} onClick={copySuggestion}>复制建议</button>
      </div>
      <div style={{ marginTop: 4, color: "#374151" }}>{suggestions.join("；") || "建议删除或整体改写该表达"}</div>
      {instructionOnly && <div style={{ color: "#9a3412", fontSize: 12, marginTop: 3 }}>这是操作说明，不应把括号内文字直接替换进原文。</div>}
    </div>
    {open && <div style={{ marginTop: 8, display: "grid", gap: 5, fontSize: 12, color: "#4b5563" }}>
      <div><span style={{ color: "#9ca3af" }}>风险原因：</span>{hit.reason || "—"}</div>
      <div><span style={{ color: "#9ca3af" }}>词库等级：</span>{(hit.source_risk_levels || []).join("、") || "—"}</div>
      <div><span style={{ color: "#9ca3af" }}>来源编号：</span>{hit.source_ids.join("、") || "—"}</div>
      <div><span style={{ color: "#9ca3af" }}>资料来源：</span>{hit.sources.join("、") || "—"}</div>
    </div>}
  </div>;
}

function Notice({ tone, children }: { tone: "success" | "warning" | "error"; children: React.ReactNode }) {
  const styles = tone === "success" ? ["#f0fdf4", "#bbf7d0", "#166534"] : tone === "warning" ? ["#fffbeb", "#fde68a", "#92400e"] : ["#fef2f2", "#fecaca", "#b91c1c"];
  return <div style={{ background: styles[0], border: `1px solid ${styles[1]}`, color: styles[2], borderRadius: 8, padding: "8px 10px", fontSize: 13 }}>{children}</div>;
}
