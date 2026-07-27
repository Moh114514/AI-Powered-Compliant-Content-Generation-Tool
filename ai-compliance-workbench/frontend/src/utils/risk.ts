import type { ComplianceResult } from "../types";

export interface RiskMeta {
  key: string;
  label: string;
  text: string; // 文字颜色
  bg: string; // 背景色
  border: string; // 边框色
}

export const RISK_META: Record<string, RiskMeta> = {
  critical: { key: "critical", label: "严重风险", text: "#b91c1c", bg: "#fee2e2", border: "#ef4444" },
  high: { key: "high", label: "高风险", text: "#c2410c", bg: "#ffedd5", border: "#f97316" },
  medium: { key: "medium", label: "中等风险", text: "#a16207", bg: "#fef9c3", border: "#eab308" },
  low: { key: "low", label: "低风险", text: "#1d4ed8", bg: "#dbeafe", border: "#3b82f6" },
  none: { key: "none", label: "未发现明显风险", text: "#15803d", bg: "#dcfce7", border: "#22c55e" },
  manual_review: { key: "manual_review", label: "需要人工复核", text: "#6d28d9", bg: "#ede9fe", border: "#8b5cf6" },
};

export function riskMeta(level: string): RiskMeta {
  return RISK_META[level] || RISK_META.low;
}

export function statusOf(result: ComplianceResult): RiskMeta {
  if (result.manual_review_required) return RISK_META.manual_review;
  return riskMeta(result.overall_risk_level);
}

export const REVIEW_RECOMMENDATION_LABEL: Record<string, string> = {
  block: "暂停发布",
  manual_review: "人工复核后发布",
  request_evidence: "补充材料后发布",
  warning: "修改后发布",
  pass: "可发布",
};

export const SYSTEM_ACTION_LABELS: Record<string, string> = {
  block: "禁止发布",
  mandatory_human_review: "需人工复核",
  request_qualification: "需补充资质",
  request_evidence: "需补充证明",
  warning: "警示",
  pass: "通过",
};

export function actionLabels(actions: string[]): string[] {
  return (actions || []).map((a) => SYSTEM_ACTION_LABELS[a] || a);
}
