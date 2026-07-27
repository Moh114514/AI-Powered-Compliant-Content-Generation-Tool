import React, { useState } from "react";
import type { MatchedRule } from "../types";
import { RiskBadge } from "./RiskBadge";
import { riskMeta, actionLabels } from "../utils/risk";

export function RuleCard({ rule, selected }: { rule: MatchedRule; selected?: boolean }) {
  const [open, setOpen] = useState(false);
  const meta = riskMeta(rule.risk_level);
  return (
    <div
      className="card"
      style={{
        borderColor: selected ? meta.border : "#e5e7eb",
        boxShadow: selected ? `0 0 0 2px ${meta.bg}` : "none",
        padding: 12,
      }}
    >
      <div
        style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}
        onClick={() => setOpen((v) => !v)}
      >
        <RiskBadge meta={meta} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 600, fontSize: 14 }}>{rule.rule_name}</div>
          <div style={{ fontSize: 12, color: "#6b7280" }}>
            {rule.rule_id} · 命中：“{rule.matched_text}”
          </div>
        </div>
        <span style={{ fontSize: 12, color: "#9ca3af" }}>{open ? "收起 ▲" : "展开 ▼"}</span>
      </div>

      {open && (
        <div style={{ marginTop: 10, fontSize: 13, color: "#374151", display: "grid", gap: 6 }}>
          <Row label="风险原因" value={rule.risk_reason || "—"} />
          <Row label="系统动作" value={actionLabels(rule.system_action).join("、") || "—"} />
          <Row label="法律结论" value={rule.legal_conclusion || "—"} />
          <Row label="禁止场景" value={rule.prohibited_context || "—"} />
          <Row label="允许场景" value={rule.allowed_context || "—"} />
          <Row label="证明材料" value={rule.evidence_requirement || "—"} />
          <Row
            label="修改策略"
            value={rule.replacement_strategy && rule.replacement_strategy.length ? rule.replacement_strategy.join("；") : "—"}
          />
          <Row label="来源依据" value={rule.source_names && rule.source_names.length ? rule.source_names.join("、") : "—"} />
          <Row
            label="自动改写"
            value={rule.auto_rewrite_allowed ? "允许" : "不允许（需人工复核）"}
          />
        </div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", gap: 8 }}>
      <div style={{ width: 76, flexShrink: 0, color: "#9ca3af" }}>{label}</div>
      <div style={{ flex: 1 }}>{value}</div>
    </div>
  );
}
