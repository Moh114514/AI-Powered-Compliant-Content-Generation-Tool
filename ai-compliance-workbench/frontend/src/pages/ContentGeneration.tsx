import React, { useEffect, useMemo, useState } from "react";
import { Sparkles, Trash2, FileText, Save, Copy, Wand2, ChevronDown, RefreshCw } from "lucide-react";
import { api } from "../api/client";
import type { Brand, GenerateResult, VersionResult, Settings } from "../types";
import { RiskBadge } from "../components/RiskBadge";
import { ComplianceReport } from "../components/ComplianceReport";
import { statusOf } from "../utils/risk";
import { copyText, downloadText } from "../utils/misc";

const DEMO = {
  brand: "guangnian18",
  platform: "小红书",
  content_type: "项目介绍",
  topic: "夏季光电抗衰体验周",
  selling_points: "全城效果最好，零风险，7天年轻十岁，限时免费体验",
  target_audience: "25-40岁关注抗初老的都市女性",
  campaign_info: "7月限时，前100名免费体验",
  tone: "亲切专业",
  length: "中",
  extra_requirements: "",
  use_brand_profile: true,
  versions: 3,
};

export default function ContentGeneration() {
  const [brands, setBrands] = useState<Brand[]>([]);
  const [platforms, setPlatforms] = useState<string[]>([]);
  const [contentTypes, setContentTypes] = useState<Record<string, string[]>>({});
  const [settings, setSettings] = useState<Settings>({});

  const [form, setForm] = useState({ ...DEMO });
  const [result, setResult] = useState<GenerateResult | null>(null);
  const [openVersions, setOpenVersions] = useState<Record<number, boolean>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rewriteModal, setRewriteModal] = useState<{ text: string; rev: any } | null>(null);

  useEffect(() => {
    api.brands().then((r) => r.success && setBrands(r.data));
    api.platforms().then((r) => r.success && setPlatforms(r.data));
    api.contentTypes().then((r) => r.success && setContentTypes(r.data));
    // 从「最近记录-继续修改」带入输入
    const cont = sessionStorage.getItem("continue_input");
    if (cont) {
      try {
        const parsed = JSON.parse(cont);
        setForm((f) => ({ ...f, ...parsed }));
      } catch { /* ignore */ }
      sessionStorage.removeItem("continue_input");
    }
    api.settings().then((r) => {
      if (r.success) {
        setSettings(r.data);
        setForm((f) => ({
          ...f,
          brand: r.data.default_brand || f.brand,
          platform: r.data.default_platform || f.platform,
          versions: r.data.default_versions || f.versions,
          tone: r.data.default_tone || f.tone,
          length: r.data.default_length || f.length,
        }));
      }
    });
  }, []);

  const ctOptions = useMemo(() => contentTypes[form.platform] || [], [contentTypes, form.platform]);

  function set<K extends keyof typeof form>(k: K, v: any) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  async function onGenerate() {
    setLoading(true);
    setError(null);
    const r = await api.generate(form);
    setLoading(false);
    if (!r.success) {
      setError(r.message || "生成失败");
      return;
    }
    setResult(r.data);
    setOpenVersions({});
  }

  function onClear() {
    setForm({ ...DEMO, brand: form.brand, platform: form.platform });
    setResult(null);
    setError(null);
  }

  function onLoadDemo() {
    setForm({ ...DEMO });
  }

  async function onSaveHistory() {
    if (!result) return;
    const r = await api.addHistory({
      operation_type: "generation",
      brand: form.brand,
      platform: form.platform,
      input: form,
      generated: result,
      detection: null,
      risk_level: result.versions[0]?.overall_risk_level || "",
    });
    alert(r.success ? "已保存到最近记录" : r.message || "保存失败");
  }

  async function updateVersion(idx: number, patch: Partial<VersionResult>) {
    setResult((res) => {
      if (!res) return res;
      const versions = res.versions.map((v, i) => (i === idx ? { ...v, ...patch } : v));
      return { ...res, versions };
    });
  }

  async function doAdjust(idx: number, adjust_type: string) {
    const v = result?.versions[idx];
    if (!v) return;
    setLoading(true);
    const r = await api.adjust({ text: v.text, platform: v.platform, content_type: v.content_type, brand: form.brand, adjust_type });
    setLoading(false);
    if (r.success) {
      updateVersion(idx, { text: r.data.text, compliance: r.data.compliance, overall_risk_level: r.data.compliance.overall_risk_level, matched_count: r.data.compliance.matched_rules.length, manual_review_required: r.data.compliance.manual_review_required });
    } else {
      alert(r.message || "操作失败");
    }
  }

  async function doRewrite(idx: number) {
    const v = result?.versions[idx];
    if (!v) return;
    setLoading(true);
    const r = await api.rewrite({ text: v.text, platform: v.platform, content_type: v.content_type, brand: form.brand });
    setLoading(false);
    if (r.success) {
      setRewriteModal({ text: v.text, rev: r.data });
    } else {
      alert(r.message || "改写失败");
    }
  }

  async function downloadReport(v: VersionResult) {
    const r = await api.report(v.compliance, "md");
    if (r.success) downloadText(`检测报告_${v.platform}_v${v.version_index}.md`, r.data.content, "text/markdown");
  }

  return (
    <div>
      <h2 style={{ margin: "0 0 4px", fontSize: 18 }}>内容生成</h2>
      <p style={{ margin: "0 0 16px", color: "#6b7280", fontSize: 13 }}>
        选择品牌、平台与内容类型，生成宣传文案并自动完成合规风险检测。
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(320px, 420px) 1fr", gap: 16, alignItems: "start" }} className="gen-grid">
        {/* 左：输入 */}
        <div className="card">
          <div style={{ display: "grid", gap: 10 }}>
            <Field label="品牌">
              <select className="select" value={form.brand} onChange={(e) => set("brand", e.target.value)}>
                {brands.map((b) => (
                  <option key={b.brand_id} value={b.brand_id}>{b.brand_name}{b.is_demo ? "（演示）" : ""}</option>
                ))}
              </select>
            </Field>
            <Field label="发布平台">
              <select className="select" value={form.platform} onChange={(e) => set("platform", e.target.value)}>
                {platforms.map((p) => (<option key={p} value={p}>{p}</option>))}
              </select>
            </Field>
            <Field label="内容类型">
              <select className="select" value={form.content_type} onChange={(e) => set("content_type", e.target.value)}>
                {ctOptions.map((c) => (<option key={c} value={c}>{c}</option>))}
              </select>
            </Field>
            <Field label="主题" hint="例如：夏季光电抗衰体验周">
              <input className="input" value={form.topic} onChange={(e) => set("topic", e.target.value)} placeholder="夏季光电抗衰体验周" />
            </Field>
            <Field label="核心卖点" hint="多个卖点可用逗号分隔">
              <textarea className="textarea" value={form.selling_points} onChange={(e) => set("selling_points", e.target.value)} placeholder="全城效果最好，零风险，7天年轻十岁" />
            </Field>
            <Field label="目标人群">
              <input className="input" value={form.target_audience} onChange={(e) => set("target_audience", e.target.value)} />
            </Field>
            <Field label="活动信息">
              <input className="input" value={form.campaign_info} onChange={(e) => set("campaign_info", e.target.value)} />
            </Field>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <Field label="语气风格">
                <input className="input" value={form.tone} onChange={(e) => set("tone", e.target.value)} />
              </Field>
              <Field label="内容长度">
                <select className="select" value={form.length} onChange={(e) => set("length", e.target.value)}>
                  {["短", "中", "长"].map((l) => (<option key={l} value={l}>{l}</option>))}
                </select>
              </Field>
            </div>
            <Field label="补充要求">
              <input className="input" value={form.extra_requirements} onChange={(e) => set("extra_requirements", e.target.value)} />
            </Field>
            <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
              <input type="checkbox" checked={form.use_brand_profile} onChange={(e) => set("use_brand_profile", e.target.checked)} />
              使用品牌资料（偏好用词/禁用词）
            </label>
            <Field label="生成版本数量">
              <select className="select" value={form.versions} onChange={(e) => set("versions", Number(e.target.value))}>
                {[1, 2, 3, 4, 5].map((n) => (<option key={n} value={n}>{n} 个</option>))}
              </select>
            </Field>

            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 4 }}>
              <button className="btn btn-primary" onClick={onGenerate} disabled={loading}>
                <Sparkles size={16} /> {loading ? "生成中…" : "生成并检测"}
              </button>
              <button className="btn" onClick={onLoadDemo}><FileText size={16} /> 加载示例</button>
              <button className="btn" onClick={onClear}><Trash2 size={16} /> 清空</button>
              <button className="btn" onClick={onSaveHistory} disabled={!result}><Save size={16} /> 保存到最近记录</button>
            </div>
            {error && <div style={{ color: "#dc2626", fontSize: 13 }}>⚠️ {error}</div>}
          </div>
        </div>

        {/* 右：结果 */}
        <div>
          {!result && (
            <div className="card" style={{ color: "#9ca3af", textAlign: "center", padding: 40, fontSize: 14 }}>
              左侧填写后点击「生成并检测」，结果将显示在此处。
            </div>
          )}
          {result && (
            <div style={{ display: "grid", gap: 14 }}>
              {result.demo_mode && (
                <div style={{ background: "#fffbeb", border: "1px solid #fde68a", color: "#92400e", borderRadius: 8, padding: "6px 10px", fontSize: 12 }}>
                  当前为演示模式（未配置大模型 API），生成内容为演示文案，关键词与正则检测正常生效。
                </div>
              )}
              {result.versions.map((v, idx) => {
                const meta = statusOf(v.compliance);
                const open = openVersions[v.version_index];
                return (
                  <div key={v.version_index} className="card">
                    <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8, marginBottom: 8 }}>
                      <b style={{ fontSize: 14 }}>版本 {v.version_index}</b>
                      <RiskBadge meta={meta} />
                      <span style={{ fontSize: 12, color: "#6b7280" }}>
                        {v.platform} · {v.content_type} · {v.char_count} 字 · {v.model} · 命中 {v.matched_count}
                      </span>
                    </div>
                    <div style={{ fontSize: 14, whiteSpace: "pre-wrap", lineHeight: 1.7, background: "#f9fafb", border: "1px solid #f1f5f9", borderRadius: 8, padding: 10 }}>
                      {v.text}
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
                      <button className="btn" style={{ padding: "4px 8px", fontSize: 12 }} onClick={async () => alert((await copyText(v.text)) ? "已复制文案" : "复制失败")}><Copy size={14} /> 复制文案</button>
                      <button className="btn" style={{ padding: "4px 8px", fontSize: 12 }} onClick={() => doAdjust(idx, "缩短")} disabled={loading}>缩短</button>
                      <button className="btn" style={{ padding: "4px 8px", fontSize: 12 }} onClick={() => doAdjust(idx, "扩写")} disabled={loading}>扩写</button>
                      <button className="btn" style={{ padding: "4px 8px", fontSize: 12 }} onClick={() => doAdjust(idx, "调整语气")} disabled={loading}>调整语气</button>
                      <button className="btn" style={{ padding: "4px 8px", fontSize: 12 }} onClick={() => doRewrite(idx)} disabled={loading}><Wand2 size={14} /> 一键合规改写</button>
                      <button className="btn" style={{ padding: "4px 8px", fontSize: 12 }} onClick={() => setOpenVersions((o) => ({ ...o, [v.version_index]: !o[v.version_index] }))}>
                        <ChevronDown size={14} /> {open ? "收起风险" : "查看风险"}
                      </button>
                      <button className="btn" style={{ padding: "4px 8px", fontSize: 12 }} onClick={async () => { const ok = await copyText(v.compliance.review_summary); alert(ok ? "已复制复核摘要" : "复制失败"); }}><Copy size={14} /> 复制复核摘要</button>
                      <button className="btn" style={{ padding: "4px 8px", fontSize: 12 }} onClick={() => downloadReport(v)}><FileText size={14} /> 下载检测报告</button>
                    </div>
                    {open && (
                      <div style={{ marginTop: 10 }}>
                        <ComplianceReport result={v.compliance} />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {rewriteModal && (
        <RewriteModal
          text={rewriteModal.text}
          rev={rewriteModal.rev}
          onClose={() => setRewriteModal(null)}
        />
      )}
    </div>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 4 }}>{label}{hint && <span style={{ color: "#9ca3af", fontWeight: 400, marginLeft: 6 }}>{hint}</span>}</div>
      {children}
    </div>
  );
}

function RewriteModal({ text, rev, onClose }: { text: string; rev: any; onClose: () => void }) {
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.35)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50, padding: 16 }}>
      <div style={{ background: "#fff", borderRadius: 12, maxWidth: 640, width: "100%", maxHeight: "85vh", overflow: "auto", padding: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <h3 style={{ margin: 0, fontSize: 16 }}>一键合规改写</h3>
          <button className="btn" onClick={onClose}>关闭</button>
        </div>
        <div style={{ fontSize: 13, color: "#6b7280", marginBottom: 6 }}>原文</div>
        <div style={{ fontSize: 14, whiteSpace: "pre-wrap", background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 8, padding: 10, marginBottom: 12 }}>{text}</div>
        <div style={{ fontSize: 13, color: "#6b7280", marginBottom: 6 }}>建议修改稿</div>
        <div style={{ fontSize: 14, whiteSpace: "pre-wrap", background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 8, padding: 10, marginBottom: 12 }}>{rev.suggested_revision || "（无可自动生成的改写稿，需人工复核）"}</div>
        {rev.unresolved_items && rev.unresolved_items.length > 0 && (
          <div style={{ fontSize: 13, color: "#6d28d9", marginBottom: 12 }}>
            需人工复核：{rev.unresolved_items.join("；")}
          </div>
        )}
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn btn-primary" onClick={async () => alert((await copyText(rev.suggested_revision || "")) ? "已复制" : "复制失败")}><Copy size={14} /> 复制修改稿</button>
          <button className="btn" onClick={() => downloadText("合规改写稿.txt", rev.suggested_revision || "", "text/plain")}>下载 TXT</button>
        </div>
      </div>
    </div>
  );
}
