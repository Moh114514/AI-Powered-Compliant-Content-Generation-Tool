import React, { useState } from "react";
import type { ComplianceResult } from "../types";
import { RiskHighlight } from "./RiskHighlight";
import { RuleCard } from "./RuleCard";
import { RiskBadge } from "./RiskBadge";
import { ReviewSummaryBox } from "./ReviewSummaryBox";
import { statusOf, REVIEW_RECOMMENDATION_LABEL, riskMeta } from "../utils/risk";
import { copyText } from "../utils/misc";

export function ComplianceReport({ result, onRewrite }: { result: ComplianceResult; onRewrite?: () => void }) {
  const [selectedRule, setSelectedRule] = useState<string | null>(null);
  const status = statusOf(result);
  const recLabel = REVIEW_RECOMMENDATION_LABEL[result.publish_recommendation] || result.publish_recommendation;

  return (
    <div style={{ display: "grid", gap: 12 }}>
      {/* 状态头 */}
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 10 }}>
        <RiskBadge meta={status} size="md" />
        <span style={{ fontSize: 13, color: "#374151" }}>
          发布建议：<b>{recLabel}</b>
        </span>
        {result.review_level && (
          <span style={{ fontSize: 12, color: "#6b7280" }}>复核等级 {result.review_level}</span>
        )}
        {result.manual_review_required && (
          <span style={{ fontSize: 12, color: "#6d28d9" }}>· 需人工复核</span>
        )}
      </div>

      {result.platform_rules_incomplete && (
        <div style={{ background: "#fffbeb", border: "1px solid #fde68a", color: "#92400e", borderRadius: 8, padding: "8px 10px", fontSize: 12 }}>
          ⚠️ 平台专项规则覆盖可能不完整，已执行通用法律规则进行检测。
        </div>
      )}

      {/* 未发现明显风险时的提示 */}
      {result.overall_risk_level === "none" && (
        <div style={{ background: "#f0fdf4", border: "1px solid #bbf7d0", color: "#166534", borderRadius: 8, padding: "8px 10px", fontSize: 13 }}>
          未发现明显高风险表达，但仍需核验主体资质、项目资质、图片素材、数据来源和活动真实性。
        </div>
      )}

      {/* 原文高亮 */}
      <div className="card">
        <div style={{ fontSize: 12, color: "#9ca3af", marginBottom: 6 }}>原文风险高亮</div>
        <div style={{ fontSize: 14, lineHeight: 1.9 }}>
          <RiskHighlight text={result.input_text} spans={result.highlights || []} onSelect={(sp) => setSelectedRule(sp.rule_id)} />
        </div>
      </div>

      {/* 命中的确定性规则 */}
      <div>
        <div style={{ fontSize: 13, fontWeight: 600, margin: "4px 0 8px" }}>
          命中规则（{result.matched_rules.length}）
        </div>
        {result.matched_rules.length === 0 ? (
          <div style={{ fontSize: 13, color: "#6b7280" }}>未命中关键词/正则规则。</div>
        ) : (
          <div style={{ display: "grid", gap: 8 }}>
            {result.matched_rules.map((m) => (
              <RuleCard key={m.rule_id + (m.spans[0]?.matched_text || "")} rule={m} selected={selectedRule === m.rule_id} />
            ))}
          </div>
        )}
      </div>

      {/* 语义风险 */}
      {result.semantic_findings && result.semantic_findings.length > 0 && (
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, margin: "4px 0 8px" }}>语义风险（{result.semantic_findings.length}）</div>
          <div style={{ display: "grid", gap: 6 }}>
            {result.semantic_findings.map((sf, i) => (
              <div key={i} className="card" style={{ padding: 10, borderLeft: `3px solid ${riskMeta(sf.risk_level).border}` }}>
                <div style={{ fontSize: 13, fontWeight: 600 }}>{sf.semantic_rule_name}</div>
                <div style={{ fontSize: 12, color: "#6b7280" }}>
                  命中：“{sf.matched_text}” · {riskMeta(sf.risk_level).label}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 人工复核事项 */}
      {result.manual_review_issues && result.manual_review_issues.length > 0 && (
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, margin: "4px 0 8px" }}>需人工复核事项</div>
          <div style={{ display: "grid", gap: 6 }}>
            {result.manual_review_issues.map((iss, i) => (
              <div key={i} className="card" style={{ padding: 10, background: "#faf9ff" }}>
                <div style={{ fontSize: 13 }}>
                  <b>[{iss.issue_type}]</b> {iss.question}
                </div>
                <div style={{ fontSize: 12, color: "#6d28d9", marginTop: 2 }}>建议对接：{iss.recommended_contact}</div>
                {iss.required_evidence && (
                  <div style={{ fontSize: 12, color: "#6b7280" }}>所需材料：{iss.required_evidence}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 建议修改稿 */}
      {result.suggested_revision && (
        <div className="card" style={{ background: "#f0fdf4", borderColor: "#bbf7d0" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
            <strong style={{ fontSize: 14 }}>建议修改稿（合规改写）</strong>
            <button className="btn" style={{ padding: "4px 8px", fontSize: 12 }} onClick={async () => alert((await copyText(result.suggested_revision)) ? "已复制" : "复制失败")}>
              复制
            </button>
          </div>
          <div style={{ fontSize: 14, whiteSpace: "pre-wrap", lineHeight: 1.7 }}>{result.suggested_revision}</div>
        </div>
      )}

      {/* 人工复核摘要 */}
      {result.review_summary && <ReviewSummaryBox summary={result.review_summary} />}

      {/* 免责声明 */}
      <div style={{ fontSize: 12, color: "#9ca3af", borderTop: "1px dashed #e5e7eb", paddingTop: 8 }}>
        {result.disclaimer}
      </div>
    </div>
  );
}
