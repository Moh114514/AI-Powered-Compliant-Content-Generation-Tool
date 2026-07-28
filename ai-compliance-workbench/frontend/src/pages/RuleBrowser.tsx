import React, { useEffect, useMemo, useState } from "react";
import { Copy, ExternalLink, RefreshCw, X } from "lucide-react";
import { api } from "../api/client";
import { RiskBadge } from "../components/RiskBadge";
import type { RuleDetail, RuleSummary } from "../types";
import { copyText } from "../utils/misc";
import { riskMeta } from "../utils/risk";

const EMPTY_FILTERS = { category: "", risk_level: "", platform: "", status: "", keyword: "" };
const RULE_FILTER_KEY = "workbench:rule-filters:v1";
type RuleFilters = typeof EMPTY_FILTERS;

function loadFilters(): RuleFilters {
  try {
    return { ...EMPTY_FILTERS, ...JSON.parse(sessionStorage.getItem(RULE_FILTER_KEY) || "{}") };
  } catch {
    return { ...EMPTY_FILTERS };
  }
}

export default function RuleBrowser() {
  const [platforms, setPlatforms] = useState<string[]>([]);
  const [catalog, setCatalog] = useState<RuleSummary[]>([]);
  const [filters, setFilters] = useState(loadFilters);
  const [debouncedKeyword, setDebouncedKeyword] = useState("");
  const [rows, setRows] = useState<RuleSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [detail, setDetail] = useState<RuleDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedKeyword(filters.keyword), 250);
    return () => window.clearTimeout(timer);
  }, [filters.keyword]);

  useEffect(() => {
    sessionStorage.setItem(RULE_FILTER_KEY, JSON.stringify(filters));
  }, [filters]);

  useEffect(() => {
    async function initialize() {
      const [platformResponse, rulesResponse] = await Promise.all([api.platforms(), api.rules({ limit: 500 })]);
      if (platformResponse.success) setPlatforms(platformResponse.data);
      if (rulesResponse.success) setCatalog(rulesResponse.data.rules);
      const failure = [platformResponse, rulesResponse].find((response) => !response.success);
      if (failure && !failure.success) setError(failure.message);
    }
    void initialize();
  }, []);

  useEffect(() => {
    let active = true;
    async function query() {
      setLoading(true);
      setError(null);
      const response = await api.rules({ ...filters, keyword: debouncedKeyword, limit: 500 });
      if (!active) return;
      setLoading(false);
      if (response.success) {
        setRows(response.data.rules);
        setTotal(response.data.total);
      } else setError(response.message);
    }
    void query();
    return () => { active = false; };
  }, [filters.category, filters.risk_level, filters.platform, filters.status, debouncedKeyword]);

  const categories = useMemo(() => [...new Set(catalog.map((item) => item.category_name).filter(Boolean) as string[])].sort(), [catalog]);
  const riskLevels = useMemo(() => [...new Set(catalog.map((item) => item.risk_level).filter(Boolean))], [catalog]);
  const statuses = useMemo(() => [...new Set(catalog.map((item) => item.effective_status).filter(Boolean) as string[])].sort(), [catalog]);

  async function reload() {
    setLoading(true);
    const response = await api.reloadRules();
    if (!response.success) {
      setError(response.message);
      setLoading(false);
      return;
    }
    const rulesResponse = await api.rules({ ...filters, keyword: debouncedKeyword, limit: 500 });
    setLoading(false);
    if (rulesResponse.success) {
      setRows(rulesResponse.data.rules);
      setTotal(rulesResponse.data.total);
      setCatalog(rulesResponse.data.rules);
    } else setError(rulesResponse.message);
  }

  async function openDetail(ruleId: string) {
    setError(null);
    const response = await api.ruleDetail(ruleId);
    if (response.success) setDetail(response.data);
    else setError(response.message);
  }

  return <div>
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, marginBottom: 12 }}>
      <div><h2 style={{ margin: "0 0 4px", fontSize: 18 }}>规则查询</h2><p style={{ margin: 0, color: "#6b7280", fontSize: 13 }}>只读浏览核心规则、表达变体、适用平台、示例和正式来源。</p></div>
      <button className="btn" onClick={reload} disabled={loading}><RefreshCw size={16} /> {loading ? "加载中…" : "重新加载规则库"}</button>
    </div>
    {error && <div className="card" style={{ marginBottom: 12, color: "#b91c1c", borderColor: "#fecaca", background: "#fef2f2" }}>⚠️ {error}</div>}

    <div className="card" style={{ marginBottom: 12 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 10 }}>
        <input className="input" placeholder="搜索 ID、名称、说明或变体" value={filters.keyword} onChange={(event) => setFilters((current) => ({ ...current, keyword: event.target.value }))} />
        <select className="select" value={filters.category} onChange={(event) => setFilters((current) => ({ ...current, category: event.target.value }))}><option value="">全部分类</option>{categories.map((item) => <option key={item}>{item}</option>)}</select>
        <select className="select" value={filters.risk_level} onChange={(event) => setFilters((current) => ({ ...current, risk_level: event.target.value }))}><option value="">全部风险</option>{riskLevels.map((item) => <option key={item} value={item}>{riskMeta(item).label}</option>)}</select>
        <select className="select" value={filters.platform} onChange={(event) => setFilters((current) => ({ ...current, platform: event.target.value }))}><option value="">全部平台</option>{platforms.map((item) => <option key={item}>{item}</option>)}</select>
        <select className="select" value={filters.status} onChange={(event) => setFilters((current) => ({ ...current, status: event.target.value }))}><option value="">全部状态</option>{statuses.map((item) => <option key={item}>{item}</option>)}</select>
        <button className="btn" onClick={() => setFilters({ ...EMPTY_FILTERS })}><X size={16} /> 重置</button>
      </div>
      <div style={{ fontSize: 12, color: "#9ca3af", marginTop: 8 }}>共 {total} 条规则{loading ? " · 查询中…" : ""}</div>
    </div>

    <div style={{ display: "grid", gap: 8 }}>
      {rows.map((rule) => <button key={rule.rule_id} className="card" style={{ padding: 10, display: "flex", alignItems: "center", gap: 10, cursor: "pointer", textAlign: "left", width: "100%" }} onClick={() => openDetail(rule.rule_id)}>
        <RiskBadge meta={riskMeta(rule.risk_level)} />
        <div style={{ flex: 1, minWidth: 0 }}><div style={{ fontSize: 14, fontWeight: 500 }}>{rule.rule_name}</div><div style={{ fontSize: 12, color: "#6b7280" }}>{rule.rule_id} · {rule.category_name || "—"} · {rule.variant_count ?? 0} 个变体 · {rule.source_count ?? 0} 个来源</div></div>
        <span style={{ fontSize: 12, color: "#9ca3af" }}>{rule.effective_status || "active"} ›</span>
      </button>)}
      {!loading && rows.length === 0 && <div className="card" style={{ color: "#9ca3af", textAlign: "center", padding: 30 }}>没有匹配规则</div>}
    </div>

    {detail && <DetailModal detail={detail} onClose={() => setDetail(null)} />}
  </div>;
}

function DetailModal({ detail, onClose }: { detail: RuleDetail; onClose: () => void }) {
  const rule = detail.rule;
  return <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.35)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50, padding: 16 }} onClick={onClose}>
    <div style={{ background: "#fff", borderRadius: 12, maxWidth: 800, width: "100%", maxHeight: "90vh", overflow: "auto", padding: 20 }} onClick={(event) => event.stopPropagation()}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, marginBottom: 12 }}>
        <div><h3 style={{ margin: 0, fontSize: 16 }}>{rule.rule_name}</h3><div style={{ fontSize: 12, color: "#6b7280" }}>{rule.rule_id} · {rule.category_name} · {rule.effective_status || "active"}</div></div>
        <div style={{ display: "flex", gap: 6 }}><button className="btn" onClick={async () => alert((await copyText(rule.rule_id)) ? "已复制规则 ID" : "复制失败")}><Copy size={14} /> 复制 ID</button><button className="btn" onClick={onClose}><X size={16} /> 关闭</button></div>
      </div>
      <div style={{ display: "grid", gap: 8, fontSize: 13, color: "#374151" }}>
        <Row label="规则说明" value={rule.rule_description || "—"} />
        <Row label="风险等级" value={<RiskBadge meta={riskMeta(rule.risk_level)} />} />
        <Row label="复核等级" value={rule.review_level || "—"} />
        <Row label="法律结论" value={rule.legal_conclusion || "—"} />
        <Row label="系统动作" value={(Array.isArray(rule.system_action) ? rule.system_action : [rule.system_action]).filter(Boolean).join("、") || "—"} />
        <Row label="禁止场景" value={rule.prohibited_context || "—"} />
        <Row label="允许场景" value={rule.allowed_context || "—"} />
        <Row label="证明材料" value={rule.evidence_requirement || rule.qualification_requirement || "—"} />
        <Row label="修改策略" value={rule.replacement_strategy || "—"} />
        <Row label="版本信息" value={`v${rule.version || "?"} · 更新于 ${rule.updated_at || "—"}`} />

        <Group title={`表达变体（${detail.variants.length}）`}><div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>{detail.variants.map((variant) => <span key={variant.variant_id} style={{ fontSize: 12, background: "#f3f4f6", borderRadius: 6, padding: "2px 8px" }}>{variant.variant_text || variant.regex_pattern} <span style={{ color: "#9ca3af" }}>({variant.matching_method})</span></span>)}</div></Group>
        <Group title="适用平台"><div style={{ fontSize: 12 }}>{detail.platforms.length ? detail.platforms.map((item) => `${item.platform}/${item.platform_product_line || item.content_type || "全部"}`).join("、") : "通用（无平台限制）"}</div></Group>
        <Group title={`规则示例（${detail.examples?.length ?? 0}）`}><div style={{ display: "grid", gap: 6 }}>{detail.examples?.slice(0, 10).map((example) => <div key={example.example_id} style={{ padding: 8, borderRadius: 6, background: example.example_type === "compliant" ? "#f0fdf4" : "#fef2f2" }}><b>{example.example_type}</b>：{example.original_text}</div>) || "—"}</div></Group>
        <Group title="来源依据"><div style={{ display: "grid", gap: 6 }}>{detail.sources?.length ? detail.sources.map((source) => <div key={source.source_id} style={{ border: "1px solid #f1f5f9", borderRadius: 6, padding: 8 }}><b>{source.source_id} {source.source_name}</b><div style={{ color: "#6b7280", marginTop: 2 }}>{source.issuing_authority || ""} · {source.verification_status || "未标记核验状态"}</div>{source.official_url && <a href={source.official_url} target="_blank" rel="noreferrer" style={{ display: "inline-flex", gap: 4, alignItems: "center", marginTop: 4 }}><ExternalLink size={12} /> 官方页面</a>}</div>) : detail.source_names.join("、") || "—"}</div></Group>
      </div>
      <div style={{ fontSize: 12, color: "#9ca3af", marginTop: 12, borderTop: "1px dashed #e5e7eb", paddingTop: 8 }}>规则页面只读；正式维护应修改权威 JSON 并执行校验与回归测试。</div>
    </div>
  </div>;
}

function Row({ label, value }: { label: string; value: React.ReactNode }) { return <div style={{ display: "flex", gap: 8 }}><div style={{ width: 76, flexShrink: 0, color: "#9ca3af" }}>{label}</div><div style={{ flex: 1 }}>{value}</div></div>; }
function Group({ title, children }: { title: string; children: React.ReactNode }) { return <div><div style={{ color: "#9ca3af", marginBottom: 4 }}>{title}</div>{children}</div>; }
