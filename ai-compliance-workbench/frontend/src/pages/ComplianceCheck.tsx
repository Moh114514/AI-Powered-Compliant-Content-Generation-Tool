import React, { useEffect, useMemo, useRef, useState } from "react";
import { FileText, ShieldCheck, Trash2 } from "lucide-react";
import { api } from "../api/client";
import { ComplianceReport } from "../components/ComplianceReport";
import type { Brand, ComplianceResult } from "../types";

const DEMO_RISKY = {
  text: "夏季光电抗衰体验周来啦！我们全城效果最好，零风险，7天让你年轻十岁，限时免费体验，名额有限速来！",
  platform: "小红书",
  content_type: "项目介绍",
  brand: "guangnian18",
  publisher_identity: "医美机构",
  business_domain: "医疗美容",
  content_legal_nature: "medical_advertisement",
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
  content_legal_nature: "service_information",
  is_paid_ad: false,
  context_note: "仅提供一般信息，发布前仍需核验素材与项目资质。",
};

const CHECK_DRAFT_KEY = "workbench:compliance-check-draft:v1";

function loadCheckDraft(): { form: typeof DEMO_RISKY; result: ComplianceResult | null } {
  try {
    const saved = JSON.parse(sessionStorage.getItem(CHECK_DRAFT_KEY) || "null");
    if (saved?.form) {
      return { form: { ...DEMO_RISKY, ...saved.form }, result: saved.result || null };
    }
  } catch {
    // Ignore corrupt browser state.
  }
  return { form: { ...DEMO_RISKY }, result: null };
}

export default function ComplianceCheck() {
  const initialDraft = useRef(loadCheckDraft()).current;
  const [brands, setBrands] = useState<Brand[]>([]);
  const [platforms, setPlatforms] = useState<string[]>([]);
  const [contentTypes, setContentTypes] = useState<Record<string, string[]>>({});
  const [form, setForm] = useState(initialDraft.form);
  const [result, setResult] = useState<ComplianceResult | null>(initialDraft.result);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    async function initialize() {
      const [brandResponse, platformResponse, typeResponse] = await Promise.all([api.brands(), api.platforms(), api.contentTypes()]);
      if (brandResponse.success) setBrands(brandResponse.data);
      if (platformResponse.success) setPlatforms(platformResponse.data);
      if (typeResponse.success) setContentTypes(typeResponse.data);
      const failure = [brandResponse, platformResponse, typeResponse].find((response) => !response.success);
      if (failure && !failure.success) setError(failure.message);
    }
    void initialize();
  }, []);

  useEffect(() => {
    try {
      sessionStorage.setItem(CHECK_DRAFT_KEY, JSON.stringify({ form, result }));
    } catch {
      // Keep the page usable if the report is larger than the storage quota.
    }
  }, [form, result]);

  const contentTypeOptions = useMemo(() => contentTypes[form.platform] || [], [contentTypes, form.platform]);

  useEffect(() => {
    if (contentTypeOptions.length && !contentTypeOptions.includes(form.content_type)) {
      setForm((current) => ({ ...current, content_type: contentTypeOptions[0] }));
    }
  }, [contentTypeOptions, form.content_type]);

  function setField<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function changePlatform(platform: string) {
    setForm((current) => ({ ...current, platform, content_type: contentTypes[platform]?.[0] || "" }));
    setResult(null);
  }

  async function onCheck() {
    if (!form.text.trim()) {
      setError("请先粘贴待检测文本");
      return;
    }
    setLoading(true);
    setError(null);
    setNotice(null);
    const response = await api.check(form);
    setLoading(false);
    if (!response.success) {
      setError(response.message || "检测失败");
      return;
    }
    setResult(response.data);
    if (response.data.history_error) setError(response.data.history_error);
    else if (response.data.history_saved) setNotice("本次检测已自动保存到最近记录。");
  }

  function loadExample(example: typeof DEMO_RISKY) {
    setForm({ ...example });
    setResult(null);
    setError(null);
    setNotice(null);
  }

  return <div>
    <h2 style={{ margin: "0 0 4px", fontSize: 18 }}>合规检测</h2>
    <p style={{ margin: "0 0 16px", color: "#6b7280", fontSize: 13 }}>粘贴文案并选择真实发布场景，系统会执行关键词、正则和语义风险检测。</p>
    {error && <div className="card" style={{ marginBottom: 12, color: "#b91c1c", borderColor: "#fecaca", background: "#fef2f2" }}>⚠️ {error}</div>}
    {notice && <div className="card" style={{ marginBottom: 12, color: "#166534", borderColor: "#bbf7d0", background: "#f0fdf4" }}>{notice}</div>}

    <div className="card" style={{ marginBottom: 16 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <div style={{ gridColumn: "1 / -1" }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, fontWeight: 500, marginBottom: 4 }}><span>待检测文本</span><span style={{ color: "#9ca3af", fontWeight: 400 }}>{form.text.length}/20000</span></div>
          <textarea className="textarea" maxLength={20000} style={{ minHeight: 150 }} value={form.text} onChange={(event) => setField("text", event.target.value)} placeholder="粘贴需要检测的医美宣传文案……" />
        </div>
        <Field label="发布平台"><select className="select" value={form.platform} onChange={(event) => changePlatform(event.target.value)}>{platforms.map((platform) => <option key={platform}>{platform}</option>)}</select></Field>
        <Field label="内容类型"><select className="select" value={form.content_type} onChange={(event) => setField("content_type", event.target.value)}>{contentTypeOptions.map((type) => <option key={type}>{type}</option>)}</select></Field>
        <Field label="品牌"><select className="select" value={form.brand} onChange={(event) => setField("brand", event.target.value)}>{brands.map((brand) => <option key={brand.brand_id} value={brand.brand_id}>{brand.brand_name}{brand.is_demo ? "（演示）" : ""}</option>)}</select></Field>
        <Field label="发布主体类型"><select className="select" value={form.publisher_identity} onChange={(event) => setField("publisher_identity", event.target.value)}>{["医美机构", "医生个人号", "机构员工个人号", "品牌方", "个人/KOL", "其他"].map((item) => <option key={item}>{item}</option>)}</select></Field>
        <Field label="业务领域"><select className="select" value={form.business_domain} onChange={(event) => setField("business_domain", event.target.value)}>{["医疗美容", "生活美容", "化妆品", "医疗器械", "混合业务"].map((item) => <option key={item}>{item}</option>)}</select></Field>
        <Field label="内容法律性质"><select className="select" value={form.content_legal_nature} onChange={(event) => setField("content_legal_nature", event.target.value)}><option value="medical_advertisement">医疗广告/商业推广</option><option value="service_information">服务信息公开</option><option value="health_education">健康科普</option><option value="diagnosis_communication">诊疗沟通</option><option value="uncertain">不确定</option></select></Field>
        <Field label="是否付费广告"><select className="select" value={String(form.is_paid_ad)} onChange={(event) => setField("is_paid_ad", event.target.value === "true")}><option value="false">否</option><option value="true">是</option></select></Field>
        <div style={{ gridColumn: "1 / -1" }}><div style={{ fontSize: 13, fontWeight: 500, marginBottom: 4 }}>上下文说明（可选）</div><input className="input" maxLength={2000} value={form.context_note} onChange={(event) => setField("context_note", event.target.value)} placeholder="例如：机构公众号科普文章，末尾含预约入口" /></div>
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
        <button className="btn btn-primary" onClick={onCheck} disabled={loading || !form.text.trim()}><ShieldCheck size={16} /> {loading ? "检测中…" : "开始检测"}</button>
        <button className="btn" onClick={() => loadExample(DEMO_RISKY)} disabled={loading}><FileText size={16} /> 加载风险示例</button>
        <button className="btn" onClick={() => loadExample(DEMO_COMPLIANT)} disabled={loading}><FileText size={16} /> 加载低风险示例</button>
        <button className="btn" onClick={() => { setForm({ ...DEMO_RISKY, text: "" }); setResult(null); setError(null); setNotice(null); }} disabled={loading}><Trash2 size={16} /> 清空</button>
      </div>
      <div style={{ fontSize: 12, color: "#9ca3af", marginTop: 8 }}>结果只覆盖输入文本；图片、视频画面、证照真伪和素材授权仍需人工检查。</div>
    </div>

    {result && <ComplianceReport result={result} />}
  </div>;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) { return <div><div style={{ fontSize: 13, fontWeight: 500, marginBottom: 4 }}>{label}</div>{children}</div>; }
