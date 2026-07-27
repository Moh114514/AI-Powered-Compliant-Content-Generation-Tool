import React, { useEffect, useMemo, useState } from "react";
import { BookOpen, Copy, RefreshCw, Search, X } from "lucide-react";
import { api } from "../api/client";
import type { RuleSummary, RuleDetail } from "../types";
import { RiskBadge } from "../components/RiskBadge";
import { riskMeta } from "../utils/risk";
import { copyText } from "../utils/misc";

export default function RuleBrowser() {
  const [categories, setCategories] = useState<string[]>([]);
  const [riskLevels, setRiskLevels] = useState<string[]>([]);
  const [statuses, setStatuses] = useState<string[]>([]);
  const [platforms, setPlatforms] = useState<string[]>([]);

  const [filters, setFilters] = useState({ category: "", risk_level: "", platform: "", status: "", keyword: "" });
  const [rows, setRows] = useState<RuleSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [detail, setDetail] = useState<RuleDetail | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.platforms().then((r) => r.success && setPlatforms(r.data));
    api.rules({}).then((r) => {
      if (r.success) {
        const all = r.data.rules;
        setCategories([...new Set(all.map((x) => x.category_name).filter(Boolean))]);
        setRiskLevels([...new Set(all.map((x) => x.risk_level).filter(Boolean))]);
        setStatuses([...new Set(all.map((x) => x.effective_status).filter(Boolean))]);
      }
    });
  }, []);

  useEffect(() => {
    setLoading(true);
    api.rules(filters).then((r) => {
      setLoading(false);
      if (r.success) {
        setRows(r.data.rules);
        setTotal(r.data.total);
      }
    });
  }, [filters]);

  function reset() {
    setFilters({ category: "", risk_level: "", platform: "", status: "", keyword: "" });
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <div>
          <h2 style={{ margin: "0 0 4px", fontSize: 18 }}>规则查询</h2>
          <p style={{ margin: 0, color: "#6b7280", fontSize: 13 }}>只读浏览现有合规规则库，可搜索、筛选与查看来源。</p>
        </div>
        <button className="btn" onClick={async () => { await api.reloadRules(); setFilters((f) => ({ ...f })); alert("规则库已重新加载"); }}><RefreshCw size={16} /> 重新加载规则库</button>
      </div>

      <div className="card" style={{ marginBottom: 12 }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 10 }}>
          <input className="input" placeholder="搜索 rule_id / 名称 / 说明" value={filters.keyword} onChange={(e) => setFilters((f) => ({ ...f, keyword: e.target.value }))} />
          <select className="select" value={filters.category} onChange={(e) => setFilters((f) => ({ ...f, category: e.target.value }))}>
            <option value="">全部分类</option>
            {categories.map((c) => (<option key={c} value={c}>{c}</option>))}
          </select>
          <select className="select" value={filters.risk_level} onChange={(e) => setFilters((f) => ({ ...f, risk_level: e.target.value }))}>
            <option value="">全部风险</option>
            {riskLevels.map((c) => (<option key={c} value={c}>{riskMeta(c).label}</option>))}
          </select>
          <select className="select" value={filters.platform} onChange={(e) => setFilters((f) => ({ ...f, platform: e.target.value }))}>
            <option value="">全部平台</option>
            {platforms.map((c) => (<option key={c} value={c}>{c}</option>))}
          </select>
          <select className="select" value={filters.status} onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))}>
            <option value="">全部状态</option>
            {statuses.map((c) => (<option key={c} value={c}>{c}</option>))}
          </select>
          <button className="btn" onClick={reset}><X size={16} /> 重置</button>
        </div>
        <div style={{ fontSize: 12, color: "#9ca3af", marginTop: 8 }}>共 {total} 条规则{loading ? " · 查询中…" : ""}</div>
      </div>

      <div style={{ display: "grid", gap: 8 }}>
        {rows.map((r) => (
          <div key={r.rule_id} className="card" style={{ padding: 10, display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }} onClick={() => api.ruleDetail(r.rule_id).then((res) => res.success && setDetail(res.data))}>
            <RiskBadge meta={riskMeta(r.risk_level)} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 14, fontWeight: 500 }}>{r.rule_name}</div>
              <div style={{ fontSize: 12, color: "#6b7280" }}>{r.rule_id} · {r.category_name || "—"}</div>
            </div>
            <span style={{ fontSize: 12, color: "#9ca3af" }}>查看 ›</span>
          </div>
        ))}
        {!loading && rows.length === 0 && <div className="card" style={{ color: "#9ca3af", textAlign: "center", padding: 30 }}>无匹配规则</div>}
      </div>

      {detail && <DetailModal detail={detail} onClose={() => setDetail(null)} />}
    </div>
  );
}

function DetailModal({ detail, onClose }: { detail: RuleDetail; onClose: () => void }) {
  const r = detail.rule;
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.35)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50, padding: 16 }} onClick={onClose}>
      <div style={{ background: "#fff", borderRadius: 12, maxWidth: 720, width: "100%", maxHeight: "88vh", overflow: "auto", padding: 20 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <div>
            <h3 style={{ margin: 0, fontSize: 16 }}>{r.rule_name}</h3>
            <div style={{ fontSize: 12, color: "#6b7280" }}>{r.rule_id} · {r.category_name}</div>
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            <button className="btn" style={{ padding: "4px 8px", fontSize: 12 }} onClick={async () => alert((await copyText(r.rule_id)) ? "已复制规则 ID" : "复制失败")}><Copy size={14} /> 复制 ID</button>
            <button className="btn" onClick={onClose}><X size={16} /> 关闭</button>
          </div>
        </div>
        <div style={{ display: "grid", gap: 8, fontSize: 13, color: "#374151" }}>
          <Row label="规则说明" value={r.rule_description || "—"} />
          <Row label="风险等级" value={<RiskBadge meta={riskMeta(r.risk_level)} />} />
          <Row label="法律结论" value={r.legal_conclusion || "—"} />
          <Row label="系统动作" value={(Array.isArray(r.system_action) ? r.system_action : [r.system_action]).join("、") || "—"} />
          <Row label="当前状态" value={r.effective_status || "—"} />
          <Row label="禁止场景" value={r.prohibited_context || "—"} />
          <Row label="允许场景" value={r.allowed_context || "—"} />
          <Row label="证明材料" value={r.evidence_requirement || "—"} />
          <Row label="修改策略" value={r.replacement_strategy || "—"} />
          <Row label="版本信息" value={`v${r.version || "?"} · 更新于 ${r.updated_at || "—"}`} />
          <div>
            <div style={{ color: "#9ca3af", marginBottom: 4 }}>表达变体（{detail.variants.length}）</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {detail.variants.map((v) => (
                <span key={v.variant_id} style={{ fontSize: 12, background: "#f3f4f6", borderRadius: 6, padding: "2px 8px" }}>
                  {v.variant_text} <span style={{ color: "#9ca3af" }}>({v.matching_method})</span>
                </span>
              ))}
            </div>
          </div>
          <div>
            <div style={{ color: "#9ca3af", marginBottom: 4 }}>适用平台</div>
            <div style={{ fontSize: 12 }}>{detail.platforms.length ? detail.platforms.map((p) => `${p.platform}/${p.content_type || "全部"}`).join("、") : "通用（无平台限制）"}</div>
          </div>
          <div>
            <div style={{ color: "#9ca3af", marginBottom: 4 }}>来源依据</div>
            <div style={{ fontSize: 13 }}>{detail.source_names.length ? detail.source_names.join("、") : "—"}</div>
          </div>
        </div>
        <div style={{ fontSize: 12, color: "#9ca3af", marginTop: 12, borderTop: "1px dashed #e5e7eb", paddingTop: 8 }}>
          本工具不提供在线编辑规则；规则维护请通过原始规则库与构建流程完成。
        </div>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{ display: "flex", gap: 8 }}>
      <div style={{ width: 76, flexShrink: 0, color: "#9ca3af" }}>{label}</div>
      <div style={{ flex: 1 }}>{value}</div>
    </div>
  );
}
