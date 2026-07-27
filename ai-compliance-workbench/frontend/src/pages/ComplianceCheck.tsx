import React, { useEffect, useState } from "react";
import { ShieldCheck, FileText, Trash2, Sparkles } from "lucide-react";
import { api } from "../api/client";
import type { Brand, ComplianceResult } from "../types";
import { ComplianceReport } from "../components/ComplianceReport";

const DEMO_RISKY = {
  text: "夏季光电抗衰体验周来啦！我们全城效果最好，零风险，7天让你年轻十岁，限时免费体验，名额有限速来！",
  platform: "小红书",
  content_type: "项目介绍",
  brand: "guangnian18",
  publisher_identity: "医美机构",
  business_domain: "医疗美容",
  is_paid_ad: true,
  context_note: "",
};
const DEMO_COMPLIANT = {
  text: "夏季光电抗衰体验周开启。本文介绍项目流程、适用人群与注意事项，并说明需到店由专业医师评估个人情况，不承诺统一效果及恢复时间。",
  platform: "小红书",
  content_type: "项目介绍",
  brand: "guangnian18",
  publisher_identity: "医美机构",
  business_domain: "医疗美容",
  is_paid_ad: false,
  context_note: "",
};

export default function ComplianceCheck() {
  const [brands, setBrands] = useState<Brand[]>([]);
  const [platforms, setPlatforms] = useState<string[]>([]);
  const [contentTypes, setContentTypes] = useState<Record<string, string[]>>({});

  const [form, setForm] = useState({ ...DEMO_RISKY });
  const [result, setResult] = useState<ComplianceResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.brands().then((r) => r.success && setBrands(r.data));
    api.platforms().then((r) => r.success && setPlatforms(r.data));
    api.contentTypes().then((r) => r.success && setContentTypes(r.data));
  }, []);

  const ctOptions = contentTypes[form.platform] || [];

  function set<K extends keyof typeof form>(k: K, v: any) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  async function onCheck() {
    if (!form.text.trim()) {
      setError("请先粘贴待检测文本");
      return;
    }
    setLoading(true);
    setError(null);
    const r = await api.check(form);
    setLoading(false);
    if (!r.success) {
      setError(r.message || "检测失败");
      return;
    }
    setResult(r.data);
  }

  return (
    <div>
      <h2 style={{ margin: "0 0 4px", fontSize: 18 }}>合规检测</h2>
      <p style={{ margin: "0 0 16px", color: "#6b7280", fontSize: 13 }}>
        粘贴文案并选择场景，自动检测关键词、正则与语义风险，给出高亮与修改建议。
      </p>

      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          <div style={{ gridColumn: "1 / -1" }}>
            <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 4 }}>待检测文本</div>
            <textarea className="textarea" style={{ minHeight: 120 }} value={form.text} onChange={(e) => set("text", e.target.value)} placeholder="粘贴需要检测的医美宣传文案…" />
          </div>
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
          <Field label="品牌">
            <select className="select" value={form.brand} onChange={(e) => set("brand", e.target.value)}>
              {brands.map((b) => (<option key={b.brand_id} value={b.brand_id}>{b.brand_name}{b.is_demo ? "（演示）" : ""}</option>))}
            </select>
          </Field>
          <Field label="发布主体类型">
            <select className="select" value={form.publisher_identity} onChange={(e) => set("publisher_identity", e.target.value)}>
              {["医美机构", "品牌方", "个人/KOL", "其他"].map((o) => (<option key={o} value={o}>{o}</option>))}
            </select>
          </Field>
          <Field label="业务领域">
            <input className="input" value={form.business_domain} onChange={(e) => set("business_domain", e.target.value)} placeholder="医疗美容" />
          </Field>
          <Field label="是否付费广告">
            <select className="select" value={String(form.is_paid_ad)} onChange={(e) => set("is_paid_ad", e.target.value === "true")}>
              <option value="false">否</option>
              <option value="true">是</option>
            </select>
          </Field>
          <div style={{ gridColumn: "1 / -1" }}>
            <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 4 }}>可选上下文说明</div>
            <input className="input" value={form.context_note} onChange={(e) => set("context_note", e.target.value)} placeholder="例如：本内容为品牌科普，非医疗建议" />
          </div>
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
          <button className="btn btn-primary" onClick={onCheck} disabled={loading}><ShieldCheck size={16} /> {loading ? "检测中…" : "开始检测"}</button>
          <button className="btn" onClick={() => setForm({ ...DEMO_RISKY })}><FileText size={16} /> 加载风险示例</button>
          <button className="btn" onClick={() => setForm({ ...DEMO_COMPLIANT })}><FileText size={16} /> 加载合规示例</button>
          <button className="btn" onClick={() => { setForm({ ...DEMO_RISKY, text: "" }); setResult(null); setError(null); }}><Trash2 size={16} /> 清空</button>
        </div>
        {error && <div style={{ color: "#dc2626", fontSize: 13, marginTop: 8 }}>⚠️ {error}</div>}
        <div style={{ fontSize: 12, color: "#9ca3af", marginTop: 8 }}>
          检测结果将自动保存到「最近记录」（如已在工具设置中开启）。
        </div>
      </div>

      {result && <ComplianceReport result={result} />}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 4 }}>{label}</div>
      {children}
    </div>
  );
}
